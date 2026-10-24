package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-16-tauri — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio:
 * Rust/Tauri v2 (tauri-android + wry).
 */
public final class Engine16TauriActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-16-tauri";
    }

    @Override
    protected String engineLabel() {
        return "Rust/Tauri v2 (tauri-android + wry)";
    }
}
