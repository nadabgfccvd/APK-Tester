package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-15-cordova — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Cordova
 * (WebView).
 */
public final class Engine15CordovaActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-15-cordova";
    }

    @Override
    protected String engineLabel() {
        return "Cordova (WebView)";
    }
}
