package dev.apktester.behemoth.sim3d;

/**
 * Marching cubes do terreno do :sim3d — extracao de iso-superficie sobre
 * grade 48x48x48 (49^3 amostras, espacamento 0,15 m), inteiro Q16.
 *
 * Nota de engenharia honesta: a poligonizacao usa a decomposicao canonica
 * de cada cubo em 6 tetraedros ao longo da diagonal principal (variante
 * classica do marching cubes que resolve por construcao os casos ambiguos
 * da tabela 256 original). A superficie isovalente resultante e a mesma;
 * os triangulos sao deterministicos e independentes de tabela externa.
 *
 * Campo de densidade: soma de senos/cossenos BAM24 em 3 eixos com
 * frequencias fracionarias — suave, sem aleatoriedade de runtime.
 */
public final class MarchingCubes {

    /** Lado da grade em celulas (48^3 celulas, 49^3 amostras). */
    public static final int GRID = 48;

    /** Amostras por eixo (GRID + 1). */
    public static final int SAMPLES = GRID + 1;

    /** Espacamento da grade (0,15 m em Q16, truncado). */
    public static final int SPACING = 9830;

    /** Origem da grade centrada (−24 celulas). */
    public static final int ORIGIN = -24 * SPACING;

    /** Valor iso (0,1 em Q16). */
    public static final int ISO = 6553;

    // arestas do tetraedro (pares de indice local): 0=(v0,v1) 1=(v0,v2)
    // 2=(v0,v3) 3=(v1,v2) 4=(v1,v3) 5=(v2,v3). Tabela de 16 casos do
    // marching tetraedros (bit i do caso = canto i dentro da iso):
    // triangulos de arestas derivados analiticamente (ciclos de arestas
    // cruzadas; casos complementares compartilham o mesmo conjunto).
    private static final int[][][] TET_TRI_TABLE = {
            {},                          // 0x0
            {{0, 1, 2}},                 // 0x1: v0
            {{0, 3, 4}},                 // 0x2: v1
            {{1, 2, 4}, {1, 4, 3}},      // 0x3: v0,v1 (quad)
            {{1, 3, 5}},                 // 0x4: v2
            {{0, 2, 5}, {0, 5, 3}},      // 0x5: v0,v2 (quad)
            {{0, 1, 5}, {0, 5, 4}},      // 0x6: v1,v2 (quad)
            {{2, 4, 5}},                 // 0x7: v0,v1,v2
            {{2, 4, 5}},                 // 0x8: v3
            {{0, 1, 5}, {0, 5, 4}},      // 0x9: v0,v3 (quad)
            {{0, 2, 5}, {0, 5, 3}},      // 0xA: v1,v3 (quad)
            {{1, 3, 5}},                 // 0xB: v0,v1,v3
            {{1, 2, 4}, {1, 4, 3}},      // 0xC: v2,v3 (quad)
            {{0, 3, 4}},                 // 0xD: v0,v2,v3
            {{0, 1, 2}},                 // 0xE: v1,v2,v3
            {},                          // 0xF
    };

    private final int[] field = new int[SAMPLES * SAMPLES * SAMPLES];
    private final int[] ep = new int[3];

    // saida crescente
    private int[] verts = new int[1 << 14];
    private int vertCount;

    /** Amostra o campo em toda a grade (deterministico). */
    public void sampleField() {
        int i = 0;
        for (int z = 0; z < SAMPLES; z++) {
            int wz = ORIGIN + z * SPACING;
            for (int y = 0; y < SAMPLES; y++) {
                int wy = ORIGIN + y * SPACING;
                for (int x = 0; x < SAMPLES; x++) {
                    int wx = ORIGIN + x * SPACING;
                    field[i++] = density(wx, wy, wz);
                }
            }
        }
    }

    /** Campo de densidade (Q16) em coordenadas de mundo. */
    public int density(int x, int y, int z) {
        int sinA = Q16.sinBam24(Q16.bamOfQ16(x, 11, 100));
        int cosB = Q16.cosBam24(Q16.bamOfQ16(y, 13, 100));
        int sinC = Q16.sinBam24(Q16.bamOfQ16(z, 9, 100));
        int sinD = Q16.sinBam24(Q16.bamOfQ16(x + z, 7, 100));
        return Q16.mul(sinA, cosB) + (sinC >> 1) + (sinD >> 2);
    }

