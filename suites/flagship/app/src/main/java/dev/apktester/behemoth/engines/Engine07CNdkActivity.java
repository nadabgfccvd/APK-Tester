package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-07-c-ndk — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: C (NDK,
 * clang).
 */
public final class Engine07CNdkActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-07-c-ndk";
    }

    @Override
    protected String engineLabel() {
        return "C (NDK, clang)";
    }
}
