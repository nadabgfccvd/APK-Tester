package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-17-nativescript — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio:
 * NativeScript (Tier B).
 */
public final class Engine17NativescriptActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-17-nativescript";
    }

    @Override
    protected String engineLabel() {
        return "NativeScript (Tier B)";
    }
}
