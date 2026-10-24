package dev.apktester.behemoth.nativeprobe;

import java.nio.ByteBuffer;

/**
 * Fachada Java do probe nativo (R2.2 + D3: matriz JNI completa).
 *
 * A classe existe para (1) dar vinculo estatico aos simbolos JNI da
 * libnative_probe.so (o AGP so empacota a .so referenciada via
 * externalNativeBuild do modulo) e (2) permitir que o probe do app
 * exercite as chamadas de verdade (ProbeRunner/LANG-JN-001 via reflexao —
 * a deteccao nao executa nada, ADR 0003).
 *
 * D3: alem da soma historica, a matriz JNI do registry (LANG-JN-001) tem
 * wiring real: strings (GetStringUTFChars/NewStringUTF), arrays
 * (GetIntArrayRegion), direct ByteBuffer (GetDirectBufferAddress),
 * exceptions (ThrowNew -> ArithmeticException) e AttachCurrentThread
 * (pthread nativo chama {@link #echoInt} de volta via callback Java).
 *
 * O modulo :native entra SOMENTE no flavor modern (NDK 27, piso API 21) —
 * no classic a classe nao existe no classpath e o probe reporta o
 * NOT_IMPLEMENTED estruturado (honesto com o README: nativo e modern-only).
 */
public final class NativeProbe {

    static {
        // Carregamento explicito: a lib e empacotada pagina-alinhada
        // (useLegacyPackaging=false — contrato do flagship).
        System.loadLibrary("native_probe");
    }

    private NativeProbe() {
    }

    /** Soma inteira via JNI — a funcao historica do probe nativo (R2.2). */
    public static native int sum(int a, int b);

    /** D3: ida e volta de String (GetStringUTFChars + NewStringUTF). */
    public static native String stringRoundTrip(String value);

    /** D3: soma de int[] via GetIntArrayRegion (regiao 0..length). */
    public static native int intArraySum(int[] values);

    /** D3: checksum de direct ByteBuffer via GetDirectBufferAddress. */
    public static native int directBufferChecksum(ByteBuffer buffer);

    /** D3: lanca ArithmeticException via ThrowNew quando divisor == 0. */
    public static native void throwArithmeticProbe(int divisor);

    /** D3: pthread nativo + AttachCurrentThread + callback {@link #echoInt}. */
    public static native int threadEchoSum(int value);

    /** Callback Java chamado pelo thread nativo (AttachCurrentThread). */
    public static int echoInt(int value) {
        return value * 2;
    }
}
