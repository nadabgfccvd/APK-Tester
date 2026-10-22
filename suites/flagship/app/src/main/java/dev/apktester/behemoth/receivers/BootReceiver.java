package dev.apktester.behemoth.receivers;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Fixture de registro/deteccao de receiver (A1): escuta
 * android.intent.action.BOOT_COMPLETED para o RustyDroid validar o
 * componente declarado no manifesto.
 */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i("MAXPROBE/SYS", "BOOT_COMPLETED recebido");
    }
}
