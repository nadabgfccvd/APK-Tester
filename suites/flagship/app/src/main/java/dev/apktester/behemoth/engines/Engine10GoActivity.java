package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-10-go — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Go
 * (gomobile bind).
 */
public final class Engine10GoActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-10-go";
    }

    @Override
    protected String engineLabel() {
        return "Go (gomobile bind)";
    }
}
