package dev.apktester.behemoth.receivers;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Fixture de registro/deteccao de receiver (A1): escuta
 * android.intent.action.TIME_SET para o RustyDroid validar o componente
 * declarado no manifesto.
 */
public class TimeReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i("MAXPROBE/SYS", "TIME_SET recebido");
    }
}