    /** Extrai a iso-superficie (chame sampleField() antes). */
    public void polygonize() {
        vertCount = 0;
        int[] cube = new int[8];
        int[] cxs = new int[8];
        int[] cys = new int[8];
        int[] czs = new int[8];
        int[] ep = new int[3];
        for (int cz = 0; cz < GRID; cz++) {
            for (int cy = 0; cy < GRID; cy++) {
                for (int cx = 0; cx < GRID; cx++) {
                    for (int c = 0; c < 8; c++) {
                        int sx = cx + (c & 1);
                        int sy = cy + ((c >> 1) & 1);
                        int sz = cz + ((c >> 2) & 1);
                        cube[c] = field[(sz * SAMPLES + sy) * SAMPLES + sx];
                        cxs[c] = ORIGIN + sx * SPACING;
                        cys[c] = ORIGIN + sy * SPACING;
                        czs[c] = ORIGIN + sz * SPACING;
                    }
                    polygonizeCube(cube, cxs, cys, czs);
                }
            }
        }
    }

    // decomposicao canonica em 6 tetraedros pela diagonal (c0, c7):
    // cantos: c=x|y<<1|z<<2
    private static final int[][] TETS = {
            {0, 1, 3, 7}, {0, 3, 2, 7}, {0, 2, 6, 7},
            {0, 6, 4, 7}, {0, 4, 5, 7}, {0, 5, 1, 7},
    };

    private void polygonizeCube(int[] cube, int[] cxs, int[] cys, int[] czs) {
        for (int t = 0; t < TETS.length; t++) {
            int[] tet = TETS[t];
            int mask = 0;
            for (int i = 0; i < 4; i++) {
                if (cube[tet[i]] >= ISO) {
                    mask |= 1 << i;
                }
            }
            int[][] tris = TET_TRI_TABLE[mask];
            for (int[] tri : tris) {
                for (int e = 0; e < 3; e++) {
                    tetEdgePoint(tet, tri[e], cube, cxs, cys, czs, ep);
                    appendVertex(ep);
                }
            }
        }
    }

    // arestas do tetraedro em pares de indice local (0..3)
    private static final int[][] TET_EDGES = {
            {0, 1}, {0, 2}, {0, 3}, {1, 2}, {1, 3}, {2, 3},
    };

    /** Ponto interpolado na aresta "e" do tetraedro (Q16). */
    private void tetEdgePoint(int[] tet, int e, int[] cube, int[] cxs,
                              int[] cys, int[] czs, int[] out) {
        int a = tet[TET_EDGES[e][0]];
        int b = tet[TET_EDGES[e][1]];
        int va = cube[a];
        int vb = cube[b];
        int t;
        if (vb == va) {
            t = Q16.HALF;
        } else {
            t = (int) (((long) (ISO - va) << 16) / (long) (vb - va));
        }
        out[0] = cxs[a] + Q16.mul(cxs[b] - cxs[a], t);
        out[1] = cys[a] + Q16.mul(cys[b] - cys[a], t);
        out[2] = czs[a] + Q16.mul(czs[b] - czs[a], t);
    }

    private void appendVertex(int[] p) {
        if (vertCount + 3 > verts.length) {
            int[] bigger = new int[verts.length * 2];
            System.arraycopy(verts, 0, bigger, 0, vertCount);
            verts = bigger;
        }
        verts[vertCount++] = p[0];
        verts[vertCount++] = p[1];
        verts[vertCount++] = p[2];
    }

    /** Dobra os vertices emitidos (x,y,z por vertice) no checksum. */
    public void foldChecksum(Fnv1a fnv) {
        for (int i = 0; i < vertCount; i++) {
            fnv.addInt(verts[i]);
        }
    }

    /** Numero de vertices emitidos (3 por triangulo). */
    public int getVertexCount() {
        return vertCount;
    }

    /** Numero de triangulos emitidos. */
    public int getTriangleCount() {
        return vertCount / 3;
    }

    /** Bounding box [minX, minY, minZ, maxX, maxY, maxZ] em Q16. */
    public int[] bbox() {
        int minX = Integer.MAX_VALUE;
        int minY = Integer.MAX_VALUE;
        int minZ = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE;
        int maxY = Integer.MIN_VALUE;
        int maxZ = Integer.MIN_VALUE;
        for (int i = 0; i + 2 < vertCount; i += 3) {
            minX = Math.min(minX, verts[i]);
            minY = Math.min(minY, verts[i + 1]);
            minZ = Math.min(minZ, verts[i + 2]);
            maxX = Math.max(maxX, verts[i]);
            maxY = Math.max(maxY, verts[i + 1]);
            maxZ = Math.max(maxZ, verts[i + 2]);
        }
        return new int[]{minX, minY, minZ, maxX, maxY, maxZ};
    }
}
