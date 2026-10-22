#!/usr/bin/env python3
"""Ferramenta de PROVENIENCIA: snapshot das permissoes da plataforma AOSP.

Nao e um gerador gen-* (nao participa do loop de determinismo de
verify-deterministic.sh): e uma ferramenta de rede one-shot que captura o
``frameworks/base/core/res/AndroidManifest.xml`` do AOSP (branch master) e
destila o registry canonico de permissoes consumido por
``tools/gen-flagship-manifest.py``.

O QUE ELA EXTRAI (verificado contra o snapshot, nao contra estimativas):
  1. Definicoes ``<permission android:name="android.permission.*">`` — nome,
     protectionLevel VERBATIM (string completa com flags, ex.
     ``signature|privileged|instant``), token base (primeiro token) e flag
     ``@hide`` (heuristica de comentario: ``@hide`` presente no bloco de
     comentario imediatamente anterior a declaracao).
  2. Definicoes de outras namespaces (``com.android.*``,
     ``android.intent.category.*``) — secao separada "non_platform".
  3. Uso do flagship: maxSdkVersion para variantes deprecadas (tabela
     curada, documentada) e o conjunto ``uses-permission-sdk-23``.
  4. Grupos de runtime para as permissoes ``dangerous`` — mapa curado:
     o manifesto AOSP master NAO declara ``android:group`` nas
     ``<permission>`` (os grupos vivem no PermissionController); o mapa
     abaixo segue a documentacao da plataforma (API 33-36).

Por que o flagship declara TODAS (e nao so as ~160 documentadas): o
APKBot (bot/checks/permission_drift.py) compara a auditoria contra o
manifesto AOSP REAL — que define 1.000+ strings, incluindo @hide/internas.
Declarar so o subconjunto documentado geraria ruido permanente de
"permissao nova" a cada evolucao da plataforma.

Uso:
    python3 tools/snapshot-aosp-permissions.py                 # fetch + emitir
    python3 tools/snapshot-aosp-permissions.py --offline FILE  # reprocessar snapshot salvo
    python3 tools/snapshot-aosp-permissions.py --selftest      # fetch + verificacoes duras
"""

import argparse
import base64
import collections
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "contracts" / "flagship" / "permissions-registry.json"

SOURCE_URL = (
    "https://android.googlesource.com/platform/frameworks/base/+"
    "/refs/heads/main/core/res/AndroidManifest.xml?format=TEXT"
)
FALLBACK_URL = (
    "https://raw.githubusercontent.com/aosp-mirror/"
    "platform_frameworks_base/master/core/res/AndroidManifest.xml"
)

PLATFORM_PREFIX = "android.permission."

_TAG_PERMISSION_RE = re.compile(r"<permission\s([^>]*?)/?>", re.S)
_ATTR_NAME_RE = re.compile(r'android:name\s*=\s*"([^"]+)"')
_ATTR_LEVEL_RE = re.compile(r'android:protectionLevel\s*=\s*"([^"]+)"')
_ATTR_GROUP_RE = re.compile(r'android:group\s*=\s*"([^"]+)"')
_COMMENT_SPLIT_RE = re.compile(r"(?:-->|\*/)", re.S)

