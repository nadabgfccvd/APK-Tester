package dev.apktester.behemoth.sim3d;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Orquestrador do pilar 3D headless (:sim3d) do flagship "Behemoth".
 *
 * Executa, em ordem fixa e sem ponto flutuante, os cinco subsystems do
 * pilar 3D do APK_TESTER_PROMPT.md:
 *   1. malha procedural de 1M vertices (grade 1024x1024);
 *   2. rasterizador de software (4 frames, 1536 triangulos/frame,
 *      perspectiva-correto com z-buffer e textura procedural);
 *   3. fisica de 10.000 corpos rigidos (120 passos fixos);
 *   4. sistema de 100.000 particulas CPU (120 passos);
 *   5. terreno por marching cubes (grade 48^3) + esqueleto animado.
 *
 * O relatorio (mapas ordenados) e serializado byte a byte pelo
 * {@link Sim3dGolden} e comparado ao contrato
 * contracts/flagship/sim3d-golden.json (zero drift no CI).
 */
public final class Sim3dEngine {

    /** Semente mestra do pilar 3D (a mesma dos geradores do repositorio). */
    public static final int SEED = 20261022;

    /** Resolucao do framebuffer. */
    public static final int FB_WIDTH = 320;
    public static final int FB_HEIGHT = 240;

    /** Triangulos amostrados por frame. */
    public static final int TRIS_PER_FRAME = 1536;

    private final Mesh1M mesh = new Mesh1M();
    private final TextureQ16 texture = new TextureQ16();
    private final Framebuffer fb = new Framebuffer(FB_WIDTH, FB_HEIGHT);
    private final Rasterizer raster = new Rasterizer(fb, texture);
    private final PhysicsSim physics = new PhysicsSim();
    private final MarchingCubes cubes = new MarchingCubes();
    private Skeleton skeleton;

    private long rasterFrameChecksum0;
    private long rasterFrameChecksum1;
    private long rasterFrameChecksum2;
    private long rasterFrameChecksum3;
    private long rasterFinalChecksum;
    private long meshPosChecksum;
    private long meshUvChecksum;
    private long particleStep1;
    private long particleStep60;
    private long particleStep120;
    private long skeletonFrame1;
    private long skeletonFrame15;
    private long skeletonFrame30;
    private long skeletonSkinChecksum;

