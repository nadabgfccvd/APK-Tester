package dev.apktester.behemoth.sim3d;

/**
 * Rasterizador de software do :sim3d — triangulos texturizados com
 * correcao de perspectiva e z-buffer, 100% aritmetica inteira Q16.
 *
 * Pipeline por triangulo (lei do golden, ordem fixa):
 *   1. amostragem deterministica de triangulos da malha 1M (stride fixo,
 *      inicio deslocado por frame — cobre a malha inteira em 4 frames);
 *   2. rotacao do modelo em Y (BAM24) + translacao da camera fixa;
 *   3. rejeicao por plano proximo (qualquer vertice com z <= NEAR);
 *   4. projecao em tela + interpolantes perspectiva-corretos
 *      (1/z, u/z, v/z interpolados linearmente em tela; u = (u/z)*z);
 *   5. backface cull por area com sinal (area <= 0 = descartado);
 *   6. varredura do bounding box com barycentricas inteiras (w0/w1/w2)
 *      e teste-e-escrita no z-buffer (menor z = mais perto).
 *
 * Camera fixa em (0, 2 m, -9 m) olhando para +z; o modelo gira.
 */
public final class Rasterizer {

    /** Plano proximo (0.5 m em Q16). */
    public static final int NEAR = Q16.HALF;

    /** Posicao da camera em Y (2 m). */
    private static final int CAM_Y = 2 * Q16.ONE;

    /** Distancia da camera ao plano z=0 (9 m). */
    private static final int CAM_DIST = 9 * Q16.ONE;

    /** Focal em Q16: (160 px) / tan(30 graus) = 277.128 px. */
    private static final int FOCAL = 18163395;

    private final Framebuffer fb;
    private final TextureQ16 texture;

    /** Stride de celulas da grade para triangulos macro (16 -> 25 cm). */
    public static final int MACRO_STRIDE = 16;

    // estatisticas do frame corrente
    private int trianglesSubmitted;
    private int trianglesNearRejected;
    private int trianglesBackfaceCulled;
    private int trianglesDrawn;

    private final int[] worldTri = new int[15];
    private final int[] viewTri = new int[15];

    public Rasterizer(Framebuffer fb, TextureQ16 texture) {
        this.fb = fb;
        this.texture = texture;
    }

    /** Contadores zerados no inicio de cada frame (apos fb.clear()). */
    public void beginFrame() {
        trianglesSubmitted = 0;
        trianglesNearRejected = 0;
        trianglesBackfaceCulled = 0;
        trianglesDrawn = 0;
    }

    /**
     * Frame completo: limpa o framebuffer, amostra "count" triangulos
     * macro (stride 16 da grade — celula efetiva de 25 cm; celulas
     * unitarias sao sub-pixel a 9 m) com passo fixo e inicio girando por
     * frame, aplica rotacao BAM24 "bamYaw" e rasteriza.
     */
    public void drawFrameSubset(Mesh1M mesh, int frame, int bamYaw, int count) {
        fb.clear();
        beginFrame();
        int macroSide = Mesh1M.GRID / MACRO_STRIDE;
        int macroTris = 2 * (macroSide - 1) * (macroSide - 1);
        int step = macroTris / count;
        int first = (int) (((long) frame * macroTris) / 4 % macroTris);
        int[] s = new int[2];
        Q16.sinCosBam24(bamYaw, s);
        int c = s[1];
        int sn = s[0];
        for (int k = 0; k < count; k++) {
            int idx = (first + k * step) % macroTris;
            mesh.macroTriangle(idx, MACRO_STRIDE, worldTri);
            for (int i = 0; i < 3; i++) {
                int wx = worldTri[i * 5];
                int wy = worldTri[i * 5 + 1];
                int wz = worldTri[i * 5 + 2];
                int rx = Q16.mul(wx, c) - Q16.mul(wz, sn);
                int rz = Q16.mul(wx, sn) + Q16.mul(wz, c);
                viewTri[i * 5] = rx;
                viewTri[i * 5 + 1] = wy;
                viewTri[i * 5 + 2] = rz;
                viewTri[i * 5 + 3] = worldTri[i * 5 + 3];
                viewTri[i * 5 + 4] = worldTri[i * 5 + 4];
            }
            rasterizeViewTriangle(viewTri);
        }
    }

