package dev.apktester.behemoth.services;

import android.media.browse.MediaBrowser;
import android.media.browse.MediaBrowserService;
import android.os.Bundle;
import java.util.Collections;
import java.util.List;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * MediaBrowserService (API 21) para o RustyDroid validar o componente
 * declarado no manifesto (permissao BIND_MEDIA_BROWSER_SERVICE).
 *
 * onGetRoot devolve null (nenhuma hierarquia navegavel) e onLoadChildren
 * responde lista vazia — contrato minimo da superclasse sem conteudo.
 */
public class MediaBrowserStub extends MediaBrowserService {

    @Override
    public BrowserRoot onGetRoot(String clientPackageName, int clientUid,
            Bundle rootHints) {
        return null;
    }

    @Override
    public void onLoadChildren(String parentId,
            Result<List<MediaBrowser.MediaItem>> result) {
        result.sendResult(Collections.<MediaBrowser.MediaItem>emptyList());
    }
}
