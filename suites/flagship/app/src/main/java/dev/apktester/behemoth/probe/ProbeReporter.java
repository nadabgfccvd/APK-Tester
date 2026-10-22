package dev.apktester.behemoth.probe;

import android.content.Context;
import android.util.Log;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Reporter do harness MaxProbe: registra cada execucao de probe em memória,
 * no logcat e no relatorio JSON da sessao.
 *
 * Cada registro vira um objeto JSON montado a mao (sem dependencias, sem
 * org.json): {id, module_id, domain, api, result, error, duration_ms}. A
 * lista acumulada e reescrita a cada record() em
 * files/maxprobe-report.json como array JSON, gravando primeiro em arquivo
 * temporario e renomeando depois (escrita tudo-ou-nada: qualquer falha e
 * engolida com Log.w, jamais derruba o processo). O tag de logcat segue o
 * contrato do registry: MAXPROBE/&lt;MODULE_ID&gt;.
 *
 * Nenhuma API aqui exige mais que minSdk 9: leitura/escrita usa
 * java.io puro com nome de charset "UTF-8" (StandardCharsets so existe a
 * partir da API 19) e sem try-with-resources (AutoCloseable e API 19+).
 */
public final class ProbeReporter {

    /** Tag base dos logs internos do reporter. */
    private static final String TAG = "MAXPROBE";

    /** Nome do relatorio JSON gravado no diretorio de arquivos do app. */
    public static final String REPORT_FILE = "maxprobe-report.json";

    /** Trava unica para a lista de entradas e o arquivo de relatorio. */
    private static final Object LOCK = new Object();

    /** Entradas JSON acumuladas na sessao (uma linha compacta por probe). */
    private static final List<String> ENTRIES = new ArrayList<String>();

    private ProbeReporter() {
    }

    /**
     * Registra uma execucao de probe: acrescenta o JSON em memoria, grava o
     * relatorio em disco e emite Log.i com o tag MAXPROBE/&lt;MODULE_ID&gt;.
     *
     * @param context    contexto para localizar o diretorio de arquivos
     * @param spec       especificacao do probe (contracts api-probe-registry)
     * @param ok         true quando o probe concluiu dentro da lei esperada
     * @param error      detalhe do erro; null quando ok for true
     * @param durationMs duracao medida pelo chamador (SystemClock.uptimeMillis)
     */
    public static void record(Context context, ProbeSpec spec, boolean ok,
            String error, long durationMs) {
        String json = buildJson(spec, ok, error, durationMs);
        synchronized (LOCK) {
            ENTRIES.add(json);
            Log.i("MAXPROBE/" + spec.moduleId, json);
            writeReportFile(context);
        }
    }

    /**
     * Devolve o texto do relatorio JSON da sessao ou null quando o arquivo
     * ainda nao existe (ou nao pode ser lido).
     */
    public static String readReport(Context context) {
        synchronized (LOCK) {
            BufferedReader reader = null;
            try {
                File target = new File(context.getFilesDir(), REPORT_FILE);
                if (!target.isFile()) {
                    return null;
                }
                reader = new BufferedReader(
                        new InputStreamReader(new FileInputStream(target), "UTF-8"));
                StringBuilder sb = new StringBuilder();
                char[] buffer = new char[4096];
                int read;
                while ((read = reader.read(buffer)) >= 0) {
                    sb.append(buffer, 0, read);
                }
                return sb.toString();
            } catch (Exception e) {
                Log.w(TAG, "leitura do relatorio falhou: " + e.getMessage());
                return null;
            } finally {
                if (reader != null) {
                    try {
                        reader.close();
                    } catch (IOException e) {
                        Log.w(TAG, "fechamento do relatorio falhou: " + e.getMessage());
                    }
                }
            }
        }
    }

    /** Monta a linha JSON do registro com escape manual correto. */
    private static String buildJson(ProbeSpec spec, boolean ok, String error,
            long durationMs) {
        String result = ok ? "OK" : "ERROR";
        String errorJson = ok ? "null" : "\"" + jsonEscape(
                error == null ? "erro sem detalhes" : error) + "\"";
        return new StringBuilder()
                .append("{\"id\":\"").append(jsonEscape(spec.id)).append('"')
                .append(",\"module_id\":\"").append(jsonEscape(spec.moduleId)).append('"')
                .append(",\"domain\":\"").append(jsonEscape(spec.domain)).append('"')
                .append(",\"api\":\"").append(jsonEscape(spec.api)).append('"')
                .append(",\"result\":\"").append(result).append('"')
                .append(",\"error\":").append(errorJson)
                .append(",\"duration_ms\":").append(durationMs)
                .append('}')
                .toString();
    }

    /** Escapa aspas, barra invertida e caracteres de controle para JSON. */
    private static String jsonEscape(String value) {
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

    /**
     * Reescrita tudo-ou-nada do relatorio: escreve em .tmp e renomeia por
     * cima do destino; qualquer excecao vira Log.w e nao propaga.
     */
    private static void writeReportFile(Context context) {
        File tmp = null;
        try {
            File dir = context.getFilesDir();
            File target = new File(dir, REPORT_FILE);
            tmp = new File(dir, REPORT_FILE + ".tmp");
            StringBuilder sb = new StringBuilder(ENTRIES.size() * 160);
            sb.append('[');
            for (int i = 0; i < ENTRIES.size(); i++) {
                sb.append(i == 0 ? "\n  " : ",\n  ");
                sb.append(ENTRIES.get(i));
            }
            if (!ENTRIES.isEmpty()) {
                sb.append('\n');
            }
            sb.append("]\n");
            Writer writer = new OutputStreamWriter(new FileOutputStream(tmp), "UTF-8");
            try {
                writer.write(sb.toString());
                writer.flush();
            } finally {
                writer.close();
            }
            if (target.exists() && !target.delete()) {
                throw new IOException("nao removeu o relatorio anterior");
            }
            if (!tmp.renameTo(target)) {
                throw new IOException("nao renomeou o relatorio temporario");
            }
        } catch (Exception e) {
            Log.w(TAG, "persistencia do relatorio falhou: " + e.getMessage());
            if (tmp != null && tmp.exists()) {
                // Remove o temporario para a proxima tentativa partir limpa.
                tmp.delete();
            }
        }
    }
}
