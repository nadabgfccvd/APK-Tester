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
