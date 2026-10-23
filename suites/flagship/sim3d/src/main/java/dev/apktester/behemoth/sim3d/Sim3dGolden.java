package dev.apktester.behemoth.sim3d;

import dev.apktester.behemoth.sim3d.nativecompat.NativeBridge;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/**
 * Golden runner do pilar 3D: executa o {@link Sim3dEngine} e serializa o
 * relatorio em JSON canonico (indentacao 2, ordem de insercao, inteiros
 * simples, strings ASCII escapadas) — bytes deterministicos.
 *
 * Modos:
 *   --write PATH   grava o golden (usado uma unica vez para semear o
 *                  contrato; no CI serve de fonte do zero-drift);
 *   --verify PATH  re-executa e compara byte a byte com o contrato
 *                  commitado (exit 0 = zero drift; 1 = drift com diff);
 *   --parity LIB   paridade nativa: roda a fisica Java e a fisica C++
 *                  (libsim3d_native via JNI) e compara o checksum final;
 *   --selftest     assercoes internas de sanidade (Q16, FNV, xorshift,
 *                  raster, marching cubes).
 */
public final class Sim3dGolden {

    private Sim3dGolden() {
    }

    /** Serializa o relatorio em JSON canonico. */
    static String render(Map<String, Object> report) {
        StringBuilder sb = new StringBuilder(1 << 14);
        writeValue(sb, report, 0);
        sb.append('\n');
        return sb.toString();
    }

    private static void writeValue(StringBuilder sb, Object value, int indent) {
        if (value instanceof Map) {
            writeMap(sb, (Map<?, ?>) value, indent);
        } else if (value instanceof List) {
            writeList(sb, (List<?>) value, indent);
        } else if (value instanceof String) {
            writeString(sb, (String) value);
        } else if (value instanceof int[]) {
            writeIntArray(sb, (int[]) value, indent);
        } else if (value instanceof String[]) {
            writeStringArray(sb, (String[]) value);
        } else if (value instanceof Long) {
            sb.append(((Long) value).longValue());
        } else if (value instanceof Integer) {
            sb.append(((Integer) value).intValue());
        } else {
            throw new IllegalArgumentException("tipo nao suportado: " + value.getClass());
        }
    }

    private static void writeMap(StringBuilder sb, Map<?, ?> map, int indent) {
        if (map.isEmpty()) {
            sb.append("{}");
            return;
        }
        sb.append("{\n");
        int n = map.size();
        int i = 0;
        for (Map.Entry<?, ?> e : map.entrySet()) {
            indent(sb, indent + 1);
            writeString(sb, String.valueOf(e.getKey()));
            sb.append(": ");
            writeValue(sb, e.getValue(), indent + 1);
            if (++i < n) {
                sb.append(',');
            }
            sb.append('\n');
        }
        indent(sb, indent);
        sb.append('}');
    }

    private static void writeList(StringBuilder sb, List<?> list, int indent) {
        if (list.isEmpty()) {
            sb.append("[]");
            return;
        }
        sb.append("[\n");
        for (int i = 0; i < list.size(); i++) {
            indent(sb, indent + 1);
            writeValue(sb, list.get(i), indent + 1);
            if (i + 1 < list.size()) {
                sb.append(',');
            }
            sb.append('\n');
        }
        indent(sb, indent);
        sb.append(']');
    }

    private static void writeIntArray(StringBuilder sb, int[] array, int indent) {
        sb.append('[');
        for (int i = 0; i < array.length; i++) {
            if (i > 0) {
                sb.append(", ");
            }
            sb.append(array[i]);
        }
        sb.append(']');
    }

    private static void writeStringArray(StringBuilder sb, String[] array) {
        sb.append('[');
        for (int i = 0; i < array.length; i++) {
            if (i > 0) {
                sb.append(", ");
            }
            writeString(sb, array[i]);
        }
        sb.append(']');
    }

