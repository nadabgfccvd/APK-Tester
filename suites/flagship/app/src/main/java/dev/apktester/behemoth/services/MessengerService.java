package dev.apktester.behemoth.services;

import android.app.Service;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;

/**
 * Servico Messenger IPC do Behemoth (exported=false): expõe um Binder
 * Messenger no looper principal para os testes de binding do RustyDroid.
 *
 * As mensagens recebidas sao apenas repassadas ao tratamento padrao do
 * Handler (nenhuma resposta e enviada nesta fase).
 */
public class MessengerService extends Service {

    @Override
    public IBinder onBind(Intent intent) {
        return new Messenger(new Handler(Looper.getMainLooper()) {
            @Override
            public void handleMessage(Message msg) {
                super.handleMessage(msg);
            }
        }).getBinder();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }
}
