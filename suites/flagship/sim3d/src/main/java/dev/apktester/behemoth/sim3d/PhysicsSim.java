package dev.apktester.behemoth.sim3d;

/**
 * Fisica de corpos rigidos do :sim3d — 10.000 corpos, passo fixo 1/60 s,
 * 120 passos, 100% inteiro Q16 (lei do golden: sem ponto flutuante).
 *
 * Modelo (documentado, sem promessa de realismo fisico absoluto):
 *   - integracao semi-implicita de Euler com dt racional (1/60):
 *     v += g*dt (truncamento inteiro em direcao a zero — identico em
 *     Java e C, condicao de paridade com a referencia nativa);
 *   - chao em y=0 com restituicao 0.375 e atrito tangencial 0.98;
 *   - paredes do box em x,z = +/-8 m com restituicao 0.5;
 *   - colisoes corpo-corpo via grade uniforme de 0,25 m (tabela de
 *     listas encadeadas por slot — head/next reconstruida por passo),
 *     resposta por eixo de menor penetracao: correcao posicional 50/50
 *     e impulso de velocidade com restituicao 0.2 (massas iguais),
 *     aplicados imediatamente em ordem de indice (deterministico);
 *   - sono: velocidade^2 abaixo do limiar por 30 passos consecutivos.
 *
 * Checksums: FNV-1a 64 sobre (x,y,z,vx,vy,vz,asleep) de todos os corpos,
 * no passo 1, 60 e 120.
 */
public final class PhysicsSim {

    /** Numero de corpos rigidos. */
    public static final int BODIES = 10000;

    /** Numero de passos fixos. */
    public static final int STEPS = 120;

    /** Numerador/denominador do passo fixo (1/60 s). */
    public static final int DT_NUM = 1;
    public static final int DT_DEN = 60;

    /** Gravidade em Q16 (9.80665 m/s^2, truncado, sinal para baixo). */
    public static final int GRAVITY_Q16 = -642770;

    /** Restituicao do chao em Q16 (0.375). */
    public static final int RESTITUTION_GROUND = 24576;

    /** Restituicao das paredes em Q16 (0.5). */
    public static final int RESTITUTION_WALL = Q16.HALF;

    /** Atrito tangencial do chao em Q16 (0.98). */
    public static final int FRICTION_GROUND = 64225;

    /** Restituicao corpo-corpo em Q16 (0.2). */
    public static final int RESTITUTION_BODY = 13107;

    /** Meia-extensao do box (8 m em Q16). */
    public static final int HALF_BOX = 8 * Q16.ONE;

    /** Lado da celula da grade (0.25 m em Q16). */
    public static final int CELL = 16384;

    /** Limiar de sono: |v|^2 < (0.02 m/s)^2 em Q16^2. */
    private static final int SLEEP_SPEED2 = 1718721;

    /** Passos consecutivos lentos para dormir. */
    private static final int SLEEP_STEPS = 30;

    /** Slots da grade (15 bits = 5 bits por eixo; colisao real e por distancia). */
    private static final int SLOTS = 1 << 15;

    private final int[] px = new int[BODIES];
    private final int[] py = new int[BODIES];
    private final int[] pz = new int[BODIES];
    private final int[] vx = new int[BODIES];
    private final int[] vy = new int[BODIES];
    private final int[] vz = new int[BODIES];
    private final int[] rad = new int[BODIES];
    private final boolean[] asleep = new boolean[BODIES];
    private final int[] sleepCtr = new int[BODIES];

    private final int[] head = new int[SLOTS];
    private final int[] next = new int[BODIES];

    private long initChecksum;
    private long[] stepChecksum = new long[STEPS + 1];

    /** Semeia e monta o estado inicial (deterministico). */
    public void init(int seed) {
        Xorshift32 rng = new Xorshift32(seed ^ 0x50485953); // "PHYS"
        int spanXZ = 12 * Q16.ONE;
        int spanY = 6 * Q16.ONE;
        for (int i = 0; i < BODIES; i++) {
            px[i] = ((rng.nextBounded(spanXZ) - 6 * Q16.ONE) / 64) * 64;
            py[i] = 2 * Q16.ONE + (rng.nextBounded(spanY) / 64) * 64;
            pz[i] = ((rng.nextBounded(spanXZ) - 6 * Q16.ONE) / 64) * 64;
            vx[i] = ((rng.nextBounded(Q16.ONE) - Q16.HALF) / 32) * 32;
            vy[i] = 0;
            vz[i] = ((rng.nextBounded(Q16.ONE) - Q16.HALF) / 32) * 32;
            rad[i] = 3932 + (rng.nextBounded(9175 - 3932 + 1));
            asleep[i] = false;
            sleepCtr[i] = 0;
        }
        Fnv1a fnv = new Fnv1a();
        foldState(fnv, false);
        initChecksum = fnv.value();
    }

