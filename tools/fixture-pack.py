#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fixture-pack.py — Empacota APKs fixture SEM gradle (aapt2 + d8 + zip + apksigner).

Orquestrador do caminho "packed fixture" do APK Tester (A2/A3): gera a árvore
de fonte da fixture (AndroidManifest.xml + Java POJO + res) dentro de --work e
emite um PLANO JSON com os comandos exatos: aapt2 compile/link -> javac ->
d8 (--min-api por modo) -> zip -> zipalign -> apksigner (flags de esquema por
modo). Sem --dry-run, executa o plano de forma best-effort quando TODAS as
ferramentas existem; caso contrário emite só o plano (mesma saída do dry-run).

Modos (--fixture):
  minSdk9 ......... minSdk 9/targetSdk 28 com 1 activity + 1 service + 1
                    receiver + 1 provider (escada SDK; no RustyDroid o
                    resultado esperado é BELOW_FLOOR(minSdk=9) — esse é o teste).
  sig-v1-only ..... assinatura só v1 (JAR)            (parser-torture)
  sig-v2-only ..... assinatura só v2 (APK Signature)  (parser-torture)
  sig-v3-only ..... assinatura só v3 (rotação de chave)
  unaligned ....... pula o zipalign de propósito
  zip64 ........... >65k entradas de dados via zipfile force_zip64
  unknown-perms ... permissões inventadas dev.apktester.fake.* (ÚNICO lugar do
                    repo onde string de permissão inventada é permitida)
  obfuscated ...... nomes minificados determinísticos + mapping.txt (proxy
                    honesto; ofuscação R8 real exige toolchain externa); o
                    mapping.txt também vai DENTRO do APK (assets/mapping.txt)
  huge-arsc ....... resources.arsc sintético (gen-arsc-stress): 10.000
                    entradas x 40 locales + densidades; substitui o arsc do
                    aapt2 no APK (parser-torture)
  multidex-8 ...... 8 arquivos classesN.dex (multidex nativo, minSdk 21) a
                    partir do corpus gen-dex-stress, fatiado em 8 lotes
  exported-audit .. armadilhas de manifesto intencionais (exported/permissões
                    mal declaradas) — auditoria documenta cada erro
                    (gen-trap-manifest fornece manifesto + Java)
  engine-XX-* ..... fixtures Tier C da matriz de engines (A3): 9 fixtures de
                    detecção sintética e honesta (engine-05-clojure,
                    engine-11-objc, engine-18-maui-xamarin,
                    engine-19-unity-mono, engine-20-unity-il2cpp,
                    engine-21-unreal, engine-27-b4x-appinventor,
                    engine-29-python-kivy-beeware, engine-32-twa-pwa); os
                    payloads (stubs ELF/PE/metadata/assets) vêm de
                    gen-engine-fixtures e as classes marcador Java ancoram
                    os dex-strings do contrato — payload NÃO executável
                    (ADR 0003)

Nome do APK final: APK_NAMES.get(modo, f"{modo}.apk") — zip64 vira
zip64-65k.apk e obfuscated vira obfuscated-r8.apk.

