package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-25-python-chaquopy — R2.1 do AUDIT_ROADMAP_V2: uma
 * activity por engine, declarada no manifesto com exported auditado.
 * Domínio: Python (Chaquopy, gradle real).
 */
public final class Engine25PythonChaquopyActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-25-python-chaquopy";
    }

    @Override
    protected String engineLabel() {
        return "Python (Chaquopy, gradle real)";
    }
}
