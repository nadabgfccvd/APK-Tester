package dev.apktester.engine.engine10go.probe;

/**
 * Marcador Java do engine-10 (Tier A, A4): o bridge gomobile REAL usa
 * classes go.Seq / go.Universe (nome de classe no DEX em formato Lgo/Seq;)
 * âncora textual do contrato dex-strings:go.Seq. O classes.jar do AAR
 * gomobile traz as classes de verdade; esta constante garante a forma
 * canônica com ponto no string pool do dex.
 */
public final class GoBridgeMarker {

    public static final String BRIDGE_SEQ = "go.Seq";
    public static final String BRIDGE_UNIVERSE = "go.Universe";
    public static final String ENGINE = "engine-10-go";

    private GoBridgeMarker() {
    }

    public static int checksum() {
        int h = 20261022;
        for (char c : BRIDGE_SEQ.toCharArray()) {
            h = 31 * h + c;
        }
        for (char c : BRIDGE_UNIVERSE.toCharArray()) {
            h = 31 * h + c;
        }
        return h;
    }
}
