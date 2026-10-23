package dev.apktester.engine.chaquopy;

import android.app.Activity;
import android.os.Bundle;

/** Activity real (AGP compila contra android.jar) do engine-25. */
public class MainActivity extends Activity {
    public static final String ENGINE = "engine-25-python-chaquopy";
    public static final int SEED = 20261022;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }

    public int checksum() {
        int h = SEED;
        for (char c : ENGINE.toCharArray()) {
            h = 31 * h + c;
        }
        return h;
    }
}
