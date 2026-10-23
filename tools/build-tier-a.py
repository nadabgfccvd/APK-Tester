#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-tier-a.py — builds REAIS Tier A da matriz de engines (fase A4).

Para cada um dos 14 engines "build": "real" do contrato canônico
(contracts/engines/expected-engines.json), este orquestrador:

  1. monta a árvore de trabalho (manifesto + res + POJOs padrão + fontes
     commitadas do diretório do engine);
  2. roda a toolchain REAL do engine (javac/d8/kotlinc/groovyc/NDK clang/
     cargo-ndk/gomobile/zig cc/haxe/wat2wasm/hermesc/gradle+chaquopy);
  3. empacota o APK pelo MESMO caminho do fixture-pack (aapt2 link -> javac
     -> d8 --min-api 26 -> zip -> zipalign -> apksigner v1+v2);
  4. verifica o APK contra o contrato (detector_artifacts: caminhos exatos,
     globs, dex-strings:* e elf-strings:*) — SEM âncoras de sha256, porque
     os binários Tier A dependem da versão da toolchain (o determinismo
     byte-a-byte fica para os geradores seedados e o A8).

Diferença honesta vs. Tier C (ADR 0003): aqui o payload É executável e os
artefatos vêm de compiladores reais; nada é stub.

Uso:
  python3 tools/build-tier-a.py --engine engine-01-java --out DIST \
      [--aapt2 P] [--d8 P] [--apksigner P] [--zipalign P]
  python3 tools/build-tier-a.py --verify-apk APK --engine ENGINE
  python3 tools/build-tier-a.py --sync-contracts
  python3 tools/build-tier-a.py --selftest
  python3 tools/build-tier-a.py --engine E --plan-only   # só o plano JSON

Códigos de saída: 0 ok; 1 falha de execução/verificação; 2 uso inválido.
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
import fnmatch

DEFAULT_SEED = 20261022
TOOL = "build-tier-a.py"
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
SUITES_ROOT = os.path.join(REPO_ROOT, "suites", "engines")
CONTRACT_PATH = os.path.join(REPO_ROOT, "contracts", "engines",
                             "expected-engines.json")
SUITES_JSON = os.path.join(REPO_ROOT, "contracts", "suites.json")

VERSION_CODE = 900036
VERSION_NAME = "1.0.0"
MIN_SDK = 26
TARGET_SDK = 36
KS_PASS = "pass:apktester"
KS_ALIAS = "apktester"

# Pinos de versão documentados (a instalação é trabalho do
# tools/setup-tier-a-toolchain.sh; aqui só servem ao plano e ao report).
PINS = {
    "kotlin": "2.0.20",
    "compose-mp": "1.6.11",
    "groovy": "3.0.21",
    "go": "1.23.4",
    "gomobile": "v0.0.0-20261011034528-197770444867",
    "zig": "0.13.0",
    "haxe": "4.3.6",
    "wabt": "1.0.36",
    "gradle": "8.10.2",
    "chaquopy": "16.1.0",
    "agp": "8.7.3",
    "hermes-engine": "0.11.0",
    "rust": "stable (runner; versão exata no report)",
    "cargo-ndk": "3.5.0",
    "ndk": "r27 (ANDROID_NDK_LATEST_HOME do runner)",
    "tauri": "2.12",
    "wry": "0.57",
    "wasmer": "7",
}


def slugify(engine: str) -> str:
    """Slug de pacote Java válido a partir do nome do diretório."""
    return re.sub(r"[^a-z0-9_]", "", engine.lower())


def app_id(engine: str) -> str:
    return "dev.apktester.engine." + slugify(engine)


# ---------------------------------------------------------------------------
# SPECS — fonte única dos 14 engines Tier A (build real).
# Cruzada com o contrato canônico pelo --selftest (zero drift).
# ---------------------------------------------------------------------------
SPECS = {
    "engine-01-java": {
        "kind": "java-multidex",
        "language": "Java",
        "description": "Multi-dex real (corpus >64k refs) + invoke-custom "
                       "(lambdas via LambdaMetafactory, min-api 26) + "
                       "marcador dex-strings do contrato.",
    },
    "engine-02-kotlin": {
        "kind": "kotlin",
        "language": "Kotlin",
        "description": "kotlinc 2.0.20 -include-runtime: kotlin-stdlib no "
                       "DEX (kotlin.jvm.internal) + <module>.kotlin_module "
                       "em META-INF.",
    },
    "engine-03-kmp": {
        "kind": "kmp",
        "language": "Kotlin Multiplatform",
        "description": "Fontes compartilhadas (common/platform) "
                       "compiladas pelo kotlinc + runtime Compose-MP "
                       "(runtime-desktop 1.6.11) no mesmo DEX.",
    },
    "engine-06-groovy": {
        "kind": "groovy",
        "language": "Groovy",
        "description": "groovyc 3.0.21 + runtime org.codehaus.groovy dexado "
                       "junto (página real do runtime no DEX).",
    },
    "engine-07-c-ndk": {
        "kind": "ndk-c",
        "language": "C (NDK)",
        "description": "clang do NDK r27: libnative-c.so para arm64-v8a e "
                       "x86_64 com exports JNI Java_*.",
    },
    "engine-08-cpp-ndk": {
        "kind": "ndk-cpp",
        "language": "C++ (NDK)",
        "description": "clang++ do NDK com libc++ + libc++_shared.so "
                       "copiada do sysroot para os dois ABIs.",
    },
    "engine-09-rust": {
        "kind": "rust",
        "language": "Rust",
        "description": "cargo-ndk (sem dependências externas, panic=unwind, "
                       "strip=false): librust_native.so com "
                       "rust_begin_unwind no ELF.",
    },
    "engine-10-go": {
        "kind": "gomobile",
        "language": "Go",
        "description": "gomobile bind (x/mobile pinado): libgojni.so "
                       "(jni/ do AAR -> lib/ do APK) + bridge dexado com "
                       "marcador literal go.Seq.",
    },
    "engine-12-zig": {
        "kind": "zig",
        "language": "Zig",
        "description": "zig cc 0.13 freestanding (-nostdlib) para "
                       "x86_64-linux-android: libzig_native.so com strings "
                       "zig no ELF.",
    },
    "engine-16-tauri": {
        "kind": "rust-workspace",
        "language": "Rust/Tauri v2",
        "description": "Dois cdylibs reais da stack Tauri: tauri-android "
                       "(crate tauri 2.12) e wry (crate wry 0.57), "
                       "cargo-ndk para x86_64.",
    },
    "engine-24-haxe": {
        "kind": "haxe",
        "language": "Haxe",
        "description": "Haxe 4.3.6 -java (hxjava+ant): classes haxe.root "
                       "compiladas por javac e dexadas.",
    },
    "engine-25-python-chaquopy": {
        "kind": "gradle-chaquopy",
        "language": "Python/Chaquopy",
        "description": "Gradle 8.10.2 + AGP 8.7.3 + Chaquopy 16.1.0: APK "
                       "gradle real com libpython3*.so e assets/chaquopy "
                       "(x86_64), assinado pelo apksigner do pack.",
    },
    "engine-30-wasm-in-app": {
        "kind": "wasm",
        "language": "Rust/WASM (host embutido)",
        "description": "module.wasm compilado pelo wat2wasm (wabt 1.0.36) + "
                       "host libwasmer.so (crate wasmer 7, singlepass) via "
                       "cargo-ndk.",
    },
    "engine-31-hybrid": {
        "kind": "hybrid",
        "language": "Kotlin+Rust+Hermes+WASM",
        "description": "TST-14 num ÚNICO APK: DEX Kotlin + librust_hybrid.so "
                       "(cargo-ndk) + index.android.bundle (hermesc real) + "
                       "module.wasm (wat2wasm).",
    },
}

