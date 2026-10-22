package dev.apktester.behemoth.services;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

/**
 * Servico de stress de foreground do Behemoth (exported=false): declara no
 * manifesto os 13 foregroundServiceType da plataforma
 * (dataSync|mediaPlayback|location|camera|microphone|phoneCall|
 * connectedDevice|mediaProjection|remoteMessaging|shortService|specialUse|
 * health|systemExperiments) com a propriedade
 * android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE=apktester-fgs-stress.
 *
 * startForeground com tipos (e as notificacoes exigidas) e executado
 * apenas em probes futuros (A5+); nesta fase o servico existe como fixture
 * de registro no manifesto e permanece no estado stopped.
 */
public class ForegroundStub extends Service {

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }
}
