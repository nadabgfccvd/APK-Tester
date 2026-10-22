package dev.apktester.behemoth.services;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): implementa
 * android.accessibilityservice.AccessibilityService para o RustyDroid
 * validar o componente declarado no manifesto (permissao
 * BIND_ACCESSIBILITY_SERVICE, config em res/xml/accessibility_service_config.xml).
 *
 * Corpo vazio de proposito: nenhum evento e processado nesta fase.
 */
public class AccessibilityStubService extends AccessibilityService {

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }

    @Override
    public void onInterrupt() {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
