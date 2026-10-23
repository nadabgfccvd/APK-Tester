package dev.apktester.engine.chaquopy;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

/** Service real do engine-25 (Chaquopy também usa services internos). */
public class TestService extends Service {
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
