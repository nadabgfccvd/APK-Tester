package dev.apktester.engine.engine03kmp.probe

/**
 * Código COMMON do engine-03 (Tier A, A4), no estilo multiplataforma
 * Kotlin: fonte compartilhada compilada pelo kotlinc junto com a parte de
 * plataforma (PlatformAndroid.kt). O runtime Compose-MP
 * (org.jetbrains.compose.runtime:runtime-desktop, pin 1.6.11) entra no
 * MESMO DEX pelo d8 — é o "shared DEX" do contrato.
 *
 * Nota honesta: o par expect/actual exige o compilador multiplataforma do
 * plugin Gradle KMP (kotlinc CLI recusa expect/actual no mesmo módulo);
 * aqui a KMP-ness é representada pelo layout de fontes compartilhadas +
 * runtime Compose-MP + <module>.kotlin_module + marcador kotlin.multiplatform.
 */
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
