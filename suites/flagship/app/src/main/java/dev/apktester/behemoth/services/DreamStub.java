package dev.apktester.behemoth.services;

import android.service.dreams.DreamService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * DreamService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_DREAM_SERVICE).
 *
 * Nenhum sonho (screensaver) e desenhado nesta fase: a superclasse nao
 * exige overrides.
 */
public class DreamStub extends DreamService {
}