    /** Executa o pilar completo e monta o relatorio ordenado. */
    public Map<String, Object> run() {
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("schema_version", 1);
        report.put("generator", "dev.apktester.behemoth.sim3d (modulo :sim3d do flagship Behemoth)");
        report.put("seed", SEED);
        report.put("math", "Q16.16 ponto fixo somente-inteiro; trigonometria BAM24 via CORDIC (24 iteracoes); checksums FNV-1a 64 (dobrado little-endian byte a byte)");

        runMesh();
        Map<String, Object> meshReport = new LinkedHashMap<>();
        meshReport.put("grid", Mesh1M.GRID);
        meshReport.put("vertices", Mesh1M.VERTICES);
        meshReport.put("triangles", Mesh1M.TRIANGLES);
        meshReport.put("positions_fnv1a64", hex16(meshPosChecksum));
        meshReport.put("uv_fnv1a64", hex16(meshUvChecksum));
        meshReport.put("height_min_q16", mesh.getHeightMinQ16());
        meshReport.put("height_max_q16", mesh.getHeightMaxQ16());
        report.put("mesh_1m", meshReport);

        runRaster();
        Map<String, Object> rasterReport = new LinkedHashMap<>();
        int[] rt = getRasterTotals();
        rasterReport.put("width", FB_WIDTH);
        rasterReport.put("height", FB_HEIGHT);
        rasterReport.put("frames", 4);
        rasterReport.put("triangles_per_frame", TRIS_PER_FRAME);
        rasterReport.put("texture", "checker_noise_64x64_rgb565");
        rasterReport.put("triangles_submitted", rt[0]);
        rasterReport.put("triangles_near_rejected", rt[1]);
        rasterReport.put("triangles_backface_culled", rt[2]);
        rasterReport.put("triangles_drawn", rt[3]);
        rasterReport.put("pixels_drawn", rt[4]);
        rasterReport.put("frame_fnv1a64", new String[]{
                hex16(rasterFrameChecksum0), hex16(rasterFrameChecksum1),
                hex16(rasterFrameChecksum2), hex16(rasterFrameChecksum3)});
        rasterReport.put("final_fnv1a64", hex16(rasterFinalChecksum));
        report.put("rasterizer", rasterReport);

        runPhysics();
        Map<String, Object> physReport = new LinkedHashMap<>();
        physReport.put("bodies", PhysicsSim.BODIES);
        physReport.put("steps", PhysicsSim.STEPS);
        physReport.put("dt", PhysicsSim.DT_NUM + "/" + PhysicsSim.DT_DEN);
        physReport.put("gravity_q16", PhysicsSim.GRAVITY_Q16);
        physReport.put("restitution_ground_q16", PhysicsSim.RESTITUTION_GROUND);
        physReport.put("restitution_body_q16", PhysicsSim.RESTITUTION_BODY);
        physReport.put("cell_q16", PhysicsSim.CELL);
        physReport.put("init_fnv1a64", hex16(physics.getInitChecksum()));
        physReport.put("step_fnv1a64", stepMap(physics));
        physReport.put("asleep_final", physics.getAsleepCount());
        physReport.put("ground_contacts_final", physics.getGroundContacts());
        physReport.put("max_height_q16", physics.getMaxHeight());
        report.put("physics", physReport);

        ParticleSystem particles = runParticles();
        Map<String, Object> partReport = new LinkedHashMap<>();
        partReport.put("count", ParticleSystem.COUNT);
        partReport.put("steps", ParticleSystem.STEPS);
        partReport.put("emitter_q16", new int[]{ParticleSystem.EMIT_X, ParticleSystem.EMIT_Y, ParticleSystem.EMIT_Z});
        partReport.put("respawns", particles.getRespawns());
        partReport.put("step_fnv1a64", particleStepMap(particles));
        int[] bb = particles.bbox();
        partReport.put("bbox_q16", bb);
        report.put("particles", partReport);

        runMarchingCubes();
        Map<String, Object> mcReport = new LinkedHashMap<>();
        mcReport.put("grid", MarchingCubes.GRID);
        mcReport.put("samples", MarchingCubes.SAMPLES);
        mcReport.put("spacing_q16", MarchingCubes.SPACING);
        mcReport.put("iso_q16", MarchingCubes.ISO);
        mcReport.put("method", "marching cubes com decomposicao canonica em 6 tetraedros por cubo (resolve ambiguidades da tabela 256 por construcao)");
        mcReport.put("triangles", cubes.getTriangleCount());
        mcReport.put("vertices", cubes.getVertexCount());
        Fnv1a cf = new Fnv1a();
        cubes.foldChecksum(cf);
        mcReport.put("positions_fnv1a64", hex16(cf.value()));
        mcReport.put("bbox_q16", cubes.bbox());
        report.put("marching_cubes", mcReport);

        runSkeleton();
        Map<String, Object> skReport = new LinkedHashMap<>();
        skReport.put("joints", Skeleton.JOINTS);
        skReport.put("frames", Skeleton.FRAMES);
        skReport.put("key_poses", 2);
        skReport.put("skin_vertices", Skeleton.SKIN_VERTICES);
        skReport.put("frame_fnv1a64", new String[]{
                hex16(skeletonFrame1), hex16(skeletonFrame15), hex16(skeletonFrame30)});
        skReport.put("skin_fnv1a64", hex16(skeletonSkinChecksum));
        skReport.put("max_reach_q16", skeleton.getMaxReach());
        report.put("skeleton", skReport);
        return report;
    }

    private void runMesh() {
        mesh.generate();
        Fnv1a pos = new Fnv1a();
        Fnv1a uv = new Fnv1a();
        mesh.foldChecksums(pos, uv);
        meshPosChecksum = pos.value();
        meshUvChecksum = uv.value();
    }