# Mapa curado: grupo de runtime das permissoes dangerous (doc API 33-36).
# O manifesto AOSP master nao declara android:group; este mapa e o answer
# key do grupo e vive versionado aqui (revisado a cada snapshot).
DANGEROUS_GROUPS = {
    "READ_CONTACTS": "CONTACTS",
    "WRITE_CONTACTS": "CONTACTS",
    "GET_ACCOUNTS": "CONTACTS",
    "READ_CALENDAR": "CALENDAR",
    "WRITE_CALENDAR": "CALENDAR",
    "SEND_SMS": "SMS",
    "RECEIVE_SMS": "SMS",
    "READ_SMS": "SMS",
    "RECEIVE_WAP_PUSH": "SMS",
    "RECEIVE_MMS": "SMS",
    "READ_EXTERNAL_STORAGE": "STORAGE",
    "WRITE_EXTERNAL_STORAGE": "STORAGE",
    "READ_MEDIA_AUDIO": "STORAGE",
    "READ_MEDIA_VIDEO": "STORAGE",
    "READ_MEDIA_IMAGES": "STORAGE",
    "READ_MEDIA_VISUAL_USER_SELECTED": "STORAGE",
    "ACCESS_MEDIA_LOCATION": "STORAGE",
    "ACCESS_FINE_LOCATION": "LOCATION",
    "ACCESS_COARSE_LOCATION": "LOCATION",
    "ACCESS_BACKGROUND_LOCATION": "LOCATION",
    "READ_CALL_LOG": "PHONE",
    "WRITE_CALL_LOG": "PHONE",
    "PROCESS_OUTGOING_CALLS": "PHONE",
    "READ_PHONE_STATE": "PHONE",
    "READ_PHONE_NUMBERS": "PHONE",
    "CALL_PHONE": "PHONE",
    "USE_SIP": "PHONE",
    "ANSWER_PHONE_CALLS": "PHONE",
    "ACCEPT_HANDOVER": "PHONE",
    "BODY_SENSORS": "SENSORS",
    "BODY_SENSORS_BACKGROUND": "SENSORS",
    "ACTIVITY_RECOGNITION": "SENSORS",
    "POST_NOTIFICATIONS": "NOTIFICATIONS",
    "BLUETOOTH_SCAN": "NEARBY_DEVICES",
    "BLUETOOTH_CONNECT": "NEARBY_DEVICES",
    "BLUETOOTH_ADVERTISE": "NEARBY_DEVICES",
    "UWB_RANGING": "NEARBY_DEVICES",
    "NEARBY_WIFI_DEVICES": "NEARBY_DEVICES",
    "RANGING": "NEARBY_DEVICES",
    "CAMERA": "CAMERA",
    "RECORD_AUDIO": "MICROPHONE",
    # READ_CELL_BROADCASTS: dangerous sem grupo de runtime no
    # PermissionController — fica com grupo vazio, documentado.
}

# maxSdkVersion das <uses-permission> deprecadas no flagship (plataforma
# documentada; o manifesto master nao usa maxSdkVersion nos self-uses).
FLAGSHIP_MAX_SDK = {
    "android.permission.GET_TASKS": 25,
    "android.permission.PROCESS_OUTGOING_CALLS": 28,
    "android.permission.USE_CREDENTIALS": 22,
    "android.permission.PERSISTENT_ACTIVITY": 15,
    "android.permission.READ_EXTERNAL_STORAGE": 32,
    "android.permission.WRITE_EXTERNAL_STORAGE": 32,
    "android.permission.USE_FINGERPRINT": 27,
    "android.permission.BLUETOOTH": 30,
    "android.permission.BLUETOOTH_ADMIN": 30,
}

# Conjunto emitido como <uses-permission-sdk-23> (so relevante em API 23+;
# o manifesto AOSP master nao usa o elemento — escolha documentada da suite).
FLAGSHIP_SDK23 = [
    "android.permission.GET_ACCOUNTS",
    "android.permission.USE_FINGERPRINT",
    "android.permission.READ_PHONE_NUMBERS",
]

HIDE_WINDOW_CHARS = 4000  # janela maxima do comentario anterior


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "apktester-snapshot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_manifest() -> tuple[bytes, str]:
    """(bytes do XML, url efetiva). Googlesource (base64) com fallback raw."""
    try:
        blob = fetch(SOURCE_URL)
        xml = base64.b64decode(blob, validate=True)
        if b"<manifest" in xml:
            return xml, SOURCE_URL
    except Exception:
        pass
    return fetch(FALLBACK_URL), FALLBACK_URL


