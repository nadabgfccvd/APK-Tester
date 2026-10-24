//
// Modulo :native do flagship "Behemoth" (R2.2 do AUDIT_ROADMAP_V2).
//
// Minimo viavel honesto: UMA .so real (libnative_probe.so) buildada por
// CMake/NDK pinnado com UMA funcao JNI (soma inteira — provavel, auditavel
// e sem estado). Framework Java minSdk 9; o JNI e API 1.
//
// O NDK e baixado da fonte oficial pelo CI via sdkmanager (pinado em
// ndkVersion aqui e no passo de setup dos workflows) — nada de binario
// commitado (lei do repo, ADR 0002).
//
plugins {
    id("com.android.library")
}

android {
    namespace = "dev.apktester.behemoth.nativeprobe"
    compileSdk = 36
    buildToolsVersion = "35.0.0"
    ndkVersion = "27.2.12479018"

    defaultConfig {
        // Piso do NDK 27 (CXX1110: platform 21 é o mínimo suportado). O
        // módulo entra SOMENTE no flavor modern (ver dependencies do :app) —
        // o classic minSdk 9 permanece framework-only (A1).
        minSdk = 21
        externalNativeBuild {
            cmake {
                // ABIs do gate de tamanho (size-report conta .so por
                // entrada); os dois cobrem emulador (x86_64) e device (arm64).
                abiFilters += listOf("arm64-v8a", "x86_64")
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.31.1"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}
