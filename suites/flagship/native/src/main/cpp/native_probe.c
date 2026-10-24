/*
 * R2.2 (AUDIT_ROADMAP_V2) — probe nativo minimo do :native.
 *
 * UMA funcao JNI (soma inteira, provavel e sem estado): o proposito e
 * ter uma .so REAL (libnative_probe.so) empacotada pelo AGP/CMake nos
 * dois flavors, para que (a) a categoria "so" do size-report contenha
 * bytes reais e (b) o rd inspect veja ELF/JNI na estrutura do flagship.
 * A deteccao NAO valida payload nem autoriza execucao (ADR 0003).
 */
#include <jni.h>

JNIEXPORT jint JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_nativeSum(
        JNIEnv *env, jclass clazz, jint a, jint b) {
    (void) env;
    (void) clazz;
    return a + b;
}
