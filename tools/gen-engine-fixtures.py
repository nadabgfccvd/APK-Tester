#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-engine-fixtures.py — payloads, contratos e verificação das fixtures
Tier C da matriz de engines (fase A3).

Fonte única das 9 fixtures de detecção sintética e honesta: engine-05-clojure,
engine-11-objc, engine-18-maui-xamarin, engine-19-unity-mono,
engine-20-unity-il2cpp, engine-21-unreal, engine-27-b4x-appinventor,
engine-29-python-kivy-beeware e engine-32-twa-pwa. Cada spec declara:
  - payloads binários/txt que entram no APK (lib/, assets/, assemblies/);
  - classes marcador Java (dex-strings do contrato, compiladas pelo javac do
    fixture-pack junto com os POJOs padrão);
  - detector_artifacts — DEVE ser igual ao de contracts/engines/
    expected-engines.json (a igualdade é afirmada pelo --selftest e pelo
    --sync-contracts; drift = falha).

Lei da honestidade (ADR 0003): "detecção não valida payload nem autoriza
execução" — os stubs ELF/PE/metadata são marcadores de layout, NÃO runtimes
reais; todo README da suíte declara "fixture de detecção; payload não
executável".

Modos:
  --out DIR [--engine N] [--report P]   gera payloads (+ report de sha256);
                                        grava também DIR/manifest.json no
                                        formato convencional do repositório
                                        (chave "artifacts", {path, sha256}
                                        relativos a DIR) — é o que o cheque
                                        determinism do APKBot compara entre
                                        execuções/tempos
  --sync-contracts                      escreve suites/engines/<engine>/
                                        expected-engines.json (valida contra
                                        o contrato canônico em contracts/)
  --verify-apk APK --engine N           valida o APK empacotado contra o
                                        contrato + contracts/engines/
                                        tier-c-payload-report.json
  --selftest                            provas locais (determinismo, magias,
                                        cobertura do contrato, round-trip)

Determinismo: stdlib only, seed padrão 20261022, filler derivado de
sha256(seed:path:indice) — sem módulo random, sem timestamps.

Uso:
  python3 tools/gen-engine-fixtures.py --out /tmp/payloads
  python3 tools/fixture-pack.py --fixture engine-05-clojure --out dist
  python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-05-clojure.apk \
      --engine engine-05-clojure

Códigos de saída: 0 ok; 1 validação falhou; 2 argumentos inválidos.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import zipfile

DEFAULT_SEED = 20261022
TOOL = "gen-engine-fixtures.py"
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
CONTRACT_PATH = os.path.join(REPO_ROOT, "contracts", "engines",
                             "expected-engines.json")
PAYLOAD_REPORT_PATH = os.path.join(REPO_ROOT, "contracts", "engines",
                                   "tier-c-payload-report.json")
SUITES_ROOT = os.path.join(REPO_ROOT, "suites", "engines")

MARKER_TXT = """APK Tester — fixture de detecção Tier C
engine: {engine}
language: {language}
rustydroid_engines: {engines}
payload não executável (ADR 0003): detecção não valida payload nem autoriza execução
gerado por: tools/gen-engine-fixtures.py via tools/fixture-pack.py
seed: {seed}
"""

