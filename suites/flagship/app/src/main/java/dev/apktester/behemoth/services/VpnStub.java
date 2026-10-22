package dev.apktester.behemoth.services;

import android.net.VpnService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * VpnService para o RustyDroid validar o componente declarado no manifesto
 * (permissao BIND_VPN_SERVICE, sem intent-filter).
 *
 * Nenhum tunel e aberto nesta fase: a superclasse nao exige overrides.
 */
public class VpnStub extends VpnService {
}
