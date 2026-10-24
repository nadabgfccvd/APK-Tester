#!/usr/bin/env python3
"""Gerador do manifesto completo e das auditorias do flagship "Behemoth" (A1).

Fonte de dados: contracts/flagship/permissions-registry.json (snapshot
verbatim do AOSP capturado por tools/snapshot-aosp-permissions.py). Nada de
estimativa: a lista de permissoes E o snapshot; o manifesto, as auditorias e
o asset de runtime saem da MESMA fonte — zero drift por construcao.

Saidas (caminhos relativos a --out; na integracao, --out e a raiz do repo):
  suites/flagship/AndroidManifest.xml                     (canonical, commitada)
  suites/flagship/app/src/main/AndroidManifest.xml        (copia byte-identica p/ build)
  suites/flagship/app/src/classic/AndroidManifest.xml     (overlay flavor classic)
  suites/flagship/app/src/modern/AndroidManifest.xml      (overlay flavor modern)
  contracts/flagship/permissions-audit.md                 (answer key de permissoes)
  contracts/flagship/manifest-audit.md                    (answer key de componentes)
  suites/flagship/app/src/main/assets/permissions/registry.json (dado de runtime
                                                    consumido pelo PermissionsHub)

Determinismo: mesma entrada => mesmos bytes (sem timestamps; a proveniencia
vem do registry versionado). --seed e aceito por contrato de interface com
verify-deterministic.sh, mas nao altera a saida (a fonte de dados e o
registry, nao o gerador aleatorio).

Uso:
    python3 tools/gen-flagship-manifest.py --out .            # integracao (raiz do repo)
    python3 tools/gen-flagship-manifest.py --out /tmp/out     # sandbox
    python3 tools/gen-flagship-manifest.py --selftest
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "contracts" / "flagship" / "permissions-registry.json"

APPLICATION_ID = "dev.apktester.behemoth"
VERSION_NAME = "1.0.0"
VERSION_CODE = 900036
SHARED_USER_ID = "dev.apktester.behemoth"

CUSTOM_PERMS = [
    {
        "name": "dev.apktester.behemoth.permission.CUSTOM_NORMAL",
        "protection_level": "normal",
        "kind": "permission",
        "note": "permissao custom normal — guarda a LEITURA do GuardedNormalProvider "
                "(exported; autoridade dev.apktester.behemoth.guarded.normal); "
                "referenciada de verdade desde a A9 (roadmap 3.6)",
    },
    {
        "name": "dev.apktester.behemoth.permission.CUSTOM_SIGNATURE",
        "protection_level": "signature",
        "kind": "permission",
        "note": "permissao custom signature — guarda o GuardedProvider (leitura e escrita)",
    },
]

CUSTOM_GROUP = "dev.apktester.behemoth.permission-group.BEHEMOTH"
CUSTOM_TREE = "dev.apktester.behemoth.permission-tree.DYNAMIC"

USES_FEATURES = [
    # (name, required, version_attr) — 3 required + glEsVersion + opcionais
    ("android.hardware.camera", True, None),
    ("android.hardware.microphone", True, None),
    ("android.hardware.sensor.compass", True, None),
    (None, True, "0x00030002"),  # glEsVersion (elemento proprio com atributo)
    ("android.hardware.location.gps", False, None),
    ("android.hardware.location.network", False, None),
    ("android.hardware.bluetooth_le", False, None),
    ("android.hardware.nfc", False, None),
    ("android.hardware.telephony", False, None),
    ("android.hardware.wifi", False, None),
    ("android.hardware.sensor.gyroscope", False, None),
    ("android.hardware.type.pc", False, None),
    ("android.software.leanback", False, None),
    ("android.software.app_widgets", False, None),
    ("android.software.device_admin", False, None),
    ("android.hardware.vulkan.version", False, "0x401000"),
]

SUPPORTS_GL_TEXTURES = [
    "GL_OES_compressed_ETC1_RGB8_texture",
    "GL_AMD_compressed_ATC_texture",
    "GL_IMG_texture_compression_pvrtc",
]

USES_NATIVE_LIBS = [
    ("libEGL.so", False),
    ("libOpenSLES.so", False),
    ("libc.so", True),
]

QUERIES_PACKAGES = ["android", "com.android.settings"]
QUERIES_INTENTS = [
    # (action, data_scheme, mime)
    ("android.intent.action.MAIN", None, None),
    ("android.intent.action.VIEW", "https", None),
    ("android.intent.action.VIEW", "geo", None),
    ("android.intent.action.DIAL", None, None),
    ("android.intent.action.SEND", None, "text/plain"),
    ("android.content.action.DOCUMENTS_PROVIDER", None, None),
    ("android.intent.action.WEB_SEARCH", None, None),
]

# Tabela de componentes A1: toda classe declarada existe no modulo :app.
# kind: activity | activity-alias | service | receiver | provider
ACTIVITIES = [
    {"class": ".MainActivity", "label": "@string/app_name", "exported": True,
     "filters": [
         {"action": "android.intent.action.MAIN", "categories": ["android.intent.category.LAUNCHER"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "https",
          "data_host": "maxprobe.dev", "data_path_prefix": "/apktester",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"], "auto_verify": True},
     ]},
    {"class": ".PermissionsHubActivity", "label": "@string/permission_hub_title",
     "exported": True, "filters": []},
    {"class": ".ButtonGridActivity", "label": "@string/button_grid_title",
     "exported": True, "filters": []},
    {"class": ".IconGridActivity", "label": "@string/icon_grid_title",
     "exported": True, "filters": []},
    {"class": ".Sim3dActivity", "label": "Sim3D Headless (pilar 3D)",
     "exported": True, "filters": []},
    {"class": ".GlesProbeActivity", "label": "GLES 3.1 Probes (shader-library)",
     "exported": True, "filters": []},
    {"class": ".ProbeReportActivity", "label": "@string/probe_report_title",
     "exported": True,
     "filters": [
         {"action": "android.intent.action.VIEW", "data_scheme": "maxprobe",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "geo",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "tel",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "sms",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "mailto",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
         {"action": "android.intent.action.VIEW", "data_scheme": "market",
          "categories": ["android.intent.category.DEFAULT",
                         "android.intent.category.BROWSABLE"]},
     ]},
]

ACTIVITY_ALIASES = [
    {"class": ".MainActivityLauncherAlias1", "target": ".MainActivity",
     "icon": "@drawable/ic_launcher_r1", "exported": True, "enabled": True,
     "launcher_filter": True,
     "note": "alias ativo com icone proprio (launcher icon multiplo)"},
    {"class": ".MainActivityLauncherAlias2", "target": ".MainActivity",
     "icon": "@drawable/ic_launcher_r2", "exported": True, "enabled": False,
     "launcher_filter": False,
     "note": "alias DESATIVADO (android:enabled=false) — caso de borda auditado"},
]

SERVICES = [
    # (class, BIND permission guard, filter action | None, meta-data | None, exported)
    (".services.AccessibilityStubService", "android.permission.BIND_ACCESSIBILITY_SERVICE",
     "android.accessibilityservice.AccessibilityService",
     ("android.accessibilityservice.AccessibilityService", "@xml/accessibility_service_config"), True),
    (".services.NotificationListenerStub", "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE",
     "android.service.notification.NotificationListenerService", None, True),
    (".services.InputMethodStub", "android.permission.BIND_INPUT_METHOD",
     "android.view.InputMethod",
     ("android.view.im", "@xml/method"), True),
    (".services.VoiceInteractionStub", "android.permission.BIND_VOICE_INTERACTION",
     "android.service.voice.VoiceInteractionService", None, True),
    (".services.CallScreeningStub", "android.permission.BIND_SCREENING_SERVICE",
     "android.telecom.CallScreeningService", None, True),
    (".services.InCallStub", "android.permission.BIND_INCALL_SERVICE",
     "android.telecom.InCallService", None, True),
    (".services.PrintStub", "android.permission.BIND_PRINT_SERVICE",
     "android.printservice.PrintService", None, True),
    (".services.AutofillStub", "android.permission.BIND_AUTOFILL_SERVICE",
     "android.service.autofill.AutofillService", None, True),
    (".services.TileStub", "android.permission.BIND_QUICK_SETTINGS_TILE",
     "android.service.quicksettings.action.QS_TILE", None, True),
    (".services.HostApduStub", "android.permission.BIND_NFC_SERVICE", None, None, True),
    (".services.MediaBrowserStub", "android.permission.BIND_MEDIA_BROWSER_SERVICE",
     "android.media.browse.MediaBrowserService", None, True),
    (".services.WallpaperStub", "android.permission.BIND_WALLPAPER",
     "android.service.wallpaper.WallpaperService", None, True),
    (".services.DreamStub", "android.permission.BIND_DREAM_SERVICE",
     "android.service.dreams.DreamService", None, True),
    (".services.VpnStub", "android.permission.BIND_VPN_SERVICE", None, None, True),
    (".services.CredentialStub", "android.permission.BIND_CREDENTIALS_SERVICE",
     "android.service.credentials.CredentialProviderService", None, True),
    (".services.MessengerService", None, None, None, False),
    (".services.ForegroundStub", None, None, None, False),
]

RECEIVERS = [
    # (class, filters [(action, data_scheme)], exported)
    (".receivers.BootReceiver", [("android.intent.action.BOOT_COMPLETED", None)], True),
    (".receivers.LocaleReceiver", [("android.intent.action.LOCALE_CHANGED", None)], True),
    (".receivers.TimeReceiver", [("android.intent.action.TIME_SET", None)], True),
    (".receivers.TimezoneReceiver", [("android.intent.action.TIMEZONE_CHANGED", None)], True),
    (".receivers.PackageReplacedReceiver", [("android.intent.action.PACKAGE_REPLACED", "package")], True),
    (".receivers.MyPackageReplacedReceiver", [("android.intent.action.MY_PACKAGE_REPLACED", None)], True),
    (".receivers.UserPresentReceiver", [("android.intent.action.USER_PRESENT", None)], True),
    (".receivers.PowerReceiver",
     [("android.intent.action.ACTION_POWER_CONNECTED", None),
      ("android.intent.action.ACTION_POWER_DISCONNECTED", None)], True),
    (".receivers.ScreenReceiver",
     [("android.intent.action.SCREEN_ON", None),
      ("android.intent.action.SCREEN_OFF", None)], True),
    (".receivers.DeviceAdminReceiverStub",
     [("android.app.action.DEVICE_ADMIN_ENABLED", None)], True),
]

PROVIDERS = [
    {"class": ".providers.BehemothProvider",
     "authorities": "dev.apktester.behemoth.provider",
     "exported": True, "grant_uri_permissions": True,
     "read_permission": None, "write_permission": None,
     "note": "CRUD proprio sobre SQLite (probe CORE-PV-001)"},
    {"class": ".providers.GuardedProvider",
     "authorities": "dev.apktester.behemoth.guarded",
     "exported": True, "grant_uri_permissions": False,
     "read_permission": "dev.apktester.behemoth.permission.CUSTOM_SIGNATURE",
     "write_permission": "dev.apktester.behemoth.permission.CUSTOM_SIGNATURE",
     "note": "provider com readPermission/writePermission guardados por permissao custom signature"},
    {"class": ".providers.GuardedNormalProvider",
     "authorities": "dev.apktester.behemoth.guarded.normal",
     "exported": True, "grant_uri_permissions": False,
     "read_permission": "dev.apktester.behemoth.permission.CUSTOM_NORMAL",
     "write_permission": None,
     "note": "provider guardado por permissao custom NORMAL (leitura) — "
             "CUSTOM_NORMAL deixa de ser orfa (A9/roadmap 3.6): o par "
             "normal/signature dos dois niveis custom fica exercitado"},
]

WIDGETS = [
    {"class": ".widgets.BehemothAppWidget", "meta": "@xml/appwidget_provider",
     "label": "@string/app_name"},
    {"class": ".widgets.SecondAppWidget", "meta": "@xml/appwidget_provider_second",
     "label": "@string/behemoth_widget_second_label"},
]

INSTRUMENTATION = {
    "class": ".probe.BehemothInstrumentation",
    "target_package": APPLICATION_ID,
    "functional_test": True,
    "handle_profiling": False,
}


# ------------------------------------------------------------------ helpers
def _attr(name: str, value: str) -> str:
    value = escape(str(value), {'"': "&quot;"})
    return f'android:{name}="{value}"'


def _indent(level: int) -> str:
    return "    " * level


def _filter_xml(fltr: dict, level: int) -> list[str]:
    lines = [f"{_indent(level)}<intent-filter"]
    if fltr.get("auto_verify"):
        lines[0] += " " + _attr("autoVerify", "true") + ">"
    else:
        lines[0] += ">"
    lines.append(f"{_indent(level + 1)}<action {_attr('name', fltr['action'])}/>")
    scheme = fltr.get("data_scheme")
    if scheme:
        data_attrs = _attr("scheme", scheme)
        if fltr.get("data_host"):
            data_attrs += f" {_attr('host', fltr['data_host'])}"
        if fltr.get("data_path_prefix"):
            data_attrs += f" {_attr('pathPrefix', fltr['data_path_prefix'])}"
        lines.append(f"{_indent(level + 1)}<data {data_attrs}/>")
    for cat in fltr.get("categories", []):
        lines.append(f"{_indent(level + 1)}<category {_attr('name', cat)}/>")
    lines.append(f"{_indent(level)}</intent-filter>")
    return lines


def build_main_manifest(registry: dict) -> str:
    perms = registry["permissions"]
    max_sdk = registry["flagship_usage"]["max_sdk_version"]
    sdk23 = set(registry["flagship_usage"]["uses_permission_sdk_23"])
    prov = registry["provenance"]
    sha_short = prov["snapshot_sha256"][:12]
    seed = 20261022
    out: list[str] = []
    add = out.append

    add('<?xml version="1.0" encoding="utf-8"?>')
    add(f'<!-- Gerado por tools/gen-flagship-manifest.py (seed {seed}, registry '
        f'AOSP sha256 {sha_short}). NAO editar a mao: regenere com '
        f'"python3 tools/gen-flagship-manifest.py" no modo integracao. -->')
    add('<manifest')
    add('    xmlns:android="http://schemas.android.com/apk/res/android">')

    # ---- permissoes custom -------------------------------------------------
    add("")
    add("    <!-- Permissoes custom da suite (namespace dev.apktester.behemoth) -->")
    for perm in CUSTOM_PERMS:
        add(f'    <permission {_attr("name", perm["name"])} '
            f'{_attr("protectionLevel", perm["protection_level"])}/>')
    add(f'    <permission-group {_attr("name", CUSTOM_GROUP)}/>')
    add(f'    <permission-tree {_attr("name", CUSTOM_TREE)}/>')

    # ---- uses-permission (snapshot verbatim) -------------------------------
    add("")
    add(f"    <!-- {len(perms)} permissoes de plataforma (snapshot verbatim do "
        f"AOSP master, sha {sha_short}) + maxSdkVersion das deprecadas -->")
    for entry in perms:
        name = entry["name"]
        attrs = _attr("name", name)
        if name in max_sdk:
            attrs += f' {_attr("maxSdkVersion", max_sdk[name])}'
        add(f'    <uses-permission {attrs}/>')
    add(f'    <!-- {len(sdk23)} via uses-permission-sdk-23 (so API 23+) -->')
    for name in sorted(sdk23):
        add(f'    <uses-permission-sdk-23 {_attr("name", name)}/>')

    # ---- features / telas / gl / libs --------------------------------------
    add("")
    add("    <!-- uses-feature: 3 required + glEsVersion 0x00030002 + opcionais -->")
    for name, required, version in USES_FEATURES:
        if name is None:
            add(f'    <uses-feature {_attr("glEsVersion", version)} '
                f'{_attr("required", "true")}/>')
            continue
        attrs = f'{_attr("name", name)} {_attr("required", str(required).lower())}'
        if version:
            attrs += f' {_attr("version", version)}'
        add(f'    <uses-feature {attrs}/>')
    add('    <uses-configuration android:reqTouchScreen="finger"/>')
    add('    <uses-configuration android:reqFiveWayNav="true" '
        'android:reqKeyboardType="qwerty"/>')
    add('    <supports-screens android:anyDensity="true" android:largeScreens="true" '
        'android:normalScreens="true" android:resizeable="true" '
        'android:smallScreens="true" android:xlargeScreens="true"/>')
    add("    <compatible-screens>")
    for size, dens in (("small", "ldpi"), ("normal", "hdpi"),
                       ("large", "xhdpi"), ("xlarge", "xxhdpi")):
        add(f'        <screen {_attr("screenSize", size)} {_attr("screenDensity", dens)}/>')
    add("    </compatible-screens>")
    for tex in SUPPORTS_GL_TEXTURES:
        add(f'    <supports-gl-texture {_attr("name", tex)}/>')

    # ---- queries ------------------------------------------------------------
    add("")
    add(f"    <!-- queries: {len(QUERIES_PACKAGES)} packages + "
        f"{len(QUERIES_INTENTS)} intents (visibilidade de pacotes, API 30+) -->")
    add("    <queries>")
    for pkg in QUERIES_PACKAGES:
        add(f'        <package {_attr("name", pkg)}/>')
    for action, scheme, mime in QUERIES_INTENTS:
        add("        <intent>")
        add(f'            <action {_attr("name", action)}/>')
        if scheme:
            add(f'            <data {_attr("scheme", scheme)}/>')
        if mime:
            add(f'            <data {_attr("mimeType", mime)}/>')
        add("        </intent>")
    add("    </queries>")

    # ---- application ---------------------------------------------------------
    add("")
    add("    <!-- Superficie maxima documentada em contracts/flagship/manifest-audit.md -->")
    add("    <application")
    add(f'        {_attr("name", ".BehemothApp")}')
    add(f'        {_attr("allowBackup", "true")}')
    add(f'        {_attr("fullBackupContent", "@xml/backup_rules")}')
    add(f'        {_attr("dataExtractionRules", "@xml/data_extraction_rules")}')
    add(f'        {_attr("networkSecurityConfig", "@xml/network_security_config")}')
    add(f'        {_attr("localeConfig", "@xml/locales_config")}')
    add(f'        {_attr("hardwareAccelerated", "true")}')
    add(f'        {_attr("supportsRtl", "true")}')
    add(f'        {_attr("label", "@string/app_name")}')
    add(f'        {_attr("icon", "@mipmap/ic_launcher")}')
    add(f'        {_attr("roundIcon", "@mipmap/ic_launcher_round")}')
    add(f'        {_attr("theme", "@style/Theme.Behemoth")}')
    add('        android:usesCleartextTraffic="false">')
    add("        <!-- CONFLITO DELIBERADO (auditado): networkSecurityConfig permite "
        "cleartext para 10.0.0.1 enquanto usesCleartextTraffic=false — o RustyDroid "
        "deve reportar a divergencia em vez de crashar -->")
    for lib, required in USES_NATIVE_LIBS:
        add(f'        <uses-native-library {_attr("name", lib)} '
            f'{_attr("required", str(required).lower())}/>')

    for act in ACTIVITIES:
        add(f'        <activity {_attr("name", act["class"])} '
            f'{_attr("label", act["label"])} '
            f'{_attr("exported", str(act["exported"]).lower())}>')
        for fltr in act["filters"]:
            out.extend(_filter_xml(fltr, 12))
        add("        </activity>")

    for alias in ACTIVITY_ALIASES:
        add(f'        <activity-alias {_attr("name", alias["class"])} '
            f'{_attr("targetActivity", alias["target"])} '
            f'{_attr("label", "@string/app_name")} '
            f'{_attr("icon", alias["icon"])} '
            f'{_attr("enabled", str(alias["enabled"]).lower())} '
            f'{_attr("exported", str(alias["exported"]).lower())}>')
        if alias["launcher_filter"]:
            out.extend(_filter_xml(
                {"action": "android.intent.action.MAIN",
                 "categories": ["android.intent.category.LAUNCHER"]}, 12))
        add("        </activity-alias>")

    for cls, guard, action, meta, exported in SERVICES:
        attrs = f'{_attr("name", cls)} {_attr("exported", str(exported).lower())}'
        if cls == ".services.ForegroundStub":
            # Flags validas do atributo foregroundServiceType (aapt2 API 36):
            # camera, connectedDevice, dataSync, health, location, mediaPlayback,
            # mediaProcessing, mediaProjection, microphone, phoneCall,
            # remoteMessaging, shortService, specialUse, systemExempted.
            # NOTA: a PERMISSAO da plataforma e FOREGROUND_SERVICE_SYSTEM_EXPERIMENTS,
            # mas o FLAG do manifesto e systemExempted (nomes divergem no AOSP).
            fgs_types = ("dataSync|mediaPlayback|location|camera|microphone|"
                         "phoneCall|connectedDevice|mediaProjection|"
                         "remoteMessaging|shortService|specialUse|health|"
                         "systemExempted|mediaProcessing")
            attrs += f' {_attr("foregroundServiceType", fgs_types)}'
        if guard:
            attrs += f' {_attr("permission", guard)}'
        if action:
            add(f'        <service {attrs}>')
            out.extend(_filter_xml({"action": action}, 12))
            if meta:
                add(f'            <meta-data {_attr("name", meta[0])} '
                    f'{_attr("resource", meta[1])}/>')
            add("        </service>")
        else:
            add(f'        <service {attrs}/>')
        if cls == ".services.ForegroundStub":
            add(f'        <property {_attr("name", "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE")} '
                f'{_attr("value", "apktester-fgs-stress")}/>')

    for cls, filters, exported in RECEIVERS:
        add(f'        <receiver {_attr("name", cls)} '
            f'{_attr("exported", str(exported).lower())}>')
        for action, scheme in filters:
            fltr = {"action": action}
            if scheme:
                fltr["data_scheme"] = scheme
            out.extend(_filter_xml(fltr, 12))
        add("        </receiver>")

    for widget in WIDGETS:
        add(f'        <receiver {_attr("name", widget["class"])} '
            f'{_attr("label", widget["label"])} {_attr("exported", "true")}>')
        out.extend(_filter_xml(
            {"action": "android.appwidget.action.APPWIDGET_UPDATE"}, 12))
        add(f'            <meta-data {_attr("name", "android.appwidget.provider")} '
            f'{_attr("resource", widget["meta"])}/>')
        add("        </receiver>")

    for prov_entry in PROVIDERS:
        attrs = (f'{_attr("name", prov_entry["class"])} '
                 f'{_attr("authorities", prov_entry["authorities"])} '
                 f'{_attr("exported", str(prov_entry["exported"]).lower())}')
        if prov_entry["grant_uri_permissions"]:
            attrs += ' android:grantUriPermissions="true"'
        if prov_entry["read_permission"]:
            attrs += f' {_attr("readPermission", prov_entry["read_permission"])}'
        if prov_entry["write_permission"]:
            attrs += f' {_attr("writePermission", prov_entry["write_permission"])}'
        add(f'        <provider {attrs}/>')
    add("    </application>")

    instr = INSTRUMENTATION
    add("")
    add(f'    <instrumentation {_attr("name", instr["class"])} '
        f'{_attr("targetPackage", instr["target_package"])} '
        f'{_attr("functionalTest", str(instr["functional_test"]).lower())} '
        f'{_attr("handleProfiling", str(instr["handle_profiling"]).lower())}/>')
    add("</manifest>")
    return "\n".join(out) + "\n"


def build_classic_overlay() -> str:
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- Gerado por tools/gen-flagship-manifest.py — overlay do flavor classic.',
        '     sharedUserId SO no classic (spec do flagship). O atributo',
        '     extractNativeLibs/useLegacyPackaging e controlado pelo AGP 8 no build',
        '     (nao no manifesto) e chega junto das libs nativas no marco A4.',
        '     NAO editar a mao: regenere. -->',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
        f'    android:sharedUserId="{SHARED_USER_ID}">',
        '</manifest>',
    ]) + "\n"


def build_modern_overlay() -> str:
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- Gerado por tools/gen-flagship-manifest.py — overlay do flavor modern',
        '     (minSdk 26). Em A1 nao adiciona atributos: androidx/compose chegam em',
        '     A5/A6. Mantido como ponto de mergulho do merger. NAO editar a mao. -->',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
        '</manifest>',
    ]) + "\n"


def build_assets_registry(registry: dict) -> str:
    max_sdk = registry["flagship_usage"]["max_sdk_version"]
    perms = []
    for entry in registry["permissions"]:
        perms.append({
            "name": entry["name"],
            "protection_level": entry["protection_level"],
            "base_level": entry["base_level"],
            "group": entry["group"],
            "max_sdk_version": max_sdk.get(entry["name"]),
            "hide": entry["hide"],
        })
    doc = {
        "schema_version": 1,
        "application_id": APPLICATION_ID,
        "version_name": VERSION_NAME,
        "version_code": VERSION_CODE,
        "generated_by": "tools/gen-flagship-manifest.py",
        "source_snapshot_sha256": registry["provenance"]["snapshot_sha256"],
        "counts": registry["counts"],
        "permissions": perms,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_assets_tsv(registry: dict) -> str:
    """Formato simples para o PermissionsHub: TSV parseavel com String.split
    no API 9 (sem org.json/JsonReader, que sao API 11+ no framework)."""
    max_sdk = registry["flagship_usage"]["max_sdk_version"]
    lines = ["# name<TAB>base_level<TAB>group<TAB>maxSdkVersion<TAB>hide",
             f"# gerado por tools/gen-flagship-manifest.py; snapshot AOSP "
             f"sha256 {registry['provenance']['snapshot_sha256']}"]
    for entry in registry["permissions"]:
        lines.append("\t".join([
            entry["name"],
            entry["base_level"],
            entry["group"],
            str(max_sdk.get(entry["name"], "")),
            "hide" if entry["hide"] else "public",
        ]))
    return "\n".join(lines) + "\n"


def build_gen_manifest(outputs: dict, registry: dict) -> str:
    """Ledger de integridade: sha256 de cada arquivo gerado.

    Convencao do repositorio (bot/checks/determinism.py): todo gen-*.py grava
    um manifest.json com entradas artifacts [{path, sha256}]. Fica versionado
    em contracts/flagship/ ao lado dos answer keys.
    """
    doc = {
        "tool": "tools/gen-flagship-manifest.py",
        "seed": 20261022,
        "registry_snapshot_sha256": registry["provenance"]["snapshot_sha256"],
        "note": "gerado; NAO editar a mao — regenere com a ferramenta",
        "artifacts": [
            {"path": rel,
             "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
            for rel, text in sorted(outputs.items())
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _md_cell(text: str) -> str:
    return str(text).replace("|", "\\|")


def build_permissions_audit(registry: dict) -> str:
    perms = registry["permissions"]
    max_sdk = registry["flagship_usage"]["max_sdk_version"]
    sdk23 = sorted(registry["flagship_usage"]["uses_permission_sdk_23"])
    by_level = registry["counts"]["by_base_level"]
    by_group = registry["counts"]["by_group"]
    prov = registry["provenance"]
    total = len(perms)
    hide_count = sum(1 for e in perms if e["hide"])
    lines: list[str] = []
    add = lines.append

    add("# Permissions Audit — flagship \"Behemoth\" (dev.apktester.behemoth)")
    add("")
    add("STATUS: **preenchida em A1** — answer key das permissoes declaradas pelo")
    add("flagship, gerada por `tools/gen-flagship-manifest.py` a partir do registry")
    add("canonico `contracts/flagship/permissions-registry.json` (snapshot verbatim")
    add("do `frameworks/base/core/res/AndroidManifest.xml` do AOSP master,")
    add(f"sha256 `{prov['snapshot_sha256']}`, capturado em {prov['snapshot_utc']}).")
    add("")
    add("## Metodologia")
    add("")
    add("1. **Verbatim, nao estimativa.** A lista de permissoes E o snapshot AOSP:")
    add(f"   {total} strings `android.permission.*` definidas no manifesto da")
    add("   plataforma — incluindo `@hide`/internas (as ~160 citadas no master")
    add("   prompt sao o subconjunto publicamente documentado; o manifesto real")
    add("   define mais. O APKBot (bot/checks/permission_drift.py) compara esta")
    add("   tabela contra o AOSP ao vivo: declarar menos geraria ruido permanente.")
    add("2. **protectionLevel verbatim** — a string completa do AOSP com flags")
    add("   (`signature|privileged|instant`, `dangerous|runtime`, ...). As")
    add("   contagens agregam pelo token base.")
    add("3. **Grupos de runtime** — o manifesto AOSP master nao declara")
    add("   `android:group` nas `<permission>` (grupos vivem no")
    add("   PermissionController); o grupo das `dangerous` vem do mapa curado")
    add("   `DANGEROUS_GROUPS` da ferramenta de snapshot (doc API 33-36).")
    add("4. **Flag @hide** — heuristica de comentario: `@hide` no bloco de")
    add("   comentario imediatamente anterior a declaracao.")
    add("5. **maxSdkVersion** — nao existe nas `<permission>` AOSP; o valor e da")
    add("   `<uses-permission>` do flagship (tabela curada de variantes")
    add("   deprecadas, ver secao abaixo).")
    add("")
    add("## Contagens por protectionLevel (token base)")
    add("")
    add("| protectionLevel (base) | contagem |")
    add("|------------------------|----------|")
    for level in sorted(by_level):
        add(f"| {level} | {by_level[level]} |")
    add(f"| **total** | **{total}** |")
    add("")
    add("Nota: `signatureOrSystem` (legacy) nao ocorre mais no manifesto master —")
    add("foi substituido por `signature|privileged`. Os niveis `internal`,")
    add("`role`, `system` e `module` sao niveis internos da plataforma e entram")
    add("no answer key tal como o RustyDroid os encontra.")
    add("")
    add("## Contagens por grupo de runtime (somente dangerous)")
    add("")
    add("| grupo | contagem |")
    add("|-------|----------|")
    for group in sorted(by_group):
        add(f"| {group} | {by_group[group]} |")
    add(f"| (sem grupo) | {42 - sum(by_group.values())} |")
    add("")
    add("`READ_CELL_BROADCASTS` e `dangerous` sem grupo de runtime no")
    add("PermissionController — excecao documentada no mapa curado.")
    add("")
    add("## Flag @hide")
    add("")
    add(f"{hide_count} de {total} permissoes marcadas como `@hide`/internas")
    add(f"({hide_count * 100 // total}% do total). Permissoes signature/@hide sao")
    add("inobtiveis em device real: o flagship testa a **classificacao** do")
    add("permission engine do RustyDroid, nao instalabilidade (hard-truth do")
    add("master prompt).")
    add("")
    add("## maxSdkVersion (uses-permission deprecadas)")
    add("")
    add("| permissao | maxSdkVersion |")
    add("|-----------|---------------|")
    for name in sorted(max_sdk):
        add(f"| {name} | {max_sdk[name]} |")
    add("")
    add("## uses-permission-sdk-23 (declaradas so para API 23+)")
    add("")
    for name in sdk23:
        add(f"- `{name}`")
    add("")
    add("## Permissoes custom da suite")
    add("")
    add("| name | protectionLevel | papel |")
    add("|------|-----------------|-------|")
    for perm in CUSTOM_PERMS:
        add(f"| {perm['name']} | {perm['protection_level']} | {perm['note']} |")
    add(f"| {CUSTOM_GROUP} | permission-group | agrupamento custom |")
    add(f"| {CUSTOM_TREE} | permission-tree | arvore de permissoes dinamicas |")
    add("")
    add("## Definicoes nao-plataforma no snapshot (12)")
    add("")
    add("Definicoes `com.android.*` / `android.intent.category.*` presentes no")
    add("manifesto AOSP (nao entram na tabela canonica nem nas contagens de")
    add("plataforma; o flagship NAO as declara — sao registro de proveniencia):")
    add("")
    add("| name | protectionLevel |")
    add("|------|-----------------|")
    for entry in registry["non_platform_definitions"]:
        add(f"| {entry['name']} | {_md_cell(entry['protection_level'])} |")
    add("")
    add("## Tabela canonica (ordem alfabetica)")
    add("")
    add("Colunas: name | protectionLevel (verbatim) | group | maxSdkVersion | @hide.")
    add("")
    add("| name | protectionLevel | group | maxSdkVersion | @hide |")
    add("|------|-----------------|-------|---------------|-------|")
    for entry in perms:
        add(f"| {entry['name']} | {_md_cell(entry['protection_level'])} | "
            f"{_md_cell(entry['group'])} | {max_sdk.get(entry['name'], '')} | "
            f"{'sim' if entry['hide'] else 'nao'} |")
    add("")
    add("## Regras duras")
    add("")
    add("1. Permissoes signature/`@hide` sao inobtiveis em device real — o")
    add("   flagship testa a classificacao, nao instalabilidade.")
    add("2. **Strings inventadas NUNCA entram aqui.** Permissoes inexistentes/fake")
    add("   vivem exclusivamente em `suites/parser-torture/unknown-perms/`.")
    add("3. O diff entre `rustydroid inspect --json` e esta tabela deve ser")
    add("   zero-drift (contagem por nivel, grupo por permissao, maxSdk e flag")
    add("   @hide).")
    add("4. AOSP master evolve todo dia: divergencias apontadas pelo APKBot")
    add("   (`permission_drift`) sao resolvidas re-executando")
    add("   `tools/snapshot-aosp-permissions.py` + este gerador.")
    return "\n".join(lines) + "\n"


def build_manifest_audit(registry: dict) -> str:
    perms = registry["permissions"]
    max_sdk = registry["flagship_usage"]["max_sdk_version"]
    sdk23 = sorted(registry["flagship_usage"]["uses_permission_sdk_23"])
    lines: list[str] = []
    add = lines.append

    add("# Manifest Audit — flagship \"Behemoth\" (dev.apktester.behemoth)")
    add("")
    add("STATUS: **A1 — esqueleto completo, todo componente declarado tem classe")
    add("real**. Este documento e o answer key do `rustydroid inspect --json` para")
    add("o manifesto do flagship (CORE-12: manifest-as-truth). Gerado por")
    add("`tools/gen-flagship-manifest.py` — manifesto e auditoria saem da mesma")
    add("tabela de componentes (zero drift por construcao). A superficie final")
    add("(30+ activities por dominio, aliases r3..r8, AIDL, mais widgets) chega")
    add("nos marcos A5/A6 — os valores-alvo fixos de cada secao continuam")
    add("contratuais na coluna `alvo`.")
    add("")
    add("## Identidade")
    add("")
    add("| campo | valor |")
    add("|-------|-------|")
    add(f"| applicationId | `{APPLICATION_ID}` |")
    add(f"| versionName | `{VERSION_NAME}` |")
    add(f"| versionCode | `{VERSION_CODE}` |")
    add("| minSdk | 9 (classic) / 26 (modern) |")
    add("| targetSdk | 36 |")
    add("| sharedUserId | `dev.apktester.behemoth` — **somente** flavor classic |")
    add("| extractNativeLibs | atributo removido do manifesto (regra AGP 8); `useLegacyPackaging` por flavor entra com as libs nativas no marco A4 |")
    add("")
    add("## Permissoes")
    add("")
    add("| item | contagem |")
    add("|------|----------|")
    add(f"| uses-permission (plataforma, snapshot verbatim) | {len(perms)} |")
    add(f"| uses-permission com maxSdkVersion | {len(max_sdk)} |")
    add(f"| uses-permission-sdk-23 | {len(sdk23)} |")
    add(f"| permission custom | {len(CUSTOM_PERMS)} (normal + signature) |")
    add("| permission-group custom | 1 |")
    add("| permission-tree custom | 1 |")
    add("")
    add("Answer key detalhado: contracts/flagship/permissions-audit.md.")
    add("")
    add("## Activities")
    add("")
    add("| classe | label | exported | intent-filters | status |")
    add("|--------|-------|----------|----------------|--------|")
    for act in ACTIVITIES:
        filters = "; ".join(f["action"] for f in act["filters"]) or "—"
        extra = " (https autoVerify)" if any(f.get("auto_verify") for f in act["filters"]) else ""
        add(f"| {act['class']} | {act['label']} | {str(act['exported']).lower()} | "
            f"{len(act['filters'])} filter(s){extra}: {filters} | A1 |")
    add(f"**atual: {len(ACTIVITIES)} — alvo: >= 30 (uma por dominio, incl. telas 3D/Shaders/GLES em A5/A6)**")
    add("")
    add("### Activity-aliases (2)")
    add("")
    add("| classe | target | icone | enabled | launcher | nota |")
    add("|--------|--------|-------|---------|----------|------|")
    for alias in ACTIVITY_ALIASES:
        add(f"| {alias['class']} | {alias['target']} | {alias['icon']} | "
            f"{str(alias['enabled']).lower()} | "
            f"{'sim' if alias['launcher_filter'] else 'nao'} | {alias['note']} |")
    add("Alvo final: 8 aliases (r1..r8 com icones do gen-icons).")
    add("")
    add("## Services")
    add("")
    add("| classe | guard (permission) | intent-filter | exported | status |")
    add("|--------|--------------------|---------------|----------|--------|")
    for cls, guard, action, _meta, exported in SERVICES:
        add(f"| {cls} | {guard or '—'} | {action or '—'} | "
            f"{str(exported).lower()} | A1 |")
    add(f"**atual: {len(SERVICES)} — alvo: >= 15 (AIDL + Messenger bound; foreground com TODOS os types declarados)**")
    add("")
    add("### Servicos de sistema (15 <service> + DeviceAdminReceiver = 16)")
    add("")
    add("| servico | classe base | BIND_* |")
    add("|---------|-------------|--------|")
    system_map = [
        ("Accessibility", "AccessibilityService", "android.permission.BIND_ACCESSIBILITY_SERVICE"),
        ("NotificationListener", "NotificationListenerService", "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"),
        ("InputMethod (IME)", "InputMethodService", "android.permission.BIND_INPUT_METHOD"),
        ("DeviceAdmin (receiver)", "DeviceAdminReceiver", "android.permission.BIND_DEVICE_ADMIN"),
        ("VoiceInteraction", "VoiceInteractionService", "android.permission.BIND_VOICE_INTERACTION"),
        ("CallScreening", "CallScreeningService", "android.permission.BIND_SCREENING_SERVICE"),
        ("Telecom (InCall)", "InCallService", "android.permission.BIND_INCALL_SERVICE"),
        ("Print", "PrintService", "android.permission.BIND_PRINT_SERVICE"),
        ("Autofill", "AutofillService", "android.permission.BIND_AUTOFILL_SERVICE"),
        ("Tile", "TileService", "android.permission.BIND_QUICK_SETTINGS_TILE"),
        ("HostApdu", "HostApduService", "android.permission.BIND_NFC_SERVICE"),
        ("MediaBrowser", "MediaBrowserService", "android.permission.BIND_MEDIA_BROWSER_SERVICE"),
        ("Wallpaper", "WallpaperService", "android.permission.BIND_WALLPAPER"),
        ("Dream", "DreamService", "android.permission.BIND_DREAM_SERVICE"),
        ("Vpn", "VpnService", "android.permission.BIND_VPN_SERVICE"),
        ("Credential", "CredentialProviderService", "android.permission.BIND_CREDENTIALS_SERVICE"),
    ]
    for svc, base, bind in system_map:
        add(f"| {svc} | {base} | {bind} |")
    add("")
    add("ForegroundStub declara TODOS os 14 foregroundServiceType (dataSync,")
    add("mediaPlayback, location, camera, microphone, phoneCall, connectedDevice,")
    add("mediaProjection, remoteMessaging, shortService, specialUse, health,")
    add("systemExempted, mediaProcessing) + property")
    add("`android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE`. O nome do flag")
    add("systemExempted diverge da permissao FOREGROUND_SERVICE_SYSTEM_EXPERIMENTS")
    add("(divergencia do proprio AOSP, documentada aqui).")
    add("")
    add("## Receivers (10)")
    add("")
    add("| classe | actions | exported | status |")
    add("|--------|---------|----------|--------|")
    for cls, filters, exported in RECEIVERS:
        actions = "; ".join(a for a, _s in filters)
        add(f"| {cls} | {actions} | {str(exported).lower()} | A1 |")
    add("")
    add("## Providers (2)")
    add("")
    add("| classe | authorities | exported | readPermission | writePermission | nota |")
    add("|--------|-------------|----------|----------------|-----------------|------|")
    for prov_entry in PROVIDERS:
        add(f"| {prov_entry['class']} | {prov_entry['authorities']} | "
            f"{str(prov_entry['exported']).lower()} | "
            f"{prov_entry['read_permission'] or '—'} | "
            f"{prov_entry['write_permission'] or '—'} | {prov_entry['note']} |")
    add("")
    add("Nota do master prompt menciona FileProvider (androidx): entra no flavor")
    add("modern junto do resto do androidx (A5/A6). Os 3 providers sao")
    add("framework-only para o classic compilar limpo (GuardedNormalProvider")
    add("entrou na A9/roadmap 3.6: CUSTOM_NORMAL deixou de ser orfa).")
    add("")
    add("## Widgets (2)")
    add("")
    add("| classe | meta-data | label | status |")
    add("|--------|-----------|-------|--------|")
    for widget in WIDGETS:
        add(f"| {widget['class']} | {widget['meta']} | {widget['label']} | A1 |")
    add("")
    add("## Instrumentation (1)")
    add("")
    add(f"- `{INSTRUMENTATION['class']}` targetPackage `{INSTRUMENTATION['target_package']}` "
        "functionalTest=true handleProfiling=false")
    add("")
    add("## Queries / features / telas")
    add("")
    add("| item | valor |")
    add("|------|-------|")
    add(f"| queries | 1 bloco: {len(QUERIES_PACKAGES)} packages + {len(QUERIES_INTENTS)} intents |")
    add("| uses-feature required | 3 (camera, microphone, sensor.compass) |")
    add("| glEsVersion | 0x00030002 (required) |")
    add(f"| uses-feature opcionais | {sum(1 for n, r, _v in USES_FEATURES if n and not r)} "
        "(gps, network location, BLE, NFC, telephony, wifi, gyroscope, type.pc, leanback, app_widgets, device_admin, vulkan.version 0x401000) |")
    add("| uses-configuration | 2 (touchscreen finger; fiveWayNav + qwerty) |")
    add("| supports-screens | any/large/normal/small/xlarge + resizeable |")
    add("| compatible-screens | 4 (small/ldpi, normal/hdpi, large/xhdpi, xlarge/xxhdpi) |")
    add(f"| supports-gl-texture | {len(SUPPORTS_GL_TEXTURES)} |")
    add(f"| uses-native-library | {len(USES_NATIVE_LIBS)} dentro de <application> (libEGL.so, libOpenSLES.so opcionais; libc.so required) |")
    add("")
    add("### Deep links")
    add("")
    add("| scheme | host/path | autoVerify | classe |")
    add("|--------|-----------|------------|--------|")
    add("| https | maxprobe.dev/apktester | sim | .MainActivity |")
    add("| maxprobe | — | nao | .ProbeReportActivity |")
    add("| geo / tel / sms / mailto / market | — | nao | .ProbeReportActivity |")
    add("")
    add("## Configs de backup/rede/locales (conflito deliberado)")
    add("")
    add("- `android:networkSecurityConfig` -> @xml/network_security_config (permite")
    add("  cleartext APENAS para 10.0.0.1)")
    add("- `android:usesCleartextTraffic=\"false\"` no <application> — **conflito")
    add("  deliberado** com a NSC acima: o RustyDroid deve reportar a divergencia")
    add("  (erro estruturado), nunca crashar.")
    add("- `android:dataExtractionRules` (API 31+) + `android:fullBackupContent`")
    add("  (legacy) -> @xml/data_extraction_rules / @xml/backup_rules")
    add("- `android:localeConfig` (API 33) -> @xml/locales_config (12 locales do")
    add("  gen-strings)")
    add("- `android:extractNativeLibs`: NAO declarado — o AGP 8 proibe o atributo no")
    add("  manifesto-fonte; o empacotamento de libs nativas (useLegacyPackaging)")
    add("  sera definido por flavor no build.gradle quando :native/:rust")
    add("  existirem (A4)")
    add("")
    add("## RustyDroid — diff esperado")
    add("")
    add("`rustydroid inspect --json` sobre o flagship deve reproduzir: contagens")
    add("deste documento, a tabela canonica de permissions-audit.md (zero drift),")
    add("os 2 aliases, os 16 servicos de sistema com seus BIND_*, o conflito de")
    add("cleartext documentado e sharedUserId SO no flavor classic.")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ generate
GENERATED_FILES = [
    "suites/flagship/AndroidManifest.xml",
    "suites/flagship/app/src/main/AndroidManifest.xml",
    "suites/flagship/app/src/classic/AndroidManifest.xml",
    "suites/flagship/app/src/modern/AndroidManifest.xml",
    "contracts/flagship/permissions-audit.md",
    "contracts/flagship/manifest-audit.md",
    "suites/flagship/app/src/main/assets/permissions/registry.json",
    "suites/flagship/app/src/main/assets/permissions/permissions.tsv",
    "contracts/flagship/manifest.json",
]


def generate(out_dir: Path) -> dict:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    main_xml = build_main_manifest(registry)
    outputs = {
        "suites/flagship/AndroidManifest.xml": main_xml,
        "suites/flagship/app/src/main/AndroidManifest.xml": main_xml,
        "suites/flagship/app/src/classic/AndroidManifest.xml": build_classic_overlay(),
        "suites/flagship/app/src/modern/AndroidManifest.xml": build_modern_overlay(),
        "contracts/flagship/permissions-audit.md": build_permissions_audit(registry),
        "contracts/flagship/manifest-audit.md": build_manifest_audit(registry),
        "suites/flagship/app/src/main/assets/permissions/registry.json":
            build_assets_registry(registry),
        "suites/flagship/app/src/main/assets/permissions/permissions.tsv":
            build_assets_tsv(registry),
    }
    outputs["contracts/flagship/manifest.json"] = build_gen_manifest(
        outputs, registry)
    for rel, text in outputs.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {"registry": registry, "outputs": outputs}


def run_selftest() -> int:
    import re
    import xml.etree.ElementTree as ET

    with tempfile.TemporaryDirectory() as tmp:
        a = generate(Path(tmp) / "a")
        generate(Path(tmp) / "b")
        for rel, text in a["outputs"].items():
            assert (Path(tmp) / "a" / rel).read_text(encoding="utf-8") == text
            assert (Path(tmp) / "b" / rel).read_text(encoding="utf-8") == text, \
                f"determinismo quebrado: {rel}"

    registry = a["registry"]
    perms = registry["permissions"]
    platform_names = {e["name"] for e in perms}
    ns = "{http://schemas.android.com/apk/res/android}"

    root = ET.fromstring(a["outputs"]["suites/flagship/AndroidManifest.xml"])
    used = set()
    sdk23_used = set()
    for child in root:
        tag = child.tag.split("}")[-1]
        if tag == "uses-permission":
            used.add(child.attrib[f"{ns}name"])
        elif tag == "uses-permission-sdk-23":
            sdk23_used.add(child.attrib[f"{ns}name"])
    assert used == platform_names, (
        f"uses-permission != registry: faltam {len(platform_names - used)}, "
        f"sobram {len(used - platform_names)}")
    assert sdk23_used == set(registry["flagship_usage"]["uses_permission_sdk_23"])

    audit = a["outputs"]["contracts/flagship/permissions-audit.md"]
    rows = re.findall(r"^\|\s*(android\.permission\.[A-Z0-9_]+)\s*\|", audit, re.M)
    # A tabela de maxSdkVersion repete 9 nomes (linhas duplicadas sao
    # inofensivas: o APKBot compara CONJUNTOS — ver bot/checks/permission_drift.py).
    assert set(rows) == platform_names, (
        f"diferenca audit vs registry: {len(set(rows) ^ platform_names)} nomes")

    # Compatibilidade com o APKBot (regexes de bot/checks/permission_drift.py).
    uses_re = re.compile(
        r"<uses-permission(?:-sdk-23)?\s+[^>]*?"
        r'android:name\s*=\s*"([^"]+)"', re.S)
    declared = uses_re.findall(a["outputs"]["suites/flagship/AndroidManifest.xml"])
    plat_declared = {n for n in declared if n.startswith("android.permission.")}
    assert plat_declared <= platform_names

    assets = json.loads(
        a["outputs"]["suites/flagship/app/src/main/assets/permissions/registry.json"])
    assert len(assets["permissions"]) == len(perms)
    tsv = a["outputs"]["suites/flagship/app/src/main/assets/permissions/permissions.tsv"]
    tsv_rows = [line for line in tsv.splitlines()
                if line and not line.startswith("#")]
    assert len(tsv_rows) == len(perms)
    ledger = json.loads(a["outputs"]["contracts/flagship/manifest.json"])
    ledger_paths = {e["path"] for e in ledger["artifacts"]}
    assert ledger_paths == {rel for rel in a["outputs"] if rel != "contracts/flagship/manifest.json"}

    for rel in ("contracts/flagship/manifest-audit.md",):
        text = a["outputs"][rel]
        for cls, *_rest in SERVICES:
            assert cls in text, f"{cls} ausente em {rel}"
        for act in ACTIVITIES:
            assert act["class"] in text
        for alias in ACTIVITY_ALIASES:
            assert alias["class"] in text
    print(f"[gen-flagship-manifest] OK: {len(perms)} permissoes, "
          f"{len(ACTIVITIES)} activities + {len(ACTIVITY_ALIASES)} aliases, "
          f"{len(SERVICES)} services, {len(RECEIVERS)} receivers, "
          f"{len(PROVIDERS)} providers, {len(WIDGETS)} widgets; "
          f"determinismo e compatibilidade APKBot verificados")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera manifesto + auditorias do flagship Behemoth (A1).")
    parser.add_argument("--out", default=str(REPO_ROOT),
                        help="raiz onde os caminhos relativos sao gravados")
    parser.add_argument("--seed", type=int, default=20261022,
                        help="aceito por contrato de interface (nao altera a saida)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    out_dir = Path(args.out)
    result = generate(out_dir)
    total = len(result["outputs"])
    digest = hashlib.sha256(
        "".join(result["outputs"][k] for k in sorted(result["outputs"])).encode()
    ).hexdigest()
    print(f"[gen-flagship-manifest] {total} arquivos gravados sob {out_dir} "
          f"(sha256 conjunto {digest[:12]}, seed {args.seed} — saida "
          "independente de seed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
