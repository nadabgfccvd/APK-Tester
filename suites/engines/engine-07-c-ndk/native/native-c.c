/* native-c.c — engine-07 (Tier A, A4): C puro do NDK, sem STL.
 * Exporta um símbolo JNI Java_* real (nome válido para o pacote do APK)
 * e strings de ancoragem no ELF. Compilado por
 * <NDK>/toolchains/llvm/prebuilt/linux-x86_64/bin/{aarch64-linux-android,
 * x86_64-linux-android}26-clang -shared -fPIC. */
#include <stdint.h>

#define APKTESTER_ENGINE "engine-07-c-ndk"
#define APKTESTER_MARKER "apktester-native-c"

__attribute__((visibility("default")))
int32_t Java_dev_apktester_engine_engine07c_1ndk_probe_probe(
    void *env, void *thiz) {
    (void)env;
    (void)thiz;
    const char *marker = APKTESTER_MARKER;
    const char *engine = APKTESTER_ENGINE;
    int32_t h = 20261022;
    while (*marker) {
        h = 31 * h + *marker++;
    }
    while (*engine) {
        h = 31 * h + *engine++;
    }
    return h;
}
