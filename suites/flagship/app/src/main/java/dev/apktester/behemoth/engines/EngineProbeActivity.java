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

    /**
     * R2.3 (AUDIT_ROADMAP_V2): app_name localizado de
     * assets/locales/&lt;tag&gt;/strings.properties (gen-strings.py) — a
     * categoria "locales" do size-report passa a ter bytes REAIS e usados.
     * Cadeia de fallback determinística pt-BR -> pt -> en; código
     * framework-only (minSdk 9: sem try-with-resources/StandardCharsets).
     */
    protected String localizedAppName() {
        String tag = java.util.Locale.getDefault().toString()
                .replace('_', '-');
        String[] chain;
        if (tag.regionMatches(true, 0, "pt-BR", 0, 5)) {
            chain = new String[]{"pt-BR", "pt", "en"};
        } else if (tag.regionMatches(true, 0, "pt", 0, 2)) {
            chain = new String[]{"pt", "en"};
        } else {
            chain = new String[]{tag, "en"};
        }
        java.util.Properties props = new java.util.Properties();
        for (int i = 0; i < chain.length && props.isEmpty(); i++) {
            java.io.InputStream in = null;
            try {
                in = getAssets().open("locales/" + chain[i]
                        + "/strings.properties");
                props.load(new java.io.InputStreamReader(in, "UTF-8"));
            } catch (Exception e) {
                // locale ausente no pacote — tenta o próximo da cadeia
            } finally {
                if (in != null) {
                    try {
                        in.close();
                    } catch (java.io.IOException ignored) {
                        // nada a fazer no close do probe
                    }
                }
            }
        }
        return props.getProperty("app_name", "APK Tester — Behemoth");
    }

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
        TextView localeLine = new TextView(this);
        localeLine.setText(localizedAppName());
        localeLine.setTextSize(13);
        localeLine.setPadding(0, 0, 0, 8);
        root.addView(localeLine);
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
