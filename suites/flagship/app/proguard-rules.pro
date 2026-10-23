#
# Regras R8 do flagship "Behemoth" (A6 — release "fully optimized").
#
# O R8 full mode e habilitado no build.gradle.kts (isMinifyEnabled +
# proguard-android-optimize.txt). O AGP ja mantem automaticamente todos os
# componentes declarados no AndroidManifest (activities/services/receivers/
# providers/probes) e as views/strings referenciadas estaticamente; aqui
# ficam apenas as excecoes que a analise estatica nao enxerga.
#

# JNI vincula metodos native por nome (C++ registra "Java_pacote_Classe_...").
# Hoje :sim3d/nativecompat e fallback opcional e :native entra em fase
# futura — a regra e inofensiva e preventiva para os dois casos.
-keepclasseswithmembernames class * {
    native <methods>;
}

# Bloco de compatibilidade nativa do pilar 3D: a classe e carregada por
# reflexao do JNI quando a biblioteca existe (opcional em runtime).
-keep class dev.apktester.behemoth.sim3d.nativecompat.** { *; }
