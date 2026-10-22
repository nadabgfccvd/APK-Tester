package dev.apktester.behemoth.services;

import android.service.wallpaper.WallpaperService;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * WallpaperService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_WALLPAPER).
 *
 * onCreateEngine devolve um Engine padrao (superficie vazia): nenhum
 * desenho acontece nesta fase.
 */
public class WallpaperStub extends WallpaperService {

    @Override
    public Engine onCreateEngine() {
        return new Engine();
    }
}