    /** Projeta e rasteriza um triangulo ja em espaco de camera. */
    private void rasterizeViewTriangle(int[] v) {
        trianglesSubmitted++;
        int w = fb.getWidth();
        int h = fb.getHeight();
        int halfW = w / 2;
        int halfH = h / 2;
        int[] X = new int[3];
        int[] Y = new int[3];
        int[] izq = new int[3];
        int[] uzq = new int[3];
        int[] vzq = new int[3];
        for (int i = 0; i < 3; i++) {
            int vx = v[i * 5];
            int vy = v[i * 5 + 1] - CAM_Y;
            int vz = v[i * 5 + 2] + CAM_DIST;
            if (vz <= NEAR) {
                trianglesNearRejected++;
                return;
            }
            long sx = (((long) vx * FOCAL) >> 16) / vz;
            long sy = (((long) vy * FOCAL) >> 16) / vz;
            // (vx*FOCAL)>>16 = pixels em Q16; / vz (Q16) cancela a escala ->
            // resultado JA e pixels crus (inteiros)
            X[i] = halfW + (int) sx;
            Y[i] = halfH - (int) sy;
            izq[i] = (int) ((1L << 32) / vz);                       // 1/z (Q16)
            uzq[i] = (int) (((long) v[i * 5 + 3] << 16) / vz);      // u/z (Q16)
            vzq[i] = (int) (((long) v[i * 5 + 4] << 16) / vz);      // v/z (Q16)
        }
        int area = (X[1] - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (Y[1] - Y[0]);
        if (area <= 0) {
            trianglesBackfaceCulled++;
            return;
        }
        int minX = Math.max(0, Math.min(X[0], Math.min(X[1], X[2])));
        int maxX = Math.min(w - 1, Math.max(X[0], Math.max(X[1], X[2])));
        int minY = Math.max(0, Math.min(Y[0], Math.min(Y[1], Y[2])));
        int maxY = Math.min(h - 1, Math.max(Y[0], Math.max(Y[1], Y[2])));
        if (minX > maxX || minY > maxY) {
            trianglesBackfaceCulled++;
            return;
        }
        for (int y = minY; y <= maxY; y++) {
            for (int x = minX; x <= maxX; x++) {
                int w0 = (X[2] - X[1]) * (y - Y[1]) - (Y[2] - Y[1]) * (x - X[1]);
                int w1 = (X[0] - X[2]) * (y - Y[2]) - (Y[0] - Y[2]) * (x - X[2]);
                int w2 = (X[1] - X[0]) * (y - Y[0]) - (Y[1] - Y[0]) * (x - X[0]);
                if (w0 < 0 || w1 < 0 || w2 < 0) {
                    continue;
                }
                long izSum = (long) w0 * izq[0] + (long) w1 * izq[1] + (long) w2 * izq[2];
                long uzSum = (long) w0 * uzq[0] + (long) w1 * uzq[1] + (long) w2 * uzq[2];
                long vzzSum = (long) w0 * vzq[0] + (long) w1 * vzq[1] + (long) w2 * vzq[2];
                if (izSum <= 0) {
                    continue;
                }
                // 1/z em Q16 = izSum/(area*65536)  =>  z = 65536^2 * area / izSum
                int z = (int) (((1L << 32) * (long) area) / izSum);
                int u = (int) (((uzSum / area) * (long) z) >> 16); // u = (u/z)*z
                int vv = (int) (((vzzSum / area) * (long) z) >> 16);
                int texel = texture.sample(u, vv);
                fb.plot(x, y, z, texel);
            }
        }
        trianglesDrawn++;
    }

    public int getTrianglesSubmitted() {
        return trianglesSubmitted;
    }

    public int getTrianglesNearRejected() {
        return trianglesNearRejected;
    }

    public int getTrianglesBackfaceCulled() {
        return trianglesBackfaceCulled;
    }

    public int getTrianglesDrawn() {
        return trianglesDrawn;
    }

    public int getPixelsDrawn() {
        return fb.getPixelsDrawn();
    }
}
