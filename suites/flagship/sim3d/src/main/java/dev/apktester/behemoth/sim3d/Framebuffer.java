package dev.apktester.behemoth.sim3d;

/**
 * Framebuffer do rasterizador por software: cor RGB565 empacotada em int[]
 * + z-buffer Q16 (menor = mais perto). Checksum FNV-1a 64 sobre a cor,
 * pixel a pixel, linha a linha (ordem fixa — lei do golden).
 */
public final class Framebuffer {

    private final int width;
    private final int height;
    private final int[] color;
    private final int[] depth;

    private int pixelsDrawn;

    public Framebuffer(int width, int height) {
        this.width = width;
        this.height = height;
        this.color = new int[width * height];
        this.depth = new int[width * height];
    }

    /** Limpa cor e z (z = mais distante possivel: Integer.MAX_VALUE). */
    public void clear() {
        java.util.Arrays.fill(color, 0);
        java.util.Arrays.fill(depth, Integer.MAX_VALUE);
        pixelsDrawn = 0;
    }

    /** Teste-e-atualiza de um pixel (retorna true se gravou). */
    public boolean plot(int x, int y, int z, int rgb565) {
        if (x < 0 || y < 0 || x >= width || y >= height) {
            return false;
        }
        int idx = y * width + x;
        if (z < depth[idx]) {
            depth[idx] = z;
            color[idx] = rgb565;
            pixelsDrawn++;
            return true;
        }
        return false;
    }

    /** Dobra a cor de todos os pixels no checksum (ordem de linha). */
    public void foldColor(Fnv1a fnv) {
        for (int i = 0; i < color.length; i++) {
            fnv.addInt(color[i]);
        }
    }

    public int getWidth() {
        return width;
    }

    public int getHeight() {
        return height;
    }

    public int getPixelsDrawn() {
        return pixelsDrawn;
    }
}
