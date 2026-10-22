package dev.apktester.behemoth.providers;

import android.content.ContentProvider;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.content.UriMatcher;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.net.Uri;
import android.os.SystemClock;
import android.util.Log;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;

/**
 * ContentProvider CRUD proprio do Behemoth (autoridade
 * dev.apktester.behemoth.provider, exported=true com grantUriPermissions).
 *
 * Persistencia em SQLite privado behemoth.db, tabela items(_id, value).
 * Probe CORE-PV-001 registrado uma unica vez no onCreate (abertura do
 * banco); operacoes desconhecidas levantam IllegalArgumentException (lei do
 * contrato: erro estruturado, nunca crash silencioso).
 */
public class BehemothProvider extends ContentProvider {

    private static final String TAG = "MAXPROBE/CORE";

    /** Autoridade declarada no manifesto (attributo android:authorities). */
    public static final String AUTHORITY = "dev.apktester.behemoth.provider";

    /** URI da colecao items. */
    private static final Uri BASE_URI = Uri.parse("content://" + AUTHORITY + "/items");

    private static final int MATCH_ITEMS = 1;
    private static final int MATCH_ITEM_ID = 2;

    private static final UriMatcher MATCHER = new UriMatcher(UriMatcher.NO_MATCH);

    static {
        MATCHER.addURI(AUTHORITY, "items", MATCH_ITEMS);
        MATCHER.addURI(AUTHORITY, "items/#", MATCH_ITEM_ID);
    }

    private static final String TABLE = "items";

    /** Guarda o registro unico do probe CORE-PV-001 no onCreate. */
    private static boolean sProbeLogged = false;

    private DbHelper helper;

    /** SQLiteOpenHelper do banco privado behemoth.db (versao 1). */
    private static final class DbHelper extends SQLiteOpenHelper {

        DbHelper(Context context) {
            super(context, "behemoth.db", null, 1);
        }

        @Override
        public void onCreate(SQLiteDatabase db) {
            db.execSQL("CREATE TABLE items ("
                    + "_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    + "value TEXT NOT NULL)");
        }

        @Override
        public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
            db.execSQL("DROP TABLE IF EXISTS items");
            onCreate(db);
        }
    }

    @Override
    public boolean onCreate() {
        helper = new DbHelper(getContext());
        logCreateProbeOnce();
        return true;
    }

    /** Registra CORE-PV-001 uma unica vez por processo (abertura do banco). */
    private void logCreateProbeOnce() {
        if (sProbeLogged) {
            return;
        }
        sProbeLogged = true;
        Context context = getContext();
        if (context == null) {
            return;
        }
        long startedAt = SystemClock.uptimeMillis();
        boolean ok;
        String error = null;
        try {
            helper.getReadableDatabase();
            ok = true;
        } catch (Exception e) {
            ok = false;
            error = e.getMessage() == null ? e.getClass().getName() : e.getMessage();
        }
        long durationMs = SystemClock.uptimeMillis() - startedAt;
        Log.i(TAG, "CORE-PV-001 onCreate ok=" + ok);
        ProbeReporter.record(context, ProbeCatalog.CORE_PV_001, ok,
                ok ? null : error, durationMs);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        SQLiteDatabase db = helper.getReadableDatabase();
        switch (MATCHER.match(uri)) {
            case MATCH_ITEMS:
                return db.query(TABLE, projection, selection, selectionArgs,
                        null, null, sortOrder);
            case MATCH_ITEM_ID:
                return db.query(TABLE, projection, "_id = ?",
                        new String[] { String.valueOf(ContentUris.parseId(uri)) },
                        null, null, sortOrder);
            default:
                throw new IllegalArgumentException("URI desconhecida: " + uri);
        }
    }

    @Override
    public String getType(Uri uri) {
        switch (MATCHER.match(uri)) {
            case MATCH_ITEMS:
                return "vnd.android.cursor.dir/vnd.dev.apktester.behemoth.item";
            case MATCH_ITEM_ID:
                return "vnd.android.cursor.item/vnd.dev.apktester.behemoth.item";
            default:
                throw new IllegalArgumentException("URI desconhecida: " + uri);
        }
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        if (MATCHER.match(uri) != MATCH_ITEMS) {
            throw new IllegalArgumentException("insert exige a colecao items: " + uri);
        }
        ContentValues row = values != null ? values : new ContentValues();
        if (row.get("value") == null) {
            row.put("value", "seed-item");
        }
        long id = helper.getWritableDatabase().insert(TABLE, null, row);
        if (id < 0) {
            return null;
        }
        Uri result = ContentUris.withAppendedId(BASE_URI, id);
        notifyChange(result);
        return result;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
            String[] selectionArgs) {
        SQLiteDatabase db = helper.getWritableDatabase();
        int count;
        switch (MATCHER.match(uri)) {
            case MATCH_ITEMS:
                count = db.update(TABLE, values, selection, selectionArgs);
                break;
            case MATCH_ITEM_ID:
                count = db.update(TABLE, values, "_id = ?",
                        new String[] { String.valueOf(ContentUris.parseId(uri)) });
                break;
            default:
                throw new IllegalArgumentException("URI desconhecida: " + uri);
        }
        if (count > 0) {
            notifyChange(uri);
        }
        return count;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        SQLiteDatabase db = helper.getWritableDatabase();
        int count;
        switch (MATCHER.match(uri)) {
            case MATCH_ITEMS:
                count = db.delete(TABLE, selection, selectionArgs);
                break;
            case MATCH_ITEM_ID:
                count = db.delete(TABLE, "_id = ?",
                        new String[] { String.valueOf(ContentUris.parseId(uri)) });
                break;
            default:
                throw new IllegalArgumentException("URI desconhecida: " + uri);
        }
        if (count > 0) {
            notifyChange(uri);
        }
        return count;
    }

    /** Notifica o resolver sobre mudancas na URI (best-effort). */
    private void notifyChange(Uri uri) {
        Context context = getContext();
        if (context != null && context.getContentResolver() != null) {
            context.getContentResolver().notifyChange(uri, null);
        }
    }
}
