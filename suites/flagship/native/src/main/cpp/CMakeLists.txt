# R2.2 (AUDIT_ROADMAP_V2) — libnative_probe.so: UMA funcao JNI, sem estado.
# build-tools/ndk sao pinnados pelos workflows; aqui nenhuma dependencia
# externa (o probe nao precisa de nada alem do NDK).
cmake_minimum_required(VERSION 3.22)
project(native_probe C)

add_library(native_probe SHARED native_probe.c)

# MinApi 9: -fPIC e padrao do AGP; sem exceptions/RTTI (C puro).
target_compile_options(native_probe PRIVATE -Wall -Wextra -Os)
