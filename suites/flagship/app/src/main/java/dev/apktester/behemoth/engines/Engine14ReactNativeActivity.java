package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-14-react-native — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio: React
 * Native (Hermes).
 */
public final class Engine14ReactNativeActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-14-react-native";
    }

    @Override
    protected String engineLabel() {
        return "React Native (Hermes)";
    }
}
