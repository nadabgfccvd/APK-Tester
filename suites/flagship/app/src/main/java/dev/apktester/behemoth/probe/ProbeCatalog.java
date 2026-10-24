package dev.apktester.behemoth.probe;

/**
 * Catalogo dos probes do flagship Behemoth (A1 + D3: wiring completo).
 *
 * Os campos espelham as entradas de
 * contracts/flagship/api-probe-registry.json (seed do contrato): qualquer
 * mudanca de texto precisa passar antes pelo registry em contracts/flagship/.
 * A paridade registry X catalogo e auditada pelo APKBot
 * (bot/checks/probe_registry_parity.py): answer key sem codigo e drift.
 *
 * D3: os 17 probes do registry existem AQUI e todos tem wiring real — os 9
 * de componentes gravam via ProbeReporter a partir dos proprios hosts
 * (MainActivity, ButtonGridActivity, BehemothApp, ...) e os 8 orfos
 * (ST-DB, NET, MEDIA-PL, MEDIA-CM, SYS-SN/LC/TP, LANG-JN) sao executados
 * pelo ProbeRunner a partir da instrumentacao (BehemothInstrumentation).
 */
public final class ProbeCatalog {

    /** Ciclo de vida de Activity (onCreate..onResume medidos nesta fase). */
    public static final ProbeSpec CORE_LC_001 = new ProbeSpec(
            "CORE-LC-001", "CORE", "lifecycle",
            "Activity lifecycle completo (onCreate..onDestroy, recreate, config change)");

    /** PackageManager: getPackageInfo com contagens de componentes do manifesto. */
    public static final ProbeSpec CORE_PM_001 = new ProbeSpec(
            "CORE-PM-001", "CORE", "pm",
            "PackageManager: getPackageInfo, queryIntentActivities, getInstalledPackages");

    /** ContentProvider proprio com CRUD SQLite (onCreate e operacoes). */
    public static final ProbeSpec CORE_PV_001 = new ProbeSpec(
            "CORE-PV-001", "CORE", "provider",
            "ContentProvider CRUD proprio + FileProvider");

    /** Widgets: grade de 1200 botoes e grade de 600 icones vetoriais. */
    public static final ProbeSpec UI_WD_001 = new ProbeSpec(
            "UI-WD-001", "UI", "widget",
            "Zoo android.widget + ButtonGrid (btn_0001..btn_1200) + IconGrid (600)");

    /** Rasterizacao CPU via Canvas/Bitmap (checksum deterministico). */
    public static final ProbeSpec UI_GX_001 = new ProbeSpec(
            "UI-GX-001", "UI", "graphics",
            "Canvas/Bitmap software rendering (rotas CPU, sem GLES)");

    /** Medicao de texto com TextPaint (rota CPU, layout deterministico). */
    public static final ProbeSpec UI_TX_001 = new ProbeSpec(
            "UI-TX-001", "UI", "text",
            "TextView/TextPaint/StaticLayout com pseudolocale, RTL e fontScale");

    /** Handler/Looper do looper principal com duracao de post medida. */
    public static final ProbeSpec ST_OS_001 = new ProbeSpec(
            "ST-OS-001", "ST", "os",
            "Handler/Looper/MessageQueue (postDelayed deterministico)");

    /** D3: SQLiteDatabase CRUD real (banco privado do app, descartavel). */
    public static final ProbeSpec ST_DB_001 = new ProbeSpec(
            "ST-DB-001", "ST", "sqlite",
            "SQLiteDatabase CRUD (+ Room no flavor modern)");

    /** D3: HttpURLConnection record/replay servido de fixture embutida. */
    public static final ProbeSpec NET_RP_001 = new ProbeSpec(
            "NET-RP-001", "NET", "net",
            "HttpURLConnection record/replay com fixtures locais");

    /** D3: rota de playback (MediaPlayer/AudioTrack) — erro estruturado sob
     * o RustyDroid (registry expect NOT_IMPLEMENTED). */
    public static final ProbeSpec MEDIA_PL_001 = new ProbeSpec(
            "MEDIA-PL-001", "MEDIA", "media",
            "MediaPlayer/AudioTrack playback do corpus WAV gerado");

    /** D3: Camera2 open/preview stub — erro estruturado (sem crash). */
    public static final ProbeSpec MEDIA_CM_001 = new ProbeSpec(
            "MEDIA-CM-001", "MEDIA", "media",
            "Camera2: open/preview stub");

    /** D3: SensorManager com TODOS os tipos declarados (register/unregister). */
    public static final ProbeSpec SYS_SN_001 = new ProbeSpec(
            "SYS-SN-001", "SYS", "sensors",
            "SensorManager: TODOS os tipos declarados (register/unregister)");

    /** D3: LocationManager (lastKnownLocation + requestLocationUpdates). */
    public static final ProbeSpec SYS_LC_001 = new ProbeSpec(
            "SYS-LC-001", "SYS", "location",
            "LocationManager: lastKnownLocation + requestLocationUpdates");

    /** D3: TelephonyManager probes basicos (state, network type). */
    public static final ProbeSpec SYS_TP_001 = new ProbeSpec(
            "SYS-TP-001", "SYS", "telephony",
            "TelephonyManager: probes b\u00e1sicos (state, network type)");

    /** D3: matriz JNI via reflexao (a :native e modern-only, NDK 27). */
    public static final ProbeSpec LANG_JN_001 = new ProbeSpec(
            "LANG-JN-001", "LANG", "jni",
            "Matriz JNI: strings, arrays, direct ByteBuffer, exceptions, "
                    + "AttachCurrentThread");

    /** Pilar 3D headless: motor :sim3d completo com golden checksums Q16. */
    public static final ProbeSpec MEDIA_SM_001 = new ProbeSpec(
            "MEDIA-SM-001", "MEDIA", "sim3d",
            "Sim3D headless: rasterizador+fisica 10k+particulas 100k+marching cubes+esqueleto (golden Q16)");

    /** Pilar 3D GPU: compilacao/link GLES 3.1 de toda a shader-library. */
    public static final ProbeSpec MEDIA_GX_001 = new ProbeSpec(
            "MEDIA-GX-001", "MEDIA", "gles",
            "GLES 3.1: compilacao/link de todos os programas da shader-library com resultado estruturado");

    private ProbeCatalog() {
    }
}
