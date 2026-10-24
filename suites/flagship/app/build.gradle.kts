//
// Modulo :app do flagship "Behemoth" (dev.apktester.behemoth).
// Flavor classic: minSdk 9, codigo framework-only (nenhuma dependencia
// externa; rotas de API nova sao guardadas por Build.VERSION.SDK_INT dentro
// dos metodos). Flavor modern: minSdk 26 (androidx/compose entram em A5/A6).
//
import java.util.Base64

plugins {
    id("com.android.application")
}

// Diretorios de saida dos geradores build-time (deterministicos, seed fixo).
// Usados via Provider para continuar corretos mesmo com --project-cache-dir.
val genStringsDir = layout.buildDirectory.dir("gen/strings")
val genIconsDir = layout.buildDirectory.dir("gen/icons")
val genAssetsDir = layout.buildDirectory.dir("gen/assets")
// A5 — ativos do pilar 3D (shader-library, texturas, malhas, audio).
val genSim3dDir = layout.buildDirectory.dir("gen/sim3d")
// A6 — carga deterministica para o gate de tamanho [850, 1000] MiB.
// O preset "full" (~768 MiB) alimenta o release do Size Gate; o preset
// "quick" (~15 MiB) acelera builds de debug (CI passa -PbulkPreset=quick).
val bulkPreset = providers.gradleProperty("bulkPreset").getOrElse("full")
val genBulkDir = layout.buildDirectory.dir("gen/bulk-out")

// A6 — keystore de fixture commitado como texto base64 (decodificado no
// build/). NAO e segredo: chave de teste publica, senha documentada no
// build.gradle.kts; garante release byte-reproduzivel entre maquinas.
val keystoreSrc = layout.projectDirectory.file("../keystore/behemoth-test.keystore.b64")
val keystoreOut = layout.buildDirectory.file("keystore/behemoth-test.keystore")

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

    // A6 — assinatura release com keystore de fixture commitado como texto
    // base64 (decodificado no build). NAO e segredo: chave de teste publica,
    // senha documentada; garante que builds release sejam byte-reproduziveis
    // entre maquinas (a alternativa ~/.android/debug.keystore varia por host).
    signingConfigs {
        create("behemothTest") {
            storeFile = keystoreOut.get().asFile
            storePassword = "behemoth2026"
            keyAlias = "behemoth-test"
            keyPassword = "behemoth2026"
            storeType = "PKCS12"
        }
    }

    buildTypes {
        release {
            // A6 — "fully optimized": R8 full + resource shrinking + zipalign
            // (padrao do AGP) + libs nativas descomprimidas (packaging abaixo).
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            signingConfig = signingConfigs.getByName("behemothTest")
            // A6 — sem informacao de VCS no APK (metadado dependente do
            // ambiente; determinismo do pacote e requisito do repo).
            vcsInfo {
                include = false
            }
        }
    }

    packaging {
        // Libs nativas pagina-alinhadas e descomprimidas no APK
        // (android:extractNativeLibs=false; hoje nao ha .so, mas o contrato
        // do flagship exige esse modo quando :native entrar).
        jniLibs.useLegacyPackaging = false
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
                // R2.3: assets/locales/<tag>/strings.properties do
                // gen-strings.py — lidos em runtime pelas sondas.
                genStringsDir.map { it.dir("assets") },
                genSim3dDir,
                genBulkDir,
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

// ===== A5 — ativos do pilar 3D (escala de amostra; 4K/longos sao A6) =====
tasks.register<Exec>("genShaders") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-shaders.py").absolutePath,
        "--out", genSim3dDir.get().asFile.absolutePath,
        "--seed", "20261022",
    )
}

tasks.register<Exec>("genTextures") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-textures.py").absolutePath,
        "--out", genSim3dDir.get().asFile.absolutePath,
        "--size", "256",
        "--seed", "20261022",
    )
}

tasks.register<Exec>("genMeshes") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-meshes.py").absolutePath,
        "--out", genSim3dDir.get().asFile.absolutePath,
        "--seed", "20261022",
    )
}

tasks.register<Exec>("genAudio") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-audio.py").absolutePath,
        "--out", genSim3dDir.get().asFile.absolutePath,
        "--loops", "2",
        "--loop-seconds", "15",
        "--seed", "20261022",
    )
}

// A6 — carga deterministica para o gate de tamanho (tools/gen-bulk.py).
tasks.register<Exec>("genBulk") {
    commandLine(
        "python3",
        repoRoot.resolve("tools/gen-bulk.py").absolutePath,
        "--out", genBulkDir.get().asFile.absolutePath,
        "--preset", bulkPreset,
        "--seed", "20261022",
    )
}

// Dependencia do modulo do pilar 3D (biblioteca Java pura).
// R2.2: :native e :rust entram nos DOIS flavors (a .so e minSdk 9-safe);
// :compose entra SOMENTE no modern (minSdk 21 — o classic nunca compila
// Kotlin/Compose e a lib nem participa do variant classic).
dependencies {
    implementation(project(":sim3d"))
    implementation(project(":native"))
    implementation(project(":rust"))
    add("modernImplementation", project(":compose"))
}

// preBuild e criada pelo AGP depois do evaluate; matching.configureEach
// conecta os geradores de forma lazy, sem depender do momento do registro.
tasks.matching { it.name == "preBuild" }.configureEach {
    dependsOn("genStrings", "genIcons", "genAssets", "genShaders", "genTextures", "genMeshes", "genAudio", "genBulk")
}

// A6 — decodifica o keystore de fixture (texto b64 -> PKCS12 binario em
// build/keystore/) antes de qualquer validacao de assinatura release.
val decodeKeystore = tasks.register("decodeKeystore") {
    inputs.file(keystoreSrc)
    outputs.file(keystoreOut)
    doLast {
        val out = keystoreOut.get().asFile
        out.parentFile.mkdirs()
        val decoded = Base64.getMimeDecoder().decode(keystoreSrc.asFile.readText())
        out.writeBytes(decoded)
    }
}
tasks.matching { it.name.startsWith("validateSigning") }.configureEach {
    dependsOn(decodeKeystore)
}
