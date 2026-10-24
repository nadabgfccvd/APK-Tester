package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-13-flutter — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio:
 * Flutter/Dart (libflutter.so).
 */
public final class Engine13FlutterActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-13-flutter";
    }

    @Override
    protected String engineLabel() {
        return "Flutter/Dart (libflutter.so)";
    }
}
