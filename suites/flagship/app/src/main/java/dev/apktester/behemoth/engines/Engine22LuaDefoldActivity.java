package dev.apktester.behemoth.engines;

/**
 * Sonda do engine-22-lua-defold — R2.1 do AUDIT_ROADMAP_V2: uma activity
 * por engine, declarada no manifesto com exported auditado. Domínio: Lua
 * (Defold, bob.jar).
 */
public final class Engine22LuaDefoldActivity extends EngineProbeActivity {

    @Override
    protected String engineId() {
        return "engine-22-lua-defold";
    }

    @Override
    protected String engineLabel() {
        return "Lua (Defold, bob.jar)";
    }
}