PYTHON_ENTRY = '''"""Fixture de detecção Tier C (engine-29-python-kivy-beeware).

Entrypoint Python empacotado no layout python-for-android/briefcase
(assets/python/main.py). payload não executável (ADR 0003): a detecção
não valida payload nem autoriza execução.
"""

FIXTURE = "engine-29-python-kivy-beeware"
RUSTYDROID_ENGINES = ("python-kivy-beeware",)
SEED = {seed}


def main() -> int:
    print("fixture de detecção; payload não executável")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

# ---------------------------------------------------------------------------
# SPECS — fonte única das fixtures Tier C. detector_artifacts é a cópia
# literal do contrato canônico (contracts/engines/expected-engines.json);
# --selftest e --sync-contracts afirmam a igualdade (zero drift).
# ---------------------------------------------------------------------------
ENGINES = {
    "engine-05-clojure": {
        "language": "Clojure",
        "rustydroid_engines": ["clojure"],
        "detector_artifacts": [
            "classes.dex", "dex-strings:clojure.lang",
            "assets/fixture-marker.txt"],
        "java_markers": [("clojure.lang", ["RT", "Var"]),
                         ("clojure.core", ["Core"])],
        "dex_string_markers": ["clojure.lang"],
        "payloads": [("assets/fixture-marker.txt", "marker_txt")],
        "notes": "detection fixture, payload not executable. Stub com "
                 "strings clojure.lang e layout correto (tools/fixture-pack.py).",
    },
    "engine-11-objc": {
        "language": "Objective-C",
        "rustydroid_engines": ["objc"],
        "detector_artifacts": [
            "lib/x86_64/libobjc-fixture.so", "assets/fixture-marker.txt"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("lib/x86_64/libobjc-fixture.so", "elf"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": ["objc_msgSend", "objc_getClass", "sel_registerName",
                        "OBJC_METACLASS_$_NSObject", "objc_autoreleasePoolPush"],
        "notes": "detection fixture, payload not executable. Stub ELF com "
                 "marcadores objc_* (runtime ObjC é raro em Android — fixture "
                 "honesta).",
    },
    "engine-18-maui-xamarin": {
        "language": "C#/MAUI/Xamarin",
        "rustydroid_engines": ["maui-xamarin"],
        "detector_artifacts": [
            "assemblies/*.dll", "lib/x86_64/libmonodroid.so"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("assemblies/MyApp.dll", "dll"),
            ("assemblies/Mono.Android.dll", "dll"),
            ("lib/x86_64/libmonodroid.so", "elf"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": ["monodroid", "mono_jit_init", "xamarin_app_setup"],
        "dll_names": {"assemblies/MyApp.dll": "MyApp",
                      "assemblies/Mono.Android.dll": "Mono.Android"},
        "dll_markers": {"assemblies/MyApp.dll":
                        ["Mono.Android", "Xamarin.Forms", "Mono.Runtime"],
                        "assemblies/Mono.Android.dll":
                        ["Android.Runtime", "Android.App", "Mono.Android"]},
        "notes": "detection fixture, payload not executable. Stubs de "
                 "assemblies/*.dll + libmonodroid.so (layout Mono correto).",
    },
    "engine-19-unity-mono": {
        "language": "C#/Unity Mono",
        "rustydroid_engines": ["unity-mono"],
        "detector_artifacts": [
            "assets/bin/Data/Managed/Assembly-CSharp.dll",
            "lib/x86_64/libunity.so", "lib/x86_64/libmonobdwgc-2.0.so"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("assets/bin/Data/Managed/Assembly-CSharp.dll", "dll"),
            ("lib/x86_64/libunity.so", "elf"),
            ("lib/x86_64/libmonobdwgc-2.0.so", "elf"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": {"lib/x86_64/libunity.so":
                        ["UnityMain", "UnityPlayer", "libunity.so"],
                        "lib/x86_64/libmonobdwgc-2.0.so":
                        ["mono_jit_init", "monobdwgc-2.0", "monoeg_gmalloc"]},
        "dll_names": {"assets/bin/Data/Managed/Assembly-CSharp.dll":
                      "Assembly-CSharp"},
        "dll_markers": {"assets/bin/Data/Managed/Assembly-CSharp.dll":
                        ["UnityEngine", "MonoBehaviour", "Assembly-CSharp"]},
        "notes": "detection fixture, payload not executable. "
                 "Assembly-CSharp.dll stub + runtime Mono do Unity.",
    },
    "engine-20-unity-il2cpp": {
        "language": "C#/Unity IL2CPP",
        "rustydroid_engines": ["unity-il2cpp"],
        "detector_artifacts": [
            "lib/x86_64/libil2cpp.so",
            "assets/bin/Data/Managed/Metadata/global-metadata.dat",
            "lib/x86_64/libunity.so"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("lib/x86_64/libil2cpp.so", "elf"),
            ("assets/bin/Data/Managed/Metadata/global-metadata.dat",
             "metadata"),
            ("lib/x86_64/libunity.so", "elf"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": {"lib/x86_64/libil2cpp.so":
                        ["il2cpp_init", "il2cpp_string_new",
                         "il2cpp_runtime_invoke", "libil2cpp.so"],
                        "lib/x86_64/libunity.so":
                        ["UnityMain", "UnityPlayer", "libunity.so"]},
        "notes": "detection fixture, payload not executable. libil2cpp.so + "
                 "global-metadata.dat stubs (layout IL2CPP correto).",
    },
    "engine-21-unreal": {
        "language": "C++/Unreal",
        "rustydroid_engines": ["unreal"],
        "detector_artifacts": ["lib/x86_64/libUE4.so", "assets/*.pak"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("lib/x86_64/libUE4.so", "elf"),
            ("assets/main.pak", "pak"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": ["UE4", "UnrealEngine", "libUE4.so", "FRunnable"],
        "notes": "detection fixture, payload not executable. libUE4.so stub "
                 "+ .pak placeholder.",
    },
    "engine-27-b4x-appinventor": {
        "language": "B4X/App Inventor",
        "rustydroid_engines": ["b4x-appinventor"],
        "detector_artifacts": [
            "classes.dex", "dex-strings:anywheresoftware.b4a"],
        "java_markers": [("anywheresoftware.b4a", ["BA", "Common"]),
                         ("com.google.appinventor.components.runtime",
                          ["Form"])],
        "dex_string_markers": ["anywheresoftware.b4a", "com.google.appinventor"],
        "payloads": [("assets/fixture-marker.txt", "marker_txt")],
        "notes": "detection fixture, payload not executable. Stub DEX com "
                 "strings anywheresoftware.b4a / com.google.appinventor.",
    },
    "engine-29-python-kivy-beeware": {
        "language": "Python/Kivy/BeeWare",
        "rustydroid_engines": ["python-kivy-beeware"],
        "detector_artifacts": [
            "lib/x86_64/libpython3*.so", "assets/python/main.py"],
        "java_markers": [],
        "dex_string_markers": [],
        "payloads": [
            ("lib/x86_64/libpython3.11.so", "elf"),
            ("assets/python/main.py", "python_entry"),
            ("assets/fixture-marker.txt", "marker_txt")],
        "elf_markers": ["Py_Initialize", "PyRun_SimpleString", "3.11.8",
                        "libpython3.11.so"],
        "notes": "detection fixture, payload not executable. Stub libpython + "
                 "entrypoint python empacotado (layout "
                 "python-for-android/briefcase).",
    },
    "engine-32-twa-pwa": {
        "language": "TWA/PWA",
        "rustydroid_engines": ["twa"],
        "detector_artifacts": [
            "dex-strings:asset_statements",
            "dex-strings:androidx.browser.trusted",
            "assets/fixture-marker.txt"],
        "java_markers": [("androidx.browser.trusted",
                          ["TrustedWebActivityIntentUtils"])],
        "dex_string_markers": ["asset_statements", "androidx.browser.trusted"],
        "payloads": [("assets/fixture-marker.txt", "marker_txt")],
        "notes": "detection fixture, payload not executable. Marcadores de "
                 "TWA (digital asset links, androidx.browser.trusted) + "
                 "activity vazia.",
    },
}
ENGINE_IDS = tuple(sorted(ENGINES))
JAVA_DEX_EXTRA = ("classes.dex",)  # produzido pelo fixture-pack, não é payload


# ---------------------------------------------------------------------------
# Primitivas determinísticas de stub
# ---------------------------------------------------------------------------
def filler(seed: int, path: str, size: int) -> bytes:
    """Bytes pseudo-aleatórios REPRODUZÍVEIS (sha256 em cadeia) — sem random."""
    out = bytearray()
    counter = 0
    while len(out) < size:
        digest = hashlib.sha256(
            f"{seed}:{path}:{counter}".encode("utf-8")).digest()
        out.extend(digest)
        counter += 1
    return bytes(out[:size])


def write_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def write_out_manifest(out: str, seed: int, extra_exclude: tuple = ()) -> list:
    """Grava <out>/manifest.json no formato convencional do repositório e
    devolve as entradas [{path, sha256}, ...] (ordenadas por path).

    Varre a árvore gerada sob --out (payloads + classes marcador Java) e
    declara sha256 por arquivo com caminho relativo a --out, sempre com "/".
    Ficam de fora o próprio manifest.json e o report de sha256 (padrão
    tier-c-payload-report.json ou o caminho passado em --report) — o report
    tem contrato próprio commitado (contracts/engines/) e é revalidado pelo
    --selftest; o manifest cobre exatamente os artefatos que o fixture-pack
    consome. Byte-estável: chaves ordenadas, indent 2, sem timestamps
    (lei da ADR 0001).
    """
    excluded = {os.path.abspath(p) for p in extra_exclude}
    entries = []
    for dirpath, dirnames, filenames in os.walk(out):
        dirnames.sort()
        for name in sorted(filenames):
            abs_path = os.path.join(dirpath, name)
            if name == "manifest.json" or \
                    os.path.abspath(abs_path) in excluded:
                continue
            rel = os.path.relpath(abs_path, out).replace(os.sep, "/")
            with open(abs_path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            entries.append({"path": rel, "sha256": digest})
    entries.sort(key=lambda e: e["path"])
    manifest = {
        "schema_version": 1,
        "generator": TOOL,
        "seed": seed,
        "synthetic": True,
        "artifacts": entries,
    }
    write_file(os.path.join(out, "manifest.json"),
               (json.dumps(manifest, indent=2, ensure_ascii=False,
                           sort_keys=True) + "\n").encode("utf-8"))
    return entries


def elf64_stub(markers: list, soname: str, seed: int, path: str) -> bytes:
    """ELF64 LSB ET_DYN/EM_X86_64 mínimo e honesto: sem código, .rodata com
    os marcadores (strings), tabela de seções válida. Stub de detecção."""
    rodata = b"".join(m.encode("utf-8") + b"\x00" for m in list(markers) +
                      [soname])
    shstrtab = b"\x00.rodata\x00.shstrtab\x00"
    pad = (-(64 + 56 + len(rodata) + len(shstrtab))) % 8
    shoff = 64 + 56 + len(rodata) + len(shstrtab) + pad
    base_total = shoff + 3 * 64
    tail = filler(seed, path, max(0, 4096 - base_total))
    total = base_total + len(tail)
    ehdr = (b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8 +
            struct.pack("<HHIQQQIHHHHHH", 3, 62, 1, 0, 64, shoff, 0,
                        64, 56, 1, 64, 3, 2))
    phdr = struct.pack("<IIQQQQQQ", 1, 4, 0, 0, 0, total, total, 0x1000)
    sh_null = struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    sh_rodata = struct.pack("<IIQQQQIIQQ", 1, 1, 2, 0, 64 + 56, len(rodata),
                            0, 0, 8, 0)
    sh_str = struct.pack("<IIQQQQIIQQ", 9, 3, 0, 0,
                         64 + 56 + len(rodata), len(shstrtab), 0, 0, 1, 0)
    return (ehdr + phdr + rodata + shstrtab + b"\x00" * pad + sh_null +
            sh_rodata + sh_str + tail)


def pe_dll_stub(assembly: str, markers: list, seed: int, path: str) -> bytes:
    """Stub PE (DLL) mínimo e honesto: MZ + PE/COFF (i386, DLL, timestamp 0)
    + uma seção .text cujo conteúdo carrega a assinatura BSJB (metadata
    Mono/CLI) e os marcadores. NÃO é um assembly executável."""
    dos = b"MZ" + b"\x00" * 0x3a + struct.pack("<I", 0x40)
    pe_sig = b"PE\x00\x00"
    coff = struct.pack("<HHIIIHH", 0x014c, 1, 0, 0, 0, 0, 0x2102)
    text_hdr = struct.pack("<8sIIIIIIHHI", b".text\x00\x00\x00", 0, 0, 0, 0,
                           0, 0, 0, 0, 0x60000020)
    blob = (b"BSJB" + assembly.encode("utf-8") + b"\x00" +
            b"".join(m.encode("utf-8") + b"\x00" for m in markers))
    blob += filler(seed, path, max(0, 1024 - len(blob)))
    off = len(dos) + len(pe_sig) + len(coff) + len(text_hdr)
    text_hdr = struct.pack("<8sIIIIIIHHI", b".text\x00\x00\x00", len(blob),
                           0x1000, len(blob), off, 0, 0, 0, 0, 0x60000020)
    tail = filler(seed, path + ":tail", max(0, 4096 - (off + len(blob))))
    return dos + pe_sig + coff + text_hdr + blob + tail


def metadata_dat_stub(seed: int, path: str) -> bytes:
    """global-metadata.dat (Unity IL2CPP): magic 0xFAB11BAF + versão 31 +
    marcadores textuais. payload não executável."""
    head = struct.pack("<II", 0xFAB11BAF, 31)
    marks = (b"global-metadata.dat v31 (fixture)\x00"
             b"engine-20-unity-il2cpp\x00")
    tail = filler(seed, path, 2048 - len(head) - len(marks))
    return head + marks + tail


def pak_stub(seed: int, path: str) -> bytes:
    """.pak placeholder (Unreal): magic 0x5A6F12E1 + versão 8 + marcador."""
    head = struct.pack("<II", 0x5A6F12E1, 8)
    marks = b"UE4-pak-fixture engine-21-unreal\x00"
    tail = filler(seed, path, 1536 - len(head) - len(marks))
    return head + marks + tail


def marker_txt(engine: str, spec: dict, seed: int) -> bytes:
    body = MARKER_TXT.format(
        engine=engine, language=spec["language"],
        engines=",".join(spec["rustydroid_engines"]), seed=seed)
    return body.encode("utf-8")


def python_entry(seed: int) -> bytes:
    return PYTHON_ENTRY.format(seed=seed).encode("utf-8")


# ---------------------------------------------------------------------------
# Geração de payloads + fontes Java marcador
# ---------------------------------------------------------------------------
def payload_bytes(engine: str, spec: dict, rel: str, kind: str,
                  seed: int) -> bytes:
    if kind == "marker_txt":
        return marker_txt(engine, spec, seed)
    if kind == "python_entry":
        return python_entry(seed)
    if kind == "metadata":
        return metadata_dat_stub(seed, rel)
    if kind == "pak":
        return pak_stub(seed, rel)
    if kind == "elf":
        return elf64_stub(spec["elf_markers"] if isinstance(
            spec.get("elf_markers"), list) else spec["elf_markers"][rel],
            os.path.basename(rel), seed, rel)
    if kind == "dll":
        return pe_dll_stub(spec["dll_names"][rel], spec["dll_markers"][rel],
                           seed, rel)
    raise ValueError(f"kind de payload desconhecido: {kind}")


def payload_paths(spec: dict) -> list:
    return sorted(p[0] for p in spec["payloads"])


def generate_payloads(engine: str, out: str, seed: int) -> dict:
    """Escreve os payloads de UM engine diretamente em `out`; devolve o mapa
    path -> sha256 (determinístico)."""
    spec = ENGINES[engine]
    written = {}
    for rel, kind in sorted(spec["payloads"]):
        data = payload_bytes(engine, spec, rel, kind, seed)
        write_file(os.path.join(out, rel), data)
        written[rel] = hashlib.sha256(data).hexdigest()
    return written


def java_sources(engine: str) -> list:
    """Fontes Java marcador (relpath, conteúdo) — compiladas pelo fixture-pack
    junto com os POJOs padrão; ancoram os dex-strings do contrato."""
    spec = ENGINES[engine]
    sources = []
    first = True
    for pkg, classes in spec["java_markers"]:
        pkg_path = pkg.replace(".", "/")
        for cls in classes:
            lines = [
                f"package {pkg};",
                "",
                f"/** Fixture de detecção Tier C ({engine}) — classe marcador.",
                " *  payload não executável (ADR 0003): detecção não valida "
                "payload nem autoriza execução. */",
                f"public final class {cls} {{",
                "",
                f'    public static final String FIXTURE_ID = "{engine}";',
            ]
            if first:
                for i, marker in enumerate(spec["dex_string_markers"]):
                    lines.append(f'    public static final String MARKER_{i} '
                                 f'= "{marker}";')
                lines += [
                    "",
                    "    public String marker() {",
                    "        return MARKER_0;",
                    "    }",
                ]
                first = False
            else:
                lines += [
                    "",
                    "    public String marker() {",
                    f'        return "{engine}";',
                    "    }",
                ]
            lines += ["}", ""]
            sources.append((f"src/{pkg_path}/{cls}.java", "\n".join(lines)))
    return sources


def payload_report(seed: int, per_engine: dict) -> dict:
    """Report canônico (engines -> path -> sha256/bytes) que âncora a
    verificação CI (`--verify-apk`) e é commitado em contracts/engines/."""
    engines = {}
    for engine in ENGINE_IDS:
        files = {}
        for rel in payload_paths(ENGINES[engine]):
            data = payload_bytes(engine, ENGINES[engine], rel,
                                 dict(ENGINES[engine]["payloads"])[rel],
                                 seed)
            files[rel] = {"sha256": hashlib.sha256(data).hexdigest(),
                          "bytes": len(data)}
        engines[engine] = {"dir": ENGINES[engine].get(
            "dir", engine), "files": files}
    return {
        "schema_version": 1,
        "tool": TOOL,
        "description": "sha256 canônico dos payloads Tier C dentro dos APKs "
                       "(âncora da verificação --verify-apk; regenere com "
                       "python3 tools/gen-engine-fixtures.py --out TMP e "
                       "copie o report para contracts/engines/)",
        "seed": seed,
        "engines": engines,
    }


# ---------------------------------------------------------------------------
# Contratos por diretório (--sync-contracts)
# ---------------------------------------------------------------------------
def dir_contract(engine: str) -> dict:
    spec = ENGINES[engine]
    return {
        "engine": engine,
        "dir": engine,
        "tier": "C",
        "build": "fixture",
        "language": spec["language"],
        "rustydroid_engines": list(spec["rustydroid_engines"]),
        "detector_artifacts": list(spec["detector_artifacts"]),
        "payload_not_executable": True,
        "pack_command": f"python3 tools/fixture-pack.py --fixture {engine} "
                        f"--out dist",
        "verify_command": f"python3 tools/gen-engine-fixtures.py "
                          f"--verify-apk dist/{engine}.apk --engine {engine}",
        "note": "fixture de detecção; payload não executável (ADR 0003). "
                "Empacotada por tools/fixture-pack.py, payloads por "
                "tools/gen-engine-fixtures.py.",
    }


def load_canonical_contract() -> dict:
    with open(CONTRACT_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def check_against_canonical() -> list:
    """Cruza ENGINES com o contrato canônico; devolve lista de drifts.

    O contrato canônico indexa por `id` curto ("engine-05") com `dir`
    ("engine-05-clojure"); as specs desta ferramenta são chaveadas pelo
    diretório. A igualdade exigida: dir, tier, build, rustydroid_engines,
    detector_artifacts."""
    canonical = load_canonical_contract()
    by_dir = {e.get("dir"): e for e in canonical.get("engines", [])}
    drifts = []
    for engine in ENGINE_IDS:
        entry = by_dir.get(engine)
        if entry is None:
            drifts.append(f"{engine}: ausente do contrato canônico")
            continue
        spec = ENGINES[engine]
        if entry.get("tier") != "C" or entry.get("build") != "fixture":
            drifts.append(f"{engine}: tier/build do contrato divergem")
        for key in ("rustydroid_engines", "detector_artifacts"):
            if list(entry.get(key, [])) != list(spec[key]):
                drifts.append(f"{engine}: {key} diverge do contrato canônico")
    extra = set(by_dir) - set(ENGINE_IDS)
    c_tier = [k for k in extra
              if by_dir[k].get("tier") == "C" and by_dir[k].get("build")
              == "fixture"]
    if c_tier:
        drifts.append(f"contrato canônico tem entradas tier C fora das "
                      f"specs: {sorted(c_tier)}")
    return drifts


def sync_contracts() -> int:
    drifts = check_against_canonical()
    if drifts:
        for d in drifts:
            print(f"[{TOOL}] DRIFT: {d}", file=sys.stderr)
        print(f"[{TOOL}] ERRO: specs divergem do contrato canônico "
              f"({CONTRACT_PATH})", file=sys.stderr)
        return 1
    for engine in ENGINE_IDS:
        path = os.path.join(SUITES_ROOT, engine, "expected-engines.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(dir_contract(engine), indent=2,
                                ensure_ascii=False, sort_keys=True) + "\n")
        print(f"[{TOOL}] contrato por diretório escrito: "
              f"suites/engines/{engine}/expected-engines.json")
    print(f"[{TOOL}] sync ok: {len(ENGINE_IDS)} engines, zero drift contra "
          "contracts/engines/expected-engines.json")
    return 0


# ---------------------------------------------------------------------------
# Verificação de APK empacotado (--verify-apk)
# ---------------------------------------------------------------------------
def _dex_strings_hit(zf: zipfile.ZipFile, marker: str) -> bool:
    needle = marker.encode("utf-8")
    for name in sorted(zf.namelist()):
        base = name.rsplit("/", 1)[-1]
        if name.startswith("classes") and base.endswith(".dex"):
            if needle in zf.read(name):
                return True
    return False


def verify_apk(apk: str, engine: str, seed: int = DEFAULT_SEED,
               report: dict | None = None) -> int:
    spec = ENGINES[engine]
    if report is None:
        with open(PAYLOAD_REPORT_PATH, "r", encoding="utf-8") as fh:
            report = json.load(fh)
    entry = report["engines"][engine]["files"]
    with zipfile.ZipFile(apk) as zf:
        names = zf.namelist()
        if "AndroidManifest.xml" not in names:
            print(f"[{TOOL}] ERRO: AndroidManifest.xml ausente de {apk}",
                  file=sys.stderr)
            return 1
        problems = []
        for artifact in spec["detector_artifacts"]:
            if artifact.startswith("dex-strings:"):
                marker = artifact.split(":", 1)[1]
                if not _dex_strings_hit(zf, marker):
                    problems.append(f"dex-strings:{marker} ausente dos dex")
                continue
            matches = sorted(n for n in names if fnmatch.fnmatch(n, artifact))
            if not matches:
                problems.append(f"artefato {artifact} ausente do APK")
                continue
            for path in matches:
                data = zf.read(path)
                if path in entry:
                    want = entry[path]["sha256"]
                    got = hashlib.sha256(data).hexdigest()
                    if want != got:
                        problems.append(f"sha256 de {path} diverge do report "
                                        f"(esperado {want}, obtido {got})")
                if path.endswith("fixture-marker.txt"):
                    text = data.decode("utf-8", "replace")
                    if engine not in text or "payload não executável" not in \
                            text:
                        problems.append(f"{path}: marcador sem a declaração "
                                        "de honestidade")
    if problems:
        for p in problems:
            print(f"[{TOOL}] FALHA {engine} em {apk}: {p}", file=sys.stderr)
        return 1
    print(f"[{TOOL}] ok {engine}: {len(spec['detector_artifacts'])} artefatos "
          f"de detecção presentes e ancorados no report ({apk})")
    return 0


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def selftest() -> int:
    tmp = tempfile.mkdtemp(prefix="apktester-engfix-selftest-")
    try:
        drifts = check_against_canonical()
        assert not drifts, f"drift contra o contrato canônico: {drifts}"
        print(f"[{TOOL}] selftest 1/5: specs == contrato canônico "
              f"({len(ENGINE_IDS)} engines tier C)")
        for engine in ENGINE_IDS:
            spec = ENGINES[engine]
            artifacts = set(spec["detector_artifacts"]) - set(JAVA_DEX_EXTRA)
            for artifact in artifacts:
                if artifact.startswith("dex-strings:"):
                    marker = artifact.split(":", 1)[1]
                    assert marker in spec["dex_string_markers"], \
                        f"{engine}: marcador {marker} fora das specs java"
                else:
                    hits = [p for p in payload_paths(spec)
                            if fnmatch.fnmatch(p, artifact)]
                    assert hits, f"{engine}: payload nenhum casa {artifact}"
        print("[{0}] selftest 2/5: cobertura de artefatos ok (arquivos + "
              "dex-strings)".format(TOOL))
        out_a = os.path.join(tmp, "a")
        out_b = os.path.join(tmp, "b")
        rep_a = payload_report(DEFAULT_SEED, {})
        for engine in ENGINE_IDS:
            generate_payloads(engine,
                              os.path.join(out_a, engine, "payload"),
                              DEFAULT_SEED)
            generate_payloads(engine,
                              os.path.join(out_b, engine, "payload"),
                              DEFAULT_SEED)
            # classes marcador Java: mesma árvore que o CLI escreve em src/
            for rel_src, content in java_sources(engine):
                write_file(os.path.join(out_a, engine, rel_src),
                           content.encode("utf-8"))
        n_java = sum(len(java_sources(e)) for e in ENGINE_IDS)
        assert n_java == 7, f"esperava 7 classes marcador, achei {n_java}"
        assert java_sources("engine-05-clojure") == [
            ("src/clojure/lang/RT.java", java_sources("engine-05-clojure")[0][1]),
            ("src/clojure/lang/Var.java", java_sources("engine-05-clojure")[1][1]),
            ("src/clojure/core/Core.java", java_sources("engine-05-clojure")[2][1]),
        ], "ordem/caminhos das classes marcador mudaram"
        rep_b = payload_report(DEFAULT_SEED, {})
        assert rep_a == rep_b, "payload_report diverge entre execuções"
        for engine in ENGINE_IDS:
            for rel, meta in rep_a["engines"][engine]["files"].items():
                with open(os.path.join(out_a, engine, "payload", rel),
                          "rb") as fh:
                    data = fh.read()
                assert hashlib.sha256(data).hexdigest() == meta["sha256"], \
                    f"{engine}/{rel}: sha256 diverge do report"
        print("[{0}] selftest 3/5: determinismo 2x + report âncora ok".format(
            TOOL))
        ent_a = write_out_manifest(out_a, DEFAULT_SEED)
        man_a = open(os.path.join(out_a, "manifest.json"), "rb").read()
        ent_a2 = write_out_manifest(out_a, DEFAULT_SEED)
        man_a2 = open(os.path.join(out_a, "manifest.json"), "rb").read()
        assert ent_a == ent_a2 and man_a == man_a2, \
            "manifest.json diverge entre escritas (não-determinístico)"
        n_payload = sum(len(rep_a["engines"][e]["files"])
                        for e in ENGINE_IDS)
        assert len(ent_a) == n_payload + n_java, \
            f"manifest devia cobrir {n_payload} payloads + {n_java} java, " \
            f"achei {len(ent_a)}"
        for entry in ent_a:
            assert set(entry) == {"path", "sha256"}, \
                f"entrada do manifest com chaves inesperadas: {entry}"
            with open(os.path.join(out_a, entry["path"]), "rb") as fh:
                assert hashlib.sha256(fh.read()).hexdigest() == \
                    entry["sha256"], f"{entry['path']}: sha diverge"
        assert len({e["path"] for e in ent_a}) == len(ent_a), \
            "paths duplicados no manifest"
        print("[{0}] selftest extra: manifest.json convencional ok "
              "({1} artefatos, 2x byte-idêntico)".format(TOOL, len(ent_a)))
        for engine in ENGINE_IDS:
            for rel, meta in rep_a["engines"][engine]["files"].items():
                data = open(os.path.join(out_a, engine, "payload", rel),
                            "rb").read()
                if rel.endswith(".so"):
                    assert data[:4] == b"\x7fELF", f"{rel}: sem magic ELF"
                elif rel.endswith(".dll"):
                    assert data[:2] == b"MZ" and b"BSJB" in data, \
                        f"{rel}: sem MZ/BSJB"
                elif rel.endswith("global-metadata.dat"):
                    assert struct.unpack("<I", data[:4])[0] == 0xFAB11BAF, \
                        f"{rel}: sem magic FAB11BAF"
                elif rel.endswith(".pak"):
                    assert struct.unpack("<I", data[:4])[0] == 0x5A6F12E1, \
                        f"{rel}: sem magic pak"
                assert meta["bytes"] == len(data)
        print("[{0}] selftest 4/5: magias ELF/MZ+BSJB/FAB11BAF/pak ok".format(
            TOOL))
        round_engine = "engine-05-clojure"
        fake_apk = os.path.join(tmp, "fake.apk")
        with zipfile.ZipFile(fake_apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", "<manifest/>")
            zf.writestr("classes.dex",
                        b"[" + b"|".join(
                            m.encode("utf-8")
                            for m in ENGINES[round_engine]
                            ["dex_string_markers"]) + b"]")
            for rel in payload_paths(ENGINES[round_engine]):
                zf.write(os.path.join(out_a, round_engine, "payload", rel),
                         rel)
        assert verify_apk(fake_apk, round_engine, report=rep_a) == 0, \
            "verify-apk reprovou o APK sintético de round-trip"
        bad_apk = os.path.join(tmp, "bad.apk")
        with zipfile.ZipFile(bad_apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", "<manifest/>")
            zf.writestr("classes.dex", b"sem marcador")
        assert verify_apk(bad_apk, round_engine, report=rep_a) == 1, \
            "verify-apk deveria reprovar APK sem marcadores"
        if os.path.isfile(PAYLOAD_REPORT_PATH):
            with open(PAYLOAD_REPORT_PATH, "r", encoding="utf-8") as fh:
                committed = json.load(fh)
            assert committed == rep_a, \
                "contracts/engines/tier-c-payload-report.json diverge do " \
                "report recalculado (regenere e recommit)"
            print("[{0}] selftest extra: report commitado == recalculado".format(
                TOOL))
        print("[{0}] selftest 5/5: round-trip verify-apk ok (bom passa, mau "
              "reprova, in-process)".format(TOOL))
        print(f"[{TOOL}] selftest OK: 9 engines tier C determinísticos e "
              "ancorados ao contrato")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Payloads, contratos e verificação das fixtures Tier C.")
    ap.add_argument("--out", default=None,
                    help="raiz de saída: <out>/payload (stubs/assets) + "
                         "<out>/src (classes marcador Java); sem --engine "
                         "usa um subdiretório por engine")
    ap.add_argument("--engine", default=None, choices=ENGINE_IDS,
                    help="gera só um engine (padrão: todos)")
    ap.add_argument("--report", default=None,
                    help="caminho do report de sha256 (padrão: "
                         "<out>/tier-c-payload-report.json)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"semente determinística (padrão: {DEFAULT_SEED})")
    ap.add_argument("--sync-contracts", action="store_true",
                    help="escreve suites/engines/<engine>/expected-engines.json")
    ap.add_argument("--verify-apk", metavar="APK", default=None,
                    help="valida o APK empacotado contra o contrato + report")
    ap.add_argument("--selftest", action="store_true",
                    help="provas locais de determinismo/cobertura/round-trip")
    args = ap.parse_args(argv)
    if args.verify_apk and not args.engine:
        ap.error("--verify-apk exige --engine")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    if args.verify_apk:
        return verify_apk(args.verify_apk, args.engine, args.seed)
    if args.sync_contracts:
        return sync_contracts()
    if not args.out:
        print(f"[{TOOL}] ERRO: --out é obrigatório "
              "(ou use --selftest/--sync-contracts)", file=sys.stderr)
        return 2
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    engines = [args.engine] if args.engine else list(ENGINE_IDS)
    files_total = 0
    for engine in engines:
        root = out if args.engine else os.path.join(out, engine)
        paydir = os.path.join(root, "payload")
        written = generate_payloads(engine, paydir, args.seed)
        # classes marcador Java: compiladas pelo javac do fixture-pack (NUNCA
        # entram no zip do payload); ancoram os dex-strings do contrato.
        for rel_src, content in java_sources(engine):
            write_file(os.path.join(root, rel_src), content.encode("utf-8"))
        files_total += len(written)
        for rel, sha in sorted(written.items()):
            print(f"[{TOOL}] {engine}: payload/{rel} (sha256 {sha[:12]}...)")
    report = payload_report(args.seed, {})
    report["engines"] = {e: report["engines"][e] for e in engines}
    report_path = os.path.abspath(args.report) if args.report else \
        os.path.join(out, "tier-c-payload-report.json")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(report, indent=2, ensure_ascii=False,
                            sort_keys=True) + "\n")
    n_entries = write_out_manifest(out, args.seed,
                                   extra_exclude=(report_path,))
    print(f"[{TOOL}] OK: {files_total} payloads em {out}; report de sha256 "
          f"em {report_path}; manifest com {len(n_entries)} artefatos em "
          f"{os.path.join(out, 'manifest.json')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
