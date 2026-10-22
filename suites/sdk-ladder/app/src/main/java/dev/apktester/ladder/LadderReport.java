package dev.apktester.ladder;

import android.util.Log;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.util.Locale;

/**
 * Persistencia do relatorio do degrau (ladder-report.json): monta o JSON a
 * mao com StringBuilder e escape proprio (sem org.json, que e API 11+, e sem
 * dependencias) e grava com escrita tudo-ou-nada — arquivo ".tmp" e depois
 * renameTo — no mesmo padrao do ProbeReporter do flagship.
 *
 * Nenhuma API aqui exige mais que minSdk 9: java.io puro com nome de charset
 * "UTF-8" (StandardCharsets so existe a partir da API 19), sem
 * try-with-resources (AutoCloseable e API 19+) e String.format sempre com
 * Locale.US (digitos estaveis independente de locale do sistema).
 */
public final class LadderReport {

    /** Tag base dos logs internos do report. */
    private static final String TAG = "LADDER";

    /** Nome do relatorio JSON gravado no diretorio de arquivos do app. */
    public static final String REPORT_FILE = "ladder-report.json";

    private LadderReport() {
    }

    /**
     * Escapa aspas, barra invertida e caracteres de controle para JSON;
     * caracteres abaixo de 0x20 viram \u%04x com Locale.US. null vira "".
     */
    public static String escape(String value) {
        if (value == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(value.length() + 16);
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '\\':
                    sb.append("\\\\");
                    break;
                case '"':
                    sb.append("\\\"");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format(Locale.US, "\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    /** Acrescenta o par "chave":"valor-texto" (valor escapado). */
    public static void appendKeyValue(StringBuilder sb, String key, String value) {
        sb.append('"').append(escape(key)).append("\":\"")
                .append(escape(value)).append('"');
    }

    /** Acrescenta o par "chave":numero. */
    public static void appendKeyValue(StringBuilder sb, String key, int value) {
        sb.append('"').append(escape(key)).append("\":").append(value);
    }

    /** Acrescenta o par "chave":["a","b", ...] (array de strings). */
    public static void appendStringArray(StringBuilder sb, String key,
            String[] values) {
        sb.append('"').append(escape(key)).append("\":[");
        for (int i = 0; i < values.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append('"').append(escape(values[i])).append('"');
        }
        sb.append(']');
    }

    /**
     * Monta o JSON do relatorio do degrau. Sem timestamps: o conteudo
     * depende apenas de fatos do pacote e do asset gerado (determinismo do
     * repositorio — nenhum campo depende de hora ou estado global).
     */
    public static String buildReport(String applicationId, int versionCode,
            String versionName, int minSdkDeclared, int sdkInt, int targetSdk,
            String[] components, String rustydroidExpectation) {
        StringBuilder sb = new StringBuilder(256);
        sb.append("{\n");
        appendKeyValue(sb, "application_id", applicationId);
        sb.append(",\n");
        appendKeyValue(sb, "version_code", versionCode);
        sb.append(",\n");
        appendKeyValue(sb, "version_name", versionName);
        sb.append(",\n");
        appendKeyValue(sb, "min_sdk_declared", minSdkDeclared);
        sb.append(",\n");
        appendKeyValue(sb, "sdk_int", sdkInt);
        sb.append(",\n");
        appendKeyValue(sb, "target_sdk", targetSdk);
        sb.append(",\n");
        appendStringArray(sb, "components", components);
        sb.append(",\n");
        appendKeyValue(sb, "rustydroid_expectation", rustydroidExpectation);
        sb.append("\n}\n");
        return sb.toString();
    }

    /**
     * Escrita tudo-ou-nada: grava "&lt;name&gt;.tmp" no diretorio, remove o
     * destino anterior e renomeia o temporario por cima. Devolve true quando
     * o arquivo final esta no lugar; qualquer falha e logada e devolve false
     * (lei de erro estruturado, nunca crash).
     */
    public static boolean writeFile(File dir, String name, String content) {
        File tmp = null;
        try {
            File target = new File(dir, name);
            tmp = new File(dir, name + ".tmp");
            Writer writer = new OutputStreamWriter(new FileOutputStream(tmp),
                    "UTF-8");
            try {
                writer.write(content);
                writer.flush();
            } finally {
                writer.close();
            }
            if (target.exists() && !target.delete()) {
                throw new IOException("nao removeu o destino anterior");
            }
            if (!tmp.renameTo(target)) {
                throw new IOException("nao renomeou o temporario");
            }
            return true;
        } catch (Exception e) {
            Log.w(TAG, "gravacao de " + name + " falhou: " + e.getMessage());
            if (tmp != null && tmp.exists()) {
                // Remove o temporario para a proxima tentativa partir limpa.
                tmp.delete();
            }
            return false;
        }
    }

    /**
     * Leitura best-effort: devolve o texto do arquivo ou null quando
     * ausente/ilegivel (nunca propaga excecao).
     */
    public static String readFile(File dir, String name) {
        FileInputStream in = null;
        try {
            File target = new File(dir, name);
            if (!target.isFile()) {
                return null;
            }
            in = new FileInputStream(target);
            StringBuilder sb = new StringBuilder((int) target.length() + 16);
            byte[] buffer = new byte[4096];
            int read;
            while ((read = in.read(buffer)) >= 0) {
                sb.append(new String(buffer, 0, read, "UTF-8"));
            }
            return sb.toString();
        } catch (Exception e) {
            Log.w(TAG, "leitura de " + name + " falhou: " + e.getMessage());
            return null;
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (IOException e) {
                    Log.w(TAG, "fechamento de " + name
                            + " falhou: " + e.getMessage());
                }
            }
        }
    }
}
