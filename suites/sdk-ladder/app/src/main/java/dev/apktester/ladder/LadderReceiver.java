package dev.apktester.ladder;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Receiver do degrau: responde a acao de probe declarada no manifesto
 * (dev.apktester.ladder.action.PROBE) com codigo RESULT_OK em broadcasts
 * ordenados. Nada de API nova (BroadcastReceiver e setResultCode sao API 1).
 */
public class LadderReceiver extends BroadcastReceiver {

    private static final String TAG = "LADDER";

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i(TAG, "PROBE recebido: " + intent.getAction());
        setResultCode(Activity.RESULT_OK);
    }
}
