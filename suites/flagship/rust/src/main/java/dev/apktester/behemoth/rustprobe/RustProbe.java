package dev.apktester.behemoth.rustprobe;

/**
 * R2.2 (AUDIT_ROADMAP_V2) — fachada Java do probe Rust.
 *
 * Mesmo contrato do {@code NativeProbe} (:native): vinculo estatico do
 * simbolo JNI exportado pelo crate (librust_probe.so, cargo-ndk) e
 * chamada provavel exercitavel pelo app. A deteccao nao valida payload
 * nem autoriza execucao (ADR 0003).
 */
public final class RustProbe {

    static {
        System.loadLibrary("rust_probe");
    }

    private RustProbe() {
    }

    /** Soma inteira via JNI — a unica funcao do probe Rust (R2.2). */
    public static native int sum(int a, int b);
}
