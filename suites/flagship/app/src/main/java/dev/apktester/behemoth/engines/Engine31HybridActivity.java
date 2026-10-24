package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-31-hybrid — R2.1 do AUDIT_ROADMAP_V2: uma activity por
 * engine, declarada no manifesto com exported auditado. Domínio: Hibrido
 * TST-14 (Kotlin+Rust+Hermes+WASM).
 */
public final class Engine31HybridActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-31-hybrid";
    }

    @Override
    protected String engineLabel() {
        return "Hibrido TST-14 (Kotlin+Rust+Hermes+WASM)";
    }
}
