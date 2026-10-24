package dev.apktester.behemoth.engines;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Base das sondas por engine (R2.1 do AUDIT_ROADMAP_V2): uma Activity
 * REAL por engine da answer key — tela minima, framework-only (o flavor
 * classic e minSdk 9), com o id canônico e o domínio do contrato.
 * O APKBot vigia a cobertura (cheque activity_coverage: todo engine de
 * contracts/engines/expected-engines.json tem activity declarada, o
 * mesmo padrão do locale_sync).
 */
abstract class EngineProbeActivity extends Activity {

    /** id canônico no answer key
     * (contracts/engines/expected-engines.json). */
    protected abstract String engineId();

    /** rótulo curto do domínio/linguagem exibido na tela. */
    protected abstract String engineLabel();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);
        TextView title = new TextView(this);
        title.setText("Engine probe — " + engineId());
        title.setTextSize(20);
        title.setPadding(0, 0, 0, pad);
        root.addView(title);
        TextView body = new TextView(this);
        body.setText(engineLabel() + "\n\nManifest-as-truth (CORE-12): "
                + "toda activity declarada no manifesto existe no módulo "
                + ":app e abre uma tela real.");
        body.setTextSize(14);
        root.addView(body);
        setContentView(root);
    }
}
