package dev.apktester.behemoth.sim3d;

/**
 * Matriz 4x4 em Q16.16 (row-major, m[linha*4+coluna]) para a cinematica
 * forward do esqueleto. Somente-inteiro: produtos acumulam em long antes
 * do deslocamento de 16 bits (overflow auditado: entradas de rotacao sao
 * +/-65536, translações ~2e5 — soma maxima ~2e10, cabe em long).
 */
public final class Mat4 {

    private final int[] m = new int[16];

    /** Cria matriz identidade. */
    public Mat4() {
        identity();
    }

    /** Restaura a identidade. */
    public void identity() {
        java.util.Arrays.fill(m, 0);
        m[0] = Q16.ONE;
        m[5] = Q16.ONE;
        m[10] = Q16.ONE;
        m[15] = Q16.ONE;
    }

    /** Copia de outra matriz. */
    public void set(Mat4 other) {
        System.arraycopy(other.m, 0, m, 0, 16);
    }

    /** this = this * other (ordem: aplica other depois). */
    public void mul(Mat4 other) {
        int[] b = other.m;
        int[] out = new int[16];
        for (int r = 0; r < 4; r++) {
            for (int c = 0; c < 4; c++) {
                long sum = 0;
                for (int k = 0; k < 4; k++) {
                    sum += (long) m[r * 4 + k] * (long) b[k * 4 + c];
                }
                out[r * 4 + c] = (int) (sum >> 16);
            }
        }
        System.arraycopy(out, 0, m, 0, 16);
    }

    /** this = this * T — translacao no espaco local corrente. */
    public void translate(int tx, int ty, int tz) {
        m[12] += Q16.mul(m[0], tx) + Q16.mul(m[1], ty) + Q16.mul(m[2], tz);
        m[13] += Q16.mul(m[4], tx) + Q16.mul(m[5], ty) + Q16.mul(m[6], tz);
        m[14] += Q16.mul(m[8], tx) + Q16.mul(m[9], ty) + Q16.mul(m[10], tz);
    }

    /** Multiplica pela rotacao X (angulo BAM24): this = this * Rx. */
    public void rotateXBam24(int bam) {
        Mat4 r = new Mat4();
        int[] s = new int[2];
        Q16.sinCosBam24(bam, s);
        r.m[5] = s[1];
        r.m[6] = -s[0];
        r.m[9] = s[0];
        r.m[10] = s[1];
        mul(r);
    }

    /** Multiplica pela rotacao Y (angulo BAM24). */
    public void rotateYBam24(int bam) {
        Mat4 r = new Mat4();
        int[] s = new int[2];
        Q16.sinCosBam24(bam, s);
        r.m[0] = s[1];
        r.m[2] = s[0];
        r.m[8] = -s[0];
        r.m[10] = s[1];
        mul(r);
    }

    /** Multiplica pela rotacao Z (angulo BAM24). */
    public void rotateZBam24(int bam) {
        Mat4 r = new Mat4();
        int[] s = new int[2];
        Q16.sinCosBam24(bam, s);
        r.m[0] = s[1];
        r.m[1] = -s[0];
        r.m[4] = s[0];
        r.m[5] = s[1];
        mul(r);
    }

    /** Transforma ponto (Q16) pela matriz (w=1 implicito). */
    public void transformPoint(int[] p) {
        int x = p[0];
        int y = p[1];
        int z = p[2];
        p[0] = Q16.mul(m[0], x) + Q16.mul(m[1], y) + Q16.mul(m[2], z) + m[12];
        p[1] = Q16.mul(m[4], x) + Q16.mul(m[5], y) + Q16.mul(m[6], z) + m[13];
        p[2] = Q16.mul(m[8], x) + Q16.mul(m[9], y) + Q16.mul(m[10], z) + m[14];
    }
}
