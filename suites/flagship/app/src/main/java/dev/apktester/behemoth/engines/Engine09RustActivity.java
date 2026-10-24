package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-09-rust — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Rust
 * (cargo-ndk).
 */
public final class Engine09RustActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-09-rust";
    }

    @Override
    protected String engineLabel() {
        return "Rust (cargo-ndk)";
    }
}
