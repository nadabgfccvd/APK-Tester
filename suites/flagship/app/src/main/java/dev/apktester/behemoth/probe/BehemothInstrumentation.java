package dev.apktester.behemoth.probe;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;

/**
 * Instrumentacao de registro do Behemoth (declarada no manifesto com
 * targetPackage dev.apktester.behemoth).
 *
 * D3 (wiring completo): alem de registrar, iniciar e se encerrar com
 * resultado OK para o runtime hospedeiro validar o ciclo minimo, a
 * instrumentacao agora EXECUTA os 8 probes orfos do registry
 * (contracts/flagship/api-probe-registry.json) via {@link ProbeRunner} —
 * SQLiteDatabase CRUD, HttpURLConnection record/replay, MediaPlayer/
 * AudioTrack, Camera2, SensorManager, LocationManager, TelephonyManager
 * e a matriz JNI. Cada resultado e gravado no maxprobe-report.json via
 * ProbeReporter com a lei do registry (OK / NOT_IMPLEMENTED / ERROR);
 * nenhuma excecao escapa (ADR 0003: erro estruturado, nunca crash).
 *
 * Os outros 9 probes do registry continuam sendo gravados pelos proprios
 * componentes hospedeiros (MainActivity, ButtonGridActivity, BehemothApp,
 * Sim3dActivity, GlesProbeActivity, ...).
 */
public class BehemothInstrumentation extends Instrumentation {

    @Override
    public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        // Auto-encerramento: a instrumentacao registra, inicia, executa o
        // ProbeRunner e finaliza com RESULT_OK + resumo nos extras.
        start();
    }

    @Override
    public void onStart() {
        ProbeRunner.Summary summary = ProbeRunner.runAll(
                getTargetContext());
        Bundle results = new Bundle();
        results.putString("maxprobe.runner", "ProbeRunner(D3)");
        results.putInt("maxprobe.probes", summary.total);
        results.putInt("maxprobe.ok", summary.ok);
        results.putInt("maxprobe.not_implemented", summary.notImplemented);
        results.putInt("maxprobe.error", summary.error);
        finish(Activity.RESULT_OK, results);
    }
}
