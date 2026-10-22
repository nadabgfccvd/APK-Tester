package dev.apktester.behemoth.services;

import android.service.notification.NotificationListenerService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * NotificationListenerService para o RustyDroid validar o componente
 * declarado no manifesto (permissao BIND_NOTIFICATION_LISTENER_SERVICE).
 *
 * Nenhum override e necessario: a superclasse nao tem metodos abstratos e
 * os callbacks de notificacao permanecem com o comportamento padrao.
 */
public class NotificationListenerStub extends NotificationListenerService {
}
