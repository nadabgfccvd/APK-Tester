package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-21-unreal — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Unreal
 * (UE4).
 */
public final class Engine21UnrealActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-21-unreal";
    }

    @Override
    protected String engineLabel() {
        return "Unreal (UE4)";
    }
}
