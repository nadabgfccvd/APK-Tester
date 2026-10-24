package dev.apktester.behemoth.nativeprobe;

/**
 * R2.2 (AUDIT_ROADMAP_V2) — fachada Java do probe nativo.
 *
 * A classe existe para (1) dar vinculo estatico ao simbolo JNI da
 * libnative_probe.so (o AGP so empacota a .so referenciada via
 * externalNativeBuild do modulo) e (2) permitir que o probe do app
 * exercite a chamada de verdade (MainActivity/probe report podem chamar
 * {@link #sum(int, int)} — a deteccao nao executa nada, ADR 0003).
 */
public final class NativeProbe {

    static {
        // Carregamento explicito: a lib e empacotada pagina-alinhada
        // (useLegacyPackaging=false — contrato do flagship).
        System.loadLibrary("native_probe");
    }

    private NativeProbe() {
    }

    /** Soma inteira via JNI — a unica funcao do probe nativo (R2.2). */
    public static native int sum(int a, int b);
}
