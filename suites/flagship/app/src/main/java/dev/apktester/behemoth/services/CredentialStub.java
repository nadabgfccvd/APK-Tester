package dev.apktester.behemoth.services;

import android.os.CancellationSignal;
import android.os.OutcomeReceiver;
import android.service.credentials.BeginCreateCredentialRequest;
import android.service.credentials.BeginCreateCredentialResponse;
import android.service.credentials.BeginGetCredentialRequest;
import android.service.credentials.BeginGetCredentialResponse;
import android.service.credentials.ClearCredentialStateRequest;
import android.credentials.ClearCredentialStateException;
import android.credentials.CreateCredentialException;
import android.service.credentials.CredentialProviderService;
import android.credentials.GetCredentialException;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * CredentialProviderService (API 34) para o RustyDroid validar o
 * componente declarado no manifesto (permissao BIND_CREDENTIALS_SERVICE).
 *
 * Os tres metodos abstratos permanecem vazios: nenhuma credencial e
 * oferecida, criada ou limpa nesta fase. A classe so e carregada quando o
 * sistema vincula o servico em API 34+.
 */
public class CredentialStub extends CredentialProviderService {

    @Override
    public void onBeginGetCredential(BeginGetCredentialRequest request,
            CancellationSignal cancellationSignal,
            OutcomeReceiver<BeginGetCredentialResponse, GetCredentialException> callback) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }

    @Override
    public void onBeginCreateCredential(BeginCreateCredentialRequest request,
            CancellationSignal cancellationSignal,
            OutcomeReceiver<BeginCreateCredentialResponse, CreateCredentialException> callback) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }

    @Override
    public void onClearCredentialState(ClearCredentialStateRequest request,
            CancellationSignal cancellationSignal,
            OutcomeReceiver<Void, ClearCredentialStateException> callback) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
