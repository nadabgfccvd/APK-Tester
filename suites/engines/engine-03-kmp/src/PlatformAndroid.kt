package dev.apktester.engine.engine03kmp.probe

/**
 * Parte de PLATAFORMA (Android/JVM) do engine-03 — compilada no mesmo
 * módulo kotlinc com o código comum (SharedCounter.kt).
 */
fun platformName(): String = "android-jvm"

/** consumidor da parte de plataforma (ancora o símbolo no DEX) */
fun platformChecksum(): Int = SharedCounter().tick() + platformName().length
