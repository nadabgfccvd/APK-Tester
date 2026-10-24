/*
 * R2.2 + D3 — probe nativo do :native com a matriz JNI do registry
 * (LANG-JN-001): soma, strings, arrays, direct ByteBuffer, exceptions
 * (ThrowNew) e AttachCurrentThread (pthread nativo chama o callback Java
 * NativeProbe.echoInt via GetStaticMethodID/CallStaticIntMethod).
 *
 * O proposito e ter uma .so REAL (libnative_probe.so) empacotada pelo
 * AGP/CMake nos dois flavors, para que (a) a categoria "so" do size-report
 * contenha bytes reais, (b) o rd inspect veja ELF/JNI na estrutura do
 * flagship e (c) o probe LANG-JN-001 exercite a matriz JNI de verdade
 * (ProbeRunner, via reflexao — a deteccao nao executa nada, ADR 0003).
 *
 * Correcao D3: o simbolo da soma historica era
 * Java_..._NativeProbe_nativeSum enquanto o Java declara sum(...) —
 * UnsatisfiedLinkError garantido na primeira chamada. O simbolo agora
 * casa com a declaracao Java (verificado pela matriz em runtime).
 */
#include <jni.h>
#include <pthread.h>

/* JavaVM cacheada em JNI_OnLoad para o AttachCurrentThread da matriz. */
static JavaVM *g_vm = NULL;

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    (void) reserved;
    g_vm = vm;
    return JNI_VERSION_1_6;
}

JNIEXPORT jint JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_sum(
        JNIEnv *env, jclass clazz, jint a, jint b) {
    (void) env;
    (void) clazz;
    return a + b;
}

JNIEXPORT jstring JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_stringRoundTrip(
        JNIEnv *env, jclass clazz, jstring value) {
    (void) clazz;
    if (value == NULL) {
        return NULL;
    }
    const char *utf = (*env)->GetStringUTFChars(env, value, NULL);
    if (utf == NULL) {
        return NULL; /* OutOfMemoryError ja pendente pela JVM. */
    }
    jstring echoed = (*env)->NewStringUTF(env, utf);
    (*env)->ReleaseStringUTFChars(env, value, utf);
    return echoed;
}

JNIEXPORT jint JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_intArraySum(
        JNIEnv *env, jclass clazz, jintArray values) {
    (void) clazz;
    if (values == NULL) {
        return 0;
    }
    jsize length = (*env)->GetArrayLength(env, values);
    jint *body = (*env)->GetIntArrayElements(env, values, NULL);
    if (body == NULL) {
        return 0;
    }
    jint total = 0;
    for (jsize i = 0; i < length; i++) {
        total += body[i];
    }
    (*env)->ReleaseIntArrayElements(env, values, body, JNI_ABORT);
    return total;
}

JNIEXPORT jint JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_directBufferChecksum(
        JNIEnv *env, jclass clazz, jobject buffer) {
    (void) clazz;
    if (buffer == NULL) {
        return 0;
    }
    jbyte *base = (*env)->GetDirectBufferAddress(env, buffer);
    jlong capacity = (*env)->GetDirectBufferCapacity(env, buffer);
    if (base == NULL || capacity <= 0) {
        return 0;
    }
    jint total = 0;
    for (jlong i = 0; i < capacity; i++) {
        total += (jint) base[i];
    }
    return total;
}

JNIEXPORT void JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_throwArithmeticProbe(
        JNIEnv *env, jclass clazz, jint divisor) {
    (void) clazz;
    jclass arithmetic = (*env)->FindClass(env, "java/lang/ArithmeticException");
    if (arithmetic == NULL) {
        return; /* ClassNotFoundException pendente. */
    }
    if (divisor == 0) {
        (*env)->ThrowNew(env, arithmetic, "maxprobe: divisao por zero (D3)");
        return;
    }
    (void) divisor;
}

/* Corpo do thread nativo: anexa-se a JVM, chama echoInt(value) e desanexa. */
typedef struct ThreadArgs {
    jint value;
    jint result;
} ThreadArgs;

static void *thread_body(void *arg) {
    ThreadArgs *args = (ThreadArgs *) arg;
    JNIEnv *env = NULL;
    args->result = 0;
    if (g_vm == NULL) {
        return NULL;
    }
    if ((*g_vm)->AttachCurrentThread(g_vm, &env, NULL) != JNI_OK) {
        return NULL;
    }
    jclass clazz = (*env)->FindClass(env,
            "dev/apktester/behemoth/nativeprobe/NativeProbe");
    if (clazz != NULL) {
        jmethodID echo = (*env)->GetStaticMethodID(env, clazz, "echoInt",
                "(I)I");
        if (echo != NULL) {
            args->result = (*env)->CallStaticIntMethod(env, clazz, echo,
                    args->value);
        }
    }
    (*g_vm)->DetachCurrentThread(g_vm);
    return NULL;
}

JNIEXPORT jint JNICALL
Java_dev_apktester_behemoth_nativeprobe_NativeProbe_threadEchoSum(
        JNIEnv *env, jclass clazz, jint value) {
    (void) env;
    (void) clazz;
    ThreadArgs args;
    args.value = value;
    args.result = 0;
    pthread_t thread;
    int created = pthread_create(&thread, NULL, thread_body, &args);
    if (created != 0) {
        return 0; /* AttachCurrentThread improvavel sem thread; 0 e sinal. */
    }
    pthread_join(thread, NULL);
    return args.result;
}
