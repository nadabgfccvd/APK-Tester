package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-28-avalonia-dotnet — R2.1 do AUDIT_ROADMAP_V2: uma
 * activity por engine, declarada no manifesto com exported auditado.
 * Domínio: Avalonia/.NET (Tier B).
 */
public final class Engine28AvaloniaDotnetActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-28-avalonia-dotnet";
    }

    @Override
    protected String engineLabel() {
        return "Avalonia/.NET (Tier B)";
    }
}