    /** Executa os 120 passos fixos. */
    public void run() {
        for (int step = 1; step <= STEPS; step++) {
            integrate();
            constrain();
            collide();
            updateSleep();
            Fnv1a fnv = new Fnv1a();
            foldState(fnv, true);
            stepChecksum[step] = fnv.value();
        }
    }

    /** Integracao semi-implicita (so corpos acordados). */
    private void integrate() {
        for (int i = 0; i < BODIES; i++) {
            if (asleep[i]) {
                continue;
            }
            vy[i] += GRAVITY_Q16 / DT_DEN;
            px[i] += vx[i] / DT_DEN;
            py[i] += vy[i] / DT_DEN;
            pz[i] += vz[i] / DT_DEN;
        }
    }

    /** Chao e paredes (so corpos acordados). */
    private void constrain() {
        for (int i = 0; i < BODIES; i++) {
            if (asleep[i]) {
                continue;
            }
            if (py[i] < rad[i]) {
                py[i] = rad[i];
                if (vy[i] < 0) {
                    vy[i] = -Q16.mul(vy[i], RESTITUTION_GROUND);
                }
                vx[i] = Q16.mul(vx[i], FRICTION_GROUND);
                vz[i] = Q16.mul(vz[i], FRICTION_GROUND);
            }
            if (px[i] < -HALF_BOX + rad[i]) {
                px[i] = -HALF_BOX + rad[i];
                if (vx[i] < 0) {
                    vx[i] = -Q16.mul(vx[i], RESTITUTION_WALL);
                }
            } else if (px[i] > HALF_BOX - rad[i]) {
                px[i] = HALF_BOX - rad[i];
                if (vx[i] > 0) {
                    vx[i] = -Q16.mul(vx[i], RESTITUTION_WALL);
                }
            }
            if (pz[i] < -HALF_BOX + rad[i]) {
                pz[i] = -HALF_BOX + rad[i];
                if (vz[i] < 0) {
                    vz[i] = -Q16.mul(vz[i], RESTITUTION_WALL);
                }
            } else if (pz[i] > HALF_BOX - rad[i]) {
                pz[i] = HALF_BOX - rad[i];
                if (vz[i] > 0) {
                    vz[i] = -Q16.mul(vz[i], RESTITUTION_WALL);
                }
            }
        }
    }

    /** Slot da grade (hash barato por deslocamento — colisao e por distancia). */
    private int slotOf(int x, int y, int z) {
        int cx = Q16.floorDiv(x, CELL) & 31;
        int cy = Q16.floorDiv(y, CELL) & 31;
        int cz = Q16.floorDiv(z, CELL) & 31;
        return (cx << 10) | (cy << 5) | cz;
    }

    /** Colisoes corpo-corpo pela grade uniforme (ordem de indice fixa). */
    private void collide() {
        java.util.Arrays.fill(head, -1);
        for (int i = 0; i < BODIES; i++) {
            int slot = slotOf(px[i], py[i], pz[i]);
            next[i] = head[slot];
            head[slot] = i;
        }
        for (int i = 0; i < BODIES; i++) {
            int cxi = Q16.floorDiv(px[i], CELL);
            int cyi = Q16.floorDiv(py[i], CELL);
            int czi = Q16.floorDiv(pz[i], CELL);
            for (int dz = -1; dz <= 1; dz++) {
                for (int dy = -1; dy <= 1; dy++) {
                    for (int dx = -1; dx <= 1; dx++) {
                        int slot = slotOfCell(cxi + dx, cyi + dy, czi + dz);
                        for (int j = head[slot]; j >= 0; j = next[j]) {
                            if (j <= i) {
                                continue;
                            }
                            testPair(i, j);
                        }
                    }
                }
            }
        }
    }

    private int slotOfCell(int cx, int cy, int cz) {
        return ((cx & 31) << 10) | ((cy & 31) << 5) | (cz & 31);
    }

