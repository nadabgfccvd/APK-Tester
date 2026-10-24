package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-19-unity-mono — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio: Unity
 * (Mono).
 */
public final class Engine19UnityMonoActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-19-unity-mono";
    }

    @Override
    protected String engineLabel() {
        return "Unity (Mono)";
    }
}
