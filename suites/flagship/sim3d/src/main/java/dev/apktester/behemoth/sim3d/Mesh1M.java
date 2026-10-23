package dev.apktester.behemoth.sim3d;

/**
 * Malha procedural de 1.048.576 vertices (2^20 = grade 1024x1024) — o
 * "1M-vertex procedural mesh" do pilar 3D. Terreno de value-noise inteiro
 * em 3 oitavas, altura em [0, 3] m, espalhado em 16 m x 16 m centrado na
 * origem; UV em [0, 8) (textura repete 8x8).
 *
 * Memoria: 3 arrays de posicao + 2 de UV (int) = ~20 MB; geracao em uma
 * passada (~40 ops/vertice). 2.093.058 triangulos (2 por celula de grade).
 */
public final class Mesh1M {

    /** Lado da grade de vertices (1024^2 = 2^20 vertices). */
    public static final int GRID = 1024;

    /** Numero exato de vertices. */
    public static final int VERTICES = GRID * GRID;

    /** Numero exato de triangulos (2 por celula de 1023x1023). */
    public static final int TRIANGLES = 2 * (GRID - 1) * (GRID - 1);

    /** Meia-extensao mundial (8 m em Q16). */
    public static final int HALF_EXTENT = 8 * Q16.ONE;

    private final int[] px = new int[VERTICES];
    private final int[] py = new int[VERTICES];
    private final int[] pz = new int[VERTICES];
    private final int[] pu = new int[VERTICES];
    private final int[] pv = new int[VERTICES];

    private int heightMinQ16 = Integer.MAX_VALUE;
    private int heightMaxQ16 = Integer.MIN_VALUE;

    /** Gera a malha inteira (deterministica, sem aleatoriedade de runtime). */
    public void generate() {
        for (int iz = 0; iz < GRID; iz++) {
            for (int ix = 0; ix < GRID; ix++) {
                int idx = iz * GRID + ix;
                int x = Q16.mulDiv(ix, 2 * HALF_EXTENT, GRID - 1) - HALF_EXTENT;
                int z = Q16.mulDiv(iz, 2 * HALF_EXTENT, GRID - 1) - HALF_EXTENT;
                int y = terrainHeight(x, z);
                px[idx] = x;
                py[idx] = y;
                pz[idx] = z;
                pu[idx] = Q16.mulDiv(ix, 8 * Q16.ONE, GRID - 1);
                pv[idx] = Q16.mulDiv(iz, 8 * Q16.ONE, GRID - 1);
                if (y < heightMinQ16) {
                    heightMinQ16 = y;
                }
                if (y > heightMaxQ16) {
                    heightMaxQ16 = y;
                }
            }
        }
    }

    /** Altura do terreno (Q16) por value-noise inteiro de 3 oitavas. */
    private int terrainHeight(int x, int z) {
        int n1 = valueNoise(x, z, 8192);
        int n2 = valueNoise(x + 524288, z - 262144, 4096);
        int n3 = valueNoise(x - 1048576, z + 786432, 2048);
        int total = n1 + (n2 >> 1) + (n3 >> 2);
        return Q16.mul(total, 112328); // (3.0/1.75) em Q16 -> altura maxima ~3 m
    }

    /**
     * Value-noise bilinear com smoothstep, lattice de passo "lattice" (Q16).
     * Hash de lattice: mistura multiplicativa inteiro (deterministica).
     */
    private int valueNoise(int x, int z, int lattice) {
        int ix = Q16.floorDiv(x, lattice);
        int iz = Q16.floorDiv(z, lattice);
        int fx = x - ix * lattice;
        int fz = z - iz * lattice;
        int u = Q16.smoothstep((int) (((long) fx << 16) / lattice));
        int v = Q16.smoothstep((int) (((long) fz << 16) / lattice));
        int h00 = latticeHash(ix, iz);
        int h10 = latticeHash(ix + 1, iz);
        int h01 = latticeHash(ix, iz + 1);
        int h11 = latticeHash(ix + 1, iz + 1);
        int a = Q16.lerp(h00, h10, u);
        int b = Q16.lerp(h01, h11, u);
        return Q16.lerp(a, b, v);
    }