    /** Testa e resolve o par (i, j) por eixo de menor penetracao. */
    private void testPair(int i, int j) {
        long ddx = (long) px[i] - px[j];
        long ddy = (long) py[i] - py[j];
        long ddz = (long) pz[i] - pz[j];
        long rr = (long) rad[i] + rad[j];
        long dist2 = ddx * ddx + ddy * ddy + ddz * ddz;
        if (dist2 >= rr * rr || dist2 == 0) {
            return;
        }
        long ax = ddx < 0 ? -ddx : ddx;
        long ay = ddy < 0 ? -ddy : ddy;
        long az = ddz < 0 ? -ddz : ddz;
        int axis;
        long ad;
        if (ax >= ay && ax >= az) {
            axis = 0;
            ad = ax;
        } else if (ay >= az) {
            axis = 1;
            ad = ay;
        } else {
            axis = 2;
            ad = az;
        }
        int sign = axisValue(axis, i) > axisValue(axis, j) ? 1 : -1;
        long corr = (rr - ad) >> 1;
        // correcao posicional 50/50 no eixo
        if (axis == 0) {
            px[i] += (int) (corr * sign);
            px[j] -= (int) (corr * sign);
        } else if (axis == 1) {
            py[i] += (int) (corr * sign);
            py[j] -= (int) (corr * sign);
        } else {
            pz[i] += (int) (corr * sign);
            pz[j] -= (int) (corr * sign);
        }
        // impulso de velocidade no eixo (massas iguais, restituicao 0.2)
        int rel = axisVel(axis, i) - axisVel(axis, j);
        if (rel * sign < 0) { // aproximando-se
            int imp = Q16.mul(rel, 39322); // (1+0.2)/2 = 0.6 em Q16
            axisVelAdd(axis, i, -imp);
            axisVelAdd(axis, j, imp);
        }
        // colisao acorda os corpos
        sleepCtr[i] = 0;
        sleepCtr[j] = 0;
        asleep[i] = false;
        asleep[j] = false;
    }

    private int axisValue(int axis, int i) {
        return axis == 0 ? px[i] : (axis == 1 ? py[i] : pz[i]);
    }

    private int axisVel(int axis, int i) {
        return axis == 0 ? vx[i] : (axis == 1 ? vy[i] : vz[i]);
    }

    private void axisVelAdd(int axis, int i, int delta) {
        if (axis == 0) {
            vx[i] += delta;
        } else if (axis == 1) {
            vy[i] += delta;
        } else {
            vz[i] += delta;
        }
    }

    /** Contadores de sono. */
    private void updateSleep() {
        for (int i = 0; i < BODIES; i++) {
            if (asleep[i]) {
                continue;
            }
            long speed2 = (long) vx[i] * vx[i] + (long) vy[i] * vy[i]
                    + (long) vz[i] * vz[i];
            if (speed2 < SLEEP_SPEED2) {
                sleepCtr[i]++;
                if (sleepCtr[i] >= SLEEP_STEPS) {
                    asleep[i] = true;
                }
            } else {
                sleepCtr[i] = 0;
            }
        }
    }

    /** Dobra o estado de todos os corpos no checksum. */
    private void foldState(Fnv1a fnv, boolean includeAsleep) {
        for (int i = 0; i < BODIES; i++) {
            fnv.addInt(px[i]);
            fnv.addInt(py[i]);
            fnv.addInt(pz[i]);
            fnv.addInt(vx[i]);
            fnv.addInt(vy[i]);
            fnv.addInt(vz[i]);
            if (includeAsleep) {
                fnv.addInt(asleep[i] ? 1 : 0);
            }
        }
    }

    /** Checksum do estado inicial. */
    public long getInitChecksum() {
        return initChecksum;
    }

    /** Checksum apos o passo "step" (1..STEPS). */
    public long getStepChecksum(int step) {
        return stepChecksum[step];
    }

    /** Contagem de corpos dormindo no final. */
    public int getAsleepCount() {
        int n = 0;
        for (int i = 0; i < BODIES; i++) {
            if (asleep[i]) {
                n++;
            }
        }
        return n;
    }

    /** Contagem de corpos encostados no chao no final. */
    public int getGroundContacts() {
        int n = 0;
        for (int i = 0; i < BODIES; i++) {
            if (py[i] <= rad[i] + 128) {
                n++;
            }
        }
        return n;
    }

    /** Altura maxima (Q16) do conjunto no final (prova de dispersao). */
    public int getMaxHeight() {
        int m = Integer.MIN_VALUE;
        for (int i = 0; i < BODIES; i++) {
            if (py[i] > m) {
                m = py[i];
            }
        }
        return m;
    }
}
