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
import android.widget.GridView;
import android.widget.ImageView;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;
import java.util.Locale;

/**
 * Icon Grid: grade de 600 ImageViews com os drawables vetoriais gerados
 * ic_vector_0001..ic_vector_0600 (tools/gen-icons.py, seed fixo).
 *
 * Fallback deterministico quando o drawable nao existe:
 * android.R.drawable.sym_def_app_icon. O content-desc segue o contrato
 * "Icon N of 600" para os walkers de acessibilidade do RustyDroid.
 *
 * Probes desta tela: UI-WD-001 no toque de cada icone e UI-GX-001
 * (rasterizacao CPU deterministica com checksum) no onCreate.
 */
public class IconGridActivity extends Activity {

    private static final String TAG = "MAXPROBE/UI";

    /** Total de icones da grade (contracts: 600 ic_vector). */
    static final int ICON_COUNT = 600;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_icon_grid);
        GridView grid = (GridView) findViewById(R.id.icon_grid);
        grid.setAdapter(new GridAdapter());
        grid.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> parent, View view,
                    int position, long id) {
                long startedAt = SystemClock.uptimeMillis();
                long durationMs = SystemClock.uptimeMillis() - startedAt;
                Log.i(TAG, "UI-WD-001 clique em ic_vector_"
                        + String.format(Locale.US, "%04d", Integer.valueOf(position + 1)));
                ProbeReporter.record(IconGridActivity.this,
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

    /** Adapter da grade: reaproveita convertView; 600 itens fixos. */
    private final class GridAdapter extends BaseAdapter {

        @Override
        public int getCount() {
            return ICON_COUNT;
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
            ImageView view = convertView instanceof ImageView
                    ? (ImageView) convertView
                    : new ImageView(IconGridActivity.this);
            view.setImageResource(drawableFor(position));
            view.setAdjustViewBounds(true);
            view.setContentDescription(getString(
                    R.string.ic_content_desc, position + 1, ICON_COUNT));
            return view;
        }
    }

    /** Drawable do icone: ic_vector_NNNN ou o icone padrao do sistema. */
    private int drawableFor(int position) {
        String resource = "ic_vector_"
                + String.format(Locale.US, "%04d", Integer.valueOf(position + 1));
        int id = getResources().getIdentifier(resource, "drawable", getPackageName());
        if (id != 0) {
            return id;
        }
        return android.R.drawable.sym_def_app_icon;
    }
}
