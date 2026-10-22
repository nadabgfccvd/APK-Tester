package dev.apktester.behemoth.services;

import android.nfc.cardemulation.HostApduService;
import android.os.Bundle;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * HostApduService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_NFC_SERVICE, sem intent-filter).
 *
 * Nenhum APDU e respondido: processCommandApdu devolve null (sem resposta)
 * e a desativacao e ignorada.
 */
public class HostApduStub extends HostApduService {

    @Override
    public byte[] processCommandApdu(byte[] commandApdu, Bundle extras) {
        return null;
    }

    @Override
    public void onDeactivated(int reason) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
