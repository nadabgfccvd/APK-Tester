package dev.apktester.ladder;

import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.util.Log;

/**
 * Service do degrau: stub minimo com binder local (mesmo processo) — nenhum
 * binding remoto, nenhuma API nova. onStartCommand devolve START_STICKY para
 * o ciclo de servico reiniciavel padrao. O componente existe para o
 * rustydroid inspect validar a superficie declarada (4 componentes, 0
 * permissoes), nao para fazer trabalho real.
 */
public class LadderService extends Service {

    private static final String TAG = "LADDER";

    /** Binder local: devolve a propria instancia do servico. */
    public class LadderBinder extends Binder {
        public LadderService getService() {
            return LadderService.this;
        }
    }

    private final LadderBinder binder = new LadderBinder();

    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "servico ativo (startId=" + startId + ")");
        return START_STICKY;
    }
}
