//
// Modulo :compose do flagship "Behemoth" (R2.2 do AUDIT_ROADMAP_V2).
//
// Minimo viavel honesto: UMA tela Compose real (ComposeProbeActivity),
// exibindo strings localizadas lidas de assets/locales/ (mesma fonte do
// :app — R2.3). Consumido APENAS pelo flavor modern (minSdk 26): o
// classic (minSdk 9) nao depende deste modulo (modernImplementation) e a
// build dele nunca compila Kotlin/Compose.
//
// Toolchain: kotlin-android + compose compiler baixados da fonte oficial
// (google()/mavenCentral — repos ja declarados no settings do projeto;
// FAIL_ON_PROJECT_REPOS mantem a lei de nenhum modulo com repos proprios).
//
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "dev.apktester.behemoth.composeprobe"
    compileSdk = 36
    buildToolsVersion = "35.0.0"

    defaultConfig {
        minSdk = 21
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

// Alinha o bytecode Kotlin ao compileOptions (Java 17) — sem isso o KGP
// 2.0 pode desalinhar jvmTarget (1.8) e o d8 reclama do mix.
kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    // BOM pinnado: versoes de runtime/compose alignadas sem materializar
    // cada artefato aqui (a resolucao vem do google()/mavenCentral).
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
}
