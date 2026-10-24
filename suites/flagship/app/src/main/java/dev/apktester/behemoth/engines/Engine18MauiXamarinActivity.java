package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-18-maui-xamarin — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio: .NET
 * MAUI/Xamarin (Tier C).
 */
public final class Engine18MauiXamarinActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-18-maui-xamarin";
    }

    @Override
    protected String engineLabel() {
        return ".NET MAUI/Xamarin (Tier C)";
    }
}
