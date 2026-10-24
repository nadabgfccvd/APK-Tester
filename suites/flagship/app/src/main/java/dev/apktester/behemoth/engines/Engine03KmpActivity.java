package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-03-kmp — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Kotlin
 * Multiplatform (Compose-MP).
 */
public final class Engine03KmpActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-03-kmp";
    }

    @Override
    protected String engineLabel() {
        return "Kotlin Multiplatform (Compose-MP)";
    }
}
