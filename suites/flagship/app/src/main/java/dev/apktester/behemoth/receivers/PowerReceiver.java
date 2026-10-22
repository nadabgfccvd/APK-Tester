package dev.apktester.behemoth.receivers;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Fixture de registro/deteccao de receiver (A1): escuta
 * android.intent.action.ACTION_POWER_CONNECTED e
 * android.intent.action.ACTION_POWER_DISCONNECTED para o RustyDroid
 * validar o componente declarado no manifesto.
 */
public class PowerReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i("MAXPROBE/SYS", "broadcast de energia recebido: "
                + (intent.getAction() == null ? "(sem action)" : intent.getAction()));
    }
}
