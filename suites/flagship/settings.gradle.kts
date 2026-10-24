//
// Settings do flagship "Behemoth" (dev.apktester.behemoth).
// Repositorios declarados apenas aqui: FAIL_ON_PROJECT_REPOS garante que
// nenhum modulo individual adicione repositorios proprios.
//
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Behemoth"

include(":app")
include(":sim3d")
// R2.2 (AUDIT_ROADMAP_V2): os três módulos prometidos desde a A1, agora
// reais — :native (1 .so com JNI via CMake/NDK pinnado), :rust (cargo-ndk
// com 1 função), :compose (1 tela Compose real, consumida só pelo flavor
// modern). Mínimo viável honesto, documentado no CHANGELOG e no ADR.
include(":native")
include(":rust")
include(":compose")
