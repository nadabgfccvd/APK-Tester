//
// Build raiz da escada sdk-ladder. O AGP e resolvido pelo pluginManagement
// (google()/mavenCentral()/gradlePluginPortal) declarado em settings.gradle.kts.
// Mesma versao do flagship (comprovada em CI com compileSdk 36 e minSdk 9).
//
plugins {
    id("com.android.application") version "8.9.2" apply false
}
