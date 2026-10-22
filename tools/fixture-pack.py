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
                    honesto; ofuscação R8 real exige toolchain externa)

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
VERSION_CODE = 900036
VERSION_NAME = "1.0.0"
KS_PASS = "pass:apktester"
KS_ALIAS = "apktester"

FAKE_PERMS = (
    "dev.apktester.fake.READ_WIDGET_MATRIX",
    "dev.apktester.fake.WRITE_TERRAIN_CHUNKS",
    "dev.apktester.fake.BIND_GHOST_SERVICE",
    "dev.apktester.fake.ACCESS_NULL_SENSOR",
)

# Tabela por modo: sdk, esquemas de assinatura (v1/v2/v3), zipalign e truques
# do parser-torture (zip64/fake_perms/obfuscated).
def _mode(min_sdk, target_sdk, v1=True, v2=True, v3=False, zipalign=True,
          zip64=False, entries=0, fake_perms=False, obfuscated=False, desc=""):
    return {"min_sdk": min_sdk, "target_sdk": target_sdk, "v1": v1, "v2": v2,
            "v3": v3, "zipalign": zipalign, "zip64": zip64,
            "zip64_entries": entries, "fake_perms": fake_perms,
            "obfuscated": obfuscated, "description": desc}


MODES = {
    "minSdk9": _mode(9, 28,
        desc="escada SDK: quarteto activity/service/receiver/provider; "
             "BELOW_FLOOR(minSdk=9) esperado no RustyDroid"),
    "sig-v1-only": _mode(9, 36, v2=False, desc="somente assinatura v1 (JAR)"),
    "sig-v2-only": _mode(24, 36, v1=False, desc="somente assinatura v2"),
    "sig-v3-only": _mode(28, 36, v1=False, v2=False,
        desc="somente assinatura v3 (rotação de chave)"),
    "unaligned": _mode(26, 36, zipalign=False,
        desc="zipalign pulado de propósito (parser-torture)"),
    "zip64": _mode(26, 36, entries=65600,
        desc=">65k entradas (força Zip64 EOCD) como data entries"),
    "unknown-perms": _mode(26, 36, fake_perms=True,
        desc="permissões inventadas dev.apktester.fake.*"),
    "obfuscated": _mode(26, 36, obfuscated=True,
        desc="nomes minificados + mapping.txt (proxy honesto sem R8)"),
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
    return ("\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<resources>',
        f'    <string name="app_name">APK Tester fixture {mode}</string>',
        f'    <string name="seed">{DEFAULT_SEED}</string>',
        '</resources>',
        '',
    ]))


