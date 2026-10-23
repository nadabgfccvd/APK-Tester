package dev.apktester.engine.engine01java.probe;

/**
 * Probe invoke-custom do engine-01 (Tier A, A4): compila com javac 8+ e o
 * d8 --min-api 26 mantém os lambdas como invokedynamic para o
 * LambdaMetafactory (suportado pela plataforma a partir da API 26).
 * O marcador textual "invoke-custom" garante o dex-strings do contrato
 * contracts/engines/expected-engines.json mesmo que uma versão do d8
 * desagueue o lambda para classe sintética.
 */
public final class InvokeCustomProbes {

    /** âncora literal do detector (dex-strings:invoke-custom) */
    public static final String INVOKE_CUSTOM_MARKER = "invoke-custom";
    public static final String ENGINE = "engine-01-java";
    public static final int SEED = 20261022;

    private InvokeCustomProbes() {
    }

    @FunctionalInterface
    public interface Probe {
        int run(int value);
    }

    public static int lambdaDirect(int input) {
        Probe square = v -> v * v;
        return square.run(input);
    }

    public static int methodRef(int input) {
        Probe ref = InvokeCustomProbes::doubleIt;
        return ref.run(input);
    }

    public static String supplierRef() {
        java.util.function.Supplier<String> sup = ENGINE::toLowerCase;
        return sup.get();
    }

    public static java.util.function.BiFunction<Integer, Integer, Integer>
            biLambda() {
        return (a, b) -> a * 31 + b;
    }

    private static int doubleIt(int v) {
        return 2 * v;
    }

    /** checksum determinístico consumido pela suíte smoke do RustyDroid */
    public static int checksum() {
        int h = SEED;
        h = 31 * h + lambdaDirect(7);
        h = 31 * h + methodRef(11);
        h = 31 * h + supplierRef().length();
        h = 31 * h + biLambda().apply(3, 4);
        return h;
    }
}
