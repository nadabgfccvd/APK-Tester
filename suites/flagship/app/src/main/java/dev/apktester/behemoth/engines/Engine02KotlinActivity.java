package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-02-kotlin — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Kotlin
 * (kotlinc -include-runtime).
 */
public final class Engine02KotlinActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-02-kotlin";
    }

    @Override
    protected String engineLabel() {
        return "Kotlin (kotlinc -include-runtime)";
    }
}
