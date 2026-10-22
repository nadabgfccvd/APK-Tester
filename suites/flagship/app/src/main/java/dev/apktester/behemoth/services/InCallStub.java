package dev.apktester.behemoth.services;

import android.telecom.InCallService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * InCallService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_INCALL_SERVICE).
 *
 * Nenhum override e necessario: a superclasse nao tem metodos abstratos e
 * nenhuma chamada e apresentada nesta fase.
 */
public class InCallStub extends InCallService {
}
