package dev.apktester.behemoth.providers;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;

/**
 * ContentProvider guardado por permissao custom NORMAL (autoridade
 * dev.apktester.behemoth.guarded.normal): leitura exige
 * dev.apktester.behemoth.permission.CUSTOM_NORMAL — a permissao custom de
 * nivel normal declarada no manifesto do flagship deixava de ser ORFA
 * (definida e nunca referenciada; auditoria A9/roadmap 3.6): agora guarda
 * de verdade um segundo componente exportado, o par normal/signature dos
 * dois niveis custom fica exercitado no parser de permissoes.
 *
 * Implementacao minima de fixture: query devolve cursor vazio com a
 * coluna "value"; escritas sao no-ops. O objetivo e o RustyDroid validar a
 * superficie de permissao do componente, nao o conteudo.
 */
public class GuardedNormalProvider extends ContentProvider {

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        MatrixCursor cursor = new MatrixCursor(new String[] { "value" });
        cursor.addRow(new Object[] { "guarded-normal" });
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        return "vnd.android.cursor.item/vnd.dev.apktester.behemoth.guarded.normal";
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
            String[] selectionArgs) {
        return 0;
    }
}