def parse_manifest(xml_text: str) -> tuple[list[dict], list[dict]]:
    """(permissions de plataforma, non_platform) — verbatim do snapshot."""
    platform: list[dict] = []
    non_platform: list[dict] = []
    spans = list(_TAG_PERMISSION_RE.finditer(xml_text))
    prev_end = 0
    for match in spans:
        attrs = match.group(1)
        name_m = _ATTR_NAME_RE.search(attrs)
        if not name_m:
            continue
        name = name_m.group(1)
        level_m = _ATTR_LEVEL_RE.search(attrs)
        group_m = _ATTR_GROUP_RE.search(attrs)
        level = level_m.group(1) if level_m else ""
        # Heuristica @hide: comentario imediatamente anterior a declaracao.
        window = xml_text[prev_end:match.start()]
        prev_end = match.start()
        hide = False
        for chunk in _COMMENT_SPLIT_RE.split(window):
            if "@hide" in chunk:
                hide = True
        # Grupo curado apenas para dangerous de plataforma; senao o que o
        # proprio manifesto declara (hoje: vazio) ou vazio.
        short = name[len(PLATFORM_PREFIX):] if name.startswith(PLATFORM_PREFIX) else ""
        group = ""
        if short in DANGEROUS_GROUPS and level.split("|")[0] == "dangerous":
            group = DANGEROUS_GROUPS[short]
        elif group_m:
            group = group_m.group(1)
        entry = {
            "name": name,
            "protection_level": level,
            "base_level": level.split("|")[0] if level else "",
            "group": group,
            "hide": hide,
        }
        if name.startswith(PLATFORM_PREFIX):
            platform.append(entry)
        else:
            non_platform.append({"name": name, "protection_level": level})
    platform.sort(key=lambda e: e["name"])
    non_platform.sort(key=lambda e: e["name"])
    return platform, non_platform


def build_registry(xml: bytes, source_url: str) -> dict:
    xml_text = xml.decode("utf-8", "replace")
    platform_raw, non_platform = parse_manifest(xml_text)

    # Dedupe: o manifesto AOSP master pode declarar o MESMO nome duas vezes
    # (observado: 2 nomes com protectionLevel divergente entre declaracoes).
    # A tabela canonica fica unica (PRIMEIRA definicao vence); as duplicatas
    # sao preservadas verbatim em provenance.duplicate_definitions.
    seen: dict[str, dict] = {}
    duplicates: list[dict] = []
    for entry in platform_raw:
        name = entry["name"]
        if name in seen:
            dup = next(d for d in duplicates if d["name"] == name) \
                if any(d["name"] == name for d in duplicates) else None
            if dup is None:
                dup = {"name": name,
                       "protection_levels": [seen[name]["protection_level"]]}
                duplicates.append(dup)
            dup["protection_levels"].append(entry["protection_level"])
            continue
        seen[name] = entry
    platform = sorted(seen.values(), key=lambda e: e["name"])
    names = {e["name"] for e in platform}

    # Validacoes duras (snapshot incoerente nao entra no repo).
    assert len(platform) >= 900, f"snapshot suspeito: {len(platform)} permissoes"
    assert "android.permission.CAMERA" in names
    assert "android.permission.BIND_ACCESSIBILITY_SERVICE" in names
    dangerous = [e for e in platform if e["base_level"] == "dangerous"]
    # READ_CELL_BROADCASTS: dangerous sem grupo (excecao documentada).
    UNGROUPED_DANGEROUS = {"android.permission.READ_CELL_BROADCASTS"}
    for e in dangerous:
        short = e["name"][len(PLATFORM_PREFIX):]
        mapped = DANGEROUS_GROUPS.get(short)
        assert mapped is not None or e["name"] in UNGROUPED_DANGEROUS, (
            f"dangerous sem grupo no mapa curado: {e['name']}")
        if mapped:
            assert e["group"] == mapped, f"grupo divergente: {e['name']}"

    max_sdk = {k: v for k, v in FLAGSHIP_MAX_SDK.items() if k in names}
    sdk23 = [n for n in FLAGSHIP_SDK23 if n in names]
    missing_sdk23 = [n for n in FLAGSHIP_SDK23 if n not in names]
    assert not missing_sdk23, f"sdk-23 ausente no snapshot: {missing_sdk23}"

    by_level = collections.Counter(e["base_level"] for e in platform)
    by_group = collections.Counter(e["group"] for e in platform if e["group"])
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1,
        "description": (
            "Registry canonico de permissoes da plataforma (snapshot verbatim "
            "de frameworks/base/core/res/AndroidManifest.xml, AOSP master). "
            "Entrada de tools/gen-flagship-manifest.py; answer key do flagship. "
            "Strings inventadas NUNCA entram aqui (regra do repositorio)."),
        "provenance": {
            "tool": "tools/snapshot-aosp-permissions.py",
            "source_url": SOURCE_URL,
            "fallback_url": FALLBACK_URL,
            "effective_url": source_url,
            "branch": "master",
            "snapshot_sha256": __import__("hashlib").sha256(xml).hexdigest(),
            "snapshot_utc": now_utc,
            "manifest_bytes": len(xml),
            "duplicate_definitions": duplicates,
            "hide_heuristic": (
                "@hide presente no bloco de comentario imediatamente anterior "
                "a declaracao (janela de 4000 chars entre elementos)"),
            "group_methodology": (
                "o manifesto AOSP master nao declara android:group nas "
                "<permission>; grupos de runtime das dangerous seguem a "
                "documentacao da plataforma (API 33-36), mapa curado versionado "
                "nesta ferramenta (DANGEROUS_GROUPS)"),
        },
        "counts": {
            "platform": len(platform),
            "non_platform": len(non_platform),
            "by_base_level": dict(sorted(by_level.items())),
            "by_group": dict(sorted(by_group.items())),
        },
        "flagship_usage": {
            "max_sdk_version": dict(sorted(max_sdk.items())),
            "uses_permission_sdk_23": sorted(sdk23),
        },
        "permissions": platform,
        "non_platform_definitions": non_platform,
    }


