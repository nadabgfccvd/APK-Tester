/*
 * sim3d_native.cpp — fallback C++ (JNI) da fisica do :sim3d.
 *
 * Lei do modulo (pilar 3D, APK_TESTER_PROMPT.md): motor principal e
 * 100% Java; este arquivo e o "C++ JNI fallback". A aritmetica e
 * EXATAMENTE a mesma do Java (inteiros int32/int64, divisao truncando
 * em direcao a zero, deslocamento aritmetico) — a paridade de checksum
 * com PhysicsSim.java e o teste (CI: --parity sim3d_native).
 *
 * Compilacao host (CI): cc -shared -fPIC -O2 -I$JAVA_HOME/include
 *   -I$JAVA_HOME/include/linux sim3d_native.cpp -o libsim3d_native.so
 * Compilacao NDK (fase A6, :native): via CMakeLists.txt do diretorio.
 *
 * Apenas C++14 padrao + jni.h; sem bibliotecas externas.
 */
#include <jni.h>
#include <cstdint>
#include <cstring>
#include <cstdlib>

namespace sim3d {

constexpr int32_t ONE = 65536;
constexpr int32_t HALF = 32768;
constexpr int32_t CORDIC_K = 39797;
constexpr int32_t ATAN_BAM24[24] = {
    2097152, 1238021, 654136, 332050, 166669, 83416, 41718,
    20860, 10430, 5215, 2608, 1304, 652, 326, 163, 81,
    41, 20, 10, 5, 3, 1, 1, 0,
};

/* ===== PRNG xorshift32 (espelho de Xorshift32.java) ===== */
struct Rng {
    int32_t state;
    explicit Rng(int32_t seed) : state(seed == 0 ? 1 : seed) {}
    /* Java: x ^= x<<13; x ^= x>>>17; x ^= x<<5 — em 32 bits SEM sinal
     * para casar com os deslocamentos logical/aritmetico do Java. */
    int32_t nextInt() {
        uint32_t x = (uint32_t)state;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        state = (int32_t)x;
        return state;
    }
    int32_t nextNonNegative() { return nextInt() & 0x7FFFFFFF; }
    int32_t nextBounded(int32_t span) { return nextNonNegative() % span; }
};

/* ===== Q16 (espelho de Q16.java) ===== */
static inline int32_t mul(int32_t a, int32_t b) {
    return (int32_t)(((int64_t)a * (int64_t)b) >> 16);
}

static inline int32_t floorDiv(int32_t a, int32_t b) {
    int32_t q = a / b;
    if ((a % b != 0) && ((a < 0) != (b < 0))) {
        q--;
    }
    return q;
}

/* ===== FNV-1a 64 (espelho de Fnv1a.java) ===== */
struct Fnv {
    uint64_t hash = 0xcbf29ce484222325ULL;
    void addByte(int32_t b) { hash = (hash ^ (uint64_t)(b & 0xFF)) * 0x100000001b3ULL; }
    void addInt(int32_t v) {
        addByte(v);
        addByte(v >> 8);
        addByte(v >> 16);
        addByte(v >> 24);
    }
    uint64_t value() const { return hash; }
};

/* ===== Constantes da fisica (espelho de PhysicsSim.java) ===== */
constexpr int32_t BODIES = 10000;
constexpr int32_t STEPS = 120;
constexpr int32_t DT_DEN = 60;
constexpr int32_t GRAVITY_Q16 = -642770;
constexpr int32_t RESTITUTION_GROUND = 24576;
constexpr int32_t RESTITUTION_WALL = HALF;
constexpr int32_t FRICTION_GROUND = 64225;
constexpr int32_t RESTITUTION_BODY_IMPULSE = 39322;  // (1+0.2)/2 em Q16
constexpr int32_t HALF_BOX = 8 * ONE;
constexpr int32_t CELL = 16384;
constexpr int32_t SLEEP_SPEED2 = 1718721;
constexpr int32_t SLEEP_STEPS = 30;
constexpr int32_t SLOTS = 1 << 15;  /* 15 bits: 5 por eixo */
constexpr uint32_t SEED_XOR = 0x50485953u;  // "PHYS"

struct State {
    int32_t px[BODIES];
    int32_t py[BODIES];
    int32_t pz[BODIES];
    int32_t vx[BODIES];
    int32_t vy[BODIES];
    int32_t vz[BODIES];
    int32_t rad[BODIES];
    uint8_t asleep[BODIES];
    int32_t sleepCtr[BODIES];
    int32_t head[SLOTS];
    int32_t next[BODIES];
};

static inline int32_t axisValue(const State& s, int axis, int i) {
    return axis == 0 ? s.px[i] : (axis == 1 ? s.py[i] : s.pz[i]);
}
static inline int32_t axisVel(const State& s, int axis, int i) {
    return axis == 0 ? s.vx[i] : (axis == 1 ? s.vy[i] : s.vz[i]);
}
static inline void axisVelAdd(State& s, int axis, int i, int32_t delta) {
    if (axis == 0) s.vx[i] += delta;
    else if (axis == 1) s.vy[i] += delta;
    else s.vz[i] += delta;
}

static void init(State& s, int32_t seed) {
    Rng rng(seed ^ (int32_t)SEED_XOR);
    const int32_t spanXZ = 12 * ONE;
    const int32_t spanY = 6 * ONE;
    for (int32_t i = 0; i < BODIES; i++) {
        s.px[i] = ((rng.nextBounded(spanXZ) - 6 * ONE) / 64) * 64;
        s.py[i] = 2 * ONE + (rng.nextBounded(spanY) / 64) * 64;
        s.pz[i] = ((rng.nextBounded(spanXZ) - 6 * ONE) / 64) * 64;
        s.vx[i] = ((rng.nextBounded(ONE) - HALF) / 32) * 32;
        s.vy[i] = 0;
        s.vz[i] = ((rng.nextBounded(ONE) - HALF) / 32) * 32;
        s.rad[i] = 3932 + rng.nextBounded(9175 - 3932 + 1);
        s.asleep[i] = 0;
        s.sleepCtr[i] = 0;
    }
}

static inline int32_t slotOf(int32_t x, int32_t y, int32_t z) {
    int32_t cx = floorDiv(x, CELL) & 31;
    int32_t cy = floorDiv(y, CELL) & 31;
    int32_t cz = floorDiv(z, CELL) & 31;
    return (cx << 10) | (cy << 5) | cz;
}

static void integrate(State& s) {
    for (int32_t i = 0; i < BODIES; i++) {
        if (s.asleep[i]) continue;
        s.vy[i] += GRAVITY_Q16 / DT_DEN;
        s.px[i] += s.vx[i] / DT_DEN;
        s.py[i] += s.vy[i] / DT_DEN;
        s.pz[i] += s.vz[i] / DT_DEN;
    }
}

static void constrain(State& s) {
    for (int32_t i = 0; i < BODIES; i++) {
        if (s.asleep[i]) continue;
        if (s.py[i] < s.rad[i]) {
            s.py[i] = s.rad[i];
            if (s.vy[i] < 0) s.vy[i] = -mul(s.vy[i], RESTITUTION_GROUND);
            s.vx[i] = mul(s.vx[i], FRICTION_GROUND);
            s.vz[i] = mul(s.vz[i], FRICTION_GROUND);
        }
        if (s.px[i] < -HALF_BOX + s.rad[i]) {
            s.px[i] = -HALF_BOX + s.rad[i];
            if (s.vx[i] < 0) s.vx[i] = -mul(s.vx[i], RESTITUTION_WALL);
        } else if (s.px[i] > HALF_BOX - s.rad[i]) {
            s.px[i] = HALF_BOX - s.rad[i];
            if (s.vx[i] > 0) s.vx[i] = -mul(s.vx[i], RESTITUTION_WALL);
        }
        if (s.pz[i] < -HALF_BOX + s.rad[i]) {
            s.pz[i] = -HALF_BOX + s.rad[i];
            if (s.vz[i] < 0) s.vz[i] = -mul(s.vz[i], RESTITUTION_WALL);
        } else if (s.pz[i] > HALF_BOX - s.rad[i]) {
            s.pz[i] = HALF_BOX - s.rad[i];
            if (s.vz[i] > 0) s.vz[i] = -mul(s.vz[i], RESTITUTION_WALL);
        }
    }
}

static inline int32_t slotOfCell(int32_t cx, int32_t cy, int32_t cz) {
    return ((cx & 31) << 10) | ((cy & 31) << 5) | (cz & 31);
}

static void testPair(State& s, int32_t i, int32_t j) {
    int64_t ddx = (int64_t)s.px[i] - s.px[j];
    int64_t ddy = (int64_t)s.py[i] - s.py[j];
    int64_t ddz = (int64_t)s.pz[i] - s.pz[j];
    int64_t rr = (int64_t)s.rad[i] + s.rad[j];
    int64_t dist2 = ddx * ddx + ddy * ddy + ddz * ddz;
    if (dist2 >= rr * rr || dist2 == 0) return;
    int64_t ax = ddx < 0 ? -ddx : ddx;
    int64_t ay = ddy < 0 ? -ddy : ddy;
    int64_t az = ddz < 0 ? -ddz : ddz;
    int axis;
    int64_t ad;
    if (ax >= ay && ax >= az) { axis = 0; ad = ax; }
    else if (ay >= az) { axis = 1; ad = ay; }
    else { axis = 2; ad = az; }
    int32_t sign = axisValue(s, axis, i) > axisValue(s, axis, j) ? 1 : -1;
    int64_t corr = (rr - ad) >> 1;
    if (axis == 0) {
        s.px[i] += (int32_t)(corr * sign);
        s.px[j] -= (int32_t)(corr * sign);
    } else if (axis == 1) {
        s.py[i] += (int32_t)(corr * sign);
        s.py[j] -= (int32_t)(corr * sign);
    } else {
        s.pz[i] += (int32_t)(corr * sign);
        s.pz[j] -= (int32_t)(corr * sign);
    }
    int32_t rel = axisVel(s, axis, i) - axisVel(s, axis, j);
    if (rel * sign < 0) {
        int32_t imp = mul(rel, RESTITUTION_BODY_IMPULSE);
        axisVelAdd(s, axis, i, -imp);
        axisVelAdd(s, axis, j, imp);
    }
    s.sleepCtr[i] = 0;
    s.sleepCtr[j] = 0;
    s.asleep[i] = 0;
    s.asleep[j] = 0;
}

static void collide(State& s) {
    std::memset(s.head, -1, sizeof(s.head));
    for (int32_t i = 0; i < BODIES; i++) {
        int32_t slot = slotOf(s.px[i], s.py[i], s.pz[i]);
        s.next[i] = s.head[slot];
        s.head[slot] = i;
    }
    for (int32_t i = 0; i < BODIES; i++) {
        int32_t cxi = floorDiv(s.px[i], CELL);
        int32_t cyi = floorDiv(s.py[i], CELL);
        int32_t czi = floorDiv(s.pz[i], CELL);
        for (int32_t dz = -1; dz <= 1; dz++) {
            for (int32_t dy = -1; dy <= 1; dy++) {
                for (int32_t dx = -1; dx <= 1; dx++) {
                    int32_t slot = slotOfCell(cxi + dx, cyi + dy, czi + dz);
                    for (int32_t j = s.head[slot]; j >= 0; j = s.next[j]) {
                        if (j <= i) continue;
                        testPair(s, i, j);
                    }
                }
            }
        }
    }
}

static void updateSleep(State& s) {
    for (int32_t i = 0; i < BODIES; i++) {
        if (s.asleep[i]) continue;
        int64_t speed2 = (int64_t)s.vx[i] * s.vx[i] + (int64_t)s.vy[i] * s.vy[i]
                + (int64_t)s.vz[i] * s.vz[i];
        if (speed2 < SLEEP_SPEED2) {
            s.sleepCtr[i]++;
            if (s.sleepCtr[i] >= SLEEP_STEPS) s.asleep[i] = 1;
        } else {
            s.sleepCtr[i] = 0;
        }
    }
}

static void foldState(const State& s, Fnv& fnv) {
    for (int32_t i = 0; i < BODIES; i++) {
        fnv.addInt(s.px[i]);
        fnv.addInt(s.py[i]);
        fnv.addInt(s.pz[i]);
        fnv.addInt(s.vx[i]);
        fnv.addInt(s.vy[i]);
        fnv.addInt(s.vz[i]);
        fnv.addInt(s.asleep[i] ? 1 : 0);
    }
}

/* Estado alocado uma unica vez (10k corpos ~ 400 KB — estatico ok). */
static State g_state;

}  // namespace sim3d

/*
 * Entrada JNI: checksum FNV-1a 64 do estado final da fisica — deve ser
 * identico a PhysicsSim.getStepChecksum(STEPS) do lado Java.
 */
extern "C" JNIEXPORT jlong JNICALL
Java_dev_apktester_behemoth_sim3d_nativecompat_NativeBridge_physicsFinalChecksum(
        JNIEnv* /*env*/, jclass /*clazz*/, jint seed, jint bodies, jint steps) {
    using namespace sim3d;
    if (bodies != BODIES || steps != STEPS) return 0;  // so o golden e suportado
    init(g_state, seed);
    for (int32_t step = 1; step <= STEPS; step++) {
        integrate(g_state);
        constrain(g_state);
        collide(g_state);
        updateSleep(g_state);
    }
    Fnv fnv;
    foldState(g_state, fnv);
    return (jlong)fnv.value();
}
