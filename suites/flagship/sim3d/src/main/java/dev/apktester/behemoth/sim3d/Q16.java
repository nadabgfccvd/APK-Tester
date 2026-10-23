package dev.apktester.behemoth.sim3d;

/**
 * Aritmetica de ponto fixo Q16.16 somente-inteiro do motor :sim3d.
 *
 * Lei de determinismo do pilar 3D (APK_TESTER_PROMPT.md, DEFINITION OF DONE:
 * "golden checksums reproducible"): TODA a matematica da simulacao e feita em
 * inteiros (int/long) — nada de float/double nem Math.sin — para que os
 * checksums sejam identicos em qualquer JVM, arquitetura ou lingua de
 * host (a referencia C++ em src/main/cpp replica estas mesmas operacoes).
 *
 * Convencoes:
 *   Q16.16 .... 1.0 = 65536; produtos via mul() (deslocamento 16);
 *   divisao ... truncamento em direcao a zero (semantica identica em Java e C);
 *   angulos ... BAM24: 2^24 unidades = 2*pi (uma volta completa);
 *   trigonometria CORDIC (24 iteracoes, tabela atan em unidades BAM24) —
 *   erro maximo ~1.7e-4, sobreprecisao desnecessaria para checksum.
 */
public final class Q16 {

    /** 1.0 em Q16.16. */
    public static final int ONE = 65536;

    /** 0.5 em Q16.16. */
    public static final int HALF = 32768;

    /** Constante de ganho do CORDIC (0.607252935 * 2^16, truncado). */
    private static final int CORDIC_K = 39797;

    /** atan(2^-i) em unidades BAM24 (2^24 = 2*pi), i = 0..23. */
    private static final int[] ATAN_BAM24 = {
            2097152, 1238021, 654136, 332050, 166669, 83416, 41718,
            20860, 10430, 5215, 2608, 1304, 652, 326, 163, 81,
            41, 20, 10, 5, 3, 1, 1, 0,
    };

    /** Raspa reutilizada (motor single-thread por design; evita alocacao). */
    private static final int[] SCRATCH = new int[2];

    private Q16() {
    }

    /** Produto Q16 (a*b) com deslocamento de 16 bits (acumula em long). */
    public static int mul(int a, int b) {
        return (int) (((long) a * (long) b) >> 16);
    }

    /** (a*b)/c em long — truncamento identico em Java e C. */
    public static int mulDiv(int a, int b, int c) {
        return (int) (((long) a * (long) b) / (long) c);
    }

    /** Divisao Q16 a/b. */
    public static int div(int a, int b) {
        return (int) (((long) a << 16) / (long) b);
    }

    /** floorDiv inteiro (piso, p/ indices de lattice com negativos). */
    public static int floorDiv(int a, int b) {
        int q = a / b;
        if ((a % b != 0) && ((a < 0) != (b < 0))) {
            q--;
        }
        return q;
    }

    /**
     * Raiz quadrada Q16 por isqrt bit a bit (sem ponto flutuante):
     * out = isqrt(a &lt;&lt; 16), pois sqrt(v)*2^16 = sqrt(a*2^16).
     */
    public static int sqrtQ16(int a) {
        if (a <= 0) {
            return 0;
        }
        long n = (long) a << 16;
        long x = n;
        long res = 0;
        long bit = 1L << 62;
        while (bit > n) {
            bit >>= 2;
        }
        while (bit != 0) {
            if (x >= res + bit) {
                x -= res + bit;
                res = (res >> 1) + bit;
            } else {
                res >>= 1;
            }
            bit >>= 2;
        }
        return (int) res;
    }

    /**
     * CORDIC em modo rotacao: preenche out[0]=sin, out[1]=cos (Q16) do
     * angulo BAM24 (modulo 2^24). Reducao de quadrante para [0, pi/2)
     * antes das 24 iteracoes (convergencia garantida).
     */
    public static void sinCosBam24(int bam, int[] out) {
        int b = bam & 0xFFFFFF;
        int q = (b >> 22) & 3;
        int a = b & 0x3FFFFF;
        int x = CORDIC_K;
        int y = 0;
        for (int i = 0; i < 24; i++) {
            if (a >= 0) {
                int xn = x - (y >> i);
                int yn = y + (x >> i);
                x = xn;
                y = yn;
                a -= ATAN_BAM24[i];
            } else {
                int xn = x + (y >> i);
                int yn = y - (x >> i);
                x = xn;
                y = yn;
                a += ATAN_BAM24[i];
            }
        }
        int s;
        int c;
        if (q == 0) {
            s = y;
            c = x;
        } else if (q == 1) {
            s = x;
            c = -y;
        } else if (q == 2) {
            s = -y;
            c = -x;
        } else {
            s = -x;
            c = y;
        }
        out[0] = s;
        out[1] = c;
    }

    /** Seno (Q16) de angulo BAM24. */
    public static int sinBam24(int bam) {
        sinCosBam24(bam, SCRATCH);
        return SCRATCH[0];
    }

    /** Cosseno (Q16) de angulo BAM24. */
    public static int cosBam24(int bam) {
        sinCosBam24(bam, SCRATCH);
        return SCRATCH[1];
    }

    /**
     * Converte coordenada Q16 (metros) em angulo BAM24 com frequencia
     * fracionaria de ciclos/metro dada por (num/den) — tudo em long:
     * bam = x * num * 2^24 / (den * 2^16) = x * num * 256 / den.
     */
    public static int bamOfQ16(int x, int num, int den) {
        return (int) (((long) x * (long) num * 256L) / (long) den);
    }

    /** Smoothstep Q16 sobre t em [0, ONE): 3t^2 - 2t^3. */
    public static int smoothstep(int t) {
        int t2 = mul(t, t);
        return mul(t2, 3 * ONE - 2 * t);
    }

    /** Lerp Q16: a + (b-a)*s (s em Q16). */
    public static int lerp(int a, int b, int s) {
        return a + mul(b - a, s);
    }
}
