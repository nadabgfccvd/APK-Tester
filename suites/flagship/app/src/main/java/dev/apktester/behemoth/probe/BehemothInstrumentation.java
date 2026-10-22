package dev.apktester.behemoth.probe;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;

/**
 * Instrumentacao de registro do Behemoth (declarada no manifesto com
 * targetPackage dev.apktester.behemoth).
 *
 * Fixture de superficie: o A1 so precisa que o componente exista, carregue
 * e se encerre com resultado OK. Probes instrumentados de verdade (matriz
 * JNI, sim3d golden) chegam nos marcos seguintes da fase A.
 */
public class BehemothInstrumentation extends Instrumentation {

    @Override
    public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        // Auto-encerramento: a instrumentacao registra, inicia e finaliza
        // com RESULT_OK para o runtime hospedeiro validar o ciclo minimo.
        start();
    }

    @Override
    public void onStart() {
        finish(Activity.RESULT_OK, new Bundle());
    }
}
