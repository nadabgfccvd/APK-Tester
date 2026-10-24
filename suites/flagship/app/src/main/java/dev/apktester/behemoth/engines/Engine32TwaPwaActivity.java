package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-32-twa-pwa — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: TWA/PWA
 * (sem payload local).
 */
public final class Engine32TwaPwaActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-32-twa-pwa";
    }

    @Override
    protected String engineLabel() {
        return "TWA/PWA (sem payload local)";
    }
}
