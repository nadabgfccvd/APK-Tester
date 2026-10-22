//
// Modulo :app do flagship "Behemoth" (dev.apktester.behemoth).
// Flavor classic: minSdk 9, codigo framework-only (nenhuma dependencia
// externa; rotas de API nova sao guardadas por Build.VERSION.SDK_INT dentro
// dos metodos). Flavor modern: minSdk 26 (androidx/compose entram em A5/A6).
//
plugins {
    id("com.android.application")
}

// Diretorios de saida dos geradores build-time (deterministicos, seed fixo).
// Usados via Provider para continuar corretos mesmo com --project-cache-dir.
val genStringsDir = layout.buildDirectory.dir("gen/strings")
val genIconsDir = layout.buildDirectory.dir("gen/icons")
val genAssetsDir = layout.buildDirectory.dir("gen/assets")

android {
    namespace = "dev.apktester.behemoth"
    compileSdk = 36
    buildToolsVersion = "35.0.0"

    defaultConfig {
        applicationId = "dev.apktester.behemoth"
        minSdk = 9
        targetSdk = 36
        versionCode = 900036
        versionName = "1.0.0"
    }

    flavorDimensions += "mode"
    productFlavors {
        create("classic") {
            dimension = "mode"
            minSdk = 9
        }
        create("modern") {
            dimension = "mode"
            minSdk = 26
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    lint {
        // Lint integral chega no marco A8; aqui fica desligado porque o flavor
        // classic (minSdk 9) estende classes de sistema de APIs novas (ex.:
        // CredentialStub, API 34) e o NewApi acusaria falso positivo em codigo
        // que o Android so carrega quando o sistema vincula o componente.
        checkReleaseBuilds = false
        abortOnError = false
    }

    sourceSets {
        getByName("main") {
            // gen-strings.py e gen-icons.py gravam res/ direto sob --out;
            // gen-assets.py grava assets/ sob --out (layouts verificados).
            res.srcDirs(
                genStringsDir.map { it.dir("res") },
                genIconsDir.map { it.dir("res") },
                "src/main/res",
            )
            assets.srcDirs(
                genAssetsDir.map { it.dir("assets") },
                "src/main/assets",
            )
        }
    }
}

// Raiz do repositorio: suites/flagship -> suites -> raiz.
val repoRoot = rootDir.parentFile.parentFile

tasks.register<Exec>("genStrings") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-strings.py").absolutePath,
        "--out", genStringsDir.get().asFile.absolutePath,
        "--seed", "20261022",
    )
}

tasks.register<Exec>("genIcons") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-icons.py").absolutePath,
        "--out", genIconsDir.get().asFile.absolutePath,
        "--seed", "20261022",
    )
}

tasks.register<Exec>("genAssets") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-assets.py").absolutePath,
        "--out", genAssetsDir.get().asFile.absolutePath,
        "--seed", "20261022",
    )
}

// preBuild e criada pelo AGP depois do evaluate; matching.configureEach
// conecta os geradores de forma lazy, sem depender do momento do registro.
tasks.matching { it.name == "preBuild" }.configureEach {
    dependsOn("genStrings", "genIcons", "genAssets")
}