    private void runRaster() {
        texture.generate();
        long[] frameSum = new long[4];
        int trisSubmitted = 0;
        int nearRejected = 0;
        int backface = 0;
        int drawn = 0;
        int pixels = 0;
        Fnv1a all = new Fnv1a();
        for (int frame = 0; frame < 4; frame++) {
            int bamYaw = frame * (1 << 24) / 45; // giro de 8 graus por frame
            raster.drawFrameSubset(mesh, frame, bamYaw, TRIS_PER_FRAME);
            Fnv1a fc = new Fnv1a();
            fb.foldColor(fc);
            frameSum[frame] = fc.value();
            all.addLong(frameSum[frame]);
            trisSubmitted += raster.getTrianglesSubmitted();
            nearRejected += raster.getTrianglesNearRejected();
            backface += raster.getTrianglesBackfaceCulled();
            drawn += raster.getTrianglesDrawn();
            pixels += raster.getPixelsDrawn();
        }
        rasterFrameChecksum0 = frameSum[0];
        rasterFrameChecksum1 = frameSum[1];
        rasterFrameChecksum2 = frameSum[2];
        rasterFrameChecksum3 = frameSum[3];
        rasterFinalChecksum = all.value();
        // os contadores do objeto raster guardam so o ultimo frame; os
        // totais agregados das 4 frames ficam em rasterTotals
        rasterTotals = new int[]{trisSubmitted, nearRejected, backface, drawn, pixels};
    }

    private int[] rasterTotals = new int[5];

    private void runPhysics() {
        physics.init(SEED);
        physics.run();
    }

    private ParticleSystem runParticles() {
        ParticleSystem particles = new ParticleSystem(SEED);
        particles.run();
        particleStep1 = particles.getStepChecksum(1);
        particleStep60 = particles.getStepChecksum(60);
        particleStep120 = particles.getStepChecksum(120);
        return particles;
    }

    private void runMarchingCubes() {
        cubes.sampleField();
        cubes.polygonize();
    }

    private void runSkeleton() {
        skeleton = new Skeleton(SEED);
        skeleton.run();
        skeletonFrame1 = skeleton.getFrameChecksum(0);
        skeletonFrame15 = skeleton.getFrameChecksum(14);
        skeletonFrame30 = skeleton.getFrameChecksum(29);
        Fnv1a sk = new Fnv1a();
        skeleton.foldSkinChecksum(sk);
        skeletonSkinChecksum = sk.value();
    }

    private Map<String, Object> stepMap(PhysicsSim p) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("1", hex16(p.getStepChecksum(1)));
        m.put("60", hex16(p.getStepChecksum(60)));
        m.put("120", hex16(p.getStepChecksum(120)));
        return m;
    }

    private Map<String, Object> particleStepMap(ParticleSystem p) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("1", hex16(particleStep1));
        m.put("60", hex16(particleStep60));
        m.put("120", hex16(particleStep120));
        return m;
    }

    /** Contadores agregados do rasterizador (para o relatorio do run()). */
    public int[] getRasterTotals() {
        return rasterTotals;
    }

    /** Acesso a fisica (paridade nativa). */
    public PhysicsSim getPhysics() {
        return physics;
    }

    /** Acesso a malha (selftest). */
    public Mesh1M getMesh() {
        return mesh;
    }

    /** Acesso ao marching cubes (selftest). */
    public MarchingCubes getMarchingCubes() {
        return cubes;
    }

    /** Acesso ao rasterizador (selftest). */
    public Rasterizer getRasterizer() {
        return raster;
    }

    /** Acesso ao esqueleto (selftest). */
    public Skeleton getSkeleton() {
        return skeleton;
    }

    /** Acesso ao framebuffer (selftest). */
    public Framebuffer getFramebuffer() {
        return fb;
    }

    /** Hex de 16 digitos com zeros a esquerda. */
    static String hex16(long v) {
        String raw = Long.toHexString(v);
        StringBuilder sb = new StringBuilder(16);
        for (int i = raw.length(); i < 16; i++) {
            sb.append('0');
        }
        return sb.append(raw).toString();
    }
}