    /** Hash 2D de lattice em [0, 65536) — mistura xorshift-multiplicativa. */
    private static int latticeHash(int ix, int iz) {
        long h = (long) ix * 374761393L + (long) iz * 668265263L;
        h = (h ^ (h >>> 13)) * 1274126177L;
        return (int) ((h ^ (h >>> 16)) & 0xFFFFL);
    }

    /**
     * Triangulo "macro" (stride de celulas) para o rasterizador: celula
     * efetiva de stride*1.56 cm (stride 16 = 25 cm) — triangulos de
     * tela perceptiveis a partir da camera (celulas unitarias sao
     * sub-pixel a 9 m). Selecao de vertices identica a triangle().
     */
    public void macroTriangle(int idx, int stride, int[] out) {
        int macroGrid = GRID / stride;
        int cell = idx >> 1;
        int ix = (cell % (macroGrid - 1)) * stride;
        int iz = (cell / (macroGrid - 1)) * stride;
        int v00 = iz * GRID + ix;
        int v10 = v00 + stride;
        int v01 = v00 + stride * GRID;
        int v11 = v10 + stride * GRID;
        int a;
        int b;
        int c;
        if ((idx & 1) == 0) {
            a = v00;
            b = v10;
            c = v11;
        } else {
            a = v00;
            b = v11;
            c = v01;
        }
        out[0] = px[a];
        out[1] = py[a];
        out[2] = pz[a];
        out[3] = pu[a];
        out[4] = pv[a];
        out[5] = px[b];
        out[6] = py[b];
        out[7] = pz[b];
        out[8] = pu[b];
        out[9] = pv[b];
        out[10] = px[c];
        out[11] = py[c];
        out[12] = pz[c];
        out[13] = pu[c];
        out[14] = pv[c];
    }

    /**
     * Preenche os 3 vertices do triangulo "idx" (0..TRIANGLES-1) no buffer
     * de 18 inteiros [x0,y0,z0,u0,v0, x1,y1,z1,u1,v1, x2,y2,z2,u2,v2].
     * Triangulos pares: (v00, v10, v11); impares: (v00, v11, v01).
     */
    public void triangle(int idx, int[] out) {
        int cell = idx >> 1;
        int ix = cell % (GRID - 1);
        int iz = cell / (GRID - 1);
        int v00 = iz * GRID + ix;
        int v10 = v00 + 1;
        int v01 = v00 + GRID;
        int v11 = v00 + GRID + 1;
        int a;
        int b;
        int c;
        if ((idx & 1) == 0) {
            a = v00;
            b = v10;
            c = v11;
        } else {
            a = v00;
            b = v11;
            c = v01;
        }
        out[0] = px[a];
        out[1] = py[a];
        out[2] = pz[a];
        out[3] = pu[a];
        out[4] = pv[a];
        out[5] = px[b];
        out[6] = py[b];
        out[7] = pz[b];
        out[8] = pu[b];
        out[9] = pv[b];
        out[10] = px[c];
        out[11] = py[c];
        out[12] = pz[c];
        out[13] = pu[c];
        out[14] = pv[c];
    }

    /**
     * Dobra todos os atributos de vertices no checksum (ordem row-major:
     * posicao x,y,z e uv u,v por vertice) — base do golden da malha.
     */
    public void foldChecksums(Fnv1a pos, Fnv1a uv) {
        for (int i = 0; i < VERTICES; i++) {
            pos.addInt(px[i]);
            pos.addInt(py[i]);
            pos.addInt(pz[i]);
            uv.addInt(pu[i]);
            uv.addInt(pv[i]);
        }
    }

    public int getHeightMinQ16() {
        return heightMinQ16;
    }

    public int getHeightMaxQ16() {
        return heightMaxQ16;
    }
}
