//
// Build raiz do flagship. O AGP e resolvido pelo pluginManagement
// (google()/mavenCentral()/gradlePluginPortal) declarado em settings.gradle.kts.
// R2.2: kotlin.android + compose compiler (plugin do próprio Kotlin 2.x)
// para o módulo :compose — versões pinnadas, baixadas da fonte oficial.
//
plugins {
    id("com.android.application") version "8.9.2" apply false
    id("com.android.library") version "8.9.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.20" apply false
}
