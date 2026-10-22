//
// Settings da escada sdk-ladder (dev.apktester.ladder.*).
// Repositorios declarados apenas aqui: FAIL_ON_PROJECT_REPOS garante que
// nenhum modulo individual adicione repositorios proprios. Convencoes
// espelhadas do flagship (unico projeto Gradle comprovado verde no CI).
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

rootProject.name = "sdk-ladder"

include(":app")
