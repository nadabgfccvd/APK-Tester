package dev.apktester.behemoth.sim3d;

/**
 * Sistema de particulas CPU do :sim3d — 100.000 particulas, 120 passos
 * fixos de 1/60 s, inteiro Q16 (lei do golden).
 *
 * Modelo: emissor unico em (0, 3 m, 0) com cone de velocidades semeado;
 * gravidade + arrasto linear 0.98; vida util de 40 a 120 passos com
 * respawn imediato no emissor (continuidade do PRNG — deterministico);
 * quicque fraco no plano y = 1/64 m.
 */
public final class ParticleSystem {

    /** Numero de particulas. */
    public static final int COUNT = 100000;

    /** Numero de passos fixos. */
    public static final int STEPS = 120;

    /** Emissor (0, 3 m, 0) em Q16. */
    public static final int EMIT_X = 0;
    public static final int EMIT_Y = 3 * Q16.ONE;
    public static final int EMIT_Z = 0;

    /** Arrasto linear em Q16 (0.98). */
    public static final int DRAG = 64225;

    /** Altura do plano de quicque (1/64 m em Q16). */
    private static final int FLOOR = 1024;

    private final int[] px = new int[COUNT];
    private final int[] py = new int[COUNT];
    private final int[] pz = new int[COUNT];
    private final int[] vx = new int[COUNT];
    private final int[] vy = new int[COUNT];
    private final int[] vz = new int[COUNT];
    private final int[] life = new int[COUNT];

    private final Xorshift32 rng;
    private long respawns;
    private final long[] stepChecksum = new long[STEPS + 1];

    /** Semeia o estado inicial (deterministico). */
    public ParticleSystem(int seed) {
        this.rng = new Xorshift32(seed ^ 0x50525453); // "PRTS"
        init();
    }

    private void init() {
        for (int i = 0; i < COUNT; i++) {
            emit(i, false);
            // dispersao inicial de 1 s de movimento (estado ja "vivo")
            px[i] += Q16.mul(vx[i], Q16.ONE);
            py[i] += Q16.mul(vy[i], Q16.ONE);
            pz[i] += Q16.mul(vz[i], Q16.ONE);
        }
    }

    /** (Re)emite a particula i no emissor com velocidade/vida semeada. */
    private void emit(int i, boolean countRespawn) {
        px[i] = EMIT_X;
        py[i] = EMIT_Y;
        pz[i] = EMIT_Z;
        vx[i] = ((rng.nextBounded(3 * Q16.ONE) - 3 * Q16.HALF) / 32) * 32;
        vy[i] = (2 * Q16.ONE + rng.nextBounded(4 * Q16.ONE) / 32 * 32);
        vz[i] = ((rng.nextBounded(3 * Q16.ONE) - 3 * Q16.HALF) / 32) * 32;
        life[i] = 40 + rng.nextBounded(81);
        if (countRespawn) {
            respawns++;
        }
    }

    /** Executa os 120 passos fixos. */
    public void run() {
        for (int step = 1; step <= STEPS; step++) {
            for (int i = 0; i < COUNT; i++) {
                if (life[i] == 0) {
                    emit(i, true);
                }
                vy[i] += PhysicsSim.GRAVITY_Q16 / PhysicsSim.DT_DEN;
                vx[i] = Q16.mul(vx[i], DRAG);
                vy[i] = Q16.mul(vy[i], DRAG);
                vz[i] = Q16.mul(vz[i], DRAG);
                px[i] += vx[i] / PhysicsSim.DT_DEN;
                py[i] += vy[i] / PhysicsSim.DT_DEN;
                pz[i] += vz[i] / PhysicsSim.DT_DEN;
                life[i]--;
                if (py[i] < FLOOR) {
                    py[i] = FLOOR;
                    if (vy[i] < 0) {
                        vy[i] = -Q16.mul(vy[i], 16384);
                    }
                }
            }
            Fnv1a fnv = new Fnv1a();
            foldState(fnv);
            stepChecksum[step] = fnv.value();
        }
    }

    /** Dobra o estado de todas as particulas no checksum. */
    private void foldState(Fnv1a fnv) {
        for (int i = 0; i < COUNT; i++) {
            fnv.addInt(px[i]);
            fnv.addInt(py[i]);
            fnv.addInt(pz[i]);
            fnv.addInt(vx[i]);
            fnv.addInt(vy[i]);
            fnv.addInt(vz[i]);
            fnv.addInt(life[i]);
        }
    }

    /** Checksum apos o passo "step" (1..STEPS). */
    public long getStepChecksum(int step) {
        return stepChecksum[step];
    }

    /** Total de respawns acumulados. */
    public long getRespawns() {
        return respawns;
    }

    /** Bounding box [minX, minY, minZ, maxX, maxY, maxZ] em Q16. */
    public int[] bbox() {
        int minX = Integer.MAX_VALUE;
        int minY = Integer.MAX_VALUE;
        int minZ = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE;
        int maxY = Integer.MIN_VALUE;
        int maxZ = Integer.MIN_VALUE;
        for (int i = 0; i < COUNT; i++) {
            if (px[i] < minX) {
                minX = px[i];
            }
            if (py[i] < minY) {
                minY = py[i];
            }
            if (pz[i] < minZ) {
                minZ = pz[i];
            }
            if (px[i] > maxX) {
                maxX = px[i];
            }
            if (py[i] > maxY) {
                maxY = py[i];
            }
            if (pz[i] > maxZ) {
                maxZ = pz[i];
            }
        }
        return new int[]{minX, minY, minZ, maxX, maxY, maxZ};
    }
}
