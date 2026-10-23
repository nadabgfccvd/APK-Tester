package dev.apktester.behemoth;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.widget.TextView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;
import dev.apktester.behemoth.sim3d.Sim3dEngine;
import java.util.Map;

/**
 * Tela do pilar 3D headless (:sim3d) — executa o motor completo de
 * simulacao (rasterizador de software + fisica 10k + particulas 100k +
 * marching cubes + esqueleto) em thread de fundo e mostra os golden
 * checksums calculados no dispositivo.
 *
 * O motor e 100% Java/Q16 inteiro (sem android.*, sem ponto flutuante):
 * roda identico no JVM do CI, no APK e sob o RustyDroid headless. O
 * contrato byte a byte vive em contracts/flagship/sim3d-golden.json
 * (verificado no CI com zero drift); aqui o probe registra que a rota
 * CPU conclui dentro da lei (sem crash, com checksums estaveis).
 *
 * Probe desta tela: MEDIA-SM-001.
 */
public class Sim3dActivity extends Activity {

    private static final String TAG = "MAXPROBE/MEDIA";

    private TextView statusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        statusView = new TextView(this);
        statusView.setPadding(32, 32, 32, 32);
        statusView.setText("sim3d: executando pilar 3D headless (thread de fundo)...");
        setContentView(statusView);

        final long startedAt = SystemClock.uptimeMillis();
        new Thread(new Runnable() {
            @Override
            public void run() {
                boolean ok;
                String error = null;
                String summary;
                try {
                    Sim3dEngine engine = new Sim3dEngine();
                    Map<String, Object> report = engine.run();
                    @SuppressWarnings("unchecked")
                    Map<String, Object> phys = (Map<String, Object>) report.get("physics");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> physSteps = (Map<String, Object>) phys.get("step_fnv1a64");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> raster = (Map<String, Object>) report.get("rasterizer");
                    summary = "fisica(120)=" + physSteps.get("120")
                            + " raster=" + raster.get("final_fnv1a64")
                            + " pixels=" + raster.get("pixels_drawn");
                    ok = physSteps.get("120") != null
                            && raster.get("final_fnv1a64") != null;
                    if (!ok) {
                        error = "relatorio sem checksums finais";
                    }
                } catch (Throwable t) { // lei do probe: erro estruturado, nunca crash
                    ok = false;
                    error = t.getClass().getSimpleName() + ": " + t.getMessage();
                    summary = null;
                }
                final boolean probeOk = ok;
                final String probeError = error;
                final String probeSummary = summary;
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        long durationMs = SystemClock.uptimeMillis() - startedAt;
                        ProbeReporter.record(Sim3dActivity.this,
                                ProbeCatalog.MEDIA_SM_001, probeOk, probeError, durationMs);
                        statusView.setText("sim3d golden (Q16 inteiro):\n"
                                + (probeSummary == null ? probeError : probeSummary)
                                + "\n\nContrato: contracts/flagship/sim3d-golden.json"
                                + "\nLei: erro estruturado, nunca crash (MAXPROBE/MEDIA).");
                        android.util.Log.i(TAG, "sim3d concluido ok=" + probeOk);
                    }
                });
            }
        }, "sim3d-golden").start();
    }
}
