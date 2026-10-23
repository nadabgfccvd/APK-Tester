package dev.apktester.behemoth.sim3d;

/**
 * Textura procedural 64x64 em RGB565 (xadrez 8x8 + grao de hash inteiro),
 * amostrada pelo rasterizador com wrap por mascara — sem ponto flutuante.
 */
public final class TextureQ16 {

    /** Lado da textura (64x64 texels). */
    public static final int SIZE = 64;

    private final int[] texels = new int[SIZE * SIZE];

    /** Gera o padrao deterministico (xadrez alternado + ruido de hash). */
    public void generate() {
        for (int ty = 0; ty < SIZE; ty++) {
            for (int tx = 0; tx < SIZE; tx++) {
                int checker = ((tx >> 3) + (ty >> 3)) & 1;
                int n = latticeHash(tx, ty) & 31;
                int r = clamp5((checker != 0 ? 20 : 8) + (n >> 2));
                int g = clamp6((checker != 0 ? 46 : 22) + (n >> 1));
                int b = clamp5((checker != 0 ? 18 : 34) + (n >> 2));
                texels[ty * SIZE + tx] = (r << 11) | (g << 5) | b;
            }
        }
    }

    /** Amostra com wrap (u,v em Q16; tiling a cada 1.0 = 64 texels). */
    public int sample(int u, int v) {
        int tx = (u >> 10) & (SIZE - 1);
        int ty = (v >> 10) & (SIZE - 1);
        return texels[ty * SIZE + tx];
    }

    private static int clamp5(int v) {
        return v < 0 ? 0 : (v > 31 ? 31 : v);
    }

    private static int clamp6(int v) {
        return v < 0 ? 0 : (v > 63 ? 63 : v);
    }

    private static int latticeHash(int x, int y) {
        long h = (long) x * 374761393L + (long) y * 668265263L;
        h = (h ^ (h >>> 13)) * 1274126177L;
        return (int) ((h ^ (h >>> 16)) & 0x7FFFFFFFL);
    }
}
