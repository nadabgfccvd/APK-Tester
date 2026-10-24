package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-23-godot — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Godot
 * (Tier B).
 */
public final class Engine23GodotActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-23-godot";
    }

    @Override
    protected String engineLabel() {
        return "Godot (Tier B)";
    }
}
