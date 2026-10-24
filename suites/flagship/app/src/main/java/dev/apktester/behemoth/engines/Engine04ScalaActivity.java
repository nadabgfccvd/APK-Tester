package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-04-scala — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Scala
 * (Tier B real).
 */
public final class Engine04ScalaActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-04-scala";
    }

    @Override
    protected String engineLabel() {
        return "Scala (Tier B real)";
    }
}
