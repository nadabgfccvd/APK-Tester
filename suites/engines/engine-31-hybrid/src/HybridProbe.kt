package dev.apktester.engine.engine31hybrid.probe

/**
 * Probe Kotlin do APK híbrido (TST-14, Tier A, A4): UM APK com os quatro
 * marcadores — DEX Kotlin (este módulo via kotlinc -include-runtime),
 * librust_hybrid.so (cargo-ndk), assets/index.android.bundle (hermesc
 * real) e assets/module.wasm (wat2wasm).
 */
const val HYBRID_MARKER: String = "tst-14-hybrid"
const val ENGINE_31: String = "engine-31-hybrid"
const val SEED_31: Int = 20261022

data class HybridParts(val kotlin: Boolean, val rust: Boolean,
                       val hermes: Boolean, val wasm: Boolean)

fun parts(): HybridParts = HybridParts(kotlin = true, rust = true,
                                       hermes = true, wasm = true)

fun checksum(): Int {
    var h = SEED_31
    for (c in ENGINE_31) {
        h = 31 * h + c.code
    }
    for (c in HYBRID_MARKER) {
        h = 31 * h + c.code
    }
    return h
}
