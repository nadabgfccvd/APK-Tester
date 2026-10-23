package dev.apktester.engine.engine03kmp.probe

/**
 * Código COMMON do engine-03 (Tier A, A4): fonte no estilo multiplataforma
 * Kotlin compilada pelo kotlinc junto com o actual de plataforma abaixo.
 * O runtime Compose-MP (org.jetbrains.compose.runtime:runtime-desktop,
 * pin 1.6.11) entra no MESMO DEX pelo d8 — é o "shared DEX" do contrato.
 */
expect fun platformName(): String

const val KMP_MARKER: String = "kotlin.multiplatform"
const val ENGINE_03: String = "engine-03-kmp"
const val SEED_03: Int = 20261022

class SharedCounter(private var count: Int = SEED_03 % 100) {
    fun tick(): Int {
        count += 1
        return count
    }

    fun checksum(): Int {
        var h = count
        for (c in ENGINE_03) {
            h = 31 * h + c.code
        }
        return 31 * h + platformName().length
    }
}
