//
// Modulo :sim3d do flagship "Behemoth" — pilar 3D headless (fase A5).
//
// Biblioteca Java PURA (java-library, zero dependencias, zero android.*):
// rasterizador de software, fisica de 10k corpos, 100k particulas,
// marching cubes e esqueleto — tudo em Q16.16 somente-inteiro para que
// os golden checksums (contracts/flagship/sim3d-golden.json) sejam
// reproduziveis byte a byte em qualquer JVM/arquitetura (e paraveis com
// o fallback C++ em src/main/cpp).
//
// Roda no JVM do CI (JavaExec), no APK (:app depende deste modulo) e,
 // por extensao, sob o RustyDroid (java.lang/java.util apenas).
//
plugins {
    `java-library`
}

java {
    sourceCompatibility = JavaVersion.VERSION_11
    targetCompatibility = JavaVersion.VERSION_11
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

// Contrato golden: suites/flagship -> raiz do repositorio.
val goldenContract = rootDir.parentFile
    .resolve("contracts/flagship/sim3d-golden.json")

tasks.register<JavaExec>("goldenWrite") {
    group = "verification"
    description = "Reexecuta o pilar 3D e grava o golden JSON (contrato)."
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("dev.apktester.behemoth.sim3d.Sim3dGolden")
    jvmArgs("-Xmx1g")
    args("--write", goldenContract.absolutePath)
}

tasks.register<JavaExec>("goldenVerify") {
    group = "verification"
    description = "Reexecuta o pilar 3D e compara byte a byte com o golden commitado."
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("dev.apktester.behemoth.sim3d.Sim3dGolden")
    jvmArgs("-Xmx1g")
    args("--verify", goldenContract.absolutePath)
}

tasks.register<JavaExec>("goldenSelftest") {
    group = "verification"
    description = "Assercoes internas de sanidade do motor (Q16, FNV, xorshift, raster, MC)."
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("dev.apktester.behemoth.sim3d.Sim3dGolden")
    jvmArgs("-Xmx1g")
    args("--selftest")
}
