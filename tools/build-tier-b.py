#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-tier-b.py — builds REAIS Tier B da matriz de engines (fase A7).

Para cada um dos 9 engines "build": "nightly" do contrato canônico
(contracts/engines/expected-engines.json), este orquestrador:

  1. baixa a toolchain PESADA pinada direto da fonte oficial
     (Maven Central, npm registry, NuGet, GitHub Releases, aqt/Qt, Flutter
     SDK) para a árvore de trabalho — nada de binário commitado;
  2. roda a parte REAL da toolchain (scalac, hermesc, cordova.js template,
     runtime NativeScript, bob.jar/Defold, export headless do Godot,
     kit Qt android, assemblies Avalonia/.NET android);
  3. empacota o APK pelo MESMO caminho do build-tier-a/fixture-pack
     (aapt2 link -> javac -> d8 --min-api 26 -> zip -> zipalign ->
     apksigner v1+v2) — exceto flutter-full e godot-export, onde a
     própria toolchain produz o APK final;
  4. verifica o APK contra o contrato (detector_artifacts) igual ao
     Tier A — SEM âncora sha256 (binários dependem da versão da
     toolchain).

Estratégia por engine (honestidade documentada no README de cada dir):

  engine-04-scala         scalac 2.13.15 real (jars do Maven Central) + d8
                          com scala-library -> classes.dex com scala.runtime
  engine-13-flutter       Flutter SDK 3.24.5 estável: flutter create +
                          build apk --release --target-platform android-x64
  engine-14-react-native  hermesc do npm react-native@0.76.9 (bundle Hermes
                          real) + libhermes.so do hermes-android AAR +
                          classes.dex do react-android AAR
  engine-15-cordova       cordova.js real do template cordova-android@14.0.1
                          + www próprio + cordova_plugins.js no formato do
                          `cordova prepare`
  engine-17-nativescript  libNativeScript.so real do AAR
                          @nativescript/android@8.8.2 + app JS em assets/app
  engine-22-lua-defold    bob.jar 1.9.8 (pipeline de conteúdo Defold:
                          game.arcd/game.arci) + libdmengine.so (release)
                          do próprio bob.jar
  engine-23-godot         Godot 4.3-stable headless + export templates:
                          --export-release android (APK real com .pck)
  engine-26-qt-qml        kit Qt 6.6.3 android_x86_64 (aqtinstall): Qt6
                          Core/Qml reais + QML próprio em assets/qml
  engine-28-avalonia-dotnet  assemblies Avalonia 11.2.2 (NuGet) +
                          libSkiaSharp.so + runtime .NET android
                          (libmono-android.release.so)

Uso:
  python3 tools/build-tier-b.py --engine engine-04-scala --out DIST \
      [--aapt2 P] [--d8 P] [--apksigner P] [--zipalign P]
  python3 tools/build-tier-b.py --verify-apk APK --engine ENGINE
  python3 tools/build-tier-b.py --sync-contracts
  python3 tools/build-tier-b.py --selftest
  python3 tools/build-tier-b.py --engine E --plan-only   # só o plano JSON

Códigos de saída: 0 ok; 1 falha de execução/verificação; 2 uso inválido.

O CI de PR NÃO roda builds Tier B (só --selftest + plan-only, job
tier-b-contracts); a build REAL roda no engines-nightly.yml (ADR 0002).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
import fnmatch

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

# build-tier-a.py tem hífens no nome (nunca foi um módulo importável);
# carregamos via importlib para reusar o pipeline comum do A4.
import importlib.util  # noqa: E402

_ta_spec = importlib.util.spec_from_file_location(
    "build_tier_a", os.path.join(TOOLS_DIR, "build-tier-a.py"))
ta = importlib.util.module_from_spec(_ta_spec)  # type: ignore[arg-type]
sys.modules["build_tier_a"] = ta
assert _ta_spec is not None and _ta_spec.loader is not None
_ta_spec.loader.exec_module(ta)  # noqa: E402  (reuso do pipeline comum A4)

DEFAULT_SEED = 20261022
TOOL = "build-tier-b.py"
REPO_ROOT = ta.REPO_ROOT
SUITES_ROOT = ta.SUITES_ROOT
CONTRACT_PATH = ta.CONTRACT_PATH
SUITES_JSON = ta.SUITES_JSON

VERSION_CODE = ta.VERSION_CODE
VERSION_NAME = ta.VERSION_NAME
MIN_SDK = ta.MIN_SDK
TARGET_SDK = ta.TARGET_SDK
KS_PASS = ta.KS_PASS
KS_ALIAS = ta.KS_ALIAS

MAVEN = "https://repo1.maven.org/maven2"
NPM = "https://registry.npmjs.org"
NUGET = "https://api.nuget.org/v3-flatcontainer"
GITHUB_DL = "https://github.com"

# Pinos de versão documentados (download é feito AQUI, da fonte oficial,
# dentro da árvore de trabalho; nada é commitado).
PINS = {
    "scala": "2.13.15",
    "flutter": "3.24.5",
    "react-native": "0.76.9",
    "hermes-android": "0.76.9",
    "cordova-android": "14.0.1",
    "nativescript-android": "8.8.2",
    "defold-bob": "1.9.8",
    "godot": "4.3-stable",
    "qt": "6.6.3",
    "aqtinstall": "3.3.0",
    "avalonia": "11.2.2",
    "skiasharp-native-assets-android": "2.88.9",
    "net-android-runtime-x64": "34.0.154",
}


def url_scala(art: str) -> str:
    v = PINS["scala"]
    return f"{MAVEN}/org/scala-lang/{art}/{v}/{art}-{v}.jar"


def url_npm(pkg: str, tarball: str) -> str:
    return f"{NPM}/{pkg}/-/{tarball}"


def url_react_aar(art: str) -> str:
    v = PINS["react-native"]
    return f"{MAVEN}/com/facebook/react/{art}/{v}/{art}-{v}-release.aar"


def url_bob_jar() -> str:
    v = PINS["defold-bob"]
    return f"{GITHUB_DL}/defold/defold/releases/download/{v}/bob.jar"


def url_godot(what: str) -> str:
    v = PINS["godot"]
    names = {
        "editor": f"Godot_v{v}_linux.x86_64.zip",
        "templates": f"Godot_v{v}_export_templates.tpz",
    }
    return f"{GITHUB_DL}/godotengine/godot/releases/download/{v}/{names[what]}"


def url_nuget(pkg: str, version: str) -> str:
    return f"{NUGET}/{pkg.lower()}/{version}/{pkg.lower()}.{version}.nupkg"


def url_flutter_sdk() -> str:
    v = PINS["flutter"]
    return ("https://storage.googleapis.com/flutter_infra_release/releases/"
            f"stable/linux/flutter_linux_{v}-stable.tar.xz")


