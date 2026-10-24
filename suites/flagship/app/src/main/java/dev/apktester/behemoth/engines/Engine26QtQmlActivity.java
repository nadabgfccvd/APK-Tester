package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-26-qt-qml — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Qt/QML
 * (Tier B).
 */
public final class Engine26QtQmlActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-26-qt-qml";
    }

    @Override
    protected String engineLabel() {
        return "Qt/QML (Tier B)";
    }
}
