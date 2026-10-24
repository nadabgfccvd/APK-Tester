package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-24-haxe — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Haxe
 * (-java, hxjava).
 */
public final class Engine24HaxeActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-24-haxe";
    }

    @Override
    protected String engineLabel() {
        return "Haxe (-java, hxjava)";
    }
}
