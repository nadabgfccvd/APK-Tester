package dev.apktester.behemoth.providers;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;

/**
 * ContentProvider guardado do Behemoth (autoridade
 * dev.apktester.behemoth.guarded): leitura e escrita exigem a permissao de
 * assinatura dev.apktester.behemoth.permission.CUSTOM_SIGNATURE declarada
 * no proprio manifesto.
 *
 * Implementacao minima de fixture: query devolve cursor vazio com a
 * coluna "value"; escritas sao no-ops. O objetivo e o RustyDroid validar a
 * superficie de permissao do componente, nao o conteudo.
 */
public class GuardedProvider extends ContentProvider {

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        MatrixCursor cursor = new MatrixCursor(new String[] { "value" });
        cursor.addRow(new Object[] { "guarded" });
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        return "vnd.android.cursor.item/vnd.dev.apktester.behemoth.guarded";
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
