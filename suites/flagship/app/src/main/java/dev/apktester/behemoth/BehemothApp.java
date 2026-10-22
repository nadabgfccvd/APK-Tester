package dev.apktester.behemoth;

import android.app.Application;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;

/**
 * Application do Behemoth: ponto de partida do harness MaxProbe.
 *
 * No onCreate agenda no looper principal a execucao do probe ST-OS-001
 * (Handler/Looper/MessageQueue): a duracao medida e o intervalo entre o
 * post e a execucao da mensagem, com relógio monotônico
 * SystemClock.uptimeMillis.
 */
public class BehemothApp extends Application {

    @Override
    public void onCreate() {
        super.onCreate();
        final long postedAt = SystemClock.uptimeMillis();
        Log.i("MAXPROBE/ST", "ST-OS-001 postado no looper principal");
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                long durationMs = SystemClock.uptimeMillis() - postedAt;
                Log.i("MAXPROBE/ST", "ST-OS-001 executado em " + durationMs + " ms");
                ProbeReporter.record(BehemothApp.this, ProbeCatalog.ST_OS_001,
                        true, null, durationMs);
            }
        });
    }
}
