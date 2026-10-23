package dev.apktester.behemoth.sim3d;

/**
 * Checksum FNV-1a de 64 bits usado nos golden checksums do :sim3d.
 *
 * Os inteiros sao dobrados little-endian, byte a byte (mesma ordem na
 * referencia C++); o resultado vai ao contrato em hex de 16 digitos.
 * Vetor de prova: fnv1a64("a") = 0xaf63dc4c8601ec8c.
 */
public final class Fnv1a {

    /** Base do FNV-1a 64. */
    private static final long BASIS = 0xcbf29ce484222325L;

    /** Primo do FNV-1a 64. */
    private static final long PRIME = 0x100000001b3L;

    private long hash = BASIS;

    /** Reinicia o estado (reuso do objeto). */
    public void reset() {
        hash = BASIS;
    }

    /** Dobra um byte. */
    public void addByte(int b) {
        hash = (hash ^ (b & 0xFFL)) * PRIME;
    }

    /** Dobra um int em 4 bytes little-endian. */
    public void addInt(int v) {
        addByte(v);
        addByte(v >> 8);
        addByte(v >> 16);
        addByte(v >> 24);
    }

    /** Dobra um long em 8 bytes little-endian. */
    public void addLong(long v) {
        for (int i = 0; i < 8; i++) {
            addByte((int) (v >> (i * 8)));
        }
    }

    /** Estado atual. */
    public long value() {
        return hash;
    }

    /** Estado em hex de 16 digitos minusculos (com zeros a esquerda). */
    public String hex() {
        String raw = Long.toHexString(hash);
        StringBuilder sb = new StringBuilder(16);
        for (int i = raw.length(); i < 16; i++) {
            sb.append('0');
        }
        return sb.append(raw).toString();
    }
}
