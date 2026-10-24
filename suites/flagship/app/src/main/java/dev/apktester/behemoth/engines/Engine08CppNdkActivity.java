package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-08-cpp-ndk — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: C++ (NDK,
 * libc++).
 */
public final class Engine08CppNdkActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-08-cpp-ndk";
    }

    @Override
    protected String engineLabel() {
        return "C++ (NDK, libc++)";
    }
}
