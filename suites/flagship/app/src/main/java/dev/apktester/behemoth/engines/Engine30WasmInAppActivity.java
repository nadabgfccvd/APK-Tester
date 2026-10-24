package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-30-wasm-in-app — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio: WASM
 * in-app (wat2wasm + wasmer).
 */
public final class Engine30WasmInAppActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-30-wasm-in-app";
    }

    @Override
    protected String engineLabel() {
        return "WASM in-app (wat2wasm + wasmer)";
    }
}
