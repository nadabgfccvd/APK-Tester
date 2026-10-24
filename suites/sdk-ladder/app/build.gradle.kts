//
// Modulo :app da escada sdk-ladder (dev.apktester.ladder.*).
// UM codigo-fonte, DOZE flavors: cada degrau e o mesmo app minimo com apenas
// o minSdk diferente. A fonte dos degraus e suites/sdk-ladder/rungs.properties
// (gerado por tools/gen-ladder.py) lida EM TEMPO DE CONFIGURACAO do Gradle —
// zero drift por construcao: os flavors NUNCA podem divergir do answer key
// contracts/sdk-ladder/answer-key.json, que sai da mesma RUNGS do gerador.
//
import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
}

// A9 (roadmap 6.4) — keystore de fixture commitado como texto base64
// (mesmo padrao do flagship/A6): os 12 degraus assinam com a MESMA chave em
// qualquer maquina (debug E release). Antes, os APKs da escada anexados ao
// workflow Release carregavam a assinatura do ~/.android/debug.keystore —
// variavel por host, quebrando a comparabilidade dos sha256sums entre
// rebuilds. NAO e segredo: chave de teste publica (ver keystore/README.md).
val keystoreSrc = layout.projectDirectory.file("../keystore/ladder-test.keystore.b64")
val keystoreOut = layout.buildDirectory.file("keystore/ladder-test.keystore")

// Degraus da escada: rungs.properties e gerado (NAO editar a mao). Sem ele o
// configure falha cedo com instrucao explicita de regeneracao.
val rungs = Properties().apply {
    val f = rootProject.file("rungs.properties")
    require(f.isFile) { "rungs.properties ausente — gere com tools/gen-ladder.py (--out <raiz>)" }
    f.inputStream().use { load(it) }
}

// "minsdk09.minSdk=9" -> flavor "minsdk09"; "targetsdk29.targetSdk=29" ->
// degrau do eixo targetSdk (D2). Ordenado para determinismo do configure (a
// ordem alfabetica dos ids equivale a numerica dentro de cada eixo).
val rungNames = rungs.stringPropertyNames()
    .filter { it.endsWith(".minSdk") }
    .map { it.removeSuffix(".minSdk") }
    .sorted()

// Eixo 2 (D2): degraus targetsdkNN declaram o proprio targetSdk; degraus
// minsdkNN usam o default 36 (a variavel em teste do eixo 1 e so o minSdk).
fun rungTargetSdk(name: String): Int =
    rungs.getProperty("$name.targetSdk")?.toInt() ?: 36

android {
    namespace = "dev.apktester.ladder"
    compileSdk = 36
    buildToolsVersion = "35.0.0"

    defaultConfig {
        // Defaults seguros: todo degrau real sobrescreve via flavor (o app
        // so existe em variante de flavor — a dimensao "rung" e obrigatoria).
        applicationId = "dev.apktester.ladder"
        minSdk = 26
        targetSdk = 36
        versionCode = 26
        versionName = "1.0.0-min26"
    }

    // A9 (roadmap 6.4) — keystore de fixture (detalhes em keystore/README.md)
    signingConfigs {
        create("ladderTest") {
            storeFile = keystoreOut.get().asFile
            storePassword = "ladder2026"
            keyAlias = "ladder-test"
            keyPassword = "ladder2026"
            storeType = "PKCS12"
        }
    }

    flavorDimensions += "rung"
    productFlavors {
        for (rungName in rungNames) {
            val rungMinSdk = rungs.getProperty("$rungName.minSdk").toInt()
            val rungTsSdk = rungTargetSdk(rungName)
            val isTargetAxis = rungName.startsWith("targetsdk")
            create(rungName) {
                dimension = "rung"
                minSdk = rungMinSdk
                targetSdk = rungTsSdk
                applicationId = "dev.apktester.ladder.$rungName"
                // Eixo 1: versionCode = minSdk; eixo 2 (D2): versionCode =
                // targetSdk (versionName distingue o eixo: -minNN vs -tsNN).
                versionCode = if (isTargetAxis) rungTsSdk else rungMinSdk
                versionName = if (isTargetAxis) "1.0.0-ts$rungTsSdk"
                              else "1.0.0-min$rungMinSdk"
                // Label por degrau: gerado via resValue (NAO declarar
                // rung_label em res/values/strings.xml — chocaria com isso).
                resValue(
                    "string", "rung_label",
                    if (isTargetAxis) "APK Ladder targetSdk $rungTsSdk (minSdk $rungMinSdk)"
                    else "APK Ladder minSdk $rungMinSdk"
                )
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    buildTypes {
        // A9 (roadmap 6.4): assinatura deterministica nos DOIS build types —
        // keystore de fixture decodificado do texto base64 commitado (ver
        // keystore/README.md). O debug deixa de usar ~/.android/debug.keystore
        // (variavel por host); o release ganha assinatura estavel de fixture.
        getByName("debug") {
            signingConfig = signingConfigs.getByName("ladderTest")
        }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("ladderTest")
        }
    }

    lint {
        // Lint integral chega no marco A8; desligado pelo mesmo motivo do
        // flagship: o codigo com guardas Build.VERSION.SDK_INT para minSdk 9
        // dispara NewApi falso positivo em APIs que so sao alcancadas quando
        // o sistema e novo.
        checkReleaseBuilds = false
        abortOnError = false
    }
}

// A9 (roadmap 6.4) — decodifica o keystore de fixture (texto b64 -> PKCS12
// binario em build/keystore/) antes de qualquer validacao de assinatura.
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