# ---------------------------------------------------------------------------
# SPECS — fonte única dos 9 engines Tier B (build nightly).
# Cruzada com o contrato canônico pelo --selftest (zero drift).
# ---------------------------------------------------------------------------
SPECS = {
    "engine-04-scala": {
        "kind": "scala-maven",
        "language": "Scala",
        "description": "scalac 2.13.15 real (Maven Central) + d8 com "
                       "scala-library: classes.dex com scala.runtime.",
    },
    "engine-13-flutter": {
        "kind": "flutter-full",
        "language": "Dart/Flutter",
        "description": "Flutter SDK 3.24.5 estável: flutter create android + "
                       "build apk --release --target-platform android-x64.",
    },
    "engine-14-react-native": {
        "kind": "rn-hermes",
        "language": "JS/React Native",
        "description": "hermesc 0.76.9 (npm) -> index.android.bundle Hermes; "
                       "libhermes.so (hermes-android AAR) + classes.dex "
                       "(react-android AAR).",
    },
    "engine-15-cordova": {
        "kind": "cordova-webview",
        "language": "JS/Cordova",
        "description": "cordova.js real do template cordova-android@14.0.1 "
                       "+ www do fixture + cordova_plugins.js canônico.",
    },
    "engine-17-nativescript": {
        "kind": "nativescript-runtime",
        "language": "JS/NativeScript",
        "description": "libNativeScript.so real do AAR @nativescript/android"
                       "@8.8.2 + app JS em assets/app/.",
    },
    "engine-22-lua-defold": {
        "kind": "defold-bob",
        "language": "Lua/Defold",
        "description": "bob.jar 1.9.8: pipeline de conteúdo Defold "
                       "(game.arcd/game.arci) + libdmengine_release.so "
                       "embutido no próprio bob.jar.",
    },
    "engine-23-godot": {
        "kind": "godot-export",
        "language": "GDScript/Godot",
        "description": "Godot 4.3-stable headless + export templates: "
                       "--export-release Android -> APK real com .pck.",
    },
    "engine-26-qt-qml": {
        "kind": "qt-libs",
        "language": "QML/Qt",
        "description": "Kit Qt 6.6.3 android_x86_64 (aqtinstall 3.3.0): "
                       "libQt6Core/Qml_x86_64.so reais + QML em assets/qml.",
    },
    "engine-28-avalonia-dotnet": {
        "kind": "avalonia-nuget",
        "language": "C#/Avalonia",
        "description": "Assemblies Avalonia 11.2.2 + SkiaSharp 2.88.9 "
                       "(android-x64) + runtime .NET android 34.0.154 "
                       "(NuGet pinado).",
    },
}

ENGINE_IDS = tuple(sorted(SPECS))

# Kinds em que a própria toolchain produz o APK final (sem pack comum).
TOOL_APK_KINDS = ("flutter-full", "godot-export")

# Padrões de fonte commitada por kind (o selftest exige pelo menos 1).
SOURCE_GLOBS = {
    "scala-maven": ("src/**/*.scala",),
    "flutter-full": ("lib/*.dart",),
    "rn-hermes": ("assets-src/*.js",),
    "cordova-webview": ("www-src/index.html", "www-src/js/*.js",
                        "www-src/css/*.css"),
    "nativescript-runtime": ("app-src/*.js", "app-src/package.json"),
    "defold-bob": ("defold/game.project", "defold/main/*.script",
                   "defold/main/*.collection", "defold/input/*.input_binding"),
    "godot-export": ("project/project.godot", "project/*.gd",
                     "project/*.tscn", "project/export_presets.cfg"),
    "qt-libs": ("qml/*.qml",),
    "avalonia-nuget": ("assets-src/*.axaml",),
}


def engine_sources(engine: str) -> list:
    """Fontes commitadas do engine (por kind) — erro claro se ausentes."""
    root = os.path.join(SUITES_ROOT, engine)
    files = set()
    for pat in SOURCE_GLOBS[SPECS[engine]["kind"]]:
        for hit in glob.glob(os.path.join(root, pat), recursive=True):
            if os.path.isfile(hit):
                files.add(hit)
    files = sorted(files)
    if not files:
        raise SystemExit(f"[{TOOL}] ERRO: sem fontes em "
                         f"suites/engines/{engine}/ "
                         f"(padrões: {SOURCE_GLOBS[SPECS[engine]['kind']]})")
    return files


def _pins_for(engine: str) -> tuple:
    kind = SPECS[engine]["kind"]
    if kind == "scala-maven":
        return ("scala",)
    if kind == "flutter-full":
        return ("flutter",)
    if kind == "rn-hermes":
        return ("react-native", "hermes-android")
    if kind == "cordova-webview":
        return ("cordova-android",)
    if kind == "nativescript-runtime":
        return ("nativescript-android",)
    if kind == "defold-bob":
        return ("defold-bob",)
    if kind == "godot-export":
        return ("godot",)
    if kind == "qt-libs":
        return ("qt", "aqtinstall")
    if kind == "avalonia-nuget":
        return ("avalonia", "skiasharp-native-assets-android",
                "net-android-runtime-x64")
    return ()


def contract_artifacts(engine: str) -> list:
    return ta.contract_artifacts(engine)


def canonical_entry(engine: str) -> dict:
    return ta.canonical_entry(engine)


def dir_contract(engine: str) -> dict:
    entry = canonical_entry(engine)
    return {
        "id": entry["id"],
        "dir": entry["dir"],
        "language": entry["language"],
        "tier": entry["tier"],
        "build": entry["build"],
        "rustydroid_engines": entry["rustydroid_engines"],
        "detector_artifacts": entry["detector_artifacts"],
        "notes": entry["notes"],
        "built_by": TOOL,
        "pins": {k: v for k, v in PINS.items() if k in _pins_for(engine)},
    }