Determinismo: stdlib only, seed padrão 20261022, sem timestamps nas saídas
(o zip CLI grava mtimes; o verify-deterministic.sh compara conteúdo por
entrada ignorando META-INF/*, então o proxy continua verificável).

Uso:
  python3 tools/fixture-pack.py --fixture minSdk9 --dry-run --out DIST
  python3 tools/fixture-pack.py --fixture zip64 --out DIST [--work W] [--seed N]
  python3 tools/fixture-pack.py --selftest

Códigos de saída: 0 ok/plano emitido; 1 falha de execução; 2 fixture inválida.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

DEFAULT_SEED = 20261022
TOOL = "fixture-pack.py"
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_CODE = 900036
VERSION_NAME = "1.0.0"
KS_PASS = "pass:apktester"
KS_ALIAS = "apktester"

# multidex-8: fatiamento do corpus gen-dex-stress em 8 lotes contíguos
# (128 classes x 60 rotinas = 7680 + strings/fields => ~1k rotinas por dex).
DEX_BATCHES = 8
DEX_CORPUS_ARGS = ("--classes", "128", "--methods-per-class", "60",
                   "--strings", "2000", "--fields", "128")
# multidex-8-full (A9/roadmap 3.3): o corpus INTEIRO no default do
# gen-dex-stress — 650 classes x 101 rotinas = 65.650 method refs,
# ACIMA do limite de 65.536 de um único dex — atravessando o d8 de
# verdade (8 lotes contíguos, ~8.2k rotinas por dex). Custo: minutos de
# geração + dexação; por isso o modo roda no NIGHTLY, não no PR CI.
DEX_CORPUS_FULL_ARGS = ()  # args vazios = defaults 650 x 101 da ferramenta


def is_multidex(mode: str) -> bool:
    """Modos multidex (fatiamento do corpus gen-dex-stress em 8 dexes)."""
    return mode in ("multidex-8", "multidex-8-full")


def corpus_args(mode: str) -> tuple:
    """Args do gen-dex-stress para o modo (reduzido p/ multidex-8; defaults
    completos 650x101 p/ multidex-8-full)."""
    return DEX_CORPUS_FULL_ARGS if mode == "multidex-8-full" \
        else DEX_CORPUS_ARGS
# huge-arsc: entradas do resources.arsc sintético (o passo do plano é
# explícito para o plano JSON não depender do default da ferramenta).
ARSC_ENTRIES = "10000"

FAKE_PERMS = (
    "dev.apktester.fake.READ_WIDGET_MATRIX",
    "dev.apktester.fake.WRITE_TERRAIN_CHUNKS",
    "dev.apktester.fake.BIND_GHOST_SERVICE",
    "dev.apktester.fake.ACCESS_NULL_SENSOR",
)

# Tabela por modo: sdk, esquemas de assinatura (v1/v2/v3), zipalign e truques
# do parser-torture (zip64/fake_perms/obfuscated/huge-arsc/multidex/traps).
def _mode(min_sdk, target_sdk, v1=True, v2=True, v3=False, zipalign=True,
          zip64=False, entries=0, fake_perms=False, obfuscated=False,
          external_manifest=False, engine=False, sign=True, malformed=None,
          desc=""):
    return {"min_sdk": min_sdk, "target_sdk": target_sdk, "v1": v1, "v2": v2,
            "v3": v3, "zipalign": zipalign, "zip64": zip64,
            "zip64_entries": entries, "fake_perms": fake_perms,
            "obfuscated": obfuscated, "external_manifest": external_manifest,
            "engine": engine, "sign": sign, "malformed": malformed,
            "description": desc}


MODES = {
    "minSdk9": _mode(9, 28,
        desc="escada SDK: quarteto activity/service/receiver/provider; "
             "BELOW_FLOOR(minSdk=9) esperado no RustyDroid"),
    "sig-v1-only": _mode(9, 36, v2=False, desc="somente assinatura v1 (JAR)"),
    "sig-v2-only": _mode(24, 36, v1=False, desc="somente assinatura v2"),
    "sig-v3-only": _mode(28, 36, v1=False, v2=False, v3=True,
        desc="somente assinatura v3 (rotação de chave)"),
    "unaligned": _mode(26, 36, zipalign=False,
        desc="zipalign pulado de propósito (parser-torture)"),
    "zip64": _mode(26, 36, zip64=True, v2=False, entries=65600,
        desc=">65k entradas (força Zip64 EOCD) como data entries; assinatura "
             "v1 ANTES do augment (a reescrita preserva os digests JAR, que "
             "cobrem o conteúdo não comprimido)"),
    "unknown-perms": _mode(26, 36, fake_perms=True,
        desc="permissões inventadas dev.apktester.fake.*"),
    "obfuscated": _mode(26, 36, obfuscated=True,
        desc="nomes minificados + mapping.txt (proxy honesto sem R8)"),
    "huge-arsc": _mode(26, 36,
        desc="resources.arsc sintetico: 10.000 entradas x 40 locales + "
             "densidades (gen-arsc-stress)"),
    "multidex-8": _mode(21, 36,
        desc="8 arquivos classesN.dex (multidex nativo, minSdk 21) a partir "
             "do corpus gen-dex-stress"),
    "multidex-8-full": _mode(21, 36,
        desc="corpus gen-dex-stress COMPLETO (650 classes x 101 rotinas = "
             "65.650 > 65.536) fatiado em 8 dexes — o limite de 64k methods "
             "atravessado de verdade pelo d8 (modo pesado: nightly, não no "
             "CI de PR; auditoria A9/roadmap 3.3)"),
    "exported-audit": _mode(26, 36, external_manifest=True,
        desc="armadilhas de manifesto intencionais (exported/permissoes mal "
             "declaradas) — auditoria documenta cada erro"),
    # --- Malformed corpus (D4): adversarial-malformed, alvo de PARSER.
    # Unsigned de proposito (a patologia e estrutural, nao de assinatura);
    # a mutacao e pos-build, deterministica por seed (stdlib only).
    "zip-slip": _mode(26, 36, sign=False, malformed="zip-slip",
        desc="entradas com traversal '../../' no Central Directory "
             "(zip-slip de extracao)"),
    "duplicate-entries": _mode(26, 36, sign=False,
        malformed="duplicate-entries",
        desc="mesmo nome de entrada DUAS VEZES com conteudo divergente "
             "(AndroidManifest.xml e assets/dup.txt)"),
    "axml-truncated": _mode(26, 36, sign=False, malformed="axml-truncated",
        desc="AndroidManifest.xml (AXML) truncado no meio de um chunk — "
             "tamanhos declarados > bytes reais"),
    "arsc-type-collision": _mode(26, 36, sign=False,
        malformed="arsc-type-collision",
        desc="resources.arsc sintetico com COLISAO de tipos: dois chunks de "
             "tipo com ids diferentes e o MESMO nome (string)"),
    "dex-corrupted": _mode(26, 36, sign=False, malformed="dex-corrupted",
        desc="classes.dex com checksum adler32 zerado e map_off "
             "invalidado (0xFFFFFFFF) — header mentiroso"),
    "v3-rotation-lineage": _mode(28, 36, v1=False, v2=False, v3=True,
        desc="assinatura v3 com PROOF-OF-ROTATION real: chave A rotacionada "
             "para chave B via apksigner rotate + --lineage"),
    # --- Tier C (A3): fixtures de detecção, payload NÃO executável (ADR 0003).
    # Specced em tools/gen-engine-fixtures.py (fonte única); o selftest dele
    # cruza estas chaves com o contrato canônico expected-engines.json.
    "engine-05-clojure": _mode(26, 36, engine=True,
        desc="Tier C: Clojure — strings clojure.lang no dex + marcador de "
             "fixture (payload não executável)"),
    "engine-11-objc": _mode(26, 36, engine=True,
        desc="Tier C: Objective-C — stub ELF libobjc-fixture.so com "
             "marcadores objc_* (payload não executável)"),
    "engine-18-maui-xamarin": _mode(26, 36, engine=True,
        desc="Tier C: MAUI/Xamarin — assemblies/*.dll stubs (BSJB) + "
             "libmonodroid.so (payload não executável)"),
    "engine-19-unity-mono": _mode(26, 36, engine=True,
        desc="Tier C: Unity Mono — Assembly-CSharp.dll stub + libunity.so + "
             "libmonobdwgc-2.0.so (payload não executável)"),
    "engine-20-unity-il2cpp": _mode(26, 36, engine=True,
        desc="Tier C: Unity IL2CPP — libil2cpp.so + global-metadata.dat "
             "stubs (payload não executável)"),
    "engine-21-unreal": _mode(26, 36, engine=True,
        desc="Tier C: Unreal — libUE4.so stub + assets/main.pak placeholder "
             "(payload não executável)"),
    "engine-27-b4x-appinventor": _mode(26, 36, engine=True,
        desc="Tier C: B4X/App Inventor — strings anywheresoftware.b4a / "
             "com.google.appinventor no dex (payload não executável)"),
    "engine-29-python-kivy-beeware": _mode(26, 36, engine=True,
        desc="Tier C: Python/Kivy/BeeWare — stub libpython3.11.so + "
             "assets/python/main.py (payload não executável)"),
    "engine-32-twa-pwa": _mode(26, 36, engine=True,
        desc="Tier C: TWA/PWA — meta-data asset_statements + strings "
             "androidx.browser.trusted no dex (payload não executável)"),
}

# Extras de manifesto por modo engine (anexados dentro de <application>):
# TWA declara os digital asset links como o template real do Trusted Web
# Activity faz (meta-data -> resource string).
ENGINE_MANIFEST_EXTRAS = {
    "engine-32-twa-pwa": [
        '        <meta-data android:name="asset_statements"',
        '                  android:resource="@string/asset_statements"/>',
    ],
}

# Extra de res por modo engine (strings_xml): TWA carrega a sentença de
# asset links (JSON em uma linha, aspas duplas são válidas em XML texto).
ENGINE_STRINGS_EXTRAS = {
    "engine-32-twa-pwa": [
        '    <string name="asset_statements">[{"relation": '
        '["delegate_permission/common.handle_all_urls"], "target": '
        '{"namespace": "web", "site": '
        '"https://dev.apktester.example"}}]</string>',
    ],
}

# Nome do APK final por modo (demais modos usam f"{modo}.apk").
APK_NAMES = {
    "zip64": "zip64-65k.apk",
    "obfuscated": "obfuscated-r8.apk",
}


def slugify(mode: str) -> str:
    """Slug de pacote Java válido a partir do nome do modo."""
    return re.sub(r"[^a-z0-9_]", "", mode.lower())


def component_classes(cfg: dict) -> list:
    """(classe, papel) dos 4 componentes; obfuscado usa a/b/c/d no pacote a.a."""
    if cfg["obfuscated"]:
        return [("a", "activity"), ("b", "service"), ("c", "receiver"),
                ("d", "provider")]
    return [("MainActivity", "activity"), ("TestService", "service"),
            ("TestReceiver", "receiver"), ("TestProvider", "provider")]


def component_kinds(cfg: dict) -> list:
    """Kinds de componente do plano (exported-audit tem alias e é honesto)."""
    if cfg["external_manifest"]:
        return ["activity", "activity-alias", "service", "receiver",
                "provider"]
    return ["activity", "service", "receiver", "provider"]


def manifest_xml(cfg: dict, mode: str, pkg: str) -> str:
    """AndroidManifest.xml determinístico (sem timestamps)."""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
        f'    package="{pkg}"',
        f'    android:versionCode="{VERSION_CODE}"',
        f'    android:versionName="{VERSION_NAME}">',
        '',
        f'    <uses-sdk android:minSdkVersion="{cfg["min_sdk"]}"',
        f'              android:targetSdkVersion="{cfg["target_sdk"]}"/>',
        '',
        '    <uses-permission android:name="android.permission.INTERNET"/>',
    ]
    for perm in (FAKE_PERMS if cfg["fake_perms"] else ()):
        lines.append(f'    <uses-permission android:name="{perm}"/>')
    lines += [
        '',
        '    <application android:label="@string/app_name" android:hasCode="true">',
    ]
    lines += ENGINE_MANIFEST_EXTRAS.get(mode, [])
    for cls, kind in component_classes(cfg):
        ref = cls if cfg["obfuscated"] else f".{cls}"
        if kind == "activity":
            lines += [
                f'        <activity android:name="{ref}" android:exported="true">',
                '            <intent-filter>',
                '                <action android:name="android.intent.action.MAIN"/>',
                '                <category android:name="android.intent.category.LAUNCHER"/>',
                '            </intent-filter>',
                '        </activity>',
            ]
        elif kind == "service":
            lines.append(f'        <service android:name="{ref}" android:exported="false"/>')
        elif kind == "receiver":
            lines.append(f'        <receiver android:name="{ref}" android:exported="false"/>')
        else:
            lines += [
                f'        <provider android:name="{ref}" android:exported="false"',
                f'                  android:authorities="{pkg}.provider"/>',
            ]
    lines += ['    </application>', '</manifest>', '']
    return "\n".join(lines)


JAVA_TEMPLATE = '''package {pkg};

/** Fixture APK Tester ({mode}) — POJO sem imports android.*: javac roda sem
 *  android.jar. Para o RustyDroid a verdade de componentes é o manifesto
 *  (CORE-12); o DEX existe para exercitar o parser/VM. */
public final class {cls} {{

    public static final int SEED = {seed};

    public String role() {{
        return "{role}";
    }}

    public String fixture() {{
        return "{mode}";
    }}

    public int checksum() {{
        int h = SEED;
        for (char c : fixture().toCharArray()) {{
            h = 31 * h + c;
        }}
        return h;
    }}
}}
'''


def strings_xml(mode: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<resources>',
        f'    <string name="app_name">APK Tester fixture {mode}</string>',
        f'    <string name="seed">{DEFAULT_SEED}</string>',
    ]
    lines += ENGINE_STRINGS_EXTRAS.get(mode, [])
    lines += ['</resources>', '']
    return "\n".join(lines)


def generate_tree(cfg: dict, mode: str, seed: int, work: str) -> list:
    """Escreve a árvore de fonte da fixture em --work; devolve os caminhos."""
    pkg = "dev.apktester.fixture." + slugify(mode)
    if cfg["external_manifest"]:
        # exported-audit: manifesto e Java vêm de gen-trap-manifest (traproot,
        # fonte única da tabela TRAPS); aqui só o res/ com o label.
        files = {"res/values/strings.xml": strings_xml(mode)}
        java_files = []
    else:
        files = {
            "AndroidManifest.xml": manifest_xml(cfg, mode, pkg),
            "res/values/strings.xml": strings_xml(mode),
        }
        java_files = []
        for cls, role in component_classes(cfg):
            cls_pkg = "a.a" if cfg["obfuscated"] else pkg
            rel = f"src/{cls_pkg.replace('.', '/')}/{cls}.java"
            files[rel] = JAVA_TEMPLATE.format(pkg=cls_pkg, cls=cls, mode=mode,
                                              role=role, seed=seed)
            java_files.append(os.path.join(work, rel))
        if cfg["obfuscated"]:
            lines = ["# mapping.txt — proxy honesto de ofuscacao (sem R8; nomes gerados offline)"]
            for cls, _role in component_classes(cfg):
                lines.append(f"a.a.{cls} -> {pkg}.{cls}:")
            mapping = "\n".join(lines) + "\n"
            # Raiz do work (contrato já existente) + cópia em assets/ que
            # entra DENTRO do APK para o RustyDroid ler.
            files["mapping.txt"] = mapping
            files["assets/mapping.txt"] = mapping
    for rel, content in files.items():
        full = os.path.join(work, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    # d8 exige que o --output EXISTA ("Output must be ... an existing
    # directory"): prepara o destino do dex base e, no multidex-8, os 8
    # subdiretórios dos lotes (o caminho de execução é exercitado no CI).
    os.makedirs(os.path.join(work, "dex"), exist_ok=True)
    if is_multidex(mode):
        for i in range(1, DEX_BATCHES + 1):
            os.makedirs(os.path.join(work, "dex", str(i)), exist_ok=True)
    r_java = os.path.join(work, "gen", pkg.replace(".", "/"), "R.java")
    return java_files + [r_java]


def find_android_jar() -> str | None:
    """Melhor android.jar em ANDROID_SDK_ROOT/ANDROID_HOME/~/Android/Sdk."""
    roots = [os.environ.get(e) for e in ("ANDROID_SDK_ROOT", "ANDROID_HOME")]
    roots.append(os.path.join(os.path.expanduser("~"), "Android", "Sdk"))
    cands = []
    for root in roots:
        if root:
            cands += glob.glob(os.path.join(root, "platforms", "*", "android.jar"))
    if not cands:
        return None

    def version_key(path: str):
        m = re.search(r"platforms[/\\]android-(\d+)[/\\]", path)
        return int(m.group(1)) if m else 0

    return sorted(cands, key=version_key)[-1]


def discover_tools(args) -> tuple:
    """Resolve aapt2/d8/zip/apksigner/zipalign (+javac/keytool) via --flag ou PATH."""
    names = ("aapt2", "d8", "zip", "apksigner", "zipalign", "javac", "keytool")
    tools = {}
    for name in names:
        path = getattr(args, name, None) or shutil.which(name)
        ok = bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)
        tools[name] = {"path": path, "available": ok}
    return tools, find_android_jar()


def build_plan(args, cfg: dict, work: str, out_apk: str, tools: dict,
               java_files: list, android_jar: str | None) -> dict:
    """Plano JSON com os comandos exatos (determinístico, sem timestamps)."""
    mode = args.fixture
    unsigned = os.path.join(work, "bundle-unsigned.apk")
    aligned = (os.path.join(work, "bundle-aligned.apk") if cfg["zipalign"]
               else unsigned)
    keystore = os.path.join(work, "debug.keystore")
    jar_tok = android_jar or "@ANDROID_JAR@"
    a2 = tools["aapt2"]["path"] or "aapt2"
    d8 = tools["d8"]["path"] or "d8"
    za = tools["zipalign"]["path"] or "zipalign"
    signer = tools["apksigner"]["path"] or "apksigner"
    jv = tools["javac"]["path"] or "javac"
    kt = tools["keytool"]["path"] or "keytool"
    manifest_src = (os.path.join(work, "traproot", "AndroidManifest.xml")
                    if cfg["external_manifest"]
                    else os.path.join(work, "AndroidManifest.xml"))
    keystore_b = os.path.join(work, "rotate-b.keystore")
    lineage = os.path.join(work, "rotation-lineage.bin")
    steps = [
        {"id": "keystore",
         "description": "keystore de debug para as fixtures (skip se já existe)",
         "command": [kt, "-genkeypair", "-keystore", keystore, "-storetype",
                     "PKCS12", "-storepass", "apktester", "-keypass",
                     "apktester", "-alias", KS_ALIAS, "-keyalg", "RSA",
                     "-keysize", "2048", "-validity", "10000", "-dname",
                     "CN=APK Tester Fixture, OU=Fixtures, O=apktester, "
                     "L=Recife, S=PE, C=BR"],
         "cwd": None, "skip_if": "keystore_existe"},
        {"id": "keystore-b",
         "description": "segunda keystore da rotacao D4 (chave B; skip se "
                        "existe)",
         "command": [kt, "-genkeypair", "-keystore", keystore_b,
                     "-storetype", "PKCS12", "-storepass", "apktester",
                     "-keypass", "apktester", "-alias", KS_ALIAS,
                     "-keyalg", "RSA", "-keysize", "2048", "-validity",
                     "10000", "-dname", "CN=APK Tester Rotation B, "
                     "OU=Fixtures, O=apktester, L=Recife, S=PE, C=BR"],
         "cwd": None, "skip_if": "keystore_b_existe"},
        {"id": "apksigner-rotate",
         "description": "gera o lineage proof-of-rotation A -> B "
                        "(apksigner rotate; exige as duas keystores)",
         "command": [signer, "rotate", "--in-old-keystore", keystore,
                     "--in-new-keystore", keystore_b, "--ks-pass", KS_PASS,
                     "--ks-key-alias", KS_ALIAS,
                     "--out-lineage", lineage], "cwd": None,
         "skip_if": "mode_nao_e_v3_rotation"},
        {"id": "aapt2-compile", "description": "compila res/ em res.zip (flat)",
         "command": [a2, "compile", "--dir", os.path.join(work, "res"), "-o",
                     os.path.join(work, "res.zip")], "cwd": None},
        {"id": "aapt2-link",
         "description": "liga manifest+res no APK base e gera R.java",
         "command": [a2, "link", "-o", unsigned, "--manifest",
                     manifest_src, "-I", jar_tok,
                     "--java", os.path.join(work, "gen"), "--min-sdk-version",
                     str(cfg["min_sdk"]), "--target-sdk-version",
                     str(cfg["target_sdk"]), "--version-code", str(VERSION_CODE),
                     "--version-name", VERSION_NAME,
                     os.path.join(work, "res.zip")], "cwd": None},
        {"id": "javac", "description": "compila POJOs + R.java (sem android.jar)",
         "command": [jv, "-encoding", "UTF-8", "-source", "8", "-target", "8",
                     "-Xlint:-options", "-d", os.path.join(work, "classes")]
                    + java_files, "cwd": None},
    ]
    if cfg["external_manifest"]:
        steps.insert(0, {
            "id": "gen-trap-manifest",
            "description": "armadilhas exported-audit: manifesto + POJOs da "
                           "tabela TRAPS (gen-trap-manifest)",
            "command": [sys.executable,
                        os.path.join(TOOLS_DIR, "gen-trap-manifest.py"),
                        "--out", os.path.join(work, "traproot"), "--seed",
                        str(args.seed)], "cwd": None})
    if cfg["engine"]:
        steps.insert(0, {
            "id": "gen-engine-payload",
            "description": "payloads Tier C (stubs ELF/PE/metadata/assets + "
                           "classes marcador java) do gen-engine-fixtures",
            "command": [sys.executable,
                        os.path.join(TOOLS_DIR, "gen-engine-fixtures.py"),
                        "--engine", mode, "--out",
                        os.path.join(work, "engroot"), "--report",
                        os.path.join(work, "engine-payload-report.json"),
                        "--seed", str(args.seed)], "cwd": None})
    if is_multidex(mode):
        n_routines = (650 * 101 if mode == "multidex-8-full"
                      else 128 * 60)
        steps.insert(0, {
            "id": "gen-dex-corpus",
            "description": f"corpus-fonte gen-dex-stress ({n_routines} "
                           f"rotinas + strings + campos) p/ fatiar em 8 dexes",
            "command": [sys.executable,
                        os.path.join(TOOLS_DIR, "gen-dex-stress.py"),
                        "--out", os.path.join(work, "dexsrc"), "--seed",
                        str(args.seed)] + list(corpus_args(mode)),
            "cwd": None})
        # Pipeline multidex: fatia os .class em 8 lotes contíguos e dexa um
        # classes.dex por lote (multidex nativo, minSdk 21).
        dexplan = os.path.join(work, "dexplan.json")
        steps.append({
            "id": "dex-partition",
            "description": f"fatiamento contíguo dos .class em "
                           f"{DEX_BATCHES} lotes (dexplan.json)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--dex-partition", os.path.join(work, "classes"),
                        dexplan, str(DEX_BATCHES)], "cwd": None})
        for i in range(1, DEX_BATCHES + 1):
            steps.append({
                "id": f"jar-batch-{i}",
                "description": f"empacota o lote {i} de classes p/ o d8",
                "command": ["zip", "-q", "-r",
                            os.path.join(work, "dexbatch", f"{i}.jar"), "."],
                "cwd": os.path.join(work, "dexbatch", str(i))})
        for i in range(1, DEX_BATCHES + 1):
            steps.append({
                "id": f"d8-{i}",
                "description": f"dexa o lote {i} com --min-api "
                               f"{cfg['min_sdk']} (multidex nativo)",
                "command": [d8, "--release", "--min-api", str(cfg["min_sdk"])]
                           + (["--lib", android_jar] if android_jar else [])
                           + ["--output", os.path.join(work, "dex", str(i)),
                              os.path.join(work, "dexbatch", f"{i}.jar")],
                "cwd": None})
        steps.append({
            "id": "collect-dex",
            "description": f"copia work/dex/N/classes.dex -> classes.dex.."
                           f"classes{DEX_BATCHES}.dex (ordem determinística)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--collect-dex", work,
                        os.path.join(work, "dexout")], "cwd": None})
        steps.append({
            "id": "zip-dex-8",
            "description": f"anexa classes.dex..classes{DEX_BATCHES}.dex na "
                           "raiz do APK",
            "command": ["zip", "-j", "-X", unsigned]
                       + ["classes.dex" if i == 1 else f"classes{i}.dex"
                          for i in range(1, DEX_BATCHES + 1)],
            "cwd": os.path.join(work, "dexout")})
    else:
        steps += [
            {"id": "jar-classes", "description": "empacota os .class p/ o d8",
             "command": ["zip", "-q", "-r",
                         os.path.join(work, "classes-input.jar"), "."],
             "cwd": os.path.join(work, "classes")},
            {"id": "d8", "description": f"dexa com --min-api {cfg['min_sdk']}",
             "command": [d8, "--release", "--min-api", str(cfg["min_sdk"])]
                        + (["--lib", android_jar] if android_jar else [])
                        + ["--output", os.path.join(work, "dex"),
                           os.path.join(work, "classes-input.jar")], "cwd": None},
            {"id": "zip-dex", "description": "anexa classes.dex na raiz do APK",
             "command": ["zip", "-j", "-X", unsigned, "classes.dex"],
             "cwd": os.path.join(work, "dex")},
        ]
    if cfg["engine"]:
        steps.append({
            "id": "zip-engine-payload",
            "description": "anexa lib/, assets/ e assemblies/ dos payloads "
                           "Tier C (sem entradas de diretório)",
            "command": ["zip", "-q", "-r", "-X", "-D", unsigned, "."],
            "cwd": os.path.join(work, "engroot", "payload")})
    if mode == "unaligned":
        steps.append({
            "id": "dealign",
            "description": "coloca assets/unaligned*.bin (STORED) como PRIMEIRA "
                           "entrada com o nome calibrado p/ dados em "
                           "offset mod 4 = 1 — desalinhamento GARANTIDO "
                           "(aapt2 sozinho já sai alinhado; zipalign -c "
                           "DEVE reprovar)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--dealign", unsigned, "--seed", str(args.seed)],
            "cwd": None})
    if cfg["obfuscated"]:
        steps.append({
            "id": "zip-mapping",
            "description": "anexa mapping.txt como assets/mapping.txt "
                           "(o RustyDroid lê de dentro do APK)",
            "command": ["zip", "-q", "-X", unsigned, "assets/mapping.txt"],
            "cwd": work})
    if mode == "huge-arsc":
        steps += [
            {"id": "gen-arsc",
             "description": "resources.arsc sintético "
                            f"({ARSC_ENTRIES} entradas x 40 locales + "
                            "densidades; gen-arsc-stress)",
             "command": [sys.executable,
                         os.path.join(TOOLS_DIR, "gen-arsc-stress.py"),
                         "--out", os.path.join(work, "arsc"), "--seed",
                         str(args.seed), "--entries", ARSC_ENTRIES],
             "cwd": None},
            {"id": "strip-arsc",
             "description": "remove o resources.arsc do aapt2 (o sintetico "
                            "entra no lugar)",
             "command": [sys.executable, os.path.abspath(__file__),
                         "--strip-entry", unsigned, "resources.arsc"],
             "cwd": None},
            {"id": "zip-arsc",
             "description": "anexa o resources.arsc sintético na raiz do APK",
             "command": ["zip", "-j", "-X", unsigned, "resources.arsc"],
             "cwd": os.path.join(work, "arsc")},
        ]
    if cfg["zipalign"]:
        steps.append({
            "id": "zipalign", "description": "alinhamento de 4 bytes (-p p/ .so)",
            "command": [za, "-f", "-p", "4", unsigned, aligned], "cwd": None})
    if cfg.get("sign", True) is False:
        # Malformed corpus (D4): sem assinatura (a patologia e estrutural);
        # o passo final e a MUTACAO deterministica que grava o --out.
        steps.append({
            "id": "malformed-mutate",
            "description": f"mutacao deterministica '{cfg['malformed']}' "
                           "(stdlib only, mtimes 1980) gravando o APK final",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--malformed-mutate", cfg["malformed"],
                        "--src", aligned, "--out", out_apk,
                        "--seed", str(args.seed)],
            "cwd": None})
    else:
        steps.append({
            "id": "apksigner",
            "description": f"assina com v1={cfg['v1']} v2={cfg['v2']} "
                           f"v3={cfg['v3']} e grava em --out",
            "command": [signer, "sign", "--ks", keystore, "--ks-pass",
                        KS_PASS, "--ks-key-alias", KS_ALIAS,
                        "--key-pass", KS_PASS,
                        "--min-sdk-version", str(cfg["min_sdk"]),
                        "--v1-signing-enabled", str(cfg["v1"]).lower(),
                        "--v2-signing-enabled", str(cfg["v2"]).lower(),
                        "--v3-signing-enabled", str(cfg["v3"]).lower(),
                        "--out", out_apk, aligned], "cwd": None})
    if mode == "v3-rotation-lineage":
        # D4: proof-of-rotation REAL — a chave B assina com o lineage que
        # prova a rotacao A -> B (apksigner rotate consome os dois keystores).
        steps.append({
            "id": "sign-with-lineage",
            "description": "re-assina o APK final com a chave B + --lineage "
                           "(proof-of-rotation A->B na v3 block)",
            "command": [signer, "sign", "--ks", keystore_b, "--ks-pass",
                        KS_PASS, "--ks-key-alias", KS_ALIAS,
                        "--key-pass", KS_PASS,
                        "--lineage", lineage, "--lineage-min-sdk-version",
                        "28", "--min-sdk-version", "28",
                        "--v1-signing-enabled", "false",
                        "--v2-signing-enabled", "false",
                        "--v3-signing-enabled", "true",
                        "--out", out_apk, out_apk], "cwd": None})
    if cfg["zip64"]:
        steps.append({
            "id": "zip64-augment",
            "description": f"adiciona {cfg['zip64_entries']} data entries "
                           "(>65k força Zip64 EOCD) REESCREVENDO o APK já "
                           "assinado v1",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--zip64-augment", "--into", out_apk, "--entries",
                        str(cfg["zip64_entries"]), "--seed", str(args.seed)],
            "cwd": None})

    notes = [
        "fontes são POJOs sem imports android.*: javac roda sem android.jar; "
        "a verdade de componentes é o AndroidManifest.xml (CORE-12)",
        "o zip CLI grava mtimes: verificação byte-a-byte é por conteúdo de "
        "entrada, ignorando META-INF/* (verify-deterministic.sh --mode apk)",
    ]
    if not android_jar:
        notes.append("android.jar não encontrado (ANDROID_SDK_ROOT): o passo "
                     "aapt2 link exige -I real para executar")
    if mode == "minSdk9":
        notes += [
            "v1/JAR: se o apksigner do seu SDK recusar assinar v1 para minSdk "
            "9, fallback: jarsigner -keystore <ks> -storepass apktester "
            "<apk> apktester",
            "resultado esperado no RustyDroid: BELOW_FLOOR(minSdk=9) — é a "
            "lei estruturada, nunca crash",
        ]
    if not cfg["zipalign"]:
        notes.append("zipalign pulado de propósito: fixture de entradas "
                     "desalinhadas do parser-torture")
    if cfg["zip64"]:
        notes.append("entradas zip64 são determinísticas por seed (sha256 de "
                     "seed:indice) e vivem em assets/zip64/")
    if cfg["fake_perms"]:
        notes.append("strings dev.apktester.fake.* são inventadas e só podem "
                     "existir nesta fixture (nunca no flagship)")
    if cfg["obfuscated"]:
        notes.append("ofuscação R8 real exige toolchain externa; proxy honesto "
                     "com nomes minificados + mapping.txt (no work e DENTRO do "
                     "APK em assets/mapping.txt); R8 real chega nos builds "
                     "Tier A / release A6")
    if mode == "huge-arsc":
        notes += [
            "resources.arsc sintético (gen-arsc-stress) substitui o do aapt2: "
            "40 configs de locale sem default + 7 densidades; âncora sha256 "
            "em suites/parser-torture/huge-arsc/arsc-report.json",
            "re-parse local do arsc: python3 tools/gen-arsc-stress.py "
            "--verify <resources.arsc> (gold standard; CI soma aapt2 dump "
            "resources como segunda opinião)",
        ]
    if is_multidex(mode):
        scope = ("corpus COMPLETO gen-dex-stress (650 x 101 = 65.650 "
                 "rotinas, acima do limite 65.536) fatiado em 8 lotes "
                 "contíguos" if mode == "multidex-8-full" else
                 "corpus gen-dex-stress fatiado em 8 lotes contíguos")
        notes.append(f"{scope} (work/dexplan.json): classes.dex.."
                     "classes8.dex na raiz do APK — multidex nativo, "
                     "minSdk 21")
    if cfg["external_manifest"]:
        notes.append("manifesto e Java vêm de tools/gen-trap-manifest.py "
                     "(fonte única da tabela TRAPS); 9 componentes (7 "
                     "armadilhas + 2 baselines) documentados em "
                     "contracts/parser-torture/exported-audit-traps.md")
    if cfg["engine"]:
        notes += [
            "fixture Tier C (A3): payloads por tools/gen-engine-fixtures.py "
            "(stubs ELF/PE/metadata/assets e classes marcador Java); report "
            "de sha256 em work/engine-payload-report.json e âncora canônica "
            "em contracts/engines/tier-c-payload-report.json",
            "payload NÃO executável (ADR 0003): detecção não valida payload "
            "nem autoriza execução; verificação via gen-engine-fixtures.py "
            "--verify-apk (artefatos do contrato expected-engines.json)",
        ]
    return {
        "tool": TOOL, "fixture": mode, "seed": args.seed,
        "description": cfg["description"],
        "application_id": "dev.apktester.fixture." + slugify(mode),
        "apk_name": os.path.basename(out_apk),
        "min_sdk": cfg["min_sdk"], "target_sdk": cfg["target_sdk"],
        "components": component_kinds(cfg),
        "work": work, "out_apk": out_apk, "android_jar": android_jar,
        "keystore": keystore, "keystore_b": keystore_b, "lineage": lineage,
        "tools": tools, "notes": notes, "steps": steps,
        "all_tools_available": all(t["available"] for t in tools.values()),
    }


def zip_dealign(zip_path: str, seed: int) -> None:
    """Reescreve o ZIP com os DADOS de resources.arsc em offset mod 4 == 1.

    O zipalign de build-tools recentes so confere o alinhamento EXIGIDO pela
    plataforma (resources.arsc nao-comprimido e 4-alinhado para
    targetSdk >= 30; .so em pagina com -p) — entradas armazenadas genericas
    nao sao mais reprovadas. A patologia e calibrada entao SOBRE o arsc: um
    blob STORED ("assets/unaligned.bin") entra como PRIMEIRA entrada e o
    comprimento dele (32..35 bytes) desloca o arsc ate offset mod 4 == 1 —
    deterministico por aritmetica, duas passadas.
    """
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        payload = [(i, zf.read(i)) for i in infos]
    if not any(i.filename == "resources.arsc" for i, _ in payload):
        raise ValueError("resources.arsc ausente — nada a desalinhar")

    def write_with_blob_len(path: str, blob_len: int) -> None:
        blob = (b"apktester-unaligned/"
                + hashlib.sha256(
                    f"{seed}:dealign:{blob_len}".encode("ascii")).digest() * 2
                )[:blob_len]
        with zipfile.ZipFile(path, "w", allowZip64=True) as zf:
            first = zipfile.ZipInfo("assets/unaligned.bin")
            first.compress_type = zipfile.ZIP_STORED
            zf.writestr(first, blob)
            for info, data in payload:
                zf.writestr(info, data)

    def data_offset(path: str, entry: str) -> int:
        with zipfile.ZipFile(path) as zf:
            info = zf.getinfo(entry)
            return (info.header_offset + 30 + len(info.filename)
                    + len(info.extra))

    tmp = zip_path + ".dealign"
    write_with_blob_len(tmp, 32)
    base = data_offset(tmp, "resources.arsc")
    delta = (1 - base) % 4
    if delta:
        write_with_blob_len(tmp, 32 + delta)
    final = data_offset(tmp, "resources.arsc")
    assert final % 4 == 1, (
        f"desalinhamento do arsc nao garantido: offset {final} "
        f"(mod 4 = {final % 4})")
    os.replace(tmp, zip_path)


def zip64_augment(zip_path: str, entries: int, seed: int) -> None:
    """Reescreve o ZIP com N data entries, forçando o EOCD64 (Zip64).

    REESCRITA completa (não append): o modo "a" do zipfile deixava bytes
    mortos entre o fim do Central Directory e o ZIP64 EOCD, e o apksig
    rejeita ("Unused space at the end of ZIP Central Directory"). Escrita
    em passada única garante CD contíguo. O count > 0xFFFF força o EOCD64.
    """
    with zipfile.ZipFile(zip_path) as zf:
        payload = [(i, zf.read(i)) for i in zf.infolist()]
    tmp = zip_path + ".zip64"
    with zipfile.ZipFile(tmp, "w", allowZip64=True) as zf:
        for info, data in payload:
            zf.writestr(info, data)
        for i in range(entries):
            data = (b"apktester-zip64/"
                    + hashlib.sha256(
                        f"{seed}:{i}".encode("ascii")).hexdigest()
                       .encode("ascii"))
            zf.writestr(f"assets/zip64/e{i:06d}.bin", data,
                        compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, zip_path)


def zip_strip_entry(zip_path: str, entry: str) -> int:
    """Reescreve o zip sem a entrada pedida (huge-arsc), preservando ordem e
    conteúdo das demais. Determinístico: mtimes fixos em 1980-01-01 e
    compress_type/attrs originais. Devolve quantas entradas casaram."""
    tmp = zip_path + ".strip"
    removed = 0
    with zipfile.ZipFile(zip_path) as zin:
        with zipfile.ZipFile(tmp, "w") as zout:
            for info in zin.infolist():
                if info.filename == entry:
                    removed += 1
                    continue
                data = zin.read(info.filename)
                ni = zipfile.ZipInfo(info.filename,
                                     date_time=(1980, 1, 1, 0, 0, 0))
                ni.compress_type = info.compress_type
                ni.external_attr = info.external_attr
                ni.internal_attr = info.internal_attr
                ni.create_system = info.create_system
                zout.writestr(ni, data)
    os.replace(tmp, zip_path)
    return removed


def u8(v: int) -> bytes:
    return v.to_bytes(1, "little")


def u16(v: int) -> bytes:
    return v.to_bytes(2, "little")


def u32(v: int) -> bytes:
    return v.to_bytes(4, "little")


def _utf8_pool(strings: list) -> bytes:
    """Chunk ResStringPool UTF-8 (structurally honest, stdlib only).

    Layout: header 28 (type 0x0001, headerSize 28, size, stringCount,
    styleCount=0, flags=UTF8_FLAG, stringsStart, stylesStart=0) + offsets
    (u32 por string) + dados ([u8 u16len][u8 u8len][bytes][NUL] — varints
    de 1 byte, pois todas as strings tem < 128 unidades).
    """
    data = b""
    offsets = []
    for s in strings:
        encoded = s.encode("utf-8")
        offsets.append(len(data))
        data += u8(len(s)) + u8(len(encoded)) + encoded + b"\x00"
    strings_start = 28 + 4 * len(strings)
    body = (u32(len(strings)) + u32(0) + u32(1 << 8)
            + u32(strings_start) + u32(0)
            + b"".join(u32(o) for o in offsets)  # relativos a stringsStart
            + data)
    total = 8 + len(body)  # size = chunk header (8) + todo o resto
    return u16(0x0001) + u16(28) + u32(total) + body


def craft_arsc_collision(seed: int) -> bytes:
    """resources.arsc sintetico com COLISAO de tipos (D4).

    Estrutura honesta de chunks — Table (0x0002) com 1 package (0x0200),
    tres pools (valores globais, chaves, tipos), 2 TypeSpec (0x0202) e
    2 Type (0x0201). A patologia: os DOIS chunks de tipo tem ids DIFERENTES
    (1 e 2) e apontam para o MESMO nome no pool de tipos ("string") —
    colisao que parsers exigentes devem rejeitar com erro estruturado
    (nunca crash). Bytes deterministicos por seed.
    """
    key_name = f"maxprobe_collision_{seed % 100000}"
    type_name = "string"

    value_pool = _utf8_pool([f"colisao-A-{seed % 100000}",
                             f"colisao-B-{seed % 100000}"])

    # Package: id 0x7F, nome em 128 u16, offsets para os pools de chave e
    # tipo (relativos ao inicio do chunk do package), contadores publicos.
    package_name = "dev.apktester.malformed"
    name_buf = package_name.encode("utf-16-le")[:256].ljust(256, b"\x00")

    key_pool = _utf8_pool([key_name])
    type_pool = _utf8_pool([type_name])

    # header do package: 8 (chunk) + 4 (id) + 256 (nome) + 4*4 (offsets e
    # contadores) = 284; os pools e os types vem depois, na ordem abaixo.
    fixed = 284
    key_strings_off = fixed
    type_strings_off = key_strings_off + len(key_pool)
    types_start = type_strings_off + len(type_pool)

    def type_spec(type_id: int) -> bytes:
        # ResTable_typeSpec: header 16 (8 do chunk + id/flags/reserved)
        # + mask u32; size = 8 + corpo apos o header do chunk.
        body = u32(1 << 0)  # entryMask da entry 0
        return (u16(0x0202) + u16(16) + u32(8 + 4 + len(body))
                + u8(type_id) + u8(0) + u16(0) + body)

    def type_chunk(type_id: int, value_index: int) -> bytes:
        # ResTable_type: header 20 + offsets (entryCount u32) + entries.
        entry = (u16(8) + u16(0) + u32(0)          # key index 0
                 + u16(8) + u8(0) + u8(0x0003 & 0xFF)  # datatype STRING
                 + u32(value_index))
        offsets = u32(0)  # offset relativo a entriesStart da entry 0
        entries_start = 20 + 4
        body = (u8(type_id) + u8(0) + u16(0)
                + u32(1)                 # entryCount
                + u32(entries_start)
                + offsets + entry)
        total = 8 + len(body)  # header do ResTable_type e 20 (8 do chunk)
        return u16(0x0201) + u16(20) + u32(total) + body

    types_and_specs = (type_spec(1) + type_spec(2)
                       + type_chunk(1, 0) + type_chunk(2, 1))
    package_body = (u32(0x7F) + name_buf
                    + u32(type_strings_off) + u32(2)   # lastPublicType = 2
                    + u32(key_strings_off) + u32(1)    # lastPublicKey = 1
                    + key_pool + type_pool + types_and_specs)
    # Chunk do package: 8 (type/hs/size) + corpo a partir do id.
    package_total = 8 + len(package_body)
    package = (u16(0x0200) + u16(284) + u32(package_total) + package_body)

    # Table: header 12 (type/hs/size + packageCount) + POOL DE VALORES
    # (global) + package. O packageCount vem ANTES do pool (header de 12).
    table_total = 12 + len(value_pool) + len(package)
    return (u16(0x0002) + u16(12) + u32(table_total)
            + u32(1) + value_pool + package)


def dex_corrupt(dex_bytes: bytes) -> bytes:
    """Corrompe o DEX de forma comprovavel: checksum adler32 zerado +
    map_off invalidado (0xFFFFFFFF). A magia 'dex\n' permanece — o parser
    identifica, tenta e deve reprovar com erro estruturado (nunca crash)."""
    body = bytearray(dex_bytes)
    if len(body) < 64 or bytes(body[:4]) != b"dex\n":
        raise ValueError("classes.dex inesperado (magia ausente)")
    body[8:12] = b"\x00\x00\x00\x00"      # checksum adler32 -> 0
    body[52:56] = b"\xff\xff\xff\xff"    # map_off invalido
    return bytes(body)


def _fixed_zip_payload(zip_path: str):
    """Le o payload [(info, bytes)] do zip (ordem do Central Directory)."""
    with zipfile.ZipFile(zip_path) as zf:
        return [(i, zf.read(i.filename)) for i in zf.infolist()]


def _write_fixed_zip(tmp_path: str, payload, extra=None, replace=None):
    """Reescreve o zip com mtimes fixos (1980) — deterministico.

    extra: entradas adicionais [(nome, bytes, compress_type)] no FIM.
    replace: {nome: novos_bytes} — a PRIMEIRA ocorrencia do nome e
    substituida (as demais mantem os bytes originais: e assim que a
    patologia de entrada duplicada se constroi).
    """
    replace = dict(replace or {})
    with zipfile.ZipFile(tmp_path, "w", allowZip64=True) as zout:
        for info, data in payload:
            ni = zipfile.ZipInfo(info.filename,
                                 date_time=(1980, 1, 1, 0, 0, 0))
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            ni.internal_attr = info.internal_attr
            ni.create_system = info.create_system
            if info.filename in replace:
                data = replace.pop(info.filename)
            zout.writestr(ni, data)
        for nome, dados, compress in (extra or []):
            ni = zipfile.ZipInfo(nome, date_time=(1980, 1, 1, 0, 0, 0))
            ni.compress_type = compress
            ni.external_attr = 0o600 << 16
            zout.writestr(ni, dados)


def _marker(seed: int, tag: str, size: int = 96) -> bytes:
    """Blob deterministico por seed/tag (mesma familia do dealign/zip64)."""
    return (f"apktester-malformed/{tag}/".encode("ascii")
            + hashlib.sha256(
                f"{seed}:{tag}".encode("ascii")).digest() * 4)[:size]


def malformed_mutate(kind: str, src_zip: str, out_zip: str, seed: int) -> None:
    """Aplica a mutacao D4 deterministica e grava o APK final.

    Todas as mutacoes reescrevem o zip com mtimes fixos (1980) e preservam
    compress_type/attrs — o conteudo mutado e funcao deterministica da
    seed e do conteudo de entrada.
    """
    payload = _fixed_zip_payload(src_zip)

    def one(name: str) -> bytes:
        for info, data in payload:
            if info.filename == name:
                return data
        raise ValueError(f"entrada ausente no APK base: {name}")

    if kind == "zip-slip":
        extra = [
            ("../../apktester-zipslip-evil.txt", _marker(seed, "zipslip-1"),
             zipfile.ZIP_DEFLATED),
            ("assets/../../apktester-zipslip-escape2.txt",
             _marker(seed, "zipslip-2"), zipfile.ZIP_STORED),
        ]
        _write_fixed_zip(out_zip, payload, extra=extra)
        return
    if kind == "duplicate-entries":
        manifest = one("AndroidManifest.xml")
        extra = [
            # MESMO nome da entrada real, com conteudo divergente:
            ("AndroidManifest.xml", manifest[::-1], zipfile.ZIP_DEFLATED),
            ("assets/dup.txt", _marker(seed, "dup-1"), zipfile.ZIP_DEFLATED),
            ("assets/dup.txt", _marker(seed, "dup-2"), zipfile.ZIP_STORED),
        ]
        _write_fixed_zip(out_zip, payload, extra=extra)
        return
    if kind == "axml-truncated":
        manifest = one("AndroidManifest.xml")
        cut = max(8, (len(manifest) * 55) // 100)
        _write_fixed_zip(out_zip, payload,
                         replace={"AndroidManifest.xml": manifest[:cut]})
        return
    if kind == "arsc-type-collision":
        _write_fixed_zip(out_zip, payload,
                         replace={"resources.arsc":
                                  craft_arsc_collision(seed)})
        return
    if kind == "dex-corrupted":
        _write_fixed_zip(out_zip, payload,
                         replace={"classes.dex": dex_corrupt(
                             one("classes.dex"))})
        return
    raise ValueError(f"mutacao desconhecida: {kind}")


def dex_partition(srcroot: str, outjson: str, batches: int) -> dict:
    """Fatiamento CONTÍGUO determinístico dos .class em N lotes (multidex-8).

    Lista global ordenada; primeiros N-1 lotes com tamanho igual (piso) e o
    resto vai para o ÚLTIMO lote. Grava OUTJSON (paths relativos a srcroot) e
    materializa cada lote em <dirname(OUTJSON)>/dexbatch/N/ com a estrutura
    de pacotes preservada (o zip do lote roda com cwd no diretório do lote).
    """
    rels = []
    for dirpath, _dirnames, filenames in os.walk(srcroot):
        for fn in filenames:
            if fn.endswith(".class"):
                rels.append(os.path.relpath(os.path.join(dirpath, fn),
                                            srcroot))
    rels.sort()
    if len(rels) < batches:
        raise SystemExit(f"[fixture-pack] ERRO: {len(rels)} .class < "
                         f"{batches} lotes pedidos")
    base, rem = divmod(len(rels), batches)
    chunks, idx = [], 0
    for b in range(batches):
        size = base + (rem if b == batches - 1 else 0)
        chunks.append(rels[idx:idx + size])
        idx += size
    batch_root = os.path.join(os.path.dirname(os.path.abspath(outjson)),
                              "dexbatch")
    for i, chunk in enumerate(chunks, start=1):
        batch_dir = os.path.join(batch_root, str(i))
        for rel in chunk:
            dst = os.path.join(batch_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(srcroot, rel), dst)
    doc = {"tool": TOOL, "schema_version": 1, "srcroot": srcroot,
           "batches_count": batches, "entries_total": len(rels),
           "strategy": "contiguo-ordenado-resto-no-ultimo",
           "batches": chunks}
    os.makedirs(os.path.dirname(os.path.abspath(outjson)), exist_ok=True)
    with open(outjson, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"[fixture-pack] dex-partition: {len(rels)} .class em {batches} "
          f"lotes -> {outjson}", file=sys.stderr)
    return doc


def collect_dex(work: str, outdir: str) -> None:
    """Copia work/dex/N/classes.dex -> OUTDIR/classes.dex (N=1), classes2.dex
    ... classesN.dex (multidex-8), em ordem determinística."""
    os.makedirs(outdir, exist_ok=True)
    for i in range(1, DEX_BATCHES + 1):
        batch_dir = os.path.join(work, "dex", str(i))
        dexes = sorted(glob.glob(os.path.join(batch_dir, "*.dex")))
        if dexes != [os.path.join(batch_dir, "classes.dex")]:
            raise SystemExit(f"[fixture-pack] ERRO: lote {i} gerou "
                             f"{[os.path.basename(d) for d in dexes]} "
                             "(esperado só classes.dex)")
        name = "classes.dex" if i == 1 else f"classes{i}.dex"
        shutil.copyfile(os.path.join(batch_dir, "classes.dex"),
                        os.path.join(outdir, name))
    print(f"[fixture-pack] collect-dex: classes.dex..classes{DEX_BATCHES}.dex "
          f"em {outdir}", file=sys.stderr)


def ensure_engine_root(seed: int, work: str, engine: str) -> str:
    """Gera engroot (payload/ + src/) do engine com gen-engine-fixtures
    (mesmos args do passo do plano); precisa existir no make_plan para o
    plano listar os .java marcador no javac."""
    out = os.path.join(work, "engroot")
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "gen-engine-fixtures.py"),
           "--engine", engine, "--out", out, "--report",
           os.path.join(work, "engine-payload-report.json"), "--seed",
           str(seed)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print("[fixture-pack] ERRO: gen-engine-fixtures falhou:\n"
              + proc.stdout.decode("utf-8", "replace"), file=sys.stderr)
        raise SystemExit(1)
    return out


def ensure_trap_root(seed: int, work: str) -> str:
    """Gera traproot com gen-trap-manifest (mesmos args do passo do plano);
    precisa existir no make_plan para o plano listar os .java do traproot."""
    out = os.path.join(work, "traproot")
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "gen-trap-manifest.py"),
           "--out", out, "--seed", str(seed)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print("[fixture-pack] ERRO: gen-trap-manifest falhou:\n"
              + proc.stdout.decode("utf-8", "replace"), file=sys.stderr)
        raise SystemExit(1)
    return out


def ensure_dex_corpus(seed: int, work: str, mode: str = "multidex-8") -> str:
    """Gera o corpus gen-dex-stress (mesmos args do passo do plano); precisa
    existir no make_plan para o plano listar os .java do corpus."""
    out = os.path.join(work, "dexsrc")
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "gen-dex-stress.py"),
           "--out", out, "--seed", str(seed)] + list(corpus_args(mode))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print("[fixture-pack] ERRO: gen-dex-stress falhou:\n"
              + proc.stdout.decode("utf-8", "replace"), file=sys.stderr)
        raise SystemExit(1)
    return out


def execute(plan: dict) -> int:
    """Executa os passos best-effort (logs PT-BR em stderr)."""
    for step in plan["steps"]:
        if (step.get("skip_if") == "keystore_existe"
                and os.path.isfile(plan["keystore"])):
            print(f"[fixture-pack] {step['id']}: keystore já existe, pulando",
                  file=sys.stderr)
            continue
        if (step.get("skip_if") == "keystore_b_existe"
                and os.path.isfile(plan.get("keystore_b", ""))):
            print(f"[fixture-pack] {step['id']}: keystore B já existe, "
                  "pulando", file=sys.stderr)
            continue
        if (step.get("skip_if") == "mode_nao_e_v3_rotation"
                and plan.get("fixture") != "v3-rotation-lineage"):
            continue
        if (step.get("skip_if") == "keystore_existe"
                and os.path.isfile(plan["keystore"])):
            print(f"[fixture-pack] {step['id']}: keystore já existe, pulando",
                  file=sys.stderr)
            continue
        print(f"[fixture-pack] {step['id']}: {step['description']}",
              file=sys.stderr)
        proc = subprocess.run(step["command"], cwd=step.get("cwd"))
        if proc.returncode != 0:
            print(f"[fixture-pack] ERRO: passo {step['id']} saiu com "
                  f"{proc.returncode}", file=sys.stderr)
            return 1
    print(f"[fixture-pack] OK: APK fixture em {plan['out_apk']}",
          file=sys.stderr)
    return 0


def selftest() -> int:
    """--dry-run dos 27 modos parseia (com apk_name); --fixture nope sai 2."""
    tmp = tempfile.mkdtemp(prefix="apktester-fixturepack-selftest-")
    try:
        for mode in MODES:
            argv = ["--fixture", mode, "--dry-run", "--seed", str(DEFAULT_SEED),
                    "--out", os.path.join(tmp, "out", mode),
                    "--work", os.path.join(tmp, "work", mode)]
            plan = make_plan(parse_args(argv))
            parsed = json.loads(json.dumps(plan, sort_keys=True))
            assert parsed["fixture"] == mode and parsed["steps"], \
                f"plano do modo {mode} inválido"
            assert parsed.get("apk_name") == APK_NAMES.get(mode, f"{mode}.apk"), \
                f"apk_name ausente/incorreto no modo {mode}"
            print(f"[fixture-pack] selftest {mode}: plano JSON ok "
                  f"({len(parsed['steps'])} passos, apk={parsed['apk_name']})")
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--fixture", "nope",
             "--out", os.path.join(tmp, "nope-out")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert proc.returncode == 2, \
            f"--fixture nope deveria sair 2, veio {proc.returncode}"
        print("[fixture-pack] selftest OK: 27 modos (18 parser-torture "
              "incl. 6 malformed D4 + 9 engines tier C) com plano "
              "parseável e apk_name; --fixture nope => exit 2")
        return 0
    except AssertionError as exc:
        print(f"[fixture-pack] selftest FALHOU: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Empacota APKs fixture sem gradle (aapt2+d8+zip+apksigner).")
    ap.add_argument("--fixture", default=None, choices=tuple(MODES),
                    help="modo da fixture (minSdk9, sig-v1-only, ...)")
    ap.add_argument("--out", default=None,
                    help="diretório do APK final (<out>/<modo>.apk)")
    ap.add_argument("--work", default=None,
                    help="árvore de trabalho (padrão: tempdir)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--dry-run", action="store_true",
                    help="só imprime o plano JSON (exit 0 mesmo sem tools)")
    for name in ("aapt2", "d8", "zip", "apksigner", "zipalign"):
        ap.add_argument(f"--{name}", default=None,
                        help=f"caminho do {name} (padrão: shutil.which)")
    ap.add_argument("--selftest", action="store_true",
                     help="valida planos dos 27 modos em tmp e sai")
    ap.add_argument("--zip64-augment", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--into", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--entries", type=int, default=0, help=argparse.SUPPRESS)
    ap.add_argument("--strip-entry", nargs=2, metavar=("ZIP", "ENTRY"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--dealign", metavar="ZIP", default=None,
                    help=argparse.SUPPRESS)
    ap.add_argument("--malformed-mutate", metavar="KIND", default=None,
                    help=argparse.SUPPRESS)
    ap.add_argument("--src", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dex-partition", nargs=3,
                    metavar=("SRCROOT", "OUTJSON", "N"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--collect-dex", nargs=2, metavar=("WORK", "OUTDIR"),
                    help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def make_plan(args) -> dict:
    """Gera árvore + plano (usado pelo dry-run e pelo selftest)."""
    cfg = MODES[args.fixture]
    apk_name = APK_NAMES.get(args.fixture, f"{args.fixture}.apk")
    out_apk = os.path.join(os.path.abspath(args.out), apk_name)
    os.makedirs(os.path.dirname(out_apk), exist_ok=True)
    work = args.work or tempfile.mkdtemp(prefix="apktester-fixturepack-")
    os.makedirs(work, exist_ok=True)
    java_files = generate_tree(cfg, args.fixture, args.seed, work)
    if cfg["engine"]:
        ensure_engine_root(args.seed, work, args.fixture)
        java_files += sorted(glob.glob(
            os.path.join(work, "engroot", "src", "**", "*.java"),
            recursive=True))
    if cfg["external_manifest"]:
        ensure_trap_root(args.seed, work)
        java_files += sorted(glob.glob(
            os.path.join(work, "traproot", "src", "**", "*.java"),
            recursive=True))
    if is_multidex(args.fixture):
        ensure_dex_corpus(args.seed, work, mode=args.fixture)
        java_files += sorted(glob.glob(
            os.path.join(work, "dexsrc", "java", "**", "*.java"),
            recursive=True))
    tools, android_jar = discover_tools(args)
    return build_plan(args, cfg, work, out_apk, tools, java_files, android_jar)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    if args.strip_entry:
        zip_path, entry = args.strip_entry
        try:
            removed = zip_strip_entry(zip_path, entry)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"[fixture-pack] ERRO: strip-entry falhou: {exc}",
                  file=sys.stderr)
            return 1
        if removed != 1:
            print(f"[fixture-pack] ERRO: entrada '{entry}' não encontrada "
                  f"em {zip_path}", file=sys.stderr)
            return 1
        print(f"[fixture-pack] strip-entry: '{entry}' removida de "
              f"{zip_path}", file=sys.stderr)
        return 0
    if args.malformed_mutate:
        if not args.src or not args.out:
            print("[fixture-pack] ERRO: --malformed-mutate exige --src e "
                  "--out", file=sys.stderr)
            return 2
        try:
            malformed_mutate(args.malformed_mutate, args.src, args.out,
                             args.seed)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            print(f"[fixture-pack] ERRO: mutacao "
                  f"{args.malformed_mutate} falhou: {exc}", file=sys.stderr)
            return 1
        print(f"[fixture-pack] malformed {args.malformed_mutate}: "
              f"{args.src} -> {args.out} (mtimes 1980, seed {args.seed})",
              file=sys.stderr)
        return 0
    if args.dealign:
        try:
            zip_dealign(args.dealign, args.seed)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"[fixture-pack] ERRO: dealign falhou: {exc}",
                  file=sys.stderr)
            return 1
        print(f"[fixture-pack] dealign: assets/unaligned.bin (STORED) como "
              f"primeira entrada de {args.dealign}; dados do resources.arsc "
              f"calibrados para offset mod 4 == 1", file=sys.stderr)
        return 0
    if args.dex_partition:
        srcroot, outjson, n = args.dex_partition
        dex_partition(srcroot, outjson, int(n))
        return 0
    if args.collect_dex:
        collect_dex(args.collect_dex[0], args.collect_dex[1])
        return 0
    if args.zip64_augment:
        if not args.into or args.entries <= 0:
            print("[fixture-pack] ERRO: --zip64-augment exige --into e "
                  "--entries", file=sys.stderr)
            return 2
        zip64_augment(args.into, args.entries, args.seed)
        print(f"[fixture-pack] zip64: {args.entries} entradas anexadas em "
              f"{args.into}", file=sys.stderr)
        return 0
    if not args.fixture:
        print("[fixture-pack] ERRO: --fixture é obrigatório "
              f"(modos: {', '.join(MODES)})", file=sys.stderr)
        return 2
    if not args.out:
        print("[fixture-pack] ERRO: --out é obrigatório (ou use --selftest)",
              file=sys.stderr)
        return 2
    plan = make_plan(args)
    print(f"[fixture-pack] árvore da fixture '{args.fixture}' gerada em "
          f"{plan['work']}", file=sys.stderr)
    if args.dry_run:
        json.dump(plan, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        print("[fixture-pack] dry-run: plano JSON emitido (exit 0)",
              file=sys.stderr)
        return 0
    required = ["aapt2", "d8", "zip", "apksigner", "javac", "keytool"]
    if MODES[args.fixture]["zipalign"]:
        required.append("zipalign")
    missing = [n for n in required if not plan["tools"][n]["available"]]
    if missing or not plan["android_jar"]:
        if missing:
            print(f"[fixture-pack] ferramentas ausentes: {', '.join(missing)}",
                  file=sys.stderr)
        if not plan["android_jar"]:
            print("[fixture-pack] android.jar não encontrado "
                  "(ANDROID_SDK_ROOT)", file=sys.stderr)
        print("[fixture-pack] sem toolchain completa: emitindo só o plano "
              "JSON (instale build-tools + JDK para executar)", file=sys.stderr)
        json.dump(plan, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    return execute(plan)


if __name__ == "__main__":
    sys.exit(main())
