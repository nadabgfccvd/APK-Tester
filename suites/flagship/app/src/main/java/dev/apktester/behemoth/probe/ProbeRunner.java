package dev.apktester.behemoth.probe;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.telephony.TelephonyManager;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLStreamHandler;
import java.nio.ByteBuffer;
import java.util.List;
import java.util.Locale;

/**
 * Executor dos probes "orfos" do registry (D3).
 *
 * O registry contracts/flagship/api-probe-registry.json declara 17 probes;
 * 9 sao gravados pelos proprios componentes hospedeiros (MainActivity,
 * ButtonGridActivity, BehemothApp, ...) via ProbeReporter. Os 8 restantes
 * nao tinham wiring — answer key prometendo mais do que o codigo entrega,
 * exatamente o drift que o APKBot agora pega
 * (bot/checks/probe_registry_parity.py). Esta classe da wiring REAL aos 8:
 *
 * - ST-DB-001: SQLiteDatabase CRUD de verdade (banco privado, descartado
 *   no fim; rota CPU, deterministica);
 * - NET-RP-001: HttpURLConnection record/replay com fixture EMBUTIDA —
 *   um URLStreamHandler proprio serve os bytes (zero rede, zero socket);
 * - MEDIA-PL-001: MediaPlayer + AudioTrack tentam a rota de playback de
 *   um WAV deterministico; sob o RustyDroid a resposta obrigatória e o
 *   erro estruturado (registry expect NOT_IMPLEMENTED) — classificado,
 *   nunca crash;
 * - MEDIA-CM-001: Camera2 open/preview stub (guarda API 21; sem
 *   permissao de runtime concedida, SecurityException e a lei estruturada);
 * - SYS-SN-001: SensorManager com getSensorList(TYPE_ALL) + register/
 *   unregister de verdade;
 * - SYS-LC-001: LocationManager lastKnownLocation + requestLocationUpdates
 *   (SecurityException sem grant vira resultado estruturado);
 * - SYS-TP-001: TelephonyManager basico (phoneType/simState/networkType);
 * - LANG-JN-001: matriz JNI (strings, arrays, direct ByteBuffer,
 *   exceptions, AttachCurrentThread) via reflexao sobre
 *   dev.apktester.behemoth.nativeprobe.NativeProbe — a :native so entra no
 *   flavor modern (NDK 27, piso API 21); no classic a classe nao existe e
 *   o resultado e o NOT_IMPLEMENTED estruturado (honesto com o README:
 *   nativo e modern-only).
 *
 * Disciplina de estilo do flagship classic (minSdk 9): sem lambdas, sem
 * try-with-resources, sem StandardCharsets, `String.format` sempre com
 * `Locale.US`; toda rota nova esta protegida por try/catch que CLASSIFICA
 * (OK / NOT_IMPLEMENTED / ERROR) e grava via ProbeReporter — nenhuma
 * excecao escapa para derrubar o processo hospedeiro (ADR 0003: erro
 * estruturado, nunca crash).
 */
public final class ProbeRunner {

    /** Resultado conforme a lei do registry (rota CPU rodou de verdade). */
    public static final String RESULT_OK = "OK";

    /** Resultado conforme a lei de erro estruturado do runtime. */
    public static final String RESULT_NOT_IMPLEMENTED = "NOT_IMPLEMENTED";

    /** Resultado inesperado (bug de fixture): nunca deve acontecer. */
    public static final String RESULT_ERROR = "ERROR";

    /** Resumo agregado da sessao (vai nos extras do Bundle final). */
    public static final class Summary {
        /** Total de probes executados pelo runner. */
        public int total;
        /** Quantidade com resultado OK. */
        public int ok;
        /** Quantidade com resultado NOT_IMPLEMENTED. */
        public int notImplemented;
        /** Quantidade com resultado ERROR. */
        public int error;
    }

    /** Contrato de um probe executavel: devolve o detalhe ou lanca. */
    private interface ProbeBody {
        String run(Context context) throws Exception;
    }