# ---------------------------------------------------------------------------
# Helpers CLI (passos do plano chamam este mesmo arquivo via subprocess).
# ---------------------------------------------------------------------------
def helper_download(url: str, dest: str, retries: int = 3) -> None:
    """Download determinístico (UA fixo, sem timestamp) com retry."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": f"apk-tester-{TOOL} (deterministic CI fixture)",
            })
            with urllib.request.urlopen(req, timeout=300) as resp, \
                    open(dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            size = os.path.getsize(dest)
            if size <= 0:
                raise RuntimeError(f"download vazio: {url}")
            print(f"[{TOOL}] download ok ({size} bytes): {url}", file=sys.stderr)
            return
        except Exception as exc:  # noqa: BLE001 — retry explícito
            last = exc
            print(f"[{TOOL}] download tentativa {attempt}/{retries} falhou: "
                  f"{exc}", file=sys.stderr)
    raise SystemExit(f"[{TOOL}] ERRO: download falhou após {retries} "
                     f"tentativas: {url} ({last})")


def helper_extract_zip_entry(zip_path: str, member: str, dest: str) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(member)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    print(f"[{TOOL}] extraído {member} -> {dest}", file=sys.stderr)


def helper_extract_tar_member(arch_path: str, member: str, dest: str) -> None:
    with tarfile.open(arch_path, "r:*") as tf:
        try:
            src = tf.extractfile(member)
        except KeyError:
            cand = [m for m in tf.getnames()
                    if m == member or m.endswith("/" + member)]
            if not cand:
                raise SystemExit(f"[{TOOL}] ERRO: membro {member} ausente "
                                 f"de {arch_path}")
            src = tf.extractfile(cand[0])
        if src is None:
            raise SystemExit(f"[{TOOL}] ERRO: membro {member} não é arquivo "
                             f"regular: {arch_path}")
        data = src.read()
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    print(f"[{TOOL}] extraído {member} -> {dest}", file=sys.stderr)


def helper_chmod_x(path: str) -> None:
    cur = os.stat(path).st_mode
    os.chmod(path, cur | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def helper_stage_file(src: str, dest: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    shutil.copyfile(src, dest)


def helper_stage_tree(src: str, dest: str) -> None:
    """Cópia determinística de árvore (ordem de caminhada sorted)."""
    src, dest = os.path.abspath(src), os.path.abspath(dest)
    for root, dirs, files in os.walk(src):
        dirs.sort()
        rel = os.path.relpath(root, src)
        out_root = dest if rel == "." else os.path.join(dest, rel)
        os.makedirs(out_root, exist_ok=True)
        for f in sorted(files):
            shutil.copyfile(os.path.join(root, f), os.path.join(out_root, f))


def helper_stage_zip_member(zip_path: str, member: str, dest: str) -> None:
    """Extrai membro de zip/aar diretamente para o STAGE."""
    helper_extract_zip_entry(zip_path, member, dest)


def helper_write_cordova_plugins(dest: str) -> None:
    """cordova_plugins.js no formato que o `cordova prepare` gera para
    um projeto sem plugins (lista vazia) — conteúdo canônico e estável."""
    content = "\n".join([
        "cordova.define('cordova/plugin_list', function (require, "
        "exports, module) {",
        "module.exports = [];",
        "});",
        "",
    ])
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def helper_prepare_godot_templates(tpz: str, dest_dir: str) -> None:
    """Extrai o .tpz (zip) para <export_templates>/<versão>/."""
    version = PINS["godot"].replace("-stable", ".stable")  # 4.3.stable
    target = os.path.join(dest_dir, version)
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(tpz) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            # membros vêm como "templates/<arquivo>"
            rel = name.split("/", 1)[1] if "/" in name else name
            out = os.path.join(target, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with zf.open(info) as src, open(out, "wb") as fh:
                shutil.copyfileobj(src, fh)
    print(f"[{TOOL}] export templates -> {target}", file=sys.stderr)


def helper_write_godot_preset(src: str, dest: str, keystore: str,
                              out_apk_name: str) -> None:
    """Cópia do export_presets.cfg com caminhos ABSOLUTOS do keystore e do
    APK de saída (o preset commitado usa placeholders)."""
    with open(src, "r", encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("@KEYSTORE_PLACEHOLDER@", os.path.abspath(keystore))
    text = text.replace("@KEYSTORE_PASS@", KS_PASS.replace("pass:", ""))
    text = text.replace("@EXPORT_PATH_PLACEHOLDER@", out_apk_name)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def helper_write_godot_editor_settings(dest: str, java_home: str,
                                       android_home: str) -> None:
    """editor_settings-4.3.tres mínimo e VÁLIDO: o export Android do
    Godot 4.3 valida export/android/{java,android}_sdk_path antes do
    export (sem gradle). Formato .tres completo — sem header, o Godot
    descarta o arquivo e recria defaults com paths vazios."""
    content = "\n".join([
        "[gd_resource type=\"EditorSettings\" format=3]",
        "",
        "[resource]",
        f"export/android/java_sdk_path = \"{java_home}\"",
        f"export/android/android_sdk_path = \"{android_home}\"",
        "",
    ])
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    print(f"[{TOOL}] editor settings godot -> {dest}", file=sys.stderr)


def helper_collect_flutter_apk(proj: str, dest: str) -> None:
    pats = [os.path.join(proj, "build", "app", "outputs", "flutter-apk",
                         "app-release.apk")]
    for p in pats:
        if os.path.isfile(p):
            shutil.copyfile(p, dest)
            print(f"[{TOOL}] APK do flutter: {p} -> {dest}", file=sys.stderr)
            return
    raise SystemExit(f"[{TOOL}] ERRO: app-release.apk não encontrado em "
                     f"{proj}")


def helper_collect_godot_apk(proj: str, dest: str) -> None:
    p = os.path.join(proj, "engine23godot.apk")
    if os.path.isfile(p):
        shutil.copyfile(p, dest)
        print(f"[{TOOL}] APK do godot: {p} -> {dest}", file=sys.stderr)
        return
    raise SystemExit(f"[{TOOL}] ERRO: engine23godot.apk não encontrado em "
                     f"{proj}")


# ---------------------------------------------------------------------------
# Passos por kind (toolchains pesadas, downloads pinados)
# ---------------------------------------------------------------------------
def plan_for_engine(engine: str, args, work: str, stage: str,
                    android_jar: str | None) -> list:
    """Passos específicos do kind; usa _download/_extract com caminhos fixos."""
    kind = SPECS[engine]["kind"]
    tl = os.path.join(work, "tl")
    os.makedirs(tl, exist_ok=True)
    me = os.path.abspath(__file__)
    py = sys.executable
    steps: list = []

    if kind == "scala-maven":
        comp = os.path.join(tl, "scala-compiler.jar")
        lib = os.path.join(tl, "scala-library.jar")
        refl = os.path.join(tl, "scala-reflect.jar")
        # scalac exige o -d existente de antemão
        os.makedirs(os.path.join(work, "scala-classes"), exist_ok=True)
        for url, dest in ((url_scala("scala-compiler"), comp),
                          (url_scala("scala-library"), lib),
                          (url_scala("scala-reflect"), refl)):
            steps.append({
                "id": f"download-{os.path.basename(dest)}",
                "description": f"jar oficial do Maven Central: {url}",
                "command": [py, me, "--download", url, dest],
                "cwd": None})
        steps.append({
            "id": "scalac",
            "description": f"scalac {PINS['scala']} (java -cp "
                           "scala-compiler) sobre as fontes .scala "
                           "commitadas",
            "command": ["java", "-cp", ":".join([comp, refl, lib]),
                        "scala.tools.nsc.Main", "-deprecation", "-classpath",
                        lib, "-d", os.path.join(work, "scala-classes")]
            + [p for p in engine_sources(engine) if p.endswith(".scala")],
            "cwd": None})
        steps.append({
            "id": "jar-scala-classes",
            "description": "empacota os .class do scalac p/ o d8",
            "command": [py, me, "--jar-classes",
                        os.path.join(work, "scala-classes.jar"),
                        os.path.join(work, "scala-classes")],
            "cwd": None})

    elif kind == "flutter-full":
        sdk = os.environ.get("FLUTTER_ROOT") or os.path.join(work, "flutter")
        flutter = os.path.join(sdk, "bin", "flutter")
        proj = os.path.join(work, "flutter-proj")
        steps.append({
            "id": "download-flutter-sdk",
            "description": f"Flutter SDK {PINS['flutter']} estável "
                           "(tarball oficial; use FLUTTER_ROOT para reaproveitar)",
            "command": [py, me, "--download", url_flutter_sdk(),
                        os.path.join(tl, "flutter.tar.xz")],
            "cwd": None})
        steps.append({
            "id": "extract-flutter-sdk",
            "description": "extrai o SDK para a árvore de trabalho",
            "command": ["tar", "-xJf", os.path.join(tl, "flutter.tar.xz"),
                        "-C", work],
            "cwd": None})
        steps.append({
            "id": "flutter-no-analytics",
            "description": "desliga telemetria do flutter (build limpa)",
            "command": [flutter, "config", "--no-analytics"],
            "cwd": None})
        steps.append({
            "id": "flutter-create",
            "description": "flutter create --platforms android "
                           "--org dev.apktester.engine --project-name "
                           "engine13flutter",
            "command": [flutter, "create", "--platforms", "android",
                        "--org", "dev.apktester.engine",
                        "--project-name", "engine13flutter", proj],
            "cwd": None})
        steps.append({
            "id": "stage-dart-main",
            "description": "sobrescreve lib/main.dart com o Dart do fixture",
            "command": [py, me, "--stage-file",
                        os.path.join(SUITES_ROOT, engine, "lib", "main.dart"),
                        os.path.join(proj, "lib", "main.dart")],
            "cwd": None})
        steps.append({
            "id": "flutter-build-apk",
            "description": f"flutter build apk --release "
                           f"(Flutter {PINS['flutter']}, android-x64; gradle "
                           "do projeto assina com debug keystore)",
            "command": [flutter, "build", "apk", "--release",
                        "--target-platform", "android-x64"],
            "cwd": proj})
        steps.append({
            "id": "collect-flutter-apk",
            "description": "copia app-release.apk para a árvore de trabalho",
            "command": [py, me, "--collect-flutter-apk", proj,
                        os.path.join(work, "tool-apk")],
            "cwd": None})

    elif kind == "rn-hermes":
        rn_tgz = os.path.join(tl, "react-native.tgz")
        hermes_aar = os.path.join(tl, "hermes-android.aar")
        react_aar = os.path.join(tl, "react-android.aar")
        hermesc = os.path.join(tl, "hermesc")
        # hermesc escreve um temp ao lado do -out; o diretório precisa existir
        os.makedirs(os.path.join(stage, "assets"), exist_ok=True)
        steps += [
            {"id": "download-react-native-npm",
             "description": "tarball oficial npm react-native@0.76.9 "
                            "(traz hermesc linux pré-construído)",
             "command": [py, me, "--download",
                         url_npm("react-native",
                                 "react-native-0.76.9.tgz"), rn_tgz],
             "cwd": None},
            {"id": "extract-hermesc",
             "description": "hermesc (ELF estático) do tarball npm",
             "command": [py, me, "--extract-tar-member", rn_tgz,
                         "package/sdks/hermesc/linux64-bin/hermesc", hermesc],
             "cwd": None},
            {"id": "chmod-hermesc",
             "description": "permissão de execução do hermesc",
             "command": [py, me, "--chmod-x", hermesc], "cwd": None},
            {"id": "download-hermes-android-aar",
             "description": "AAR hermes-android 0.76.9 (Maven Central; "
                            "libhermes.so real)",
             "command": [py, me, "--download", url_react_aar("hermes-android"),
                         hermes_aar], "cwd": None},
            {"id": "stage-libhermes",
             "description": "jni/x86_64/libhermes.so -> lib/x86_64/",
             "command": [py, me, "--extract-zip-entry", hermes_aar,
                         "jni/x86_64/libhermes.so",
                         os.path.join(stage, "lib", "x86_64",
                                      "libhermes.so")], "cwd": None},
            {"id": "download-react-android-aar",
             "description": "AAR react-android 0.76.9 (classes.jar com "
                            "com.facebook.react)",
             "command": [py, me, "--download", url_react_aar("react-android"),
                         react_aar], "cwd": None},
            {"id": "extract-react-classes",
             "description": "classes.jar do AAR react-android",
             "command": [py, me, "--extract-zip-entry", react_aar,
                         "classes.jar", os.path.join(work,
                                                     "react-classes.jar")],
             "cwd": None},
            {"id": "hermesc-bundle",
             "description": "hermesc -emit-binary: index.android.bundle "
                            "REAL (magic bytecode Hermes)",
             "command": [hermesc, "-emit-binary", "-out",
                         os.path.join(stage, "assets",
                                      "index.android.bundle"),
                         os.path.join(SUITES_ROOT, engine, "assets-src",
                                      "index.js")],
             "cwd": None},
        ]

    elif kind == "cordova-webview":
        cdv_tgz = os.path.join(tl, "cordova-android.tgz")
        steps += [
            {"id": "download-cordova-android-npm",
             "description": f"tarball oficial npm cordova-android@"
                            f"{PINS['cordova-android']} (template cordova.js)",
             "command": [py, me, "--download",
                         url_npm("cordova-android",
                                 f"cordova-android-{PINS['cordova-android']}"
                                 ".tgz"), cdv_tgz],
             "cwd": None},
            {"id": "stage-cordova-js",
             "description": "assets/www/cordova.js real do template",
             "command": [py, me, "--extract-tar-member", cdv_tgz,
                         "package/templates/project/assets/www/cordova.js",
                         os.path.join(stage, "assets", "www", "cordova.js")],
             "cwd": None},
            {"id": "stage-www",
             "description": "assets/www do fixture (index.html/js/css)",
             "command": [py, me, "--stage-tree",
                         os.path.join(SUITES_ROOT, engine, "www-src"),
                         os.path.join(stage, "assets", "www")],
             "cwd": None},
            {"id": "write-cordova-plugins",
             "description": "cordova_plugins.js no formato do "
                            "`cordova prepare` (lista vazia, canônico)",
             "command": [py, me, "--write-cordova-plugins",
                         os.path.join(stage, "assets", "www",
                                      "cordova_plugins.js")],
             "cwd": None},
        ]

    elif kind == "nativescript-runtime":
        ns_tgz = os.path.join(tl, "nativescript-android.tgz")
        ns_aar = os.path.join(tl, "nativescript-regular.aar")
        steps += [
            {"id": "download-nativescript-android-npm",
             "description": f"tarball oficial npm @nativescript/android@"
                            f"{PINS['nativescript-android']} (runtime AAR)",
             "command": [py, me, "--download",
                         url_npm("@nativescript/android",
                                 f"android-{PINS['nativescript-android']}"
                                 ".tgz"), ns_tgz],
             "cwd": None},
            {"id": "extract-nativescript-aar",
             "description": "nativescript-regular.aar do tarball npm",
             "command": [py, me, "--extract-tar-member", ns_tgz,
                         "package/framework/app/libs/runtime-libs/"
                         "nativescript-regular.aar", ns_aar],
             "cwd": None},
            {"id": "stage-libnativescript",
             "description": "jni/x86_64/libNativeScript.so -> lib/x86_64/",
             "command": [py, me, "--extract-zip-entry", ns_aar,
                         "jni/x86_64/libNativeScript.so",
                         os.path.join(stage, "lib", "x86_64",
                                      "libNativeScript.so")], "cwd": None},
            {"id": "stage-app-assets",
             "description": "assets/app/ do fixture (app JS NativeScript)",
             "command": [py, me, "--stage-tree",
                         os.path.join(SUITES_ROOT, engine, "app-src"),
                         os.path.join(stage, "assets", "app")],
             "cwd": None},
        ]

    elif kind == "defold-bob":
        bob = os.path.join(tl, "bob.jar")
        proj = os.path.join(SUITES_ROOT, engine, "defold")
        build_dir = os.path.join(proj, "build", "default")
        steps += [
            {"id": "download-bob-jar",
             "description": f"bob.jar {PINS['defold-bob']} (GitHub Releases "
                            "defold/defold)",
             "command": [py, me, "--download", url_bob_jar(), bob],
             "cwd": None},
            {"id": "bob-build-archive",
             "description": "bob -a build: pipeline de conteúdo Defold "
                            "(Lua -> game.arcd/game.arci em build/default)",
             "command": ["java", "-jar", bob, "-r", os.path.abspath(proj),
                         "-a", "--platform", "arm64-android",
                         "--variant", "release", "build"],
             "cwd": None},
            {"id": "stage-defold-archive",
             "description": "game.arcd + game.arci -> assets/",
             "command": [py, me, "--stage-defold-archive", build_dir, stage],
             "cwd": None},
            {"id": "stage-libdmengine",
             "description": "libdmengine_release.so (embutido no bob.jar) "
                            "-> lib/arm64-v8a/libdmengine.so",
             "command": [py, me, "--extract-zip-entry", bob,
                         "libexec/arm64-android/libdmengine_release.so",
                         os.path.join(stage, "lib", "arm64-v8a",
                                      "libdmengine.so")], "cwd": None},
        ]

    elif kind == "godot-export":
        editor_zip = os.path.join(tl, "godot-editor.zip")
        tpz = os.path.join(tl, "godot-templates.tpz")
        godot = os.path.join(tl, "godot")
        proj_src = os.path.join(SUITES_ROOT, engine, "project")
        proj = os.path.join(work, "godot-proj")
        keystore = os.path.join(work, "debug.keystore")
        home_templates = os.path.join(os.path.expanduser("~"),
                                      ".local", "share", "godot",
                                      "export_templates")
        steps += [
            {"id": "download-godot-editor",
             "description": f"Godot {PINS['godot']} editor linux x86_64 "
                            "(GitHub Releases godotengine/godot)",
             "command": [py, me, "--download", url_godot("editor"),
                         editor_zip], "cwd": None},
            {"id": "extract-godot-editor",
             "description": "binário headless do editor",
             "command": [py, me, "--extract-zip-entry", editor_zip,
                         f"Godot_v{PINS['godot']}_linux.x86_64", godot],
             "cwd": None},
            {"id": "chmod-godot",
             "description": "permissão de execução do editor",
             "command": [py, me, "--chmod-x", godot], "cwd": None},
            {"id": "download-godot-templates",
             "description": "export templates Android do Godot "
                            f"{PINS['godot']} (tpz ~1.1 GB)",
             "command": [py, me, "--download", url_godot("templates"), tpz],
             "cwd": None},
            {"id": "install-godot-templates",
             "description": "templates -> ~/.local/share/godot/"
                            "export_templates/4.3.stable",
             "command": [py, me, "--prepare-godot-templates", tpz,
                         home_templates], "cwd": None},
            {"id": "stage-godot-project",
             "description": "copia o projeto commitado (project.godot, "
                            "main.tscn, main.gd, icon.svg)",
             "command": [py, me, "--stage-tree", proj_src, proj],
             "cwd": None},
            {"id": "write-godot-preset",
             "description": "reescreve o preset com keystore/saída "
                            "absolutos (placeholders commitados)",
             "command": [py, me, "--write-godot-preset",
                         os.path.join(proj_src, "export_presets.cfg"),
                         os.path.join(proj, "export_presets.cfg"), keystore,
                         "engine23godot.apk"], "cwd": None},
            {"id": "write-godot-editor-settings",
             "description": "editor_settings-4.3.tres com java_sdk/"
                            "android_sdk do runner (validação do export)",
             "command": [py, me, "--write-godot-editor-settings",
                        os.path.join(os.path.expanduser("~"), ".config",
                                     "godot", "editor_settings-4.3.tres"),
                        os.environ.get("JAVA_HOME", ""),
                        os.environ.get("ANDROID_HOME")
                        or os.environ.get("ANDROID_SDK_ROOT", "")],
             "cwd": None},
            {"id": "godot-import",
             "description": "godot --headless --import (cache de recursos)",
             "command": [godot, "--headless", "--path", proj, "--import"],
             "cwd": None},
            {"id": "godot-export-release",
             "description": "godot --headless --export-release Android "
                            "(APK real assinado com o keystore do pack)",
             "command": [godot, "--headless", "--path", proj,
                         "--export-release", "Android",
                         os.path.join(proj, "engine23godot.apk")],
             "cwd": None},
            {"id": "collect-godot-apk",
             "description": "copia o APK exportado para a árvore de trabalho",
             "command": [py, me, "--collect-godot-apk", proj,
                         os.path.join(work, "tool-apk")],
             "cwd": None},
        ]

    elif kind == "qt-libs":
        qt_root = os.path.join(work, "qt")
        qt_lib = os.path.join(qt_root, f"{PINS['qt']}", "android_x86_64",
                              "lib")
        steps += [
            {"id": "ensure-aqtinstall",
             "description": f"pip3 install aqtinstall=={PINS['aqtinstall']}",
             "command": [sys.executable, "-m", "pip", "install", "--quiet",
                         f"aqtinstall=={PINS['aqtinstall']}"], "cwd": None},
            {"id": "aqt-install-qt",
             "description": f"kit Qt {PINS['qt']} android_x86_64 oficial "
                            "(download.qt.io via aqtinstall)",
             "command": [sys.executable, "-m", "aqt", "install-qt", "linux",
                         "android", PINS["qt"], "android_x86_64",
                         "-O", qt_root], "cwd": None},
            {"id": "stage-qt-core",
             "description": "libQt6Core_x86_64.so real -> lib/x86_64/",
             "command": [py, me, "--stage-file",
                         os.path.join(qt_lib, "libQt6Core_x86_64.so"),
                         os.path.join(stage, "lib", "x86_64",
                                      "libQt6Core_x86_64.so")], "cwd": None},
            {"id": "stage-qt-qml",
             "description": "libQt6Qml_x86_64.so real -> lib/x86_64/",
             "command": [py, me, "--stage-file",
                         os.path.join(qt_lib, "libQt6Qml_x86_64.so"),
                         os.path.join(stage, "lib", "x86_64",
                                      "libQt6Qml_x86_64.so")], "cwd": None},
            {"id": "stage-qml-assets",
             "description": "assets/qml/ do fixture (QML commitado)",
             "command": [py, me, "--stage-tree",
                         os.path.join(SUITES_ROOT, engine, "qml"),
                         os.path.join(stage, "assets", "qml")],
             "cwd": None},
        ]

    elif kind == "avalonia-nuget":
        av = PINS["avalonia"]
        sk = PINS["skiasharp-native-assets-android"]
        mr = PINS["net-android-runtime-x64"]
        av_pkg = os.path.join(tl, "avalonia.nupkg")
        av_android = os.path.join(tl, "avalonia.android.nupkg")
        sk_pkg = os.path.join(tl, "skiasharp.nupkg")
        mr_pkg = os.path.join(tl, "net-android-runtime.nupkg")
        asm_dir = os.path.join(stage, "assemblies")
        steps += [
            {"id": "download-nuget-avalonia",
             "description": f"avalonia {av} (NuGet oficial)",
             "command": [py, me, "--download",
                         url_nuget("Avalonia", av), av_pkg], "cwd": None},
            {"id": "download-nuget-avalonia-android",
             "description": f"avalonia.android {av} (NuGet oficial)",
             "command": [py, me, "--download",
                         url_nuget("Avalonia.Android", av), av_android],
             "cwd": None},
            {"id": "download-nuget-skiasharp",
             "description": f"SkiaSharp.NativeAssets.Android {sk} (NuGet)",
             "command": [py, me, "--download",
                         url_nuget("SkiaSharp.NativeAssets.Android", sk),
                         sk_pkg], "cwd": None},
            {"id": "download-nuget-net-android-runtime",
             "description": f"Microsoft.Android.Runtime.34.android-x64 "
                            f"{mr} (runtime pack oficial)",
             "command": [py, me, "--download",
                         url_nuget("Microsoft.Android.Runtime.34.android-x64",
                                   mr), mr_pkg], "cwd": None},
            {"id": "stage-avalonia-assemblies",
             "description": "Avalonia.Base/Controls/Skia.dll (net8.0) -> "
                            "assemblies/",
             "command": [py, me, "--stage-nuget-assemblies", av_pkg, asm_dir],
             "cwd": None},
            {"id": "stage-avalonia-android-dll",
             "description": "Avalonia.Android.dll (net8.0-android34.0) -> "
                            "assemblies/",
             "command": [py, me, "--extract-zip-entry", av_android,
                         "lib/net8.0-android34.0/Avalonia.Android.dll",
                         os.path.join(asm_dir, "Avalonia.Android.dll")],
             "cwd": None},
            {"id": "stage-libskiasharp",
             "description": "runtimes/android-x64/native/libSkiaSharp.so -> "
                            "lib/x86_64/libSkiaSharp.so",
             "command": [py, me, "--extract-zip-entry", sk_pkg,
                         "runtimes/android-x64/native/libSkiaSharp.so",
                         os.path.join(stage, "lib", "x86_64",
                                      "libSkiaSharp.so")], "cwd": None},
            {"id": "stage-libmonodroid",
             "description": "runtimes/android-x64/native/"
                            "libmono-android.release.so -> lib/x86_64/",
             "command": [py, me, "--extract-zip-entry", mr_pkg,
                         "runtimes/android-x64/native/"
                         "libmono-android.release.so",
                         os.path.join(stage, "lib", "x86_64",
                                      "libmono-android.release.so")],
             "cwd": None},
        ]
    else:  # pragma: no cover
        raise SystemExit(f"[{TOOL}] kind desconhecido: {kind}")
    return steps


# ---------------------------------------------------------------------------
# Plano completo (mesma forma do Tier A; ta.execute roda)
# ---------------------------------------------------------------------------
def build_plan(args) -> dict:
    engine = args.engine
    spec = SPECS[engine]
    kind = spec["kind"]
    os.makedirs(os.path.abspath(args.out), exist_ok=True)
    out_apk = os.path.join(os.path.abspath(args.out), f"{engine}.apk")
    work = args.work or tempfile.mkdtemp(prefix="apktester-tier-b-")
    os.makedirs(work, exist_ok=True)
    stage = os.path.join(work, "stage")
    os.makedirs(stage, exist_ok=True)
    tools = ta.discover(args)
    android_jar = ta.find_android_jar()
    a2 = tools["aapt2"]["path"] or "aapt2"
    d8 = tools["d8"]["path"] or "d8"
    za = tools["zipalign"]["path"] or "zipalign"
    signer = tools["apksigner"]["path"] or "apksigner"
    keystore = os.path.join(work, "debug.keystore")
    unsigned = os.path.join(work, "bundle-unsigned.apk")
    aligned = os.path.join(work, "bundle-aligned.apk")
    jar_tok = android_jar or "@ANDROID_JAR@"
    me = os.path.abspath(__file__)
    py = sys.executable

    tool_apk = kind in TOOL_APK_KINDS
    java_files: list = []
    if not tool_apk:
        java_files = ta.write_common_tree(engine, args.seed, work)

    steps: list = []
    if not tool_apk:
        steps.append({
            "id": "keystore",
            "description": "keystore de debug do pack (skip se já existe)",
            "command": ["keytool", "-genkeypair", "-keystore", keystore,
                        "-storetype", "PKCS12", "-storepass", "apktester",
                        "-keypass", "apktester", "-alias", KS_ALIAS,
                        "-keyalg", "RSA", "-keysize", "2048", "-validity",
                        "10000", "-dname", "CN=APK Tester Tier B, "
                        "OU=Engines, O=apktester, L=Recife, S=PE, C=BR"],
            "cwd": None, "skip_if": "keystore_existe"})
        steps += [
            {"id": "aapt2-compile",
             "description": "compila res/ em res.zip (flat)",
             "command": [a2, "compile", "--dir",
                         os.path.join(work, "res"), "-o",
                         os.path.join(work, "res.zip")], "cwd": None},
            {"id": "aapt2-link",
             "description": "liga manifest+res no APK base e gera R.java",
             "command": [a2, "link", "-o", unsigned, "--manifest",
                         os.path.join(work, "AndroidManifest.xml"),
                         "-I", jar_tok, "--java", os.path.join(work, "gen"),
                         "--min-sdk-version", str(MIN_SDK),
                         "--target-sdk-version", str(TARGET_SDK),
                         "--version-code", str(VERSION_CODE),
                         "--version-name", VERSION_NAME,
                         os.path.join(work, "res.zip")], "cwd": None},
        ]
    else:
        # flutter assina com o debug keystore do gradle; godot assina com o
        # keystore do preset (criado aqui antes do export).
        steps.append({
            "id": "keystore",
            "description": "keystore de debug (godot usa no preset; flutter "
                           "usa o do gradle)",
            "command": ["keytool", "-genkeypair", "-keystore", keystore,
                        "-storetype", "PKCS12", "-storepass", "apktester",
                        "-keypass", "apktester", "-alias", KS_ALIAS,
                        "-keyalg", "RSA", "-keysize", "2048", "-validity",
                        "10000", "-dname", "CN=APK Tester Tier B, "
                        "OU=Engines, O=apktester, L=Recife, S=PE, C=BR"],
            "cwd": None, "skip_if": "keystore_existe"})

    steps += plan_for_engine(engine, args, work, stage, android_jar)

    if not tool_apk:
        d8_inputs = [os.path.join(work, "classes-input.jar")]
        if kind == "scala-maven":
            d8_inputs.append(os.path.join(work, "scala-classes.jar"))
            d8_inputs.append(os.path.join(work, "tl", "scala-library.jar"))
        elif kind == "rn-hermes":
            d8_inputs.append(os.path.join(work, "react-classes.jar"))
        steps += [
            {"id": "javac-common",
             "description": "javac dos POJOs + R.java",
             "command": ["javac", "-encoding", "UTF-8", "-source", "8",
                         "-target", "8", "-Xlint:-options", "-d",
                         os.path.join(work, "classes")] + java_files,
             "cwd": None},
            {"id": "jar-classes",
             "description": "empacota os .class p/ o d8",
             "command": [py, me, "--jar-classes",
                         os.path.join(work, "classes-input.jar"),
                         os.path.join(work, "classes")],
             "cwd": None},
            {"id": "d8",
             "description": f"d8 --min-api {MIN_SDK} (multidex automático)",
             "command": [d8, "--release", "--min-api", str(MIN_SDK)]
             + (["--lib", android_jar] if android_jar else [])
             + ["--output", os.path.join(work, "dex")] + d8_inputs,
             "cwd": None},
            {"id": "zip-dex",
             "description": "anexa classes*.dex na raiz do APK (ordem "
                            "determinística)",
             "command": [py, me, "--zip-dex", os.path.join(work, "dex"),
                         unsigned], "cwd": None},
            {"id": "zip-stage",
             "description": "anexa lib/, assets/, assemblies/ e META-INF/ "
                            "do STAGE (sem entradas de diretório)",
             "command": [py, me, "--zip-stage", stage, unsigned],
             "cwd": None},
            {"id": "zipalign",
             "description": "alinhamento de 4 bytes (-p p/ .so)",
             "command": [za, "-f", "-p", "4", unsigned, aligned],
             "cwd": None},
            {"id": "apksigner",
             "description": "assina v1+v2 e grava em --out",
             "command": [signer, "sign", "--ks", keystore, "--ks-pass",
                         KS_PASS, "--ks-key-alias", KS_ALIAS, "--key-pass",
                         KS_PASS, "--min-sdk-version", str(MIN_SDK),
                         "--v1-signing-enabled", "true",
                         "--v2-signing-enabled", "true",
                         "--v3-signing-enabled", "false",
                         "--out", out_apk, aligned],
             "cwd": None},
        ]
    else:
        tool_apk_path = os.path.join(work, "tool-apk")
        if kind == "godot-export":
            steps.append({
                "id": "verify-tool-apk-signed",
                "description": "godot já assinou (keystore do preset); nada "
                               "a re-assinar",
                "command": [py, me, "--no-op", tool_apk_path], "cwd": None})
        else:  # flutter-full
            steps.append({
                "id": "verify-tool-apk-signed",
                "description": "APK do gradle/flutter (debug keystore do "
                               "runner); nada a re-assinar",
                "command": [py, me, "--no-op", tool_apk_path], "cwd": None})
        steps.append({
            "id": "publish-tool-apk",
            "description": "publica o APK da toolchain em --out",
            "command": [py, me, "--publish-tool-apk",
                        os.path.join(work, "tool-apk"), out_apk], "cwd": None})

    notes = [
        "build Tier B REAL (A7, engines-nightly): toolchains pesadas "
        "pinadas, baixadas da fonte oficial para a árvore de trabalho",
        "verificação por detector_artifacts do contrato (presença + globs + "
        "dex-strings/elf-strings) — SEM âncora sha256, pois os binários "
        "dependem da versão da toolchain",
        "CI de PR roda só --selftest/--plan-only (tier-b-contracts); a build "
        "real é gated no engines-nightly.yml (ADR 0002)",
    ]
    return {
        "tool": TOOL, "engine": engine, "kind": kind, "seed": args.seed,
        "description": spec["description"],
        "language": spec["language"],
        "application_id": ta.app_id(engine),
        "apk_name": f"{engine}.apk",
        "min_sdk": MIN_SDK, "target_sdk": TARGET_SDK,
        "pins": {k: v for k, v in PINS.items() if k in _pins_for(engine)},
        "work": work, "out_apk": out_apk, "android_jar": android_jar,
        "keystore": keystore, "tools": tools, "notes": notes,
        "steps": steps,
        "all_android_tools_available": tool_apk or all(
            tools[n]["available"] for n in ("aapt2", "d8", "apksigner",
                                            "zipalign")),
    }


# ---------------------------------------------------------------------------
# Helpers de empacotamento (delegam ao Tier A) e utilitários do plano
# ---------------------------------------------------------------------------
def helper_stage_defold_archive(build_dir: str, stage: str) -> None:
    for name in ("game.arcd", "game.arci"):
        src = os.path.join(build_dir, name)
        if not os.path.isfile(src):
            raise SystemExit(f"[{TOOL}] ERRO: {src} ausente (bob build?)")
        helper_stage_file(src, os.path.join(stage, "assets", name))


def helper_stage_nuget_assemblies(nupkg: str, dest_dir: str) -> None:
    with zipfile.ZipFile(nupkg) as zf:
        wanted = ("Avalonia.Base.dll", "Avalonia.Controls.dll",
                  "Avalonia.Skia.dll", "Avalonia.Themes.Fluent.dll")
        found = 0
        for name in zf.namelist():
            base = name.rsplit("/", 1)[-1]
            if base in wanted:
                helper_extract_zip_entry(nupkg, name,
                                         os.path.join(dest_dir, base))
                found += 1
    if not found:
        raise SystemExit(f"[{TOOL}] ERRO: nenhum assembly Avalonia em "
                         f"{nupkg}")


def helper_no_op(path: str) -> None:
    if not os.path.isfile(path):
        raise SystemExit(f"[{TOOL}] ERRO: APK da toolchain ausente: {path}")
    size = os.path.getsize(path)
    print(f"[{TOOL}] APK da toolchain presente ({size} bytes): {path}",
          file=sys.stderr)


def helper_publish_tool_apk(src: str, dest: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    shutil.copyfile(src, dest)
    print(f"[{TOOL}] APK Tier B publicado: {dest}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Verificação (--verify-apk) — delega ao Tier A (contrato canônico)
# ---------------------------------------------------------------------------
def verify_apk(apk: str, engine: str) -> int:
    return ta.verify_apk(apk, engine)


# ---------------------------------------------------------------------------
# Contratos por diretório (--sync-contracts)
# ---------------------------------------------------------------------------
def sync_contracts() -> int:
    for engine in ENGINE_IDS:
        path = os.path.join(SUITES_ROOT, engine, "expected-engines.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(dir_contract(engine), indent=2,
                                ensure_ascii=False, sort_keys=True) + "\n")
        print(f"[{TOOL}] contrato por diretório escrito: "
              f"suites/engines/{engine}/expected-engines.json")
    print(f"[{TOOL}] sync ok: {len(ENGINE_IDS)} engines Tier B contra "
          "contracts/engines/expected-engines.json")
    return 0


def check_against_canonical() -> list:
    """Drift entre SPECS e o contrato canônico (tier/build/artifacts)."""
    with open(CONTRACT_PATH, "r", encoding="utf-8") as fh:
        canon = json.load(fh)
    by_dir = {e.get("dir"): e for e in canon.get("engines", [])}
    drifts = []
    for engine in ENGINE_IDS:
        entry = by_dir.get(engine)
        if entry is None:
            drifts.append(f"{engine}: ausente do contrato canônico")
            continue
        if entry.get("tier") != "B" or entry.get("build") != "nightly":
            drifts.append(f"{engine}: tier/build do contrato divergem "
                          f"(esperado B/nightly)")
        if entry.get("language") != SPECS[engine]["language"]:
            drifts.append(f"{engine}: language diverge do contrato")
        artifacts = list(entry.get("detector_artifacts", []))
        for art in artifacts:
            if art.startswith("dex-strings:") or \
                    art.startswith("elf-strings:") or "*" in art:
                continue
            if not (art.startswith("lib/") or art.startswith("assets/")
                    or art.startswith("META-INF/")
                    or art.startswith("assemblies/")
                    or art.startswith("classes")
                    or art == "AndroidManifest.xml"):
                drifts.append(f"{engine}: artefato {art} fora dos prefixos "
                              "suportados")
    extra = set(by_dir) - set(ENGINE_IDS)
    b_tier = sorted(k for k in extra if by_dir[k].get("tier") == "B")
    if b_tier:
        drifts.append(f"contrato canônico tem entradas tier B fora das "
                      f"specs: {b_tier}")
    with open(SUITES_JSON, "r", encoding="utf-8") as fh:
        suites = json.load(fh).get("suites", [])
    suite_dirs = {s.get("apk") for s in suites}
    for engine in ENGINE_IDS:
        if f"suites/engines/{engine}" not in suite_dirs:
            drifts.append(f"{engine}: sem suíte smoke em contracts/"
                          "suites.json")
    return drifts


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def selftest() -> int:
    """Planos parseáveis dos 9 engines + zero drift contra o contrato."""
    tmp = tempfile.mkdtemp(prefix="apktester-tier-b-selftest-")
    try:
        drifts = check_against_canonical()
        if drifts:
            for d in drifts:
                print(f"[{TOOL}] DRIFT: {d}", file=sys.stderr)
            print(f"[{TOOL}] selftest FALHOU: drift contra o contrato "
                  "canônico", file=sys.stderr)
            return 1
        for engine in ENGINE_IDS:
            argv = ["--engine", engine, "--plan-only", "--seed",
                    str(DEFAULT_SEED),
                    "--out", os.path.join(tmp, "out", engine),
                    "--work", os.path.join(tmp, "work", engine)]
            plan = build_plan(parse_args(argv))
            parsed = json.loads(json.dumps(plan, sort_keys=True))
            assert parsed["engine"] == engine and parsed["steps"], \
                f"plano de {engine} inválido"
            assert parsed["apk_name"] == f"{engine}.apk", \
                f"apk_name de {engine} incorreto"
            assert parsed["min_sdk"] == MIN_SDK, "minSdk do plano errado"
            kind = SPECS[engine]["kind"]
            n = len(parsed["steps"])
            print(f"[{TOOL}] selftest {engine}: plano ok ({n} passos, "
                  f"kind={kind})")
        for engine in ENGINE_IDS:
            root = os.path.join(SUITES_ROOT, engine)
            for need in ("build.sh", "README.md"):
                if not os.path.isfile(os.path.join(root, need)):
                    print(f"[{TOOL}] selftest FALHOU: {need} ausente em "
                          f"suites/engines/{engine}/", file=sys.stderr)
                    return 1
            if not engine_sources(engine):
                print(f"[{TOOL}] selftest FALHOU: sem fontes em "
                      f"suites/engines/{engine}/", file=sys.stderr)
                return 1
        print(f"[{TOOL}] selftest OK: {len(ENGINE_IDS)} engines Tier B com "
              "plano parseável, zero drift do contrato, build.sh + README + "
              "fontes presentes")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Builds reais Tier B (nightly) da matriz de engines "
                    "(A7).")
    ap.add_argument("--engine", default=None, choices=tuple(ENGINE_IDS),
                    help="diretório do engine (engine-04-scala, ...)")
    ap.add_argument("--out", default=None,
                    help="diretório do APK final (<out>/<engine>.apk)")
    ap.add_argument("--work", default=None,
                    help="árvore de trabalho (padrão: tempdir)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--plan-only", action="store_true",
                    help="só imprime o plano JSON (exit 0 mesmo sem tools)")
    ap.add_argument("--verify-apk", metavar="APK", default=None,
                    help="verifica o APK contra o contrato (use com "
                         "--engine)")
    ap.add_argument("--sync-contracts", action="store_true",
                    help="escreve os expected-engines.json por diretório")
    ap.add_argument("--selftest", action="store_true",
                    help="valida planos dos 9 engines + drift do contrato")
    ap.add_argument("--report", default=None,
                    help="grava report JSON do build (sha256, passos) "
                         "no caminho dado")
    for name in ("aapt2", "d8", "apksigner", "zipalign"):
        ap.add_argument(f"--{name}", default=None,
                        help=f"caminho do {name} (padrão: shutil.which)")
    # helpers internos (não documentados)
    ap.add_argument("--download", nargs=2, metavar=("URL", "DEST"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--extract-zip-entry", nargs=3,
                    metavar=("ZIP", "MEMBER", "DEST"), help=argparse.SUPPRESS)
    ap.add_argument("--extract-tar-member", nargs=3,
                    metavar=("ARCHIVE", "MEMBER", "DEST"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--chmod-x", metavar="PATH", help=argparse.SUPPRESS)
    ap.add_argument("--stage-file", nargs=2, metavar=("SRC", "DEST"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--stage-tree", nargs=2, metavar=("SRC", "DEST"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--stage-defold-archive", nargs=2,
                    metavar=("BUILD_DIR", "STAGE"), help=argparse.SUPPRESS)
    ap.add_argument("--stage-nuget-assemblies", nargs=2,
                    metavar=("NUPKG", "DEST_DIR"), help=argparse.SUPPRESS)
    ap.add_argument("--write-cordova-plugins", metavar="DEST",
                    help=argparse.SUPPRESS)
    ap.add_argument("--prepare-godot-templates", nargs=2,
                    metavar=("TPZ", "TEMPLATES_ROOT"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--write-godot-preset", nargs=4,
                    metavar=("SRC", "DEST", "KEYSTORE", "OUT_NAME"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--write-godot-editor-settings", nargs=3,
                    metavar=("DEST", "JAVA_HOME", "ANDROID_HOME"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--collect-flutter-apk", nargs=2,
                    metavar=("PROJ", "DEST"), help=argparse.SUPPRESS)
    ap.add_argument("--collect-godot-apk", nargs=2,
                    metavar=("PROJ", "DEST"), help=argparse.SUPPRESS)
    ap.add_argument("--jar-classes", nargs="+",
                    metavar=("OUTJAR", "ROOT"), help=argparse.SUPPRESS)
    ap.add_argument("--zip-dex", nargs=2, metavar=("DEXDIR", "APK"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--zip-stage", nargs=2, metavar=("STAGE", "APK"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--no-op", metavar="PATH", help=argparse.SUPPRESS)
    ap.add_argument("--publish-tool-apk", nargs=2, metavar=("SRC", "DEST"),
                    help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def write_report(plan: dict, path: str) -> None:
    doc = {
        "tool": TOOL, "engine": plan["engine"], "kind": plan["kind"],
        "application_id": plan["application_id"],
        "apk": plan["out_apk"], "apk_name": plan["apk_name"],
        "pins": plan["pins"], "min_sdk": plan["min_sdk"],
        "target_sdk": plan["target_sdk"],
        "android_jar": plan["android_jar"],
        "steps": [s["id"] for s in plan["steps"]],
    }
    if os.path.isfile(plan["out_apk"]):
        with open(plan["out_apk"], "rb") as fh:
            data = fh.read()
        doc["apk_bytes"] = len(data)
        doc["apk_sha256"] = hashlib.sha256(data).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print(f"[{TOOL}] report: {path}", file=sys.stderr)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    if args.sync_contracts:
        return sync_contracts()
    if args.download:
        helper_download(*args.download)
        return 0
    if args.extract_zip_entry:
        helper_extract_zip_entry(*args.extract_zip_entry)
        return 0
    if args.extract_tar_member:
        helper_extract_tar_member(*args.extract_tar_member)
        return 0
    if args.chmod_x:
        helper_chmod_x(args.chmod_x)
        return 0
    if args.stage_file:
        helper_stage_file(*args.stage_file)
        return 0
    if args.stage_tree:
        helper_stage_tree(*args.stage_tree)
        return 0
    if args.stage_defold_archive:
        helper_stage_defold_archive(*args.stage_defold_archive)
        return 0
    if args.stage_nuget_assemblies:
        helper_stage_nuget_assemblies(*args.stage_nuget_assemblies)
        return 0
    if args.write_cordova_plugins:
        helper_write_cordova_plugins(args.write_cordova_plugins)
        return 0
    if args.prepare_godot_templates:
        helper_prepare_godot_templates(*args.prepare_godot_templates)
        return 0
    if args.write_godot_preset:
        helper_write_godot_preset(*args.write_godot_preset)
        return 0
    if args.write_godot_editor_settings:
        helper_write_godot_editor_settings(*args.write_godot_editor_settings)
        return 0
    if args.collect_flutter_apk:
        helper_collect_flutter_apk(*args.collect_flutter_apk)
        return 0
    if args.collect_godot_apk:
        helper_collect_godot_apk(*args.collect_godot_apk)
        return 0
    if args.jar_classes:
        if len(args.jar_classes) < 2:
            print(f"[{TOOL}] ERRO: --jar-classes exige OUTJAR e ao menos "
                  "uma raiz de classes", file=sys.stderr)
            return 2
        ta.helper_jar_classes(args.jar_classes[0],
                              list(args.jar_classes[1:]))
        return 0
    if args.zip_dex:
        ta.helper_zip_dex(*args.zip_dex)
        return 0
    if args.zip_stage:
        ta.helper_zip_stage(*args.zip_stage)
        return 0
    if args.no_op:
        helper_no_op(args.no_op)
        return 0
    if args.publish_tool_apk:
        helper_publish_tool_apk(*args.publish_tool_apk)
        return 0
    if args.verify_apk:
        if not args.engine:
            print(f"[{TOOL}] ERRO: --verify-apk exige --engine",
                  file=sys.stderr)
            return 2
        if not os.path.isfile(args.verify_apk):
            print(f"[{TOOL}] ERRO: APK não encontrado: {args.verify_apk}",
                  file=sys.stderr)
            return 1
        return verify_apk(args.verify_apk, args.engine)
    if not args.engine:
        print(f"[{TOOL}] ERRO: --engine é obrigatório "
              f"(engines: {', '.join(ENGINE_IDS)})", file=sys.stderr)
        return 2
    if not args.out:
        if args.plan_only:
            # plan-only sem --out: destino fictício (o APK não é gerado)
            args.out = os.path.join(tempfile.gettempdir(),
                                    "apktester-tier-b-plan")
        else:
            print(f"[{TOOL}] ERRO: --out é obrigatório (ou use --selftest)",
                  file=sys.stderr)
            return 2
    plan = build_plan(args)
    print(f"[{TOOL}] árvore do engine '{args.engine}' em {plan['work']}",
          file=sys.stderr)
    if args.plan_only:
        json.dump(plan, sys.stdout, indent=2, sort_keys=True,
                  ensure_ascii=False)
        sys.stdout.write("\n")
        print(f"[{TOOL}] plan-only: plano JSON emitido (exit 0)",
              file=sys.stderr)
        return 0
    rc = ta.execute(plan)
    if rc == 0 and args.report:
        write_report(plan, args.report)
    return rc


if __name__ == "__main__":
    sys.exit(main())