    private static void writeString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                sb.append('\\').append(c);
            } else if (c < 0x20) {
                sb.append(String.format("\\u%04x", (int) c));
            } else {
                sb.append(c);
            }
        }
        sb.append('"');
    }

    private static void indent(StringBuilder sb, int level) {
        for (int i = 0; i < level; i++) {
            sb.append("  ");
        }
    }

    /** Executa a engine e devolve os bytes do golden. */
    static byte[] goldenBytes() {
        return render(new Sim3dEngine().run()).getBytes(StandardCharsets.UTF_8);
    }

    private static void writeGolden(Path path) throws IOException {
        byte[] data = goldenBytes();
        Files.createDirectories(path.toAbsolutePath().getParent());
        Files.write(path, data);
        System.out.println("[sim3d] golden gravado: " + path + " (" + data.length + " bytes)");
    }

    private static int verifyGolden(Path path) throws IOException {
        if (!Files.exists(path)) {
            System.out.println("[sim3d] ERRO: contrato inexistente: " + path);
            return 1;
        }
        byte[] expected = Files.readAllBytes(path);
        byte[] actual = goldenBytes();
        if (java.util.Arrays.equals(expected, actual)) {
            System.out.println("[sim3d] verify OK: " + actual.length + " bytes identicos (zero drift)");
            return 0;
        }
        int n = Math.min(expected.length, actual.length);
        int diffAt = -1;
        for (int i = 0; i < n; i++) {
            if (expected[i] != actual[i]) {
                diffAt = i;
                break;
            }
        }
        System.out.println("[sim3d] DRIFT: esperado=" + expected.length + "B obtido=" + actual.length
                + "B primeira diferenca no byte " + diffAt);
        int start = Math.max(0, (diffAt < 0 ? n : diffAt) - 80);
        int end = Math.min(n, start + 160);
        System.out.println("[sim3d] esperado: ..." + new String(expected, start, end - start, StandardCharsets.UTF_8));
        System.out.println("[sim3d] obtido:   ..." + new String(actual, start, end - start, StandardCharsets.UTF_8));
        return 1;
    }

    /** Paridade nativa: Java vs C++ (mesma lei inteira). */
    private static int parity(String libName) {
        PhysicsSim sim = new PhysicsSim();
        sim.init(Sim3dEngine.SEED);
        sim.run();
        long javaChecksum = sim.getStepChecksum(PhysicsSim.STEPS);
        long nativeChecksum;
        try {
            System.loadLibrary(libName);
            nativeChecksum = NativeBridge.physicsFinalChecksum(
                    Sim3dEngine.SEED, PhysicsSim.BODIES, PhysicsSim.STEPS);
        } catch (UnsatisfiedLinkError e) {
            System.out.println("[sim3d] paridade nativa INDISPONIVEL (" + e.getMessage() + ")");
            return 2;
        }
        if (javaChecksum == nativeChecksum) {
            System.out.println("[sim3d] paridade nativa OK: " + Sim3dEngine.hex16(javaChecksum)
                    + " (java == native)");
            return 0;
        }
        System.out.println("[sim3d] paridade nativa FALHOU: java=" + Sim3dEngine.hex16(javaChecksum)
                + " native=" + Sim3dEngine.hex16(nativeChecksum));
        return 1;
    }

    /** Assercoes internas de sanidade (baratas, sem a execucao completa). */
    private static int selftest() {
        // FNV-1a 64: vetor publico "a" -> 0xaf63dc4c8601ec8c
        Fnv1a fnv = new Fnv1a();
        fnv.addByte('a');
        if (fnv.value() != 0xaf63dc4c8601ec8cL) {
            System.out.println("[sim3d] selftest FAIL: FNV basico divergiu: " + fnv.hex());
            return 1;
        }
        // Q16: identidades elementares
        if (Q16.mul(Q16.ONE, Q16.ONE) != Q16.ONE || Q16.mul(-3, Q16.ONE) != -3) {
            System.out.println("[sim3d] selftest FAIL: mul Q16");
            return 1;
        }
        if (Q16.sqrtQ16(4 * Q16.ONE) != 2 * Q16.ONE) {
            System.out.println("[sim3d] selftest FAIL: sqrtQ16(4) != 2: " + Q16.sqrtQ16(4 * Q16.ONE));
            return 1;
        }
        int[] sc = new int[2];
        Q16.sinCosBam24(0, sc);
        if (Math.abs(sc[0]) > 4 || sc[1] != Q16.ONE) {
            System.out.println("[sim3d] selftest FAIL: sin(0)");
            return 1;
        }
        Q16.sinCosBam24(1 << 22, sc); // pi/2
        if (sc[0] != Q16.ONE || Math.abs(sc[1]) > 4) {
            System.out.println("[sim3d] selftest FAIL: sin(pi/2)");
            return 1;
        }
        // xorshift: ciclo deterministico
        Xorshift32 r1 = new Xorshift32(42);
        Xorshift32 r2 = new Xorshift32(42);
        for (int i = 0; i < 1000; i++) {
            if (r1.nextInt() != r2.nextInt()) {
                System.out.println("[sim3d] selftest FAIL: xorshift nao reproduzivel");
                return 1;
            }
        }
        // raster: 1 triangulo grande centrado cobre > 1000 pixels
        Mesh1M mesh = new Mesh1M();
        mesh.generate();
        TextureQ16 tex = new TextureQ16();
        tex.generate();
        Framebuffer fb = new Framebuffer(64, 64);
        Rasterizer raster = new Rasterizer(fb, tex);
        raster.drawFrameSubset(mesh, 0, 0, 256);
        if (fb.getPixelsDrawn() < 256) {
            System.out.println("[sim3d] selftest FAIL: rasterizou poucos pixels: " + fb.getPixelsDrawn());
            return 1;
        }
        // marching cubes: superficie existe e cobre a regiao central
        MarchingCubes cubes = new MarchingCubes();
        cubes.sampleField();
        cubes.polygonize();
        if (cubes.getTriangleCount() < 100) {
            System.out.println("[sim3d] selftest FAIL: iso-superficie vazia: " + cubes.getTriangleCount());
            return 1;
        }
        System.out.println("[sim3d] selftest OK (fnv, q16, xorshift, raster, marching cubes)");
        return 0;
    }

    /** CLI do golden runner. */
    public static void main(String[] args) throws IOException {
        for (int i = 0; i < args.length; i++) {
            if ("--write".equals(args[i]) && i + 1 < args.length) {
                writeGolden(Path.of(args[++i]));
                return;
            }
            if ("--verify".equals(args[i]) && i + 1 < args.length) {
                System.exit(verifyGolden(Path.of(args[++i])));
            }
            if ("--parity".equals(args[i]) && i + 1 < args.length) {
                System.exit(parity(args[++i]));
            }
            if ("--selftest".equals(args[i])) {
                System.exit(selftest());
            }
        }
        System.err.println("uso: Sim3dGolden --write PATH | --verify PATH | --parity LIB | --selftest");
        System.exit(2);
    }
}