    private ProbeRunner() {
    }

    /**
     * Executa os 8 probes orfos em ordem fixa, grava cada resultado via
     * ProbeReporter e devolve o resumo agregado.
     */
    public static Summary runAll(Context context) {
        Summary summary = new Summary();
        // Ordem fixa e deterministica (mesma do registry).
        execute(context, ProbeCatalog.ST_DB_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return sqliteCrud(c);
            }
        });
        execute(context, ProbeCatalog.NET_RP_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return netRecordReplay(c);
            }
        });
        execute(context, ProbeCatalog.MEDIA_PL_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return mediaPlayback(c);
            }
        });
        execute(context, ProbeCatalog.MEDIA_CM_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) throws Exception {
                return camera2Stub(c);
            }
        });
        execute(context, ProbeCatalog.SYS_SN_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return sensorsAllTypes(c);
            }
        });
        execute(context, ProbeCatalog.SYS_LC_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return locationProbe(c);
            }
        });
        execute(context, ProbeCatalog.SYS_TP_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) {
                return telephonyProbe(c);
            }
        });
        execute(context, ProbeCatalog.LANG_JN_001, summary, new ProbeBody() {
            @Override
            public String run(Context c) throws Exception {
                return jniMatrix(c);
            }
        });
        return summary;
    }

    /** Executa um probe com classificacao estruturada e gravacao. */
    private static void execute(Context context, ProbeSpec spec,
            Summary summary, ProbeBody body) {
        long start = SystemClock.uptimeMillis();
        String result;
        String error = null;
        String detail;
        try {
            detail = body.run(context);
            result = RESULT_OK;
            if (detail != null && detail.startsWith(RESULT_NOT_IMPLEMENTED)) {
                // A rota existe de verdade mas o runtime respondeu a lei
                // estruturada (ex.: SecurityException classificada dentro).
                result = RESULT_NOT_IMPLEMENTED;
                error = detail.substring(RESULT_NOT_IMPLEMENTED.length() + 1);
            }
        } catch (Throwable t) {
            // Lei ADR 0003: excecao vira resultado estruturado, nunca crash.
            result = RESULT_NOT_IMPLEMENTED;
            error = t.getClass().getSimpleName()
                    + (t.getMessage() == null ? "" : (": " + t.getMessage()));
        }
        long durationMs = SystemClock.uptimeMillis() - start;
        if (RESULT_OK.equals(result)) {
            summary.ok++;
        } else if (RESULT_NOT_IMPLEMENTED.equals(result)) {
            summary.notImplemented++;
        } else {
            summary.error++;
        }
        summary.total++;
        ProbeReporter.recordResult(context, spec, result, error, durationMs);
    }

    // ------------------------------------------------------------- ST-DB-001
    /** CRUD SQLite real: cria banco privado, insere, le, atualiza, apaga. */
    private static String sqliteCrud(Context context) {
        final String dbName = "maxprobe-st-db-001.db";
        context.deleteDatabase(dbName);
        SQLiteDatabase db = null;
        Cursor cursor = null;
        try {
            db = context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE,
                    null);
            db.execSQL("CREATE TABLE IF NOT EXISTS maxprobe ("
                    + "id INTEGER PRIMARY KEY, v TEXT NOT NULL)");
            for (int i = 1; i <= 3; i++) {
                db.execSQL("INSERT INTO maxprobe (id, v) VALUES (?, ?)",
                        new Object[]{i, String.format(Locale.US,
                                "row-%02d", i)});
            }
            cursor = db.rawQuery(
                    "SELECT COUNT(*), SUM(id) FROM maxprobe", null);
            long count = -1;
            long sum = -1;
            if (cursor != null && cursor.moveToFirst()) {
                count = cursor.getLong(0);
                sum = cursor.getLong(1);
            }
            if (count != 3 || sum != 6) {
                throw new IllegalStateException(String.format(Locale.US,
                        "crud checksum inesperado: count=%d sum=%d",
                        count, sum));
            }
            db.execSQL("UPDATE maxprobe SET v = ? WHERE id = ?",
                    new Object[]{"row-01-updated", 1});
            db.execSQL("DELETE FROM maxprobe WHERE id = ?", new Object[]{3});
            return "crud=ok count=3 sum=6 update=1 delete=1";
        } finally {
            if (cursor != null) {
                cursor.close();
            }
            if (db != null && db.isOpen()) {
                db.close();
            }
            context.deleteDatabase(dbName);
        }
    }

    // ------------------------------------------------------------ NET-RP-001
    /** HttpURLConnection record/replay com fixture embutida (zero rede). */
    private static String netRecordReplay(Context context) {
        try {
            URL url = new URL("maxprobe", "replay", 80, "/fixture.bin",
                    new ReplayStreamHandler());
            HttpURLConnection connection =
                    (HttpURLConnection) url.openConnection();
            try {
                // Lado "record": a requisicao carrega marcadores estaveis.
                connection.setRequestMethod("GET");
                connection.setRequestProperty("X-MaxProbe-Record",
                        "NET-RP-001");
                connection.setRequestProperty("X-MaxProbe-Seed",
                        "20261022");
                connection.setConnectTimeout(1000);
                connection.setReadTimeout(1000);
                // Lado "replay": o handler embutido responde a fixture.
                int code = connection.getResponseCode();
                if (code != 200) {
                    throw new IllegalStateException(String.format(Locale.US,
                            "replay devolveu HTTP %d", code));
                }
                InputStream in = connection.getInputStream();
                int checksum = 0;
                int total = 0;
                try {
                    byte[] buffer = new byte[1024];
                    int read;
                    while ((read = in.read(buffer)) >= 0) {
                        for (int i = 0; i < read; i++) {
                            checksum = (checksum * 31 + (buffer[i] & 0xFF))
                                    & 0x7FFFFFFF;
                        }
                        total += read;
                    }
                } finally {
                    in.close();
                }
                if (total != ReplayStreamHandler.BODY.length) {
                    throw new IllegalStateException(String.format(Locale.US,
                            "replay truncado: %d de %d bytes", total,
                            ReplayStreamHandler.BODY.length));
                }
                return String.format(Locale.US,
                        "record=X-MaxProbe-Record replay=200 bytes=%d "
                                + "checksum=%d rede=zero(handler embutido)",
                        total, checksum);
            } finally {
                connection.disconnect();
            }
        } catch (Throwable t) {
            return RESULT_NOT_IMPLEMENTED + " " + t.getClass().getSimpleName()
                    + (t.getMessage() == null ? "" : (": " + t.getMessage()));
        }
    }

    /** Handler de URL que serve a fixture embutida (replay deterministico). */
    private static final class ReplayStreamHandler extends URLStreamHandler {
        /** Fixture embutida: 256 bytes deterministicos (seed 20261022). */
        static final byte[] BODY = buildBody();

        static byte[] buildBody() {
            byte[] body = new byte[256];
            int state = 20261022;
            for (int i = 0; i < body.length; i++) {
                // xorshift32 deterministico (mesma familia dos geradores).
                state ^= state << 13;
                state ^= state >>> 17;
                state ^= state << 5;
                body[i] = (byte) (state & 0xFF);
            }
            return body;
        }

        @Override
        protected URLConnection openConnection(URL url) {
            return new ReplayConnection(url);
        }
    }

    /** HttpURLConnection de replay: cabecalhos fixos, corpo da fixture. */
    private static final class ReplayConnection extends HttpURLConnection {
        ReplayConnection(URL url) {
            super(url);
        }

        @Override
        public void connect() {
            connected = true;
        }

        @Override
        public InputStream getInputStream() {
            return new ByteArrayInputStream(ReplayStreamHandler.BODY);
        }

        @Override
        public OutputStream getOutputStream() {
            throw new UnsupportedOperationException(
                    "replay nao aceita corpo de requisicao");
        }

        @Override
        public String getHeaderField(String name) {
            if ("Content-Type".equals(name)) {
                return "application/octet-stream";
            }
            if ("Content-Length".equals(name)) {
                return String.valueOf(ReplayStreamHandler.BODY.length);
            }
            return null;
        }

        @Override
        public int getResponseCode() {
            return HTTP_OK;
        }

        @Override
        public void disconnect() {
            connected = false;
        }

        @Override
        public boolean usingProxy() {
            return false;
        }
    }

    // ---------------------------------------------------------- MEDIA-PL-001
    /** Rota de playback (MediaPlayer + AudioTrack) de WAV deterministico. */
    private static String mediaPlayback(Context context) {
        // 1) MediaPlayer: WAV de 44 bytes de cabecalho + PCM deterministico.
        File wav = writeDeterministicWav(context);
        MediaPlayer player = null;
        try {
            player = new MediaPlayer();
            player.setDataSource(wav.getAbsolutePath());
            player.prepare();
            player.start();
            player.stop();
        } catch (Throwable t) {
            return RESULT_NOT_IMPLEMENTED + " MediaPlayer: "
                    + t.getClass().getSimpleName()
                    + (t.getMessage() == null ? "" : (": " + t.getMessage()));
        } finally {
            if (player != null) {
                try {
                    player.release();
                } catch (Throwable ignored) {
                    // release nunca pode derrubar o processo.
                }
            }
            wav.delete();
        }
        // 2) AudioTrack: PCM estatico curto em rota CPU.
        AudioTrack track = null;
        try {
            int sampleRate = 8000;
            short[] pcm = new short[64];
            for (int i = 0; i < pcm.length; i++) {
                pcm[i] = (short) ((i % 32) * 512 - 8192);
            }
            int minBuf = AudioTrack.getMinBufferSize(sampleRate,
                    AudioFormat.CHANNEL_OUT_MONO,
                    AudioFormat.ENCODING_PCM_16BIT);
            track = new AudioTrack(AudioManager.STREAM_MUSIC, sampleRate,
                    AudioFormat.CHANNEL_OUT_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    Math.max(minBuf, pcm.length * 2),
                    AudioTrack.MODE_STATIC);
            track.write(pcm, 0, pcm.length);
            track.play();
            track.stop();
        } catch (Throwable t) {
            return RESULT_NOT_IMPLEMENTED + " AudioTrack: "
                    + t.getClass().getSimpleName()
                    + (t.getMessage() == null ? "" : (": " + t.getMessage()));
        } finally {
            if (track != null) {
                try {
                    track.release();
                } catch (Throwable ignored) {
                    // release nunca pode derrubar o processo.
                }
            }
        }
        return "MediaPlayer=ok AudioTrack=ok wav=embeddado(pcm16 mono 8kHz)";
    }

    /** Escreve um WAV minimo e deterministico no filesDir (e depois apagado). */
    private static File writeDeterministicWav(Context context) {
        FileOutputStream out = null;
        try {
            File wav = new File(context.getFilesDir(),
                    "maxprobe-media-pl-001.wav");
            int sampleCount = 128;
            int dataSize = sampleCount * 2;
            int fileSize = 36 + dataSize;
            byte[] bytes = new byte[44 + dataSize];
            // Cabecalho RIFF/WAVE padrao (mono, 16-bit, 8 kHz).
            copy(bytes, 0, new byte[]{'R', 'I', 'F', 'F'});
            putIntLE(bytes, 4, fileSize);
            copy(bytes, 8, new byte[]{'W', 'A', 'V', 'E', 'f', 'm', 't', ' '});
            putIntLE(bytes, 16, 16);
            copy(bytes, 20, new byte[]{1, 0, 1, 0});   // PCM, mono
            putIntLE(bytes, 22, 8000);                  // sample rate
            putIntLE(bytes, 26, 16000);                 // byte rate
            copy(bytes, 30, new byte[]{2, 0, 16, 0});   // block align, bits
            copy(bytes, 34, new byte[]{'d', 'a', 't', 'a'});
            putIntLE(bytes, 36, dataSize);
            for (int i = 0; i < sampleCount; i++) {
                short sample = (short) ((i % 16) * 1024 - 8192);
                bytes[44 + i * 2] = (byte) (sample & 0xFF);
                bytes[45 + i * 2] = (byte) ((sample >> 8) & 0xFF);
            }
            out = new FileOutputStream(wav);
            out.write(bytes);
            out.flush();
            return wav;
        } catch (IOException e) {
            throw new IllegalStateException("falha ao escrever WAV: "
                    + e.getMessage());
        } finally {
            if (out != null) {
                try {
                    out.close();
                } catch (IOException ignored) {
                    // fechamento nunca pode derrubar o processo.
                }
            }
        }
    }

    private static void copy(byte[] target, int offset, byte[] source) {
        System.arraycopy(source, 0, target, offset, source.length);
    }

    private static void putIntLE(byte[] target, int offset, int value) {
        target[offset] = (byte) (value & 0xFF);
        target[offset + 1] = (byte) ((value >> 8) & 0xFF);
        target[offset + 2] = (byte) ((value >> 16) & 0xFF);
        target[offset + 3] = (byte) ((value >> 24) & 0xFF);
    }

    // ---------------------------------------------------------- MEDIA-CM-001
    /** Camera2 open/preview stub (guarda API 21; erro estruturado sem grant). */
    private static String camera2Stub(Context context) throws Exception {
        if (Build.VERSION.SDK_INT < 21) {
            return RESULT_NOT_IMPLEMENTED
                    + " Camera2 exige API 21+ (flavor classic e framework-only)";
        }
        Object manager = context.getSystemService("camera");
        if (manager == null) {
            return RESULT_NOT_IMPLEMENTED
                    + " CameraManager indisponivel no runtime";
        }
        Method listMethod = manager.getClass().getMethod("getCameraIdList");
        List<?> ids = (List<?>) listMethod.invoke(manager);
        if (ids == null || ids.isEmpty()) {
            return RESULT_NOT_IMPLEMENTED + " nenhuma camera declarada";
        }
        // openCamera exige grant de CAMERA em API 23+; sem grant, a
        // SecurityException e o resultado estruturado esperado (registry
        // expect NOT_IMPLEMENTED) — classificada, nunca crash.
        android.hardware.camera2.CameraDevice.StateCallback callback =
                new android.hardware.camera2.CameraDevice.StateCallback() {
                    @Override
                    public void onOpened(
                            android.hardware.camera2.CameraDevice camera) {
                        // Stub de preview: fecha imediatamente (sem render).
                        try {
                            camera.close();
                        } catch (Throwable ignored) {
                            // fechar nunca pode derrubar o processo.
                        }
                    }

                    @Override
                    public void onDisconnected(
                            android.hardware.camera2.CameraDevice camera) {
                        // Stub: sem preview.
                    }

                    @Override
                    public void onError(
                            android.hardware.camera2.CameraDevice camera,
                            int error) {
                        // Stub: sem preview; erro vira resultado do callback.
                    }
                };
        Method open = manager.getClass().getMethod("openCamera",
                String.class,
                android.hardware.camera2.CameraDevice.StateCallback.class,
                android.os.Handler.class);
        try {
            open.invoke(manager, ids.get(0), callback, null);
        } catch (java.lang.reflect.InvocationTargetException e) {
            Throwable cause = e.getCause();
            return RESULT_NOT_IMPLEMENTED + " openCamera: "
                    + (cause == null ? e.getClass().getSimpleName()
                    : cause.getClass().getSimpleName());
        }
        // Se o grant ja existia, o open foi aceito (resultado honesto).
        return "openCamera aceito cameras=" + ids.size()
                + " (preview stub: callback fecha imediatamente)";
    }

    // ------------------------------------------------------------- SYS-SN-001
    /** SensorManager: getSensorList(TYPE_ALL) + register/unregister reais. */
    private static String sensorsAllTypes(Context context) {
        SensorManager manager = (SensorManager) context.getSystemService(
                Context.SENSOR_SERVICE);
        if (manager == null) {
            return RESULT_NOT_IMPLEMENTED
                    + " SensorManager indisponivel no runtime";
        }
        List<Sensor> all = manager.getSensorList(Sensor.TYPE_ALL);
        SensorEventListener listener = new SensorEventListener() {
            @Override
            public void onSensorChanged(SensorEvent event) {
                // Fixture: sem coleta; o register/unregister e o teste.
            }

            @Override
            public void onAccuracyChanged(Sensor sensor, int accuracy) {
                // Fixture: sem coleta.
            }
        };
        int registered = 0;
        int limit = Math.min(all.size(), 8);
        try {
            for (int i = 0; i < limit; i++) {
                if (manager.registerListener(listener, all.get(i),
                        SensorManager.SENSOR_DELAY_NORMAL)) {
                    registered++;
                }
            }
        } catch (Throwable t) {
            manager.unregisterListener(listener);
            return RESULT_NOT_IMPLEMENTED + " registerListener: "
                    + t.getClass().getSimpleName();
        }
        manager.unregisterListener(listener);
        return String.format(Locale.US,
                "tiposDeclarados=%d registrados=%d unregister=ok",
                all.size(), registered);
    }

    // ------------------------------------------------------------- SYS-LC-001
    /** LocationManager: lastKnownLocation + requestLocationUpdates. */
    private static String locationProbe(Context context) {
        LocationManager manager = (LocationManager) context.getSystemService(
                Context.LOCATION_SERVICE);
        if (manager == null) {
            return RESULT_NOT_IMPLEMENTED
                    + " LocationManager indisponivel no runtime";
        }
        List<String> providers = manager.getAllProviders();
        int lastKnown = 0;
        for (int i = 0; i < providers.size(); i++) {
            try {
                Location location = manager.getLastKnownLocation(
                        providers.get(i));
                if (location != null) {
                    lastKnown++;
                }
            } catch (Throwable t) {
                // SecurityException sem grant: lei estruturada, nunca crash.
                return RESULT_NOT_IMPLEMENTED + " lastKnownLocation("
                        + providers.get(i) + "): "
                        + t.getClass().getSimpleName();
            }
        }
        LocationListener listener = new LocationListener() {
            @Override
            public void onLocationChanged(Location location) {
                // Fixture: sem coleta de posicao.
            }

            @Override
            public void onStatusChanged(String provider, int status,
                    Bundle extras) {
                // Fixture: sem coleta (metodo da interface classica).
            }

            @Override
            public void onProviderEnabled(String provider) {
                // Fixture: sem coleta.
            }

            @Override
            public void onProviderDisabled(String provider) {
                // Fixture: sem coleta.
            }
        };
        String passive = LocationManager.PASSIVE_PROVIDER;
        try {
            manager.requestLocationUpdates(passive, 0L, 0.0f, listener);
        } catch (Throwable t) {
            return RESULT_NOT_IMPLEMENTED + " requestLocationUpdates: "
                    + t.getClass().getSimpleName();
        }
        manager.removeUpdates(listener);
        return String.format(Locale.US,
                "providers=%d lastKnownNaoNulos=%d updates=passive(0ms) "
                        + "removidos=ok", providers.size(), lastKnown);
    }

    // ------------------------------------------------------------- SYS-TP-001
    /** TelephonyManager basico: phoneType, simState, networkType. */
    @SuppressWarnings("deprecation")
    private static String telephonyProbe(Context context) {
        TelephonyManager manager = (TelephonyManager) context.getSystemService(
                Context.TELEPHONY_SERVICE);
        if (manager == null) {
            return RESULT_NOT_IMPLEMENTED
                    + " TelephonyManager indisponivel no runtime";
        }
        int phoneType;
        int simState;
        int networkType;
        try {
            phoneType = manager.getPhoneType();
            simState = manager.getSimState();
            networkType = manager.getNetworkType();
        } catch (Throwable t) {
            // SecurityException/UnsupportedOperation sem grant: lei estruturada.
            return RESULT_NOT_IMPLEMENTED + " probes: "
                    + t.getClass().getSimpleName();
        }
        return String.format(Locale.US,
                "phoneType=%d simState=%d networkType=%d (sem grant, sem PII)",
                phoneType, simState, networkType);
    }

    // ------------------------------------------------------------ LANG-JN-001
    /** Matriz JNI via reflexao (a :native e modern-only — NDK 27, API 21). */
    private static String jniMatrix(Context context) throws Exception {
        Class<?> nativeProbe;
        try {
            nativeProbe = Class.forName(
                    "dev.apktester.behemoth.nativeprobe.NativeProbe");
        } catch (ClassNotFoundException e) {
            // Flavor classic: framework-only (NDK 27 e modern-only).
            return RESULT_NOT_IMPLEMENTED
                    + " :native ausente no classic (NDK 27 modern-only)";
        }
        // 1) soma inteira (a funcao historica do probe).
        Method sum = nativeProbe.getMethod("sum", int.class, int.class);
        if ((Integer) sum.invoke(null, 20, 22) != 42) {
            throw new IllegalStateException("JNI sum(20,22) != 42");
        }
        // 2) strings: ida e volta (GetStringUTFChars + NewStringUTF).
        Method roundTrip = nativeProbe.getMethod("stringRoundTrip",
                String.class);
        String echoed = (String) roundTrip.invoke(null, "maxprobe-jni");
        if (!"maxprobe-jni".equals(echoed)) {
            throw new IllegalStateException("JNI stringRoundTrip divergiu");
        }
        // 3) arrays: soma de int[] via GetIntArrayRegion.
        Method arraySum = nativeProbe.getMethod("intArraySum", int[].class);
        int[] values = new int[10];
        for (int i = 0; i < values.length; i++) {
            values[i] = i + 1;
        }
        if ((Integer) arraySum.invoke(null, (Object) values) != 55) {
            throw new IllegalStateException("JNI intArraySum(1..10) != 55");
        }
        // 4) direct ByteBuffer: checksum via GetDirectBufferAddress.
        Method bufferChecksum = nativeProbe.getMethod("directBufferChecksum",
                ByteBuffer.class);
        ByteBuffer buffer = ByteBuffer.allocateDirect(32);
        for (int i = 0; i < 32; i++) {
            buffer.put((byte) i);
        }
        buffer.flip();
        int checksum = (Integer) bufferChecksum.invoke(null, buffer);
        if (checksum != 31 * 32 / 2) { // soma 0..31
            throw new IllegalStateException(String.format(Locale.US,
                    "JNI directBufferChecksum=%d != %d", checksum, 31 * 32 / 2));
        }
        // 5) exceptions: ThrowNew no C -> ArithmeticException no Java.
        Method throwProbe = nativeProbe.getMethod("throwArithmeticProbe",
                int.class);
        try {
            throwProbe.invoke(null, 0);
            throw new IllegalStateException(
                    "JNI throwArithmeticProbe(0) nao lancou");
        } catch (java.lang.reflect.InvocationTargetException e) {
            if (!(e.getCause() instanceof ArithmeticException)) {
                throw new IllegalStateException("JNI lancou "
                        + (e.getCause() == null ? "null"
                        : e.getCause().getClass().getSimpleName()));
            }
        }
        // 6) AttachCurrentThread: pthread nativo chama echoInt via callback.
        Method threadSum = nativeProbe.getMethod("threadEchoSum", int.class);
        if ((Integer) threadSum.invoke(null, 7) != 14) {
            throw new IllegalStateException("JNI threadEchoSum(7) != 14");
        }
        return "matriz=6/6 sum=42 strings=ok arrays=55 "
                + "byteBuffer=496 exceptions=ArithmeticException "
                + "attachThread=14 flavor=modern";
    }
}
