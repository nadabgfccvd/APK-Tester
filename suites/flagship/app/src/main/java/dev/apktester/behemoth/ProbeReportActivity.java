package dev.apktester.behemoth;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.TextPaint;
import android.util.Log;
import android.widget.TextView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;

/**
 * Tela de relatorio do harness MaxProbe e aterrissagem dos deep links.
 *
 * Mostra o conteudo de files/maxprobe-report.json (array JSON acumulado
 * pelo ProbeReporter) ou a string de sessao vazia. Quando aberta por um
 * dos filtros VIEW do manifesto (maxprobe, geo, tel, sms, mailto, market
 * e https maxprobe.dev/apktester), exibe o scheme e a URI recebida.
 *
 * Probe desta tela: UI-TX-001 — medicao deterministica de largura de texto
 * com TextPaint (rota CPU, sem layout de GLES).
 */
public class ProbeReportActivity extends Activity {

    private static final String TAG = "MAXPROBE/UI";

    /** Texto fixo e deterministico usado na medicao do probe de texto. */
    private static final String MEASURE_SAMPLE =
            "MAXPROBE UI-TX-001 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ "
                    + "abcdefghijklmnopqrstuvwxyz minSdk9 targetSdk36";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_probe_report);

        TextView deeplinkView = (TextView) findViewById(R.id.deeplink_text);
        Uri data = getIntent().getData();
        if (data != null) {
            deeplinkView.setText((data.getScheme() == null ? "(sem scheme)" : data.getScheme())
                    + " | " + data.toString());
        } else {
            deeplinkView.setText(getString(R.string.probe_deeplink_none));
        }

        TextView reportView = (TextView) findViewById(R.id.probe_report_text);
        String report = ProbeReporter.readReport(this);
        reportView.setText(report != null
                ? report
                : getString(R.string.probe_report_empty));

        runTextProbe();
    }

    /** UI-TX-001: mede largura do texto fixo com TextPaint (64 repeticoes). */
    private void runTextProbe() {
        long startedAt = SystemClock.uptimeMillis();
        boolean ok;
        String error = null;
        float width = 0f;
        try {
            TextPaint paint = new TextPaint();
            paint.setTextSize(16f * getResources().getDisplayMetrics().scaledDensity);
            for (int i = 0; i < 64; i++) {
                width = paint.measureText(MEASURE_SAMPLE, 0, MEASURE_SAMPLE.length());
            }
            ok = width > 0f;
            if (!ok) {
                error = "largura medida nao positiva";
            }
        } catch (Exception e) {
            ok = false;
            error = e.getMessage() == null ? e.getClass().getName() : e.getMessage();
        }
        long durationMs = SystemClock.uptimeMillis() - startedAt;
        Log.i(TAG, "UI-TX-001 largura=" + width);
        ProbeReporter.record(this, ProbeCatalog.UI_TX_001, ok,
                ok ? null : error, durationMs);
    }
}
