//
// Modulo :rust do flagship "Behemoth" (R2.2 do AUDIT_ROADMAP_V2).
//
// Minimo viavel honesto: um crate Rust REAL (librust_probe.so) compilado
// por cargo-ndk (pinnado) para os ABIs do gate, exposto ao :app via
// jniLibs gerado. A funcao unica (soma i32 via JNI) e provavel e sem
// estado — mesmo padrao do :native.
//
// O toolchain e baixado da fonte oficial no CI (rustup + cargo install
// cargo-ndk --locked, NDK via sdkmanager) — nada de binario commitado.
//
plugins {
    id("com.android.library")
}

android {
    namespace = "dev.apktester.behemoth.rustprobe"
    compileSdk = 36
    buildToolsVersion = "35.0.0"
    ndkVersion = "27.2.12479018"

    defaultConfig {
        // Piso do NDK (mesma regra do :native): o módulo entra SOMENTE no
        // flavor modern; o classic minSdk 9 permanece framework-only.
        minSdk = 21
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    sourceSets {
        getByName("main") {
            // A .so vem do cargo-ndk (task rustBuild) via jniLibs gerado —
            // o layout <out>/<abi>/librust_probe.so e o padrao do AGP.
            jniLibs.srcDir(layout.buildDirectory.dir("rust-jniLibs"))
        }
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

// cargo-ndk: build --release para os ABIs do probe, output em jniLibs.
// --locked: Cargo.lock commitado (reprodutibilidade de dependencias).
// O NDK vem do env do CI (ANDROID_NDK_HOME pinado no passo de setup).
tasks.register<Exec>("rustBuild") {
    group = "build"
    description = "Compila o crate Rust para os ABIs do gate (cargo-ndk)."
    workingDir = file("src/main/rust")
    commandLine(
        "cargo", "ndk",
        "-t", "aarch64-linux-android",
        "-t", "x86_64-linux-android",
        "-o", layout.buildDirectory.dir("rust-jniLibs").get().asFile.absolutePath,
        "build", "--release",
    )
}

// Qualquer tarefa que funda libs nativas depende do build Rust
// (mergeDebugJniLibFolders / mergeReleaseJniLibFolders /
// mergeDebugNativeLibs / mergeReleaseNativeLibs / variantes de teste).
tasks.whenTaskAdded {
    if (name.startsWith("merge") &&
        (name.contains("JniLibFolders") || name.contains("NativeLibs"))
    ) {
        dependsOn("rustBuild")
    }
}
