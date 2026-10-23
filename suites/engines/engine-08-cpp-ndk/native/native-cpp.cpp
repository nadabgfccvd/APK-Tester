// native-cpp.cpp — engine-08 (Tier A, A4): C++ do NDK com libc++.
// Compilado por <NDK>/.../{aarch64-linux-android,x86_64-linux-android}
// 26-clang++ -shared -fPIC -stdlib=libc++; libc++_shared.so do sysroot
// acompanha o APK (marcador real de STL no contrato).
#include <cstdint>
#include <string>

namespace {
constexpr char kEngine[] = "engine-08-cpp-ndk";
constexpr char kMarker[] = "apktester-native-cpp";

std::string anchor() {
    std::string s;
    s.reserve(64);
    s += kEngine;
    s += ':';
    s += kMarker;
    return s;
}
}  // namespace

extern "C" __attribute__((visibility("default")))
int32_t Java_dev_apktester_engine_engine08cpp_1ndk_probe_probe(
    void *env, void *thiz) {
    (void)env;
    (void)thiz;
    const std::string s = anchor();
    int32_t h = 20261022;
    for (unsigned char c : s) {
        h = 31 * h + static_cast<int32_t>(c);
    }
    return h;
}
