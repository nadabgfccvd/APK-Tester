package dev.apktester.behemoth;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.widget.TextView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;

/**
 * Activity principal do Behemoth: resumo do probe CORE-PM-001 e navegacao
 * explicita para as telas do hub de permissoes, grades de botoes/icones e
 * relatorio MaxProbe.
 *
 * Probes desta tela:
 * - CORE-LC-001: duracao de cada callback de ciclo de vida medida com
 *   SystemClock.uptimeMillis (onCreate, onStart, onResume).
 * - CORE-PM-001: getPackageInfo com as quatro mascaras de componente;
 *   a contagem de activities/services/receivers/providers deve bater com
 *   contracts/flagship/manifest-audit.md (lei manifest-as-truth CORE-12).
 */
public class MainActivity extends Activity {

    private static final String TAG = "MAXPROBE/CORE";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        long startedAt = SystemClock.uptimeMillis();
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        runPackageManagerProbe();
        recordLifecycleStep("onCreate", SystemClock.uptimeMillis() - startedAt);
    }

    @Override
    protected void onStart() {
        long startedAt = SystemClock.uptimeMillis();
        super.onStart();
        recordLifecycleStep("onStart", SystemClock.uptimeMillis() - startedAt);
    }

    @Override
    protected void onResume() {
        long startedAt = SystemClock.uptimeMillis();
        super.onResume();
        recordLifecycleStep("onResume", SystemClock.uptimeMillis() - startedAt);
    }

    /** Handler do botao Permissions Hub (android:onClick no layout). */
    public void openPermissionsHub(View view) {
        startActivity(new Intent(this, PermissionsHubActivity.class));
    }

    /** Handler do botao Button Grid (android:onClick no layout). */
    public void openButtonGrid(View view) {
        startActivity(new Intent(this, ButtonGridActivity.class));
    }

    /** Handler do botao Icon Grid (android:onClick no layout). */
    public void openIconGrid(View view) {
        startActivity(new Intent(this, IconGridActivity.class));
    }

    /** Handler do botao MaxProbe Report (android:onClick no layout). */
    public void openProbeReport(View view) {
        startActivity(new Intent(this, ProbeReportActivity.class));
    }

    /**
     * CORE-PM-001: enumera os componentes do proprio pacote e publica o
     * resumo no TextView da tela. Toda falha vira probe ERROR, sem crash.
     */
    private void runPackageManagerProbe() {
        int flags = PackageManager.GET_ACTIVITIES
                | PackageManager.GET_SERVICES
                | PackageManager.GET_RECEIVERS
                | PackageManager.GET_PROVIDERS;
        long startedAt = SystemClock.uptimeMillis();
        boolean ok;
        String error = null;
        String summary;
        try {
            PackageInfo info = getPackageManager()
                    .getPackageInfo(getPackageName(), flags);
            int activities = info.activities != null ? info.activities.length : 0;
            int services = info.services != null ? info.services.length : 0;
            int receivers = info.receivers != null ? info.receivers.length : 0;
            int providers = info.providers != null ? info.providers.length : 0;
            long versionCode = Build.VERSION.SDK_INT >= 28
                    ? info.getLongVersionCode()
                    : info.versionCode;
            summary = "Behemoth " + info.versionName + " (" + versionCode + ")\n"
                    + "activities=" + activities
                    + " services=" + services
                    + " receivers=" + receivers
                    + " providers=" + providers;
            ok = true;
        } catch (Exception e) {
            ok = false;
            error = e.getMessage() == null ? e.getClass().getName() : e.getMessage();
            summary = "probe CORE-PM-001 falhou: " + error;
        }
        long durationMs = SystemClock.uptimeMillis() - startedAt;
        ProbeReporter.record(this, ProbeCatalog.CORE_PM_001, ok,
                ok ? null : error, durationMs);
        TextView summaryView = (TextView) findViewById(R.id.main_summary);
        summaryView.setText(summary);
    }

    /** Registra um passo do ciclo de vida com sua duracao medida. */
    private void recordLifecycleStep(String step, long durationMs) {
        Log.i(TAG, "CORE-LC-001 " + step + " concluido em " + durationMs + " ms");
        ProbeReporter.record(this, ProbeCatalog.CORE_LC_001, true, null, durationMs);
    }
}
