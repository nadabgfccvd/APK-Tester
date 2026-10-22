package dev.apktester.behemoth.services;

import android.telecom.Call;
import android.telecom.CallScreeningService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * CallScreeningService (API 24) para o RustyDroid validar o componente
 * declarado no manifesto (permissao BIND_SCREENING_SERVICE).
 *
 * Nenhuma chamada e respondida: o corpo do onScreenCall permanece vazio e
 * a classe so e carregada quando o sistema vincula o servico.
 */
public class CallScreeningStub extends CallScreeningService {

    @Override
    public void onScreenCall(Call.Details details) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