def generate_tree(cfg: dict, mode: str, seed: int, work: str) -> list:
    """Escreve a árvore de fonte da fixture em --work; devolve os caminhos."""
    pkg = "dev.apktester.fixture." + slugify(mode)
    pkg_path = pkg.replace(".", "/")
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
        files["mapping.txt"] = "\n".join(lines) + "\n"
    for rel, content in files.items():
        full = os.path.join(work, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    r_java = os.path.join(work, "gen", pkg_path, "R.java")
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
        {"id": "aapt2-compile", "description": "compila res/ em res.zip (flat)",
         "command": [a2, "compile", "--dir", os.path.join(work, "res"), "-o",
                     os.path.join(work, "res.zip")], "cwd": None},
        {"id": "aapt2-link",
         "description": "liga manifest+res no APK base e gera R.java",
         "command": [a2, "link", "-o", unsigned, "--manifest",
                     os.path.join(work, "AndroidManifest.xml"), "-I", jar_tok,
                     "--java", os.path.join(work, "gen"), "--min-sdk-version",
                     str(cfg["min_sdk"]), "--target-sdk-version",
                     str(cfg["target_sdk"]), "--version-code", str(VERSION_CODE),
                     "--version-name", VERSION_NAME,
                     os.path.join(work, "res.zip")], "cwd": None},
        {"id": "javac", "description": "compila POJOs + R.java (sem android.jar)",
         "command": [jv, "-encoding", "UTF-8", "-source", "8", "-target", "8",
                     "-Xlint:-options", "-d", os.path.join(work, "classes")]
                    + java_files, "cwd": None},
        {"id": "jar-classes", "description": "empacota os .class p/ o d8",
         "command": ["zip", "-q", "-r", os.path.join(work, "classes-input.jar"),
                     "."], "cwd": os.path.join(work, "classes")},
        {"id": "d8", "description": f"dexa com --min-api {cfg['min_sdk']}",
         "command": [d8, "--release", "--min-api", str(cfg["min_sdk"])]
                    + (["--lib", android_jar] if android_jar else [])
                    + ["--output", os.path.join(work, "dex"),
                       os.path.join(work, "classes-input.jar")], "cwd": None},
        {"id": "zip-dex", "description": "anexa classes.dex na raiz do APK",
         "command": ["zip", "-j", "-X", unsigned, "classes.dex"],
         "cwd": os.path.join(work, "dex")},
    ]
    if cfg["zip64"]:
        steps.append({
            "id": "zip64-augment",
            "description": f"adiciona {cfg['zip64_entries']} data entries via "
                           "zipfile force_zip64 (>65k força Zip64 EOCD)",
            "command": [sys.executable, os.path.abspath(__file__),
                        "--zip64-augment", "--into", unsigned, "--entries",
                        str(cfg["zip64_entries"]), "--seed", str(args.seed)],
            "cwd": None})
    if cfg["zipalign"]:
        steps.append({
            "id": "zipalign", "description": "alinhamento de 4 bytes (-p p/ .so)",
            "command": [za, "-f", "-p", "4", unsigned, aligned], "cwd": None})
    steps.append({
        "id": "apksigner",
        "description": f"assina com v1={cfg['v1']} v2={cfg['v2']} "
                       f"v3={cfg['v3']} e grava em --out",
        "command": [signer, "sign", "--ks", keystore, "--ks-pass", KS_PASS,
                    "--ks-key-alias", KS_ALIAS, "--key-pass", KS_PASS,
                    "--min-sdk-version", str(cfg["min_sdk"]),
                    "--v1-signing-enabled", str(cfg["v1"]).lower(),
                    "--v2-signing-enabled", str(cfg["v2"]).lower(),
                    "--v3-signing-enabled", str(cfg["v3"]).lower(),
                    "--out", out_apk, aligned], "cwd": None})

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
                     "com nomes minificados + mapping.txt no work")
    return {
        "tool": TOOL, "fixture": mode, "seed": args.seed,
        "description": cfg["description"],
        "application_id": "dev.apktester.fixture." + slugify(mode),
        "min_sdk": cfg["min_sdk"], "target_sdk": cfg["target_sdk"],
        "components": ["activity", "service", "receiver", "provider"],
        "work": work, "out_apk": out_apk, "android_jar": android_jar,
        "keystore": keystore, "tools": tools, "notes": notes, "steps": steps,
        "all_tools_available": all(t["available"] for t in tools.values()),
    }


def zip64_augment(zip_path: str, entries: int, seed: int) -> None:
    """Anexa N data entries com force_zip64 (conteúdo determinístico por seed)."""
    with zipfile.ZipFile(zip_path, "a", allowZip64=True) as zf:
        for i in range(entries):
            data = b"apktester-zip64/" + hashlib.sha256(
                f"{seed}:{i}".encode("ascii")).hexdigest().encode("ascii")
            zf.writestr(f"assets/zip64/e{i:06d}.bin", data,
                        compress_type=zipfile.ZIP_DEFLATED, force_zip64=True)


def execute(plan: dict) -> int:
    """Executa os passos best-effort (logs PT-BR em stderr)."""
    for step in plan["steps"]:
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
    """--dry-run de todos os 8 modos parseia; --fixture nope sai 2."""
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
            print(f"[fixture-pack] selftest {mode}: plano JSON ok "
                  f"({len(parsed['steps'])} passos)")
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--fixture", "nope",
             "--out", os.path.join(tmp, "nope-out")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert proc.returncode == 2, \
            f"--fixture nope deveria sair 2, veio {proc.returncode}"
        print("[fixture-pack] selftest OK: 8 modos com plano parseável; "
              "--fixture nope => exit 2")
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
                     help="valida planos dos 8 modos em tmp e sai")
    ap.add_argument("--zip64-augment", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--into", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--entries", type=int, default=0, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def make_plan(args) -> dict:
    """Gera árvore + plano (usado pelo dry-run e pelo selftest)."""
    cfg = MODES[args.fixture]
    out_apk = os.path.join(os.path.abspath(args.out), f"{args.fixture}.apk")
    os.makedirs(os.path.dirname(out_apk), exist_ok=True)
    work = args.work or tempfile.mkdtemp(prefix="apktester-fixturepack-")
    os.makedirs(work, exist_ok=True)
    java_files = generate_tree(cfg, args.fixture, args.seed, work)
    tools, android_jar = discover_tools(args)
    return build_plan(args, cfg, work, out_apk, tools, java_files, android_jar)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
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