def run_selftest() -> int:
    xml, url = fetch_manifest()
    reg = build_registry(xml, url)
    p = reg["permissions"]
    assert reg["counts"]["platform"] == len(p)
    camera = next(e for e in p if e["name"] == "android.permission.CAMERA")
    assert camera["base_level"] == "dangerous" and camera["group"] == "CAMERA"
    assert not camera["hide"]
    brick = next(e for e in p if e["name"] == "android.permission.BRICK")
    assert brick["hide"], "BRICK deveria ser detectado como @hide"
    fst = next(e for e in p if e["name"] == "android.permission.FORCE_STOP_PACKAGES")
    assert fst["hide"]
    pn = next(e for e in p if e["name"] == "android.permission.POST_NOTIFICATIONS")
    assert pn["base_level"] == "dangerous" and pn["group"] == "NOTIFICATIONS"
    groups = set(reg["counts"]["by_group"])
    expected_groups = {
        "CALENDAR", "CAMERA", "CONTACTS", "LOCATION", "MICROPHONE", "PHONE",
        "SMS", "SENSORS", "STORAGE", "NEARBY_DEVICES", "NOTIFICATIONS",
    }
    assert expected_groups.issubset(groups), f"grupos faltando: {expected_groups - groups}"
    print(f"[snapshot-aosp] OK: {len(p)} permissoes de plataforma, "
          f"{reg['counts']['non_platform']} nao-plataforma; "
          f"niveis={reg['counts']['by_base_level']}; "
          f"sha256={reg['provenance']['snapshot_sha256'][:12]}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot AOSP -> contracts/flagship/permissions-registry.json")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="caminho de saida do registry JSON")
    parser.add_argument("--offline", default=None,
                        help="processar snapshot salvo em FILE (sem rede)")
    parser.add_argument("--selftest", action="store_true",
                        help="fetch + verificacoes duras (nao grava)")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if args.offline:
        xml = Path(args.offline).read_bytes()
        effective = f"offline:{args.offline}"
    else:
        xml, effective = fetch_manifest()
        print(f"[snapshot-aosp] fetch ok: {len(xml)} bytes via {effective}")
    registry = build_registry(xml, effective)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(registry, ensure_ascii=False, indent=1, sort_keys=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"[snapshot-aosp] registry gravado: {out_path} "
          f"({registry['counts']['platform']} permissoes de plataforma)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
