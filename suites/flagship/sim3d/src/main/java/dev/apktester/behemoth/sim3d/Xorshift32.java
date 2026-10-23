package dev.apktester.behemoth.sim3d;

/**
 * PRNG xorshift32 (mascara de Marsaglia) — fonte unica de aleatoriedade
 * semeada do :sim3d. Inteiro puro, ciclo deterministico em qualquer host;
 * a referencia C++ replica exatamente as mesmas operacoes.
 *
 * Sementes derivadas por subsistema: seed ^ constante ASCII de 4 letras
 * (ex.: "PHYS", "PRTS") para que ordens de consumo distintas nao acoplem
 * os sistemas.
 */
public final class Xorshift32 {

    private int state;

    /** Cria o gerador; semente 0 e normalizada para 1 (lei do xorshift). */
    public Xorshift32(int seed) {
        this.state = seed == 0 ? 1 : seed;
    }

    /** Proximo inteiro de 32 bits (nao-negatividade tratada pelo chamador). */
    public int nextInt() {
        int x = state;
        x ^= x << 13;
        x ^= x >>> 17;
        x ^= x << 5;
        state = x;
        return x;
    }

    /** Inteiro nao-negativo (31 bits). */
    public int nextNonNegative() {
        return nextInt() & 0x7FFFFFFF;
    }

    /** Inteiro uniforme em [0, span). */
    public int nextBounded(int span) {
        return nextNonNegative() % span;
    }
}
