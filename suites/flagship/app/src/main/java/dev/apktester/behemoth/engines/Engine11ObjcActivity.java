package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-11-objc — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio:
 * Objective-C (NDK, Tier C).
 */
public final class Engine11ObjcActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-11-objc";
    }

    @Override
    protected String engineLabel() {
        return "Objective-C (NDK, Tier C)";
    }
}
