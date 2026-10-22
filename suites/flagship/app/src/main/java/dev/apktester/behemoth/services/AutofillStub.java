package dev.apktester.behemoth.services;

import android.os.CancellationSignal;
import android.service.autofill.AutofillService;
import android.service.autofill.FillCallback;
import android.service.autofill.FillRequest;
import android.service.autofill.SaveCallback;
import android.service.autofill.SaveRequest;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * AutofillService (API 26) para o RustyDroid validar o componente
 * declarado no manifesto (permissao BIND_AUTOFILL_SERVICE).
 *
 * Os dois metodos abstratos permanecem vazios: nenhum dataset e oferecido
 * e nenhum salvamento e respondido nesta fase.
 */
public class AutofillStub extends AutofillService {

    @Override
    public void onFillRequest(FillRequest request,
            CancellationSignal cancellationSignal, FillCallback callback) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }

    @Override
    public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