ENGINE_IDS = tuple(sorted(SPECS))
CANONICAL_IDS = {
    "engine-01": "engine-01-java", "engine-02": "engine-02-kotlin",
    "engine-03": "engine-03-kmp", "engine-06": "engine-06-groovy",
    "engine-07": "engine-07-c-ndk", "engine-08": "engine-08-cpp-ndk",
    "engine-09": "engine-09-rust", "engine-10": "engine-10-go",
    "engine-12": "engine-12-zig", "engine-16": "engine-16-tauri",
    "engine-24": "engine-24-haxe",
    "engine-25": "engine-25-python-chaquopy",
    "engine-30": "engine-30-wasm-in-app", "engine-31": "engine-31-hybrid",
}


def contract_artifacts(engine: str) -> list:
    """detector_artifacts do contrato canônico (fonte da verdade)."""
    with open(CONTRACT_PATH, "r", encoding="utf-8") as fh:
        canon = json.load(fh)
    for entry in canon.get("engines", []):
        if entry.get("dir") == engine:
            return list(entry.get("detector_artifacts", []))
    raise SystemExit(f"[{TOOL}] ERRO: {engine} ausente do contrato canônico")


def canonical_entry(engine: str) -> dict:
    with open(CONTRACT_PATH, "r", encoding="utf-8") as fh:
        canon = json.load(fh)
    for entry in canon.get("engines", []):
        if entry.get("dir") == engine:
            return entry
    raise SystemExit(f"[{TOOL}] ERRO: {engine} ausente do contrato canônico")


def dir_contract(engine: str) -> dict:
    """Contrato por diretório (mesmo formato do gen-engine-fixtures)."""
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
        "pins": {k: v for k, v in PINS.items()
                 if k in _pins_for(engine)},
    }


def _pins_for(engine: str) -> tuple:
    kind = SPECS[engine]["kind"]
    if kind in ("kotlin", "kmp"):
        return ("kotlin", "compose-mp")
    if kind == "groovy":
        return ("groovy",)
    if kind in ("ndk-c", "ndk-cpp"):
        return ("ndk",)
    if kind == "rust":
        return ("rust", "cargo-ndk")
    if kind == "gomobile":
        return ("go", "gomobile", "ndk")
    if kind == "zig":
        return ("zig",)
    if kind == "rust-workspace":
        return ("rust", "cargo-ndk", "tauri", "wry")
    if kind == "haxe":
        return ("haxe",)
    if kind == "gradle-chaquopy":
        return ("gradle", "chaquopy", "agp")
    if kind == "wasm":
        return ("wabt", "rust", "cargo-ndk", "wasmer")
    if kind == "hybrid":
        return ("kotlin", "rust", "cargo-ndk", "hermes-engine", "wabt")
    return ()


