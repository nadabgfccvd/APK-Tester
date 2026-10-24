package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-06-groovy — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Groovy
 * (runtime dexado).
 */
public final class Engine06GroovyActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-06-groovy";
    }

    @Override
    protected String engineLabel() {
        return "Groovy (runtime dexado)";
    }
}
