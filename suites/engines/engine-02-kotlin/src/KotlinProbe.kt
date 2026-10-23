@file:Suppress("unused")

package dev.apktester.engine.engine02kotlin.probe

/**
 * Probe Kotlin do engine-02 (Tier A, A4): kotlinc -include-runtime coloca
 * o kotlin-stdlib inteiro no jar de entrada do d8 — as classes
 * kotlin.jvm.internal.* (Intrinsics etc.) ficam no DEX e o
 * `<module>.kotlin_module` vai para META-INF (dois artefatos do contrato).
 */
const val KOTLIN_MARKER: String = "kotlin.jvm.internal"
const val ENGINE_02: String = "engine-02-kotlin"
const val SEED_02: Int = 20261022

data class ProbeResult(val engine: String, val checksum: Int)

/** null-check de parâmetro força kotlin.jvm.internal.Intrinsics.checkNotNullParameter */
fun probe(engine: String, seed: Int = SEED_02): ProbeResult {
    require(engine.isNotEmpty()) { "engine vazio" }
    var h = seed
    for (c in engine) {
        h = 31 * h + c.code
    }
    val doubled = listOf(1, 2, 3).map { it * 2 }.sum()
    return ProbeResult(engine, h * 31 + doubled)
}

fun checksum(): Int = probe(ENGINE_02).checksum
