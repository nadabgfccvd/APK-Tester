package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-01-java — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Java
 * (multi-dex real, invoke-custom).
 */
public final class Engine01JavaActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-01-java";
    }

    @Override
    protected String engineLabel() {
        return "Java (multi-dex real, invoke-custom)";
    }
}
