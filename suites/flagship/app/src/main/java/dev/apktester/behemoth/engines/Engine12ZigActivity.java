package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-12-zig — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Zig (zig
 * cc freestanding).
 */
public final class Engine12ZigActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-12-zig";
    }

    @Override
    protected String engineLabel() {
        return "Zig (zig cc freestanding)";
    }
}
