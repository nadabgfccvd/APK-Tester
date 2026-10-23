# CMakeLists.txt do fallback nativo do :sim3d (fase A6 — modulo :native
# com externalNativeBuild). No CI da fase A5 a paridade e provada por
# compilacao host direta (cc -shared -fPIC) — ver job flagship-3d.
cmake_minimum_required(VERSION 3.22)
project(sim3d_native CXX)

add_library(sim3d_native SHARED sim3d_native.cpp)
target_compile_features(sim3d_native PRIVATE cxx_std_14)
target_compile_options(sim3d_native PRIVATE -O2 -fno-fast-math -fwrapv)
