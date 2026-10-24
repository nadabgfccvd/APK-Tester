package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-05-clojure — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Clojure
 * (Tier C honesta).
 */
public final class Engine05ClojureActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-05-clojure";
    }

    @Override
    protected String engineLabel() {
        return "Clojure (Tier C honesta)";
    }
}
