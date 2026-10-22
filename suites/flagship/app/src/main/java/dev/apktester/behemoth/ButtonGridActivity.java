package dev.apktester.behemoth;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.GridView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;
import java.util.Locale;

/**
 * Button Grid: grade de 1200 botoes (stress de automacao AG-01/AG-02).
 *
 * Os rotulos vêm dos strings gerados btn_label_0001..btn_label_1200
 * (tools/gen-strings.py, determinísticos por seed). Cada botao tem id
 * estavel 0x00020000+posicao e content-desc "Button N of 1200" — alvos
 * confiaveis para o UIAutomator do RustyDroid.
 *
 * Probes desta tela: UI-WD-001 no toque de cada botao e UI-GX-001
 * (rasterizacao CPU deterministica com checksum) no onCreate.
 */
public class ButtonGridActivity extends Activity {

    private static final String TAG = "MAXPROBE/UI";

    /** Total de botoes da grade (contracts: btn_0001..btn_1200). */
    static final int BUTTON_COUNT = 1200;

    /** Base dos ids estaveis dos botoes (fora da faixa de R.id gerado). */
    private static final int BASE_VIEW_ID = 0x00020000;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_button_grid);
        GridView grid = (GridView) findViewById(R.id.button_grid);
        grid.setAdapter(new GridAdapter());
        grid.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> parent, View view,
                    int position, long id) {
                long startedAt = SystemClock.uptimeMillis();
                long durationMs = SystemClock.uptimeMillis() - startedAt;
                Log.i(TAG, "UI-WD-001 clique em btn_"
                        + String.format(Locale.US, "%04d", Integer.valueOf(position + 1)));
                ProbeReporter.record(ButtonGridActivity.this,
                        ProbeCatalog.UI_WD_001, true, null, durationMs);
            }
        });
        runGraphicsProbe();
    }

    /** UI-GX-001: desenha um bitmap 64x64 deterministico e extrai checksum. */
    private void runGraphicsProbe() {
        long startedAt = SystemClock.uptimeMillis();
        long checksum = 0;
        Bitmap bitmap = null;
        try {
            bitmap = Bitmap.createBitmap(64, 64, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            canvas.drawColor(0xFF1B1B1B);
            Paint paint = new Paint();
            paint.setColor(0xFF3366CC);
            canvas.drawRect(4f, 4f, 60f, 60f, paint);
            paint.setColor(0xFFCC3366);
            canvas.drawCircle(32f, 32f, 20f, paint);
            paint.setColor(0xFFFFFFFF);
            paint.setTextSize(10f);
            canvas.drawText("MAXPROBE", 6f, 54f, paint);
            int[] coords = { 0, 0, 16, 16, 32, 32, 63, 63, 7, 41 };
            for (int i = 0; i + 1 < coords.length; i += 2) {
                checksum = checksum * 31 + bitmap.getPixel(coords[i], coords[i + 1]);
            }
        } catch (Exception e) {
            String error = e.getMessage() == null ? e.getClass().getName() : e.getMessage();
            Log.w(TAG, "UI-GX-001 falhou: " + error);
            ProbeReporter.record(this, ProbeCatalog.UI_GX_001, false, error,
                    SystemClock.uptimeMillis() - startedAt);
            if (bitmap != null) {
                bitmap.recycle();
            }
            return;
        }
        if (bitmap != null) {
            bitmap.recycle();
        }
        long durationMs = SystemClock.uptimeMillis() - startedAt;
        Log.i(TAG, "UI-GX-001 checksum=" + checksum);
        ProbeReporter.record(this, ProbeCatalog.UI_GX_001, true, null, durationMs);
    }

    /** Converte dp em pixels inteiros com as metricas atuais. */
    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    /** Adapter da grade: reaproveita convertView; 1200 itens fixos. */
    private final class GridAdapter extends BaseAdapter {

        @Override
        public int getCount() {
            return BUTTON_COUNT;
        }

        @Override
        public Object getItem(int position) {
            return Integer.valueOf(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            Button button = convertView instanceof Button
                    ? (Button) convertView
                    : new Button(ButtonGridActivity.this);
            button.setText(labelFor(position));
            button.setId(BASE_VIEW_ID + position);
            button.setContentDescription(getString(
                    R.string.btn_content_desc, position + 1, BUTTON_COUNT));
            button.setIncludeFontPadding(false);
            button.setMinHeight(dp(44));
            return button;
        }
    }

    /** Rotulo do botao: string gerada btn_label_NNNN ou literal de fallback. */
    private String labelFor(int position) {
        String resource = "btn_label_"
                + String.format(Locale.US, "%04d", Integer.valueOf(position + 1));
        int id = getResources().getIdentifier(resource, "string", getPackageName());
        if (id != 0) {
            return getString(id);
        }
        return String.format(Locale.US, "btn_%04d", Integer.valueOf(position + 1));
    }
}
