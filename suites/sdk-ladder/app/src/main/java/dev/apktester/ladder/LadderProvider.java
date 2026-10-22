package dev.apktester.ladder;

import android.content.ContentProvider;
import android.content.ContentUris;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.content.UriMatcher;
import android.util.Log;

/**
 * Provider do degrau: stub deterministico sobre MatrixCursor — SEM SQLite
 * (banco de verdade nao e necessario para validar a superficie declarada e
 * SQLiteDatabase deixaria o degrau mais pesado que o minimo da suíte).
 *
 * Tres linhas fixas (_id 1..3) espelham o answer key: "rung" (flavor, do
 * proprio pacote), "seed" (seed do repositorio) e "floor" (piso do
 * RustyDroid). Insert devolve ContentUris.withAppendedId(uri, 1);
 * update devolve 1 (uma linha logica) e delete devolve 0 (no-op) — contagens
 * deterministas, nunca dependentes de estado. UriMatcher e MatrixCursor sao
 * API 1.
 */
public class LadderProvider extends ContentProvider {

    private static final String TAG = "LADDER";

    /** Colunas do cursor (schema minimo de tabela chave/valor). */
    public static final String[] COLUMNS = {"_id", "key", "value"};

    /** Piso do RustyDroid (mesma constante de tools/gen-ladder.py). */
    private static final int FLOOR_RUSTYDROID = 26;

    /** Seed do repositorio (mesma constante de tools/gen-ladder.py). */
    private static final String SEED = "20261022";

    private static final int MATCH_RUNGS = 1;
    private static final int MATCH_RUNG_ID = 2;

    private UriMatcher matcher;

    /** Autoridade do provider: applicationId + ".provider" (manifesto). */
    private String authority() {
        return getContext().getPackageName() + ".provider";
    }

    @Override
    public boolean onCreate() {
        matcher = new UriMatcher(UriMatcher.NO_MATCH);
        String authority = authority();
        matcher.addURI(authority, "rungs", MATCH_RUNGS);
        matcher.addURI(authority, "rungs/#", MATCH_RUNG_ID);
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        switch (matcher.match(uri)) {
            case MATCH_RUNGS:
                return buildCursor(0);
            case MATCH_RUNG_ID:
                return buildCursor(ContentUris.parseId(uri));
            default:
                Log.w(TAG, "uri desconhecida: " + uri);
                return new MatrixCursor(COLUMNS);
        }
    }

    /**
     * Monta o cursor com as 3 linhas deterministicas; idFilter &gt; 0
     * restringe a linha cujo _id bate (senao devolve todas).
     */
    private Cursor buildCursor(long idFilter) {
        String rung = flavorName(getContext().getPackageName());
        MatrixCursor cursor = new MatrixCursor(COLUMNS);
        String[][] rows = {
            {"rung", rung},
            {"seed", SEED},
            {"floor", String.valueOf(FLOOR_RUSTYDROID)},
        };
        for (int i = 0; i < rows.length; i++) {
            long id = i + 1;
            if (idFilter > 0 && id != idFilter) {
                continue;
            }
            cursor.addRow(new Object[] {id, rows[i][0], rows[i][1]});
        }
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        if (matcher.match(uri) == MATCH_RUNGS) {
            return "vnd.android.cursor.dir/vnd.dev.apktester.ladder";
        }
        return "vnd.android.cursor.item/vnd.dev.apktester.ladder";
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return ContentUris.withAppendedId(uri, 1);
    }

    /** Contagem deterministica: uma linha logica por update. */
    @Override
    public int update(Uri uri, ContentValues values, String selection,
            String[] selectionArgs) {
        return 1;
    }

    /** Contagem deterministica: no-op (stub sem estado). */
    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    /** Nome do flavor = sufixo do pacote apos o prefixo da escada. */
    private static String flavorName(String packageName) {
        String prefix = "dev.apktester.ladder.";
        if (packageName.startsWith(prefix)) {
            return packageName.substring(prefix.length());
        }
        return packageName;
    }
}
