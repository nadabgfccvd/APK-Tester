package dev.apktester.behemoth.services;

import android.service.voice.VoiceInteractionService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * VoiceInteractionService para o RustyDroid validar o componente declarado
 * no manifesto (permissao BIND_VOICE_INTERACTION).
 *
 * Sem session service e sem hotword: a classe base nao exige overrides.
 */
public class VoiceInteractionStub extends VoiceInteractionService {
}