# ---------------------------------------------------------------------------
# Árvore comum: manifesto, res, POJOs (mesmo estilo do fixture-pack)
# ---------------------------------------------------------------------------
JAVA_TEMPLATE = '''package {pkg};

/** Fixture APK Tester ({mode}) — build Tier A real (A4). POJO sem imports
 *  android.*: javac roda sem android.jar. Para o RustyDroid a verdade de
 *  componentes é o manifesto (CORE-12); o DEX existe para exercitar o
 *  parser/VM e a detecção do engine. */
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


def manifest_xml(engine: str) -> str:
    pkg = app_id(engine)
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
        f'    package="{pkg}"',
        f'    android:versionCode="{VERSION_CODE}"',
        f'    android:versionName="{VERSION_NAME}">',
        '',
        f'    <uses-sdk android:minSdkVersion="{MIN_SDK}"',
        f'              android:targetSdkVersion="{TARGET_SDK}"/>',
        '',
        '    <uses-permission android:name="android.permission.INTERNET"/>',
        '',
        '    <application android:label="@string/app_name" '
        'android:hasCode="true">',
        '        <activity android:name=".MainActivity" '
        'android:exported="true">',
        '            <intent-filter>',
        '                <action android:name="android.intent.action.MAIN"/>',
        '                <category '
        'android:name="android.intent.category.LAUNCHER"/>',
        '            </intent-filter>',
        '        </activity>',
        '        <service android:name=".TestService" '
        'android:exported="false"/>',
        '        <receiver android:name=".TestReceiver" '
        'android:exported="false"/>',
        '        <provider android:name=".TestProvider" '
        'android:exported="false"',
        f'                  android:authorities="{pkg}.provider"/>',
        '    </application>',
        '</manifest>',
        '',
    ]) + "\n"


def strings_xml(engine: str) -> str:
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<resources>',
        f'    <string name="app_name">APK Tester engine {engine}</string>',
        f'    <string name="seed">{DEFAULT_SEED}</string>',
        '</resources>',
        '',
    ]) + "\n"


def write_common_tree(engine: str, seed: int, work: str) -> list:
    """Manifesto + res + POJOs dos 4 componentes; devolve os .java."""
    pkg = app_id(engine)
    pkg_path = pkg.replace(".", "/")
    files = {
        "AndroidManifest.xml": manifest_xml(engine),
        "res/values/strings.xml": strings_xml(engine),
    }
    java_files = []
    for cls, role in (("MainActivity", "activity"), ("TestService", "service"),
                      ("TestReceiver", "receiver"), ("TestProvider",
                                                     "provider")):
        rel = f"src/{pkg_path}/{cls}.java"
        files[rel] = JAVA_TEMPLATE.format(pkg=pkg, cls=cls, mode=engine,
                                          role=role, seed=seed)
        java_files.append(os.path.join(work, rel))
    for rel, content in files.items():
        full = os.path.join(work, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    os.makedirs(os.path.join(work, "dex"), exist_ok=True)
    os.makedirs(os.path.join(work, "classes"), exist_ok=True)
    r_java = os.path.join(work, "gen", pkg_path, "R.java")
    return java_files + [r_java]


# Padrões de fonte commitada por kind (o selftest exige pelo menos 1).
SOURCE_GLOBS = {
    "java-multidex": ("src/**/*.java",),
    "kotlin": ("src/**/*.kt",),
    "kmp": ("src/**/*.kt",),
    "groovy": ("src/**/*.groovy",),
    "ndk-c": ("native/*.c",),
    "ndk-cpp": ("native/*.cpp",),
    "rust": ("native/Cargo.toml", "native/src/*.rs"),
    "gomobile": ("gobind/*.go", "gobind/go.mod", "src/**/*.java"),
    "zig": ("native/*.zig",),
    "rust-workspace": ("native/Cargo.toml", "native/*/Cargo.toml",
                       "native/*/src/*.rs"),
    "haxe": ("src/**/*.hx",),
    "gradle-chaquopy": ("gradle-proj/build.gradle",
                        "gradle-proj/settings.gradle",
                        "gradle-proj/app/build.gradle",
                        "gradle-proj/app/src/main/AndroidManifest.xml",
                        "gradle-proj/app/src/main/java/**/*.java",
                        "gradle-proj/app/src/main/python/*.py",
                        "gradle-proj/app/src/main/res/values/*.xml"),
    "wasm": ("module.wat", "native/Cargo.toml", "native/src/*.rs"),
    "hybrid": ("src/**/*.kt", "module.wat", "assets-src/*.js",
               "native/Cargo.toml", "native/src/*.rs"),
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


def kt_sources(engine: str) -> list:
    """Fontes Kotlin p/ o kotlinc (filtra .wat/.js/.toml do hybrid)."""
    return [p for p in engine_sources(engine) if p.endswith(".kt")]


def find_android_jar() -> str | None:
    roots = [os.environ.get(e) for e in ("ANDROID_SDK_ROOT", "ANDROID_HOME")]
    roots.append(os.path.join(os.path.expanduser("~"), "Android", "Sdk"))
    cands = []
    for root in roots:
        if root:
            cands += glob.glob(os.path.join(root, "platforms", "*",
                                            "android.jar"))
    if not cands:
        return None

    def key(path: str):
        m = re.search(r"platforms[/\\]android-(\d+)[/\\]", path)
        return int(m.group(1)) if m else 0

    return sorted(cands, key=key)[-1]


def find_ndk() -> str | None:
    for env in ("ANDROID_NDK_LATEST_HOME", "ANDROID_NDK_HOME",
                "ANDROID_NDK_ROOT"):
        v = os.environ.get(env)
        if v and os.path.isdir(v):
            return v
    for root in (os.environ.get("ANDROID_HOME"),
                 os.environ.get("ANDROID_SDK_ROOT")):
        if root:
            ndks = sorted(glob.glob(os.path.join(root, "ndk", "*")))
            if ndks:
                return ndks[-1]
    return None


def env_tool(name: str) -> str | None:
    """Ferramenta de engine via env (ex.: KOTLINC, ZIG, WAT2WASM)."""
    return os.environ.get(name) or None


def discover(args) -> dict:
    names = ("aapt2", "d8", "apksigner", "zipalign")
    tools = {}
    for name in names:
        path = getattr(args, name, None) or shutil.which(name)
        ok = bool(path) and os.path.isfile(path) and os.access(path,
                                                               os.X_OK)
        tools[name] = {"path": path, "available": ok}
    return tools


def placeholders(kind: str) -> dict:
    """Nomes de placeholder por ferramenta de engine (plano sem toolchain)."""
    base = {
        "javac": "@JAVAC@", "kotlinc": "@KOTLINC@", "groovyc": "@GROOVYC@",
        "clang": "@NDK_CLANG@", "cargo-ndk": "@CARGO_NDK@",
        "gomobile": "@GOMOBILE@", "unzip": "@UNZIP@", "zig": "@ZIG@",
        "haxe": "@HAXE@", "ant": "@ANT@", "gradle": "@GRADLE@",
        "wat2wasm": "@WAT2WASM@", "hermesc": "@HERMESC@",
    }
    return base


# ---------------------------------------------------------------------------
# Plano por engine
# ---------------------------------------------------------------------------
def plan_for_engine(engine: str, args, work: str, stage: str,
                    tools: dict, android_jar: str | None) -> list:
    """Passos ESPECÍFICOS do engine (compilações da toolchain real).

    Convenção: tudo que vai DENTRO do APK além de manifest/res/dex fica em
    STAGE (espelha a raiz do APK: lib/, assets/, META-INF/).
    """
    kind = SPECS[engine]["kind"]
    ph = placeholders(kind)
    steps: list = []

    if kind == "java-multidex":
        # Corpus >64k method refs (gen-dex-stress); o javac comum (em
        # build_plan) compila corpus + probe invoke-custom juntos.
        steps.append({
            "id": "gen-corpus",
            "description": "corpus Java >64k refs (gen-dex-stress: 220 "
                           "classes x 330 rotinas) para forçar "
                           "classes.dex + classes2.dex",
            "command": [sys.executable,
                        os.path.join(TOOLS_DIR, "gen-dex-stress.py"),
                        "--out", os.path.join(work, "corpus"), "--seed",
                        str(args.seed), "--classes", "220",
                        "--methods-per-class", "330", "--strings", "2000",
                        "--fields", "128"],
            "cwd": None})
    elif kind == "kotlin":
        steps.append({
            "id": "kotlinc",
            "description": f"kotlinc {PINS['kotlin']} -include-runtime "
                           "(kotlin-stdlib inteiro no jar de entrada do d8)",
            "command": [env_tool("KOTLINC") or ph["kotlinc"],
                        "-include-runtime", "-module-name", engine,
                        "-d", os.path.join(work, "kotlin-classes.jar")]
                       + kt_sources(engine),
            "cwd": None})
        steps.append({
            "id": "extract-kotlin-module",
            "description": "extrai META-INF/*.kotlin_module do jar p/ o "
                           "STAGE (o d8 não copia recursos)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--extract-zip", os.path.join(work,
                                                      "kotlin-classes.jar"),
                        "META-INF/", stage],
            "cwd": None})
    elif kind == "kmp":
        steps.append({
            "id": "fetch-compose-runtime",
            "description": f"runtime Compose-MP {PINS['compose-mp']} "
                           "(runtime-desktop, Maven Central, pin exato)",
            "command": ["curl", "-fsSL", "-o",
                        os.path.join(work, "compose-runtime.jar"),
                        "https://repo1.maven.org/maven2/org/jetbrains/"
                        "compose/runtime/runtime-desktop/"
                        f"{PINS['compose-mp']}/runtime-desktop-"
                        f"{PINS['compose-mp']}.jar"],
            "cwd": None})
        steps.append({
            "id": "kotlinc-kmp",
            "description": "kotlinc commonMain+platformMain (expect/actual) "
                           "-include-runtime",
            "command": [env_tool("KOTLINC") or ph["kotlinc"],
                        "-include-runtime", "-module-name", engine,
                        "-d", os.path.join(work, "kmp-classes.jar")]
                       + kt_sources(engine),
            "cwd": None})
        steps.append({
            "id": "extract-kotlin-module",
            "description": "extrai META-INF/*.kotlin_module p/ o STAGE",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--extract-zip", os.path.join(work,
                                                      "kmp-classes.jar"),
                        "META-INF/", stage],
            "cwd": None})
    elif kind == "groovy":
        # groovyc escreve no MESMO -d do javac comum: um único jar de
        # classes do app + runtime groovy como input separado do d8.
        steps.append({
            "id": "groovyc",
            "description": f"groovyc {PINS['groovy']} (GROOVY_HOME do "
                           "setup-toolchain) para o probe Groovy",
            "command": [env_tool("GROOVYC") or ph["groovyc"], "-d",
                        os.path.join(work, "classes")]
                       + engine_sources(engine),
            "cwd": None})
    elif kind in ("ndk-c", "ndk-cpp"):
        ndk = env_tool("ANDROID_NDK") or "@NDK@"
        toolbin = os.path.join(ndk, "toolchains", "llvm", "prebuilt",
                               "linux-x86_64", "bin")
        clang = "clang" if kind == "ndk-c" else "clang++"
        src = engine_sources(engine)[0]
        for abi, triple in (("arm64-v8a", "aarch64-linux-android"),
                            ("x86_64", "x86_64-linux-android")):
            out = os.path.join(stage, "lib", abi,
                               "libnative-c.so" if kind == "ndk-c"
                               else "libnative-cpp.so")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            compiler = os.path.join(toolbin, f"{triple}26-{clang}")
            if kind == "ndk-cpp":
                compiler = os.path.join(
                    toolbin, f"{triple}26-clang++")
            cmd = [compiler if os.path.isabs(compiler)
                   else f"@NDK_CLANG@{triple}26", "-shared", "-fPIC",
                   "-O2", "-o", out]
            if kind == "ndk-cpp":
                cmd += ["-stdlib=libc++"]
            cmd.append(src)
            steps.append({
                "id": f"ndk-{abi}",
                "description": f"NDK {clang} para {abi} ({triple}, api 26)",
                "command": cmd if os.path.isabs(compiler) else
                [os.path.join(toolbin, f"{triple}26-{clang}"), "-shared",
                 "-fPIC", "-O2", "-o", out]
                + (["-stdlib=libc++"] if kind == "ndk-cpp" else [])
                + [src],
                "cwd": None})
        if kind == "ndk-cpp":
            steps.append({
                "id": "copy-libcxx",
                "description": "libc++_shared.so do sysroot do NDK para os "
                               "dois ABIs (marcador real de STL)",
                "command": [sys.executable, os.path.abspath(__file__),
                            "--copy-sysroot-libcxx", ndk, stage],
                "cwd": None})
    elif kind == "rust":
        # --no-strip: o contrato pede elf-strings:rust_begin_unwind (o
        # cargo-ndk stripa o .so por padrão, removendo o .symtab).
        steps.append({
            "id": "cargo-ndk",
            "description": "cargo-ndk build --release --no-strip (cdylib "
                           "rust_native, panic=unwind; symtab preservada "
                           "p/ o marcador ELF do contrato) para os 2 ABIs",
            "command": ["cargo", "ndk",
                        "-t", "arm64-v8a", "-t", "x86_64",
                        "--platform", str(MIN_SDK),
                        "--no-strip",
                        "-o", os.path.join(stage, "lib"),
                        "build", "--release"],
            "cwd": os.path.join(SUITES_ROOT, engine, "native")})
    elif kind == "gomobile":
        steps.append({
            "id": "gomobile-bind",
            "description": f"gomobile bind (x/mobile {PINS['gomobile']}, "
                           "abi x86_64, api 26) -> AAR",
            "command": [env_tool("GOMOBILE") or ph["gomobile"], "bind",
                        "-target=android/amd64",
                        f"-androidapi={MIN_SDK}",
                        "-o", os.path.join(work, "engine.aar"), "."],
            "cwd": os.path.join(SUITES_ROOT, engine, "gobind")})
        steps.append({
            "id": "unpack-aar",
            "description": "desembrulha o AAR (classes.jar p/ o d8, "
                           "lib/** p/ o STAGE)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--aar-stage", os.path.join(work, "engine.aar"),
                        os.path.join(work, "aar"), stage],
            "cwd": None})
    elif kind == "zig":
        zig_out = os.path.join(stage, "lib", "x86_64", "libzig_native.so")
        os.makedirs(os.path.dirname(zig_out), exist_ok=True)
        steps.append({
            "id": "zig-cc",
            "description": f"zig cc {PINS['zig']} -target "
                           "x86_64-linux-android -nostdlib (freestanding: "
                           "bionic não é fornecida pelo zig)",
            "command": [env_tool("ZIG") or ph["zig"], "cc", "-target",
                        "x86_64-linux-android", "-shared", "-fPIC", "-O2",
                        "-nostdlib", "-o", zig_out]
                       + engine_sources(engine),
            "cwd": None})
    elif kind == "rust-workspace":
        steps.append({
            "id": "cargo-ndk-workspace",
            "description": "cargo-ndk do workspace tauri-android + wry "
                           "(cdylibs reais da stack Tauri v2)",
            "command": ["cargo", "ndk",
                        "-t", "x86_64", "--platform", str(MIN_SDK),
                        "-o", os.path.join(stage, "lib"),
                        "build", "--release"],
            "cwd": os.path.join(SUITES_ROOT, engine, "native")})
    elif kind == "haxe":
        steps.append({
            "id": "haxe-java",
            "description": f"haxe {PINS['haxe']} -java (hxjava + ant do "
                           "setup-toolchain): classes haxe.root compiladas",
            "command": [env_tool("HAXE") or ph["haxe"],
                        "-java", os.path.join(work, "hxout"), "-main",
                        "Main", "-cp",
                        os.path.join(SUITES_ROOT, engine, "src")],
            "cwd": None})
        steps.append({
            "id": "collect-haxe-jar",
            "description": "localiza o jar único do hxout (determinístico) "
                           "p/ o d8",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--collect-haxe-jar", os.path.join(work, "hxout"),
                        os.path.join(work, "haxe-classes.jar")],
            "cwd": None})
    elif kind == "gradle-chaquopy":
        proj = os.path.join(SUITES_ROOT, engine, "gradle-proj")
        java_home = os.environ.get("JAVA_HOME", "")
        gradle_cmd = [env_tool("GRADLE") or ph["gradle"], "-p", proj,
                      "--no-daemon", "assembleRelease"]
        if java_home:
            gradle_cmd.append(f"-Dorg.gradle.java.home={java_home}")
        steps.append({
            "id": "gradle-chaquopy",
            "description": f"gradle {PINS['gradle']} assembleRelease "
                           f"(AGP {PINS['agp']} + Chaquopy "
                           f"{PINS['chaquopy']}, abi x86_64) — APK gradle "
                           "REAL sem assinar",
            "command": gradle_cmd,
            "cwd": proj})
        steps.append({
            "id": "stage-gradle-apk",
            "description": "copia o APK release unsigned do gradle p/ o "
                           "work (entrada do apksigner)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--collect-gradle-apk", proj,
                        os.path.join(work, "gradle-unsigned.apk")],
            "cwd": None})
    elif kind == "wasm":
        wasm_out = os.path.join(stage, "assets", "module.wasm")
        os.makedirs(os.path.dirname(wasm_out), exist_ok=True)
        steps.append({
            "id": "wat2wasm",
            "description": f"wat2wasm (wabt {PINS['wabt']}): module.wat "
                           "commitado -> assets/module.wasm",
            "command": [env_tool("WAT2WASM") or ph["wat2wasm"],
                        os.path.join(SUITES_ROOT, engine, "module.wat"),
                        "-o", wasm_out],
            "cwd": None})
        steps.append({
            "id": "cargo-ndk-wasmer",
            "description": "cargo-ndk do host wasmer (crate wasmer "
                           f"{PINS['wasmer']}, singlepass) -> "
                           "lib/x86_64/libwasmer.so",
            "command": ["cargo", "ndk",
                        "-t", "x86_64", "--platform", str(MIN_SDK),
                        "-o", os.path.join(stage, "lib"),
                        "build", "--release"],
            "cwd": os.path.join(SUITES_ROOT, engine, "native")})
    elif kind == "hybrid":
        hybrid_assets = os.path.join(stage, "assets")
        os.makedirs(hybrid_assets, exist_ok=True)
        steps += [
            {"id": "kotlinc-hybrid",
             "description": "kotlinc -include-runtime (marcador Kotlin do "
                            "TST-14)",
             "command": [env_tool("KOTLINC") or ph["kotlinc"],
                         "-include-runtime", "-module-name", engine,
                         "-d", os.path.join(work, "hybrid-classes.jar")]
                        + kt_sources(engine),
             "cwd": None},
            {"id": "cargo-ndk-hybrid",
             "description": "cargo-ndk do cdylib rust_hybrid (sem deps "
                            "externas)",
             "command": ["cargo", "ndk",
                         "-t", "x86_64", "--platform", str(MIN_SDK),
                         "-o", os.path.join(stage, "lib"),
                         "build", "--release"],
             "cwd": os.path.join(SUITES_ROOT, engine, "native")},
            {"id": "hermesc",
             "description": f"hermesc {PINS['hermes-engine']} -emit-binary: "
                            "index.android.bundle REAL (magic Hermes)",
             "command": [env_tool("HERMESC") or ph["hermesc"],
                         "-emit-binary", "-out",
                         os.path.join(hybrid_assets,
                                      "index.android.bundle"),
                         os.path.join(SUITES_ROOT, engine, "assets-src",
                                      "hybrid.js")],
             "cwd": None},
            {"id": "wat2wasm",
             "description": "wat2wasm: module.wat -> assets/module.wasm",
             "command": [env_tool("WAT2WASM") or ph["wat2wasm"],
                         os.path.join(SUITES_ROOT, engine, "module.wat"),
                         "-o", os.path.join(hybrid_assets,
                                            "module.wasm")],
             "cwd": None},
        ]
    else:  # pragma: no cover
        raise SystemExit(f"[{TOOL}] kind desconhecido: {kind}")
    return steps


def ensure_dex_corpus(seed: int, work: str) -> str:
    """Gera o corpus gen-dex-stress ANTES do plano (mesmo padrão do
    fixture-pack): o glob do javac precisa dos arquivos existentes.
    O passo gen-corpus permanece no plano (documentação + re-execução
    determinística — mesma seed produz o mesmo corpus)."""
    out = os.path.join(work, "corpus")
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "gen-dex-stress.py"),
           "--out", out, "--seed", str(seed), "--classes", "220",
           "--methods-per-class", "330", "--strings", "2000",
           "--fields", "128"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print("[build-tier-a] ERRO: gen-dex-stress falhou:\n"
              + proc.stdout.decode("utf-8", "replace"), file=sys.stderr)
        raise SystemExit(1)
    return out


def build_plan(args) -> dict:
    engine = args.engine
    spec = SPECS[engine]
    kind = spec["kind"]
    os.makedirs(os.path.abspath(args.out), exist_ok=True)
    out_apk = os.path.join(os.path.abspath(args.out), f"{engine}.apk")
    work = args.work or tempfile.mkdtemp(prefix="apktester-tier-a-")
    os.makedirs(work, exist_ok=True)
    stage = os.path.join(work, "stage")
    os.makedirs(stage, exist_ok=True)
    tools = discover(args)
    android_jar = find_android_jar()
    a2 = tools["aapt2"]["path"] or "aapt2"
    d8 = tools["d8"]["path"] or "d8"
    za = tools["zipalign"]["path"] or "zipalign"
    signer = tools["apksigner"]["path"] or "apksigner"
    keystore = os.path.join(work, "debug.keystore")
    unsigned = os.path.join(work, "bundle-unsigned.apk")
    aligned = os.path.join(work, "bundle-aligned.apk")
    jar_tok = android_jar or "@ANDROID_JAR@"

    java_files = write_common_tree(engine, args.seed, work)

    steps: list = []
    gradle_kind = kind == "gradle-chaquopy"
    steps.append({
        "id": "keystore",
        "description": "keystore de debug do pack (skip se já existe)",
        "command": ["keytool", "-genkeypair", "-keystore", keystore,
                    "-storetype", "PKCS12", "-storepass", "apktester",
                    "-keypass", "apktester", "-alias", KS_ALIAS,
                    "-keyalg", "RSA", "-keysize", "2048", "-validity",
                    "10000", "-dname", "CN=APK Tester Tier A, "
                    "OU=Engines, O=apktester, L=Recife, S=PE, C=BR"],
        "cwd": None, "skip_if": "keystore_existe"})
    if not gradle_kind:
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

    steps += plan_for_engine(engine, args, work, stage, tools, android_jar)

    # ---- caminho comum do DEX/pack (o gradle-chaquopy pula tudo: o AGP
    # já produz o APK final; só assinamos) ----
    if not gradle_kind:
        if kind == "java-multidex":
            ensure_dex_corpus(args.seed, work)
        javac_cmd = ["javac", "-encoding", "UTF-8", "-source", "8",
                     "-target", "8", "-Xlint:-options", "-d",
                     os.path.join(work, "classes")] + java_files
        if kind == "java-multidex":
            javac_cmd += sorted(glob.glob(os.path.join(work, "corpus",
                                                       "java", "**",
                                                       "*.java"),
                                          recursive=True))
            javac_cmd += engine_sources(engine)
        elif kind == "gomobile":
            javac_cmd += [f for f in engine_sources(engine)
                          if f.endswith(".java")]
        steps.append({
            "id": "javac-common",
            "description": "javac dos POJOs + R.java"
                           + (" + corpus multidex + probe invoke-custom"
                              if kind == "java-multidex" else ""),
            "command": javac_cmd, "cwd": None})
        steps.append({
            "id": "jar-classes",
            "description": "empacota os .class p/ o d8",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--jar-classes", os.path.join(work,
                                                      "classes-input.jar"),
                        os.path.join(work, "classes")],
            "cwd": None})

        d8_inputs = [os.path.join(work, "classes-input.jar")]
        if kind == "kotlin":
            d8_inputs.append(os.path.join(work, "kotlin-classes.jar"))
        elif kind == "kmp":
            d8_inputs.append(os.path.join(work, "kmp-classes.jar"))
            d8_inputs.append(os.path.join(work, "compose-runtime.jar"))
        elif kind == "groovy":
            d8_inputs.append(os.path.join(env_tool("GROOVY_HOME")
                                          or "@GROOVY_HOME@", "lib",
                                          f"groovy-{PINS['groovy']}.jar"))
        elif kind == "gomobile":
            d8_inputs.append(os.path.join(work, "aar", "classes.jar"))
        elif kind == "haxe":
            d8_inputs.append(os.path.join(work, "haxe-classes.jar"))
        elif kind == "hybrid":
            d8_inputs.append(os.path.join(work, "hybrid-classes.jar"))
        steps.append({
            "id": "d8",
            "description": f"d8 --min-api {MIN_SDK} (multidex automático "
                           "quando >64k refs)",
            "command": [d8, "--release", "--min-api", str(MIN_SDK)]
                       + (["--lib", android_jar] if android_jar else [])
                       + ["--output", os.path.join(work, "dex")]
                       + d8_inputs,
            "cwd": None})
        steps.append({
            "id": "zip-dex",
            "description": "anexa classes*.dex na raiz do APK (ordem "
                           "determinística)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--zip-dex", os.path.join(work, "dex"), unsigned],
            "cwd": None})
        # zip-stage é SEMPRE no plano: o conteúdo do STAGE só existe em
        # tempo de execução (o plano é auditável; stage vazio => 0 entradas,
        # inofensivo — helper_zip_stage).
        steps.append({
            "id": "zip-stage",
            "description": "anexa lib/, assets/ e META-INF/ do STAGE "
                           "(sem entradas de diretório; 0 entradas se o "
                           "engine não tem artefatos fora do dex)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--zip-stage", stage, unsigned],
            "cwd": None})
        steps.append({
            "id": "zipalign",
            "description": "alinhamento de 4 bytes (-p p/ .so)",
            "command": [za, "-f", "-p", "4", unsigned, aligned],
            "cwd": None})
        steps.append({
            "id": "apksigner",
            "description": "assina v1+v2 e grava em --out",
            "command": [signer, "sign", "--ks", keystore, "--ks-pass",
                        KS_PASS, "--ks-key-alias", KS_ALIAS, "--key-pass",
                        KS_PASS, "--min-sdk-version", str(MIN_SDK),
                        "--v1-signing-enabled", "true",
                        "--v2-signing-enabled", "true",
                        "--v3-signing-enabled", "false",
                        "--out", out_apk, aligned],
            "cwd": None})
    else:
        steps.append({
            "id": "apksigner-gradle-apk",
            "description": "assina o APK do gradle (v1+v2) e grava em --out",
            "command": [signer, "sign", "--ks", keystore, "--ks-pass",
                        KS_PASS, "--ks-key-alias", KS_ALIAS, "--key-pass",
                        KS_PASS, "--min-sdk-version", str(MIN_SDK),
                        "--v1-signing-enabled", "true",
                        "--v2-signing-enabled", "true",
                        "--v3-signing-enabled", "false",
                        "--out", out_apk,
                        os.path.join(work, "gradle-unsigned.apk")],
            "cwd": None})

    notes = [
        "build Tier A REAL (A4): payload executável, toolchains pinados em "
        "tools/setup-tier-a-toolchain.sh",
        "verificação por detector_artifacts do contrato (presença + globs + "
        "dex-strings/elf-strings) — SEM âncora sha256, pois os binários "
        "dependem da versão da toolchain (determinismo byte-a-byte é prova "
        "do A8/geradores)",
    ]
    return {
        "tool": TOOL, "engine": engine, "kind": kind, "seed": args.seed,
        "description": spec["description"],
        "language": spec["language"],
        "application_id": app_id(engine),
        "apk_name": f"{engine}.apk",
        "min_sdk": MIN_SDK, "target_sdk": TARGET_SDK,
        "pins": {k: v for k, v in PINS.items() if k in _pins_for(engine)},
        "work": work, "out_apk": out_apk, "android_jar": android_jar,
        "keystore": keystore, "tools": tools, "notes": notes,
        "steps": steps,
        "all_android_tools_available": all(
            tools[n]["available"] for n in ("aapt2", "d8", "apksigner",
                                            "zipalign")),
    }


# ---------------------------------------------------------------------------
# Helpers internos (chamados como passos do plano)
# ---------------------------------------------------------------------------
def helper_jar_classes(out_jar: str, roots: list) -> None:
    """Zip determinístico dos .class (uma ou mais raízes de classes)."""
    valid = [r for r in roots if r and os.path.isdir(r)]
    if not valid:
        raise SystemExit(f"[{TOOL}] ERRO: nenhuma raiz de classes válida: "
                         f"{roots}")
    with zipfile.ZipFile(out_jar, "w", allowZip64=True) as zf:
        for root in valid:
            for dirpath, _dirs, files in os.walk(root):
                for fn in sorted(files):
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root)
                    info = zipfile.ZipInfo(rel,
                                           date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as fh:
                        zf.writestr(info, fh.read())
    print(f"[{TOOL}] jar-classes: {out_jar} "
          f"(raízes: {len(valid)})", file=sys.stderr)


def helper_zip_dex(dexdir: str, apk: str) -> None:
    """Anexa classes*.dex em ordem determinística (multidex automático)."""
    dexes = sorted(glob.glob(os.path.join(dexdir, "classes*.dex")))
    if not dexes:
        raise SystemExit(f"[{TOOL}] ERRO: nenhum classes*.dex em {dexdir}")
    with zipfile.ZipFile(apk, "a", allowZip64=True) as zf:
        for d in dexes:
            info = zipfile.ZipInfo(os.path.basename(d),
                                   date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(d, "rb") as fh:
                zf.writestr(info, fh.read())
    print(f"[{TOOL}] zip-dex: {len(dexes)} dex "
          f"({', '.join(os.path.basename(d) for d in dexes)})",
          file=sys.stderr)


def helper_zip_stage(stage: str, apk: str) -> None:
    """Anexa a árvore do STAGE (lib/, assets/, META-INF/) sem entradas de
    diretório (mesmo efeito de zip -q -r -X -D)."""
    count = 0
    with zipfile.ZipFile(apk, "a", allowZip64=True) as zf:
        for dirpath, _dirs, files in os.walk(stage):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, stage).replace(os.sep, "/")
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                with open(full, "rb") as fh:
                    zf.writestr(info, fh.read())
                count += 1
    print(f"[{TOOL}] zip-stage: {count} entradas de {stage}",
          file=sys.stderr)


def helper_extract_zip(jar: str, prefix: str, outdir: str) -> None:
    """Extrai entradas com o prefixo dado (ex.: META-INF/*.kotlin_module)."""
    with zipfile.ZipFile(jar) as zf:
        hits = [n for n in zf.namelist()
                if n.startswith(prefix) and n.endswith(".kotlin_module")]
        if not hits:
            raise SystemExit(f"[{TOOL}] ERRO: nenhuma entrada {prefix}*"
                             f".kotlin_module em {jar}")
        for n in hits:
            target = os.path.join(outdir, n)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(zf.read(n))
            print(f"[{TOOL}] extract-zip: {n} -> {target}", file=sys.stderr)


def helper_copy_sysroot_libcxx(ndk: str, stage: str) -> None:
    prebuilt = os.path.join(ndk, "toolchains", "llvm", "prebuilt",
                            "linux-x86_64", "sysroot", "usr", "lib")
    for abi, triple in (("arm64-v8a", "aarch64-linux-android"),
                        ("x86_64", "x86_64-linux-android")):
        src = os.path.join(prebuilt, triple, "libc++_shared.so")
        if not os.path.isfile(src):
            raise SystemExit(f"[{TOOL}] ERRO: libc++_shared.so ausente em "
                             f"{src}")
        dst = os.path.join(stage, "lib", abi, "libc++_shared.so")
        shutil.copyfile(src, dst)
        print(f"[{TOOL}] copy-sysroot-libcxx: {abi}", file=sys.stderr)


def helper_aar_stage(aar: str, outdir: str, stage: str) -> None:
    """Desembrulha o AAR: tudo em outdir; lib/** vai também para o STAGE."""
    with zipfile.ZipFile(aar) as zf:
        zf.extractall(outdir)
    for libname in ("jni", "lib"):
        libdir = os.path.join(outdir, libname)
        if not os.path.isdir(libdir):
            continue
        for dirpath, _dirs, files in os.walk(libdir):
            for fn in files:
                rel = os.path.relpath(os.path.join(dirpath, fn),
                                      outdir).replace(os.sep, "/")
                if libname == "jni":
                    # AAR: jni/<abi>/*.so -> lib/<abi>/*.so no APK
                    rel = rel.replace("jni/", "lib/", 1)
                dst = os.path.join(stage, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(dirpath, fn), dst)
                print(f"[{TOOL}] aar-stage: {rel}", file=sys.stderr)
    if not os.path.isfile(os.path.join(outdir, "classes.jar")):
        raise SystemExit(f"[{TOOL}] ERRO: classes.jar ausente do AAR "
                         f"{aar}")


def helper_collect_haxe_jar(hxout: str, dest: str) -> None:
    jars = sorted(glob.glob(os.path.join(hxout, "**", "*.jar"),
                            recursive=True))
    if len(jars) != 1:
        raise SystemExit(f"[{TOOL}] ERRO: esperado 1 jar em {hxout}, "
                         f"encontrados {len(jars)}: {jars}")
    shutil.copyfile(jars[0], dest)
    print(f"[{TOOL}] collect-haxe-jar: {jars[0]}", file=sys.stderr)


def helper_collect_gradle_apk(proj: str, dest: str) -> None:
    pats = ["app/build/outputs/apk/release/*.apk",
            "app/build/outputs/apk/release/**/*.apk"]
    found = []
    for pat in pats:
        found = sorted(glob.glob(os.path.join(proj, pat), recursive=True))
        if found:
            break
    if len(found) != 1:
        raise SystemExit(f"[{TOOL}] ERRO: esperado 1 APK release em {proj}, "
                         f"encontrados {found}")
    shutil.copyfile(found[0], dest)
    print(f"[{TOOL}] collect-gradle-apk: {found[0]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Verificação (--verify-apk)
# ---------------------------------------------------------------------------
def _dex_strings_hit(zf: zipfile.ZipFile, marker: str) -> bool:
    needle = marker.encode("utf-8")
    for name in sorted(zf.namelist()):
        base = name.rsplit("/", 1)[-1]
        if name.startswith("classes") and base.endswith(".dex"):
            if needle in zf.read(name):
                return True
    return False


def _elf_strings_hit(zf: zipfile.ZipFile, marker: str, paths: list) -> bool:
    needle = marker.encode("utf-8")
    for p in paths:
        if p in zf.namelist():
            if needle in zf.read(p):
                return True
    return False


def verify_apk(apk: str, engine: str) -> int:
    artifacts = contract_artifacts(engine)
    with zipfile.ZipFile(apk) as zf:
        names = zf.namelist()
        problems = []
        for artifact in artifacts:
            if artifact.startswith("dex-strings:"):
                marker = artifact.split(":", 1)[1]
                if not _dex_strings_hit(zf, marker):
                    problems.append(f"dex-strings:{marker} ausente dos dex")
                continue
            if artifact.startswith("elf-strings:"):
                # tratado no segundo loop (busca nos bytes dos .so)
                continue
            if artifact.endswith("/"):
                # prefixo de diretório (ex.: assets/chaquopy/): casa
                # qualquer entrada sob o prefixo (APKs não têm entradas de
                # diretório).
                matches = sorted(n for n in names
                                 if n.startswith(artifact))
            else:
                matches = sorted(n for n in names
                                 if fnmatch.fnmatch(n, artifact))
            if not matches:
                problems.append(f"artefato {artifact} ausente do APK")
                continue
            for p in matches:
                if p.endswith(".so"):
                    with zf.open(p) as fh:
                        magic = fh.read(4)
                    if magic != b"\x7fELF":
                        problems.append(f"{p}: não é ELF (magic {magic!r})")
        # elf-strings:<marker> — procura nos .so casados por caminhos *.so
        for artifact in artifacts:
            if artifact.startswith("elf-strings:"):
                marker = artifact.split(":", 1)[1]
                so_paths = [n for n in names if n.endswith(".so")]
                if not _elf_strings_hit(zf, marker, so_paths):
                    problems.append(f"elf-strings:{marker} ausente dos .so")
    if problems:
        for p in problems:
            print(f"[{TOOL}] FALHA {engine} em {apk}: {p}", file=sys.stderr)
        return 1
    print(f"[{TOOL}] ok {engine}: {len(artifacts)} artefatos de detecção "
          f"presentes no APK real ({apk})")
    return 0


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
    print(f"[{TOOL}] sync ok: {len(ENGINE_IDS)} engines Tier A contra "
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
        if entry.get("tier") != "A" or entry.get("build") != "real":
            drifts.append(f"{engine}: tier/build do contrato divergem "
                          f"(esperado A/real)")
        if entry.get("language") != SPECS[engine]["language"]:
            drifts.append(f"{engine}: language diverge do contrato")
        artifacts = list(entry.get("detector_artifacts", []))
        for art in artifacts:
            if art.startswith("dex-strings:") or \
                    art.startswith("elf-strings:") or "*" in art:
                continue
            # caminho exato deve ter origem no STAGE (lib/assets) ou raiz
            if not (art.startswith("lib/") or art.startswith("assets/")
                    or art.startswith("META-INF/")
                    or art.startswith("assemblies/")
                    or art.startswith("classes")
                    or art == "AndroidManifest.xml"):
                drifts.append(f"{engine}: artefato {art} fora dos prefixos "
                              "suportados")
    extra = set(by_dir) - set(ENGINE_IDS)
    a_tier = sorted(k for k in extra if by_dir[k].get("tier") == "A")
    if a_tier:
        drifts.append(f"contrato canônico tem entradas tier A fora das "
                      f"specs: {a_tier}")
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
    """Planos parseáveis dos 14 engines + zero drift contra o contrato."""
    tmp = tempfile.mkdtemp(prefix="apktester-tier-a-selftest-")
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
                      f"suites/engines/{engine}/src/", file=sys.stderr)
                return 1
        print(f"[{TOOL}] selftest OK: {len(ENGINE_IDS)} engines Tier A com "
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
        description="Builds reais Tier A da matriz de engines (A4).")
    ap.add_argument("--engine", default=None, choices=tuple(ENGINE_IDS),
                    help="diretório do engine (engine-01-java, ...)")
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
                    help="valida planos dos 14 engines + drift do contrato")
    ap.add_argument("--report", default=None,
                    help="grava report JSON do build (sha256, passos) "
                         "no caminho dado")
    for name in ("aapt2", "d8", "apksigner", "zipalign"):
        ap.add_argument(f"--{name}", default=None,
                        help=f"caminho do {name} (padrão: shutil.which)")
    # helpers internos (não documentados)
    ap.add_argument("--jar-classes", nargs="+",
                    metavar=("OUTJAR", "ROOT"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--zip-dex", nargs=2, metavar=("DEXDIR", "APK"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--zip-stage", nargs=2, metavar=("STAGE", "APK"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--extract-zip", nargs=3,
                    metavar=("JAR", "PREFIX", "OUTDIR"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--copy-sysroot-libcxx", nargs=2,
                    metavar=("NDK", "STAGE"), help=argparse.SUPPRESS)
    ap.add_argument("--aar-stage", nargs=3, metavar=("AAR", "OUTDIR",
                                                     "STAGE"),
                    help=argparse.SUPPRESS)
    ap.add_argument("--collect-haxe-jar", nargs=2,
                    metavar=("HXOUT", "DEST"), help=argparse.SUPPRESS)
    ap.add_argument("--collect-gradle-apk", nargs=2,
                    metavar=("PROJ", "DEST"), help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def execute(plan: dict) -> int:
    for step in plan["steps"]:
        if (step.get("skip_if") == "keystore_existe"
                and os.path.isfile(plan["keystore"])):
            print(f"[{TOOL}] {step['id']}: keystore já existe, pulando",
                  file=sys.stderr)
            continue
        print(f"[{TOOL}] {step['id']}: {step['description']}",
              file=sys.stderr)
        proc = subprocess.run(step["command"], cwd=step.get("cwd"))
        if proc.returncode != 0:
            print(f"[{TOOL}] ERRO: passo {step['id']} saiu com "
                  f"{proc.returncode}", file=sys.stderr)
            return 1
    print(f"[{TOOL}] OK: APK Tier A em {plan['out_apk']}", file=sys.stderr)
    return 0


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
    if args.jar_classes:
        if len(args.jar_classes) < 2:
            print(f"[{TOOL}] ERRO: --jar-classes exige OUTJAR e ao menos "
                  "uma raiz de classes", file=sys.stderr)
            return 2
        helper_jar_classes(args.jar_classes[0],
                           list(args.jar_classes[1:]))
        return 0
    if args.zip_dex:
        helper_zip_dex(*args.zip_dex)
        return 0
    if args.zip_stage:
        helper_zip_stage(*args.zip_stage)
        return 0
    if args.extract_zip:
        helper_extract_zip(*args.extract_zip)
        return 0
    if args.copy_sysroot_libcxx:
        helper_copy_sysroot_libcxx(*args.copy_sysroot_libcxx)
        return 0
    if args.aar_stage:
        helper_aar_stage(*args.aar_stage)
        return 0
    if args.collect_haxe_jar:
        helper_collect_haxe_jar(*args.collect_haxe_jar)
        return 0
    if args.collect_gradle_apk:
        helper_collect_gradle_apk(*args.collect_gradle_apk)
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
    rc = execute(plan)
    if rc == 0 and args.report:
        write_report(plan, args.report)
    return rc


if __name__ == "__main__":
    sys.exit(main())
