package dev.apktester.behemoth.services;

import android.service.quicksettings.TileService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * TileService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_QUICK_SETTINGS_TILE, filtro
 * android.service.quicksettings.action.QS_TILE).
 *
 * Nenhum tile e publicado nesta fase: a superclasse nao exige overrides.
 */
public class TileStub extends TileService {
}
