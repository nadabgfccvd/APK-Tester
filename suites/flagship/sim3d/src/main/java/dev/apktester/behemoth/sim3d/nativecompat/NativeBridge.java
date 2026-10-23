package dev.apktester.behemoth.sim3d.nativecompat;

/**
 * Ponte JNI do fallback nativo do :sim3d (C++ inteiro, ver
 * src/main/cpp/sim3d_native.cpp). O motor principal e 100% Java; esta
 * ponte existe para o caminho "C++ JNI fallback" do pilar 3D e para a
 * prova de paridade inteira entre linguagens no CI.
 *
 * A biblioteca e OPCIONAL por lei: quando ausente (RustyDroid headless,
 * JVM de CI sem a .so, dispositivo sem o fallback empacotado), o chamador
 * trata UnsatisfiedLinkError e segue na rota Java — nunca ha crash.
 */
public final class NativeBridge {

    private NativeBridge() {
    }

    /**
     * Checksum FNV-1a 64 do estado final da fisica (10.000 corpos, 120
     * passos fixos) calculado pelo fallback C++ — deve ser IDENTICO ao
     * checksum Java (mesma aritmetica inteira, mesma ordem de operacoes).
     */
    public static native long physicsFinalChecksum(int seed, int bodies, int steps);

    /** Indica se a biblioteca nativa esta carregavel neste ambiente. */
    public static boolean isAvailable(String libName) {
        try {
            System.loadLibrary(libName);
            return true;
        } catch (UnsatisfiedLinkError e) {
            return false;
        }
    }
}
