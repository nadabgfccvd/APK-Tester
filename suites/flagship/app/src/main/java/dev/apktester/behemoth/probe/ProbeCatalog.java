package dev.apktester.behemoth.probe;

/**
 * Catalogo dos probes registrados no marco A1 do flagship Behemoth.
 *
 * Os campos espelham verbatim as entradas de
 * contracts/flagship/api-probe-registry.json (seed do contrato, sem drift):
 * qualquer mudanca de texto precisa passar antes pelo registry em
 * contracts/flagship/. Probes de dominios futuros (net, media, sensors,
 * location, telephony, jni) entram nos marcos seguintes da fase A.
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

    private ProbeCatalog() {
    }
}
