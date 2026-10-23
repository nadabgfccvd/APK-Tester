package dev.apktester.behemoth.sim3d;

/**
 * Esqueleto articulado com animacao por keyframes do :sim3d — 16 juntas
 * em arvore binaria (pai de i = (i-1)/2), 2 poses-chave semeadas com
 * angulos BAM24 por junta, 30 frames com interpolacao Q16, cinematica
 * forward via Mat4 (Q16) e skinning de 64 vertices (1 junta por vertice).
 */
public final class Skeleton {

    /** Numero de juntas. */
    public static final int JOINTS = 16;

    /** Numero de frames animados. */
    public static final int FRAMES = 30;

    /** Vertices com skinning. */
    public static final int SKIN_VERTICES = 64;

    private final int[] parent = new int[JOINTS];
    private final int[] offX = new int[JOINTS];
    private final int[] offY = new int[JOINTS];
    private final int[] offZ = new int[JOINTS];
    private final int[][] poseA = new int[JOINTS][3];
    private final int[][] poseB = new int[JOINTS][3];

    private final Mat4[] world = new Mat4[JOINTS];
    private final int[] jointX = new int[JOINTS];
    private final int[] jointY = new int[JOINTS];
    private final int[] jointZ = new int[JOINTS];
    private final int[] skinX = new int[SKIN_VERTICES];
    private final int[] skinY = new int[SKIN_VERTICES];
    private final int[] skinZ = new int[SKIN_VERTICES];
    private final long[] frameChecksum = new long[FRAMES];

    /** Semeia a arvore, offsets e poses-chave (deterministico). */
    public Skeleton(int seed) {
        Xorshift32 rng = new Xorshift32(seed ^ 0x534B454C); // "SKEL"
        parent[0] = -1;
        offX[0] = 0;
        offY[0] = 65536; // raiz a 1,0 m
        offZ[0] = 0;
        for (int i = 1; i < JOINTS; i++) {
            parent[i] = (i - 1) / 2;
            offX[i] = ((rng.nextBounded(8192) - 4096));
            offY[i] = 4096 + rng.nextBounded(16384);
            offZ[i] = ((rng.nextBounded(8192) - 4096));
        }
        for (int i = 0; i < JOINTS; i++) {
            for (int a = 0; a < 3; a++) {
                poseA[i][a] = rng.nextBounded(1 << 24) - (1 << 23);
                poseB[i][a] = rng.nextBounded(1 << 24) - (1 << 23);
            }
        }
        for (int i = 0; i < JOINTS; i++) {
            world[i] = new Mat4();
        }
    }

    /** Executa os 30 frames (FK + skinning) com checksum por frame. */
    public void run() {
        for (int f = 0; f < FRAMES; f++) {
            int t = Q16.mulDiv(f, Q16.ONE, FRAMES - 1);
            animateFrame(t);
            Fnv1a fnv = new Fnv1a();
            foldJointChecksum(fnv);
            frameChecksum[f] = fnv.value();
        }
    }

    /** Checksum das juntas apos o frame "f" (0..FRAMES-1). */
    public long getFrameChecksum(int f) {
        return frameChecksum[f];
    }

    /** FK de um frame interpolado (t em Q16 [0,1)). */
    private void animateFrame(int t) {
        for (int i = 0; i < JOINTS; i++) {
            int ax = Q16.lerp(poseA[i][0], poseB[i][0], t);
            int ay = Q16.lerp(poseA[i][1], poseB[i][1], t);
            int az = Q16.lerp(poseA[i][2], poseB[i][2], t);
            world[i].identity();
            if (parent[i] >= 0) {
                world[i].set(world[parent[i]]);
                world[i].translate(offX[i], offY[i], offZ[i]);
            }
            world[i].rotateZBam24(az);
            world[i].rotateYBam24(ay);
            world[i].rotateXBam24(ax);
            int[] p = new int[]{0, 0, 0};
            world[i].transformPoint(p);
            jointX[i] = p[0];
            jointY[i] = p[1];
            jointZ[i] = p[2];
        }
        skinFrame();
    }

    /** Skinning: vertice j segue a junta (j % JOINTS) com offset fixo. */
    private void skinFrame() {
        for (int j = 0; j < SKIN_VERTICES; j++) {
            int joint = j % JOINTS;
            int bx = (j * 1024) % 65536 - 32768;
            int by = (j * 2048) % 65536 - 32768;
            int bz = (j * 4096) % 65536 - 32768;
            int[] p = new int[]{bx, by, bz};
            world[joint].transformPoint(p);
            skinX[j] = p[0];
            skinY[j] = p[1];
            skinZ[j] = p[2];
        }
    }

    /** Dobra as 16 posicoes de juntas do frame 0..FRAMES-1 no checksum. */
    public void foldJointChecksum(Fnv1a fnv) {
        for (int i = 0; i < JOINTS; i++) {
            fnv.addInt(jointX[i]);
            fnv.addInt(jointY[i]);
            fnv.addInt(jointZ[i]);
        }
    }

    /** Dobra as posicoes de skinning no checksum. */
    public void foldSkinChecksum(Fnv1a fnv) {
        for (int j = 0; j < SKIN_VERTICES; j++) {
            fnv.addInt(skinX[j]);
            fnv.addInt(skinY[j]);
            fnv.addInt(skinZ[j]);
        }
    }

    /** Extensao maxima do esqueleto (Q16) — sanity de FK. */
    public int getMaxReach() {
        int m = 0;
        for (int i = 0; i < JOINTS; i++) {
            int d = Math.abs(jointX[i]) + Math.abs(jointY[i]) + Math.abs(jointZ[i]);
            if (d > m) {
                m = d;
            }
        }
        return m;
    }
}
