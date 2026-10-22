package dev.apktester.behemoth.services;

import android.inputmethodservice.InputMethodService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * InputMethodService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_INPUT_METHOD, config em res/xml/method.xml).
 *
 * Nenhum override e necessario: o metodo abstrato nao existe nesta
 * superclasse e o teclado padrao nunca e criado nesta fase.
 */
public class InputMethodStub extends InputMethodService {
}
