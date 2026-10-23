package dev.apktester.behemoth;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.widget.TextView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;

/**
 * Tela dos probes GLES 3.1 da shader-library — a LEI do pilar 3D para a
 * rota GPU: compilar/linkar TODOS os programas gerados
 * (tools/gen-shaders.py, 239 programas) e logar resultados ESTRUTURADOS
 * por programa; sob o RustyDroid (sem GLES real) as chamadas retornam
 * erro estruturado NOT_IMPLEMENTED-ish — o golden PROVA a lei (nunca
 * crash, nunca excecao nao tratada).
 *
 * Estrategia anti-crash em tres camadas:
 *   1. onCreate inteiro protegido por catch(Throwable) — qualquer
 *      ausencia de classe/EGL/View vira registro estruturado e finish();
 *   2. rotas GLES31 (API 21+) isoladas em metodo guardado por
 *      Build.VERSION.SDK_INT (flavor classic minSdk 9 nunca executa);
 *   3. o renderer coleta resultado por programa (compilou/linkou ou o
 *      erro GLES) e grava no maxprobe-report via ProbeReporter.
 *
 * Probe desta tela: MEDIA-GX-001.
 */
public class GlesProbeActivity extends Activity {

    private static final String TAG = "MAXPROBE/MEDIA";

    private TextView statusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        long startedAt = SystemClock.uptimeMillis();
        statusView = new TextView(this);
        statusView.setPadding(32, 32, 32, 32);
        setContentView(statusView);
        try {
            if (android.os.Build.VERSION.SDK_INT < 21) {
                ProbeReporter.record(this, ProbeCatalog.MEDIA_GX_001, false,
                        "GLES31 indisponivel (SDK " + android.os.Build.VERSION.SDK_INT
                                + " < 21): resultado estruturado, sem crash",
                        SystemClock.uptimeMillis() - startedAt);
                statusView.setText("GLES 3.1 probes: SDK < 21 — rota GPU estruturada"
                        + " como erro (lei do pilar 3D), CPU coberta pelo :sim3d.");
                return;
            }
            statusView.setText("GLES 3.1 probes: compilando shader-library (239"
                    + " programas) via GLES31 no contexto EGL...");
            // Rotas de API nova isoladas: a classe inteira do renderer so e
            // carregada quando SDK >= 21 (verificado acima).
            startGlesProbe(startedAt);
        } catch (Throwable t) { // lei do probe: erro estruturado, nunca crash
            ProbeReporter.record(this, ProbeCatalog.MEDIA_GX_001, false,
                    t.getClass().getSimpleName() + ": " + t.getMessage(),
                    SystemClock.uptimeMillis() - startedAt);
            statusView.setText("GLES 3.1 probes: erro estruturado (sem crash): "
                    + t.getClass().getSimpleName());
        }
    }

    /**
     * Caminho GLES31 real (so chamado com SDK >= 21): GLSurfaceView +
     * renderer que compila/linka cada programa da shader-library
     * (assets/shader-library/index.json) e registra resultado estruturado.
     */
    private void startGlesProbe(final long startedAt) {
        android.opengl.GLSurfaceView glView = new android.opengl.GLSurfaceView(this);
        glView.setEGLContextClientVersion(3);
        glView.setRenderer(new GlesShaderLibraryRenderer(this, startedAt));
        setContentView(glView);
    }
}
