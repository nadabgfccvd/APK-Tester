//
// Modulo :app da escada sdk-ladder (dev.apktester.ladder.*).
// UM codigo-fonte, DOZE flavors: cada degrau e o mesmo app minimo com apenas
// o minSdk diferente. A fonte dos degraus e suites/sdk-ladder/rungs.properties
// (gerado por tools/gen-ladder.py) lida EM TEMPO DE CONFIGURACAO do Gradle —
// zero drift por construcao: os flavors NUNCA podem divergir do answer key
// contracts/sdk-ladder/answer-key.json, que sai da mesma RUNGS do gerador.
//
import java.util.Properties

plugins {
    id("com.android.application")
}

// Degraus da escada: rungs.properties e gerado (NAO editar a mao). Sem ele o
// configure falha cedo com instrucao explicita de regeneracao.
val rungs = Properties().apply {
    val f = rootProject.file("rungs.properties")
    require(f.isFile) { "rungs.properties ausente — gere com tools/gen-ladder.py (--out <raiz>)" }
    f.inputStream().use { load(it) }
}

// "minsdk09.minSdk=9" -> flavor "minsdk09"; ordenado para determinismo do
// configure (a ordem alfabetica dos ids de 2 digitos equivale a numerica).
val rungNames = rungs.stringPropertyNames()
    .filter { it.endsWith(".minSdk") }
    .map { it.removeSuffix(".minSdk") }
    .sorted()

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

    flavorDimensions += "rung"
    productFlavors {
        for (rungName in rungNames) {
            val rungMinSdk = rungs.getProperty("$rungName.minSdk").toInt()
            create(rungName) {
                dimension = "rung"
                minSdk = rungMinSdk
                applicationId = "dev.apktester.ladder.$rungName"
                versionCode = rungMinSdk
                versionName = "1.0.0-min$rungMinSdk"
                // Label por degrau: gerado via resValue (NAO declarar
                // rung_label em res/values/strings.xml — chocaria com isso).
                resValue("string", "rung_label", "APK Ladder minSdk $rungMinSdk")
            }
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
        // Lint integral chega no marco A8; desligado pelo mesmo motivo do
        // flagship: o codigo com guardas Build.VERSION.SDK_INT para minSdk 9
        // dispara NewApi falso positivo em APIs que so sao alcancadas quando
        // o sistema e novo.
        checkReleaseBuilds = false
        abortOnError = false
    }
}
