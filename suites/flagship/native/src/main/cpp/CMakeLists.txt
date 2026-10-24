# R2.2 + D3 — libnative_probe.so: matriz JNI do registry (LANG-JN-001).
# build-tools/ndk sao pinnados pelos workflows; aqui nenhuma dependencia
# externa (o probe nao precisa de nada alem do NDK; pthread e bionic).
cmake_minimum_required(VERSION 3.22)
project(native_probe C)

add_library(native_probe SHARED native_probe.c)

# MinApi do modulo e 21 (piso do NDK 27); -fPIC e padrao do AGP; sem
# exceptions/RTTI (C puro). pthread faz parte da libc do bionic.
target_compile_options(native_probe PRIVATE -Wall -Wextra -Os)
