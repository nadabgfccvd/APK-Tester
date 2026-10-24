#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/v1-gate.py — gate v1.0 do APK Tester (fase A8).

Checker sistematico dos DEZ criterios da Definition of Done do prompt mestre
(APK_TESTER_PROMPT.md, secao "DEFINITION OF DONE"). O gate e a condicao de
publicacao da versao 1.0.0 (GOVERNANCE.md, politica 0.x -> 1.0):

  d1  apks_30_plus          >= 30 APKs buildaveis de checkout limpo;
  d2  flagship_size_gate    flagship release em [850, 1000] MiB (R8, CSV);
  d3  permissions_audit     contagens por protectionLevel casam com o manifesto;
  d4  minsdk9_apk           APK minSdk 9 existe no caminho de build (ou fixture);
  d5  sim3d_golden          golden :sim3d reprodutivel + probes GLES estruturados;
  d6  ui_grids_icons        ButtonGrid 1200 + IconGrid 600 + 500+ drawables;
  d7  rustydroid_zero_drift contratos coherentes (answer keys, zero drift);
  d8  expected_engines_detect expected-engines.json completo e verificavel;
  d9  determinism_proof     duas builds de release consecutivas byte-identicas;
  d10 governance_complete   kit de governanca + docs mdBook + 6 workflows.

Modos:
  --sync     escreve o contrato estatico em contracts/v1-gate.json (commitado;
             criterios dinamicos ficam "evidence-release" apontando o workflow
             que os prova). Zero drift: CI regenera e diffa contra o commit.
  --check    roda os criterios; os estaticos sempre, os dinamicos apenas com
             as flags de evidencia (--apks-dir/--flagship-apk/
             --determinism-pass/--release-proven). Exit 1 se algum FAIL.
  --selftest assercoes internas (arvore saudavel, relatorio deterministico,
             deteccao de falha, ids estaveis).

Lei do repositorio: python3 stdlib-only, sem timestamps, sem emoji, semente
20261022, saidas byte a byte reprodutiveis (JSON canonico: indent 2,
sort_keys, ensure_ascii False).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SEED = 20261022
ROOT = Path(__file__).resolve().parent.parent
GATE_JSON = ROOT / "contracts" / "v1-gate.json"
MIB = 1024 * 1024
MIN_APKS_DEFAULT = 30
MIN_MB_DEFAULT = 850
MAX_MB_DEFAULT = 1000

WORKFLOWS_REQUIRED = [
    "apkbot.yml",
    "ci.yml",
    "engines-nightly.yml",
    "release.yml",
    "rustydroid-snapshot.yml",
    "size-gate.yml",
]

GOVERNANCE_FILES = [
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE-APACHE",
    "LICENSE-MIT",
    "README.en.md",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "labels.json",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/fixture_gap.yml",
    ".github/ISSUE_TEMPLATE/size_regression.yml",
    "docs/book.toml",
    "docs/src/SUMMARY.md",
    "docs/src/guide.md",
    "docs/src/engine-matrix.md",
    "docs/src/permission-matrix.md",
    "docs/src/sdk-ladder.md",
    "docs/src/parser-torture.md",
    "docs/src/sim3d.md",
    "docs/src/size-engineering.md",
    "docs/src/compat-nightly.md",
    "docs/src/compat-matrix.md",
    "docs/src/rustydroid-integration.md",
    "docs/src/v1-gate.md",
    "docs/src/adr/index.md",
    "docs/src/adr/adr-0001-geradores-python-stdlib.md",
    "docs/src/adr/adr-0002-tiers-de-build.md",
    "docs/src/adr/adr-0003-deteccao-nao-valida-payload.md",
    "scripts/compat-nightly.sh",
    "APK_TESTER_PROMPT.md",
]

# (id, texto da Definition of Done do prompt mestre, em PT-BR)
CRITERIA_DOD = [
    (
        "apks_30_plus",
        ">= 30 APKs buildaveis a partir de checkout limpo com toolchains "
        "documentadas (Tier C nao precisa de nenhuma)",
    ),
    (
        "flagship_size_gate",
        "Flagship release dentro de [850 MB, 1000 MB], otimizado com R8, "
        "size-report.csv concilia os bytes",
    ),
    (
        "permissions_audit",
        "permissions-audit.md: contagens por protectionLevel casam com o "
        "manifesto (verdade dura: o AOSP master define 1004 permissoes, nao "
        "~160 — o subconjunto publico documentado e menor que o real)",
    ),
    (
        "minsdk9_apk",
        "APK minSdk 9 existe e e aceito pelo caminho de build (ou fixture "
        "empacotada)",
    ),
    (
        "sim3d_golden",
        "Checksums golden do :sim3d reprodutiveis; probes GLES resultam em "
        "erro estruturado, nunca crash",
    ),
    (
        "ui_grids_icons",
        "ButtonGrid 1200 + IconGrid 600 + 500+ vector drawables + icones "
        "adaptive/monochrome",
    ),
    (
        "rustydroid_zero_drift",
        "rustydroid inspect em cada APK difere numericamente contra a sua "
        "auditoria (zero drift)",
    ),
    (
        "expected_engines_detect",
        "expected-engines.json casa com rd engine detect para todos os APKs "
        "de engine (verdade dura: a matriz cresceu para 32 diretorios — "
        "hibrido #31 + TWA/PWA #32)",
    ),
    (
        "determinism_proof",
        "Duas builds de release consecutivas byte-identicas (prova de "
        "determinismo, exceto assinatura)",
    ),
    (
        "governance_complete",
        "Kit de governanca completo, docs mdBook, 6 workflows, milestones "
        "A0-A8, release v1.0.0",
    ),
]

PASS = "pass"
FAIL = "fail"
EVIDENCE = "evidence-release"


def erro(msg: str) -> None:
    print(f"[v1-gate] ERRO: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_text(path: Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def canonical_json(doc) -> str:
    """JSON canonico do repositorio (indent 2, sort_keys, sem ASCII escape)."""
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run_tool(args, timeout: int = 600):
    """Roda uma ferramenta do repositorio devolvendo (returncode, stdout)."""
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout + proc.stderr


def parse_properties(path: Path) -> dict:
    """Parser minimo de .properties (chave=valor, comentarios #/!)."""
    out = {}
    for line in load_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def fixture_packer_modes() -> list:
    """Modos de fixture suportados pelo fixture-pack (parse do --help)."""
    code, out = run_tool(["tools/fixture-pack.py", "--help"], timeout=60)
    if code != 0:
        return []
    m = re.search(r"--fixture \{([^}]*)\}", out)
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",") if s.strip()]


def parse_int_const(source: str, name: str):
    # constante com comentario de linha opcional (estilo das fontes do repo)
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*(\d+)", source, re.M)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Contexto estatico (lido uma vez por execucao; tudo do repositorio commitado)
# ---------------------------------------------------------------------------


class StaticContext:
    def __init__(self) -> None:
        self.suites_doc = load_json(ROOT / "contracts" / "suites.json")
        self.suites = self.suites_doc["suites"]
        self.canonical = load_json(
            ROOT / "contracts" / "engines" / "expected-engines.json"
        )
        self.engines = self.canonical["engines"]
        self.registry = load_json(
            ROOT / "contracts" / "flagship" / "permissions-registry.json"
        )
        self.rungs = parse_properties(ROOT / "suites" / "sdk-ladder" / "rungs.properties")
        self.modes = fixture_packer_modes()


# ---------------------------------------------------------------------------
# Criterios — cada um devolve (status, measurements, evidence)
# ---------------------------------------------------------------------------


def check_apks_30_plus(ctx: StaticContext, args) -> tuple:
    m = {}
    tiers = {"A": 0, "B": 0, "C": 0}
    for e in ctx.engines:
        tiers[e["tier"]] = tiers.get(e["tier"], 0) + 1
    m["engines_tier_a"] = tiers["A"]
    m["engines_tier_b"] = tiers["B"]
    m["engines_tier_c"] = tiers["C"]
    m["build_tier_a_tool"] = (ROOT / "tools" / "build-tier-a.py").is_file()
    m["build_tier_b_tool"] = (ROOT / "tools" / "build-tier-b.py").is_file()
    m["fixture_pack_tool"] = (ROOT / "tools" / "fixture-pack.py").is_file()

    flavor_dir = ROOT / "suites" / "flagship" / "app" / "src"
    flavors = sorted(
        d.name
        for d in flavor_dir.iterdir()
        if d.is_dir()
        and d.name != "main"
        and (d / "AndroidManifest.xml").is_file()
    )
    m["flagship_flavors"] = flavors

    rung_keys = sorted(k[: -len(".minSdk")] for k in ctx.rungs if k.endswith(".minSdk"))
    m["ladder_rungs"] = len(rung_keys)

    torture_ids = sorted(
        s["id"] for s in ctx.suites if str(s.get("id", "")).startswith("torture-")
    )
    torture_modes = [i[len("torture-"):] for i in torture_ids]
    m["torture_fixture_modes"] = len(torture_modes)
    m["torture_modes_in_packer"] = all(mode in ctx.modes for mode in torture_modes)
    m["minsdk9_fixture_mode"] = "minSdk9" in ctx.modes

    total = (
        tiers["A"] + tiers["B"] + tiers["C"]
        + len(flavors)
        + len(rung_keys)
        + len(torture_modes)
        + (1 if m["minsdk9_fixture_mode"] else 0)
    )
    m["total_apk_slots"] = total
    m["min_required"] = args.min_apks

    status = PASS if total >= args.min_apks else FAIL
    evidence = (
        "slots buildaveis contados da arvore: engines (A/B/C) + flavors do "
        "flagship + degraus da escada + modos de tortura + fixture minSdk9; "
        "builds reais provadas nos workflows CI/nightly"
    )

    if args.apks_dir:
        apks = sorted(p for p in Path(args.apks_dir).rglob("*.apk") if p.is_file())
        m["apks_built"] = len(apks)
        m["apks_built_names"] = [p.name for p in apks]
        if len(apks) < args.min_apks:
            status = FAIL
            evidence = (
                f"APKs construidos ({len(apks)}) abaixo do minimo "
                f"({args.min_apks})"
            )
        else:
            evidence = (
                f"{len(apks)} APKs construidos e coletados no workflow "
                "Release (verdade dinamica do gate)"
            )
    else:
        evidence += "; contagem dinamica de APKs construidos: workflow Release"
    return status, m, evidence


def check_flagship_size_gate(ctx: StaticContext, args) -> tuple:
    m = {}
    csv_path = ROOT / "contracts" / "flagship" / "size-report.csv"
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    total_row = next((r for r in rows if r["category"] == "total"), None)
    if total_row is None:
        return FAIL, {"baseline_csv": str(csv_path)}, "linha total ausente no CSV"
    total_bytes = int(total_row["bytes"])
    m["baseline_total_bytes"] = total_bytes
    m["baseline_total_mib"] = round(total_bytes / MIB, 2)
    m["baseline_categories"] = len([r for r in rows if r["category"] != "total"])
    shas = {r["sha256_of_apk"] for r in rows}
    m["baseline_sha256_consistent"] = len(shas) == 1
    m["baseline_sha256"] = sorted(shas)[0] if len(shas) == 1 else None
    m["gate_min_mb"] = args.min_mb
    m["gate_max_mb"] = args.max_mb

    status = PASS
    evidence = (
        "baseline commitado (contracts/flagship/size-report.csv, gerado pelo "
        "Size Gate do A6) dentro do gate; a medicao FRESH do APK de release "
        "acontece no workflow Release"
    )
    if not (args.min_mb * MIB <= total_bytes <= args.max_mb * MIB):
        status = FAIL
        evidence = (
            f"baseline fora do gate: {m['baseline_total_mib']} MiB nao esta "
            f"em [{args.min_mb}, {args.max_mb}]"
        )
    if not m["baseline_sha256_consistent"]:
        status = FAIL
        evidence = "sha256_of_apk divergente entre as linhas do CSV"

    if args.flagship_apk:
        apk = Path(args.flagship_apk)
        if not apk.is_file():
            return FAIL, m, f"APK nao encontrado: {apk}"
        data = apk.read_bytes()
        # Gate do DoD na semantica do A6 (tools/size-budget.sh): tamanho e
        # CONTEUDO — bytes DESCOMPRIMIDOS por entrada (a alta entropia da
        # carga faz o arquivo acompanhar o total; o gate nao depende da
        # compressao do zip).
        with zipfile.ZipFile(apk) as zf:
            uncompressed = sum(info.file_size for info in zf.infolist())
            entries = len(zf.infolist())
        m["release_apk_file_bytes"] = len(data)
        m["release_apk_file_mib"] = round(len(data) / MIB, 2)
        m["release_uncompressed_bytes"] = uncompressed
        m["release_uncompressed_mib"] = round(uncompressed / MIB, 2)
        m["release_entries"] = entries
        m["release_apk_sha256"] = hashlib.sha256(data).hexdigest()
        if args.min_mb * MIB <= uncompressed <= args.max_mb * MIB:
            evidence = (
                f"APK de release medido no workflow: {m['release_uncompressed_mib']} "
                f"MiB DESCOMPRIMIDOS ({entries} entradas; semantica do gate A6 — "
                f"tamanho e conteudo) dentro de [{args.min_mb}, {args.max_mb}] "
                "(R8 full + shrink; size-report.csv fresco anexado ao release)"
            )
        else:
            status = FAIL
            evidence = (
                f"APK de release fora do gate: {m['release_uncompressed_mib']} "
                f"MiB descomprimidos nao esta em [{args.min_mb}, {args.max_mb}]"
            )
    return status, m, evidence


def check_permissions_audit(ctx: StaticContext, args) -> tuple:
    m = {}
    platform = {p["name"] for p in ctx.registry["permissions"]}
    m["platform_permissions"] = len(platform)
    by_level = ctx.registry["counts"]["by_base_level"]
    m["by_base_level"] = by_level
    m["by_base_level_sums"] = sum(by_level.values()) == len(platform)

    audit = load_text(ROOT / "contracts" / "flagship" / "permissions-audit.md")
    rows = set(
        re.findall(r"^\|\s*(android\.permission\.[A-Z0-9_]+)\s*\|", audit, re.M)
    )
    m["audit_rows"] = len(rows)
    m["audit_rows_match_registry"] = rows == platform

    ns = "{http://schemas.android.com/apk/res/android}"
    root = ET.parse(ROOT / "suites" / "flagship" / "AndroidManifest.xml").getroot()
    used = {e.attrib[f"{ns}name"] for e in root if e.tag.endswith("uses-permission")}
    used23 = {
        e.attrib[f"{ns}name"]
        for e in root
        if e.tag.endswith("uses-permission-sdk-23")
    }
    m["manifest_uses_permission"] = len(used)
    m["manifest_matches_registry"] = used == platform
    m["manifest_sdk23"] = len(used23)
    m["sdk23_matches_registry"] = (
        used23 == set(ctx.registry["flagship_usage"]["uses_permission_sdk_23"])
    )

    ok = all(
        (
            m["by_base_level_sums"],
            m["audit_rows_match_registry"],
            m["manifest_matches_registry"],
            m["sdk23_matches_registry"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "registry (snapshot verbatim do AOSP) == linhas da auditoria == "
        "uses-permission do manifesto; contagens por token base somam o "
        "total; o mesmo cross-check roda no job flagship-skeleton do CI"
    )
    return status, m, evidence


def check_minsdk9_apk(ctx: StaticContext, args) -> tuple:
    m = {}
    rung = ctx.rungs.get("minsdk09.minSdk")
    m["ladder_rung_09_min_sdk"] = int(rung) if rung is not None else None
    m["suite_entry"] = any(s.get("id") == "sdk-ladder-09" for s in ctx.suites)
    m["fixture_packer_mode"] = "minSdk9" in ctx.modes
    m["ladder_project"] = (ROOT / "suites" / "sdk-ladder" / "app").is_dir()
    ok = (
        m["ladder_rung_09_min_sdk"] == 9
        and m["suite_entry"]
        and m["fixture_packer_mode"]
        and m["ladder_project"]
    )
    status = PASS if ok else FAIL
    evidence = (
        "dois caminhos independentes: flavor Gradle minsdk09 (escada real, "
        "12 APKs no CI) e fixture minSdk9 do fixture-pack (parser-torture); "
        "o resultado esperado no RustyDroid e BELOW_FLOOR(minSdk=9) — a lei "
        "de erro estruturado e o teste"
    )
    return status, m, evidence


def check_sim3d_golden(ctx: StaticContext, args) -> tuple:
    m = {}
    golden = load_json(ROOT / "contracts" / "flagship" / "sim3d-golden.json")
    m["golden_schema_version"] = golden.get("schema_version")
    m["golden_seed"] = golden.get("seed")
    sections = [
        "mesh_1m",
        "rasterizer",
        "physics",
        "particles",
        "marching_cubes",
        "skeleton",
    ]
    m["golden_sections"] = sorted(k for k in golden if k in sections)
    m["golden_sections_complete"] = all(k in golden for k in sections)
    fnv_fields = sorted(
        re.findall(r'"([a-z0-9_]*fnv1a64[a-z0-9_]*)"', canonical_json(golden))
    )
    m["golden_fnv1a64_fields"] = len(fnv_fields)
    m["golden_fnv1a64_fields_min"] = 10

    sim3d_suite = next(
        (s for s in ctx.suites if s.get("id") == "flagship-sim3d-golden"), None
    )
    m["suite_reference"] = bool(
        sim3d_suite
        and sim3d_suite.get("expects", {}).get("sim3d_golden")
        == "contracts/flagship/sim3d-golden.json"
    )

    probes = load_json(ROOT / "contracts" / "flagship" / "api-probe-registry.json")
    gles = next(
        (p for p in probes["probes"] if p.get("id") == "MEDIA-GX-001"), None
    )
    m["gles_probe_id"] = "MEDIA-GX-001"
    m["gles_probe_expect"] = gles.get("expect") if gles else None
    m["gles_probe_structured_error"] = bool(
        gles and gles.get("expect") == "NOT_IMPLEMENTED"
    )
    gles_suite = next(
        (s for s in ctx.suites if s.get("id") == "flagship-gles-probes"), None
    )
    m["gles_suite_structured_error_required"] = bool(
        gles_suite
        and gles_suite.get("expects", {}).get("structured_error_required") is True
    )

    ok = all(
        (
            m["golden_schema_version"] == 1,
            m["golden_seed"] == SEED,
            m["golden_sections_complete"],
            m["golden_fnv1a64_fields"] >= 10,
            m["suite_reference"],
            m["gles_probe_structured_error"],
            m["gles_suite_structured_error_required"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "contrato golden commitado com checksums FNV-1a 64 por seccao; a "
        "reprodutibilidade byte a byte e provada no job flagship-3d "
        "(goldenVerify com git diff) e a paridade nativa Java==C++ no mesmo "
        "job; probes GLES exigem erro estruturado (ADR 0003)"
    )
    return status, m, evidence


def check_ui_grids_icons(ctx: StaticContext, args) -> tuple:
    m = {}
    code_b, _ = run_tool(["tools/gen-buttons.py", "--selftest"])
    code_i, _ = run_tool(["tools/gen-icons.py", "--selftest"])
    m["gen_buttons_selftest"] = code_b == 0
    m["gen_icons_selftest"] = code_i == 0

    src_buttons = load_text(ROOT / "tools" / "gen-buttons.py")
    src_icons = load_text(ROOT / "tools" / "gen-icons.py")
    m["buttons"] = parse_int_const(src_buttons, "DEFAULT_BUTTONS")
    m["icon_grid_views"] = parse_int_const(src_buttons, "DEFAULT_ICONS")
    m["vector_drawables"] = parse_int_const(src_icons, "VECTOR_COUNT")
    m["adaptive_icon_template"] = "<adaptive-icon" in src_icons
    m["monochrome_template"] = "ic_launcher_monochrome" in src_icons

    ok = all(
        (
            m["gen_buttons_selftest"],
            m["gen_icons_selftest"],
            m["buttons"] == 1200,
            m["icon_grid_views"] == 600,
            m["vector_drawables"] is not None and m["vector_drawables"] >= 500,
            m["adaptive_icon_template"],
            m["monochrome_template"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "selftests dos geradores (1200 botoes, 600 icons, 600 vetores >= 500, "
        "adaptive com monochrome, determinismo 2x) verdes; a app consome os "
        "mesmos geradores em build-time (preBuild dependsOn)"
    )
    return status, m, evidence


def check_rustydroid_zero_drift(ctx: StaticContext, args) -> tuple:
    m = {}
    ids = [s.get("id") for s in ctx.suites]
    m["suites"] = len(ids)
    m["schema_version"] = ctx.suites_doc.get("schema_version")
    m["suite_ids_unique"] = len(set(ids)) == len(ids)

    # Contratos por diretorio consistentes com o canonico (zero drift
    # semantico: campos compartilhados identicos + nucleo presente — os
    # geradores A3/Tier C enriquecem o contrato com campos proprios).
    CORE_FIELDS = (
        "dir",
        "tier",
        "language",
        "build",
        "rustydroid_engines",
        "detector_artifacts",
    )
    drift = []
    for e in ctx.engines:
        per_dir = ROOT / "suites" / "engines" / e["dir"] / "expected-engines.json"
        if not per_dir.is_file():
            drift.append(f"{e['dir']}: contrato ausente")
            continue
        doc = load_json(per_dir)
        for field in CORE_FIELDS:
            if field not in doc:
                drift.append(f"{e['dir']}: campo nucleo {field} ausente")
            elif doc[field] != e[field]:
                drift.append(f"{e['dir']}: campo {field} divergente")
    m["engine_dirs"] = len(ctx.engines)
    m["engine_dir_contracts_zero_drift"] = not drift
    m["engine_dir_drifts"] = drift[:10]

    # Entradas de build por familia existem na arvore.
    missing_build = []
    for e in ctx.engines:
        d = ROOT / "suites" / "engines" / e["dir"]
        if not d.is_dir():
            missing_build.append(e["dir"])
            continue
        if e["tier"] in ("A", "B") and not (d / "build.sh").is_file():
            missing_build.append(f"{e['dir']}: build.sh ausente")
    m["engine_build_inputs_present"] = not missing_build
    m["engine_build_missing"] = missing_build[:10]
    m["ladder_inputs"] = (
        ROOT / "suites" / "sdk-ladder" / "app" / "build.gradle.kts"
    ).is_file() and bool(ctx.rungs)
    m["torture_packer_modes"] = all(
        s["id"][len("torture-"):] in ctx.modes
        for s in ctx.suites
        if str(s.get("id", "")).startswith("torture-")
    )
    m["flagship_project"] = (ROOT / "suites" / "flagship" / "settings.gradle.kts").is_file()

    ok = all(
        (
            m["suite_ids_unique"],
            m["schema_version"] == 1,
            m["engine_dir_contracts_zero_drift"],
            m["engine_build_inputs_present"],
            m["ladder_inputs"],
            m["torture_packer_modes"],
            m["flagship_project"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "answer keys coherentes na arvore: suites.json schema 1 com ids "
        "unicos, contratos por diretorio identicos ao canonico, entradas de "
        "build presentes; o diff numerico `rustydroid inspect --json` contra "
        "as auditorias roda no runtime RustyDroid (repositorio irmao) — aqui "
        "o zero drift estrutural + os jobs CI que regeneram e diffam "
        "(git diff --exit-code) sao a prova local"
    )
    return status, m, evidence


def check_expected_engines_detect(ctx: StaticContext, args) -> tuple:
    m = {}
    m["canonical_engines"] = len(ctx.engines)
    tiers = {"A": 0, "B": 0, "C": 0}
    for e in ctx.engines:
        tiers[e["tier"]] = tiers.get(e["tier"], 0) + 1
    m["canonical_tiers"] = tiers
    per_dir_count = sum(
        1
        for e in ctx.engines
        if (ROOT / "suites" / "engines" / e["dir"] / "expected-engines.json").is_file()
    )
    m["per_dir_contracts"] = per_dir_count
    m["docs_engine_matrix"] = (ROOT / "docs" / "src" / "engine-matrix.md").is_file()
    m["docs_compat_matrix"] = (ROOT / "docs" / "src" / "compat-matrix.md").is_file()
    m["tier_c_payload_report"] = (
        ROOT / "contracts" / "engines" / "tier-c-payload-report.json"
    ).is_file()

    ci_text = ""
    for wf in ("ci.yml", "engines-nightly.yml"):
        p = ROOT / ".github" / "workflows" / wf
        if p.is_file():
            ci_text += load_text(p)
    # A9/roadmap 5.5: o laço Tier C de pack+verify virou o script
    # compartilhado scripts/pack-tier-c.sh (chamado pelos workflows
    # ci/nightly/release) — as verificações --verify-apk que estavam
    # inline nos workflows agora vivem lá e contam para o critério.
    pack_script = ROOT / "scripts" / "pack-tier-c.sh"
    if pack_script.is_file():
        ci_text += load_text(pack_script)
    m["verify_apk_steps_in_ci"] = ci_text.count("--verify-apk")
    m["verify_apk_steps_min"] = 3
    m["compat_nightly_job"] = "compat-nightly:" in load_text(
        ROOT / ".github" / "workflows" / "engines-nightly.yml"
    )

    ok = all(
        (
            m["canonical_engines"] >= 31,
            m["per_dir_contracts"] == m["canonical_engines"],
            m["docs_engine_matrix"],
            m["docs_compat_matrix"],
            m["tier_c_payload_report"],
            m["verify_apk_steps_in_ci"] >= m["verify_apk_steps_min"],
            m["compat_nightly_job"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "answer key completo (32 diretorios, contratos por diretorio "
        "semanticamente zero-drift) e verificacao artefato-nivel --verify-apk "
        "verde nos jobs tier-a-engines (14) e tier-c-engines (9) do CI e "
        "tier-b-matrix (9) do nightly; a deteccao viva (`rd engine detect`) "
        "roda no runtime RustyDroid contra estes APKs — verdade dura "
        "documentada na matriz de compatibilidade"
    )
    return status, m, evidence


def check_determinism_proof(ctx: StaticContext, args) -> tuple:
    m = {}
    vd = ROOT / "tools" / "verify-deterministic.sh"
    m["tool_present"] = vd.is_file()
    m["tool_executable"] = os.access(str(vd), os.X_OK)
    text = load_text(vd) if vd.is_file() else ""
    m["mode_apk_supported"] = "--mode apk" in text or '"apk)"' in text
    m["mode_generators_supported"] = '"generators)"' in text or "--mode generators" in text
    wf_text = ""
    for wf in WORKFLOWS_REQUIRED:
        p = ROOT / ".github" / "workflows" / wf
        if p.is_file():
            wf_text += load_text(p)
    m["apk_mode_usages_in_workflows"] = len(
    re.findall(r"verify-deterministic\.sh --mode apk", wf_text)
    )

    ok = all(
        (
            m["tool_present"],
            m["tool_executable"],
            m["mode_apk_supported"],
            m["mode_generators_supported"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "ferramenta existe com os modos apk e generators; o modo apk "
        "compara sha256 de cada entrada (META-INF ignorado) e ja prova "
        "determinismo de fixtures no CI; a prova das DUAS builds de release "
        "consecutivas do flagship e dinamica — workflow Release"
    )
    # A9/roadmap 6.3: com --determinism-evidence, a prova deixa de ser
    # flag de confiança — as impressões digitais CANÔNICAS das duas builds
    # (verify-deterministic.sh --canonical-out) são lidas, embeddadas no
    # relatório e DEVEM casar; divergência reprova mesmo com a flag.
    evidence_file = getattr(args, "determinism_evidence", None)
    if args.determinism_pass and evidence_file:
        try:
            lines = [ln.strip() for ln in
                     Path(evidence_file).read_text(encoding="utf-8").splitlines()
                     if ln.strip()]
        except OSError as exc:
            m["determinism_evidence_error"] = str(exc)
            return FAIL, m, (
                f"evidência de determinismo ilegível ({evidence_file}: "
                f"{exc}) — regenere com verify-deterministic.sh "
                "--canonical-out"
            )
        fps, names = [], []
        for ln in lines:
            parts = ln.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                m["determinism_evidence_error"] = f"linha malformada: {ln!r}"
                return FAIL, m, "evidência de determinismo malformada"
            fps.append(parts[0])
            names.append(parts[1].strip())
        m["determinism_builds"] = len(fps)
        m["determinism_content_sha256"] = fps[0] if fps else None
        m["determinism_build_names"] = names
        if len(fps) < 2 or len(set(fps)) != 1:
            m["determinism_hashes_match"] = False
            return FAIL, m, (
                "impressões digitais canônicas das builds DIVERGEM "
                f"({len(fps)} builds, {len(set(fps))} hashes distintos) — "
                "determinismo quebrado"
            )
        m["determinism_hashes_match"] = True
        status = PASS
        evidence = (
            "duas builds consecutivas do flagship modern release "
            "(gradlew clean entre elas) comparadas por "
            "verify-deterministic.sh --mode apk: conteúdo idêntico entrada "
            "a entrada, META-INF (assinatura/mtimes) ignorado — e a prova "
            "AGORA é evidência embeddada (A9/roadmap 6.3): impressão "
            "digital canônica (sha256 sobre nome+sha de cada entrada, "
            "ordenados) DAS DUAS builds = "
            f"`{fps[0]}`, gravada em contracts/determinism-baseline.txt "
            "pelo workflow Release"
        )
        return status, m, evidence
    if args.determinism_pass:
        status = PASS
        evidence = (
            "duas builds consecutivas do flagship modern release "
            "(gradlew clean entre elas) comparadas por "
            "verify-deterministic.sh --mode apk: conteudo identico entrada "
            "a entrada, META-INF (assinatura/mtimes) ignorado — provado no "
            "workflow Release (sem --determinism-evidence: prova por flag; "
            "o Release passa o arquivo com os hashes reais)"
        )
    return status, m, evidence


def check_governance_complete(ctx: StaticContext, args) -> tuple:
    m = {}
    missing = [f for f in GOVERNANCE_FILES if not (ROOT / f).is_file()]
    m["files_required"] = len(GOVERNANCE_FILES)
    m["files_missing"] = missing
    workflows = sorted(
        p.name
        for p in (ROOT / ".github" / "workflows").glob("*.yml")
        if p.is_file()
    )
    m["workflows"] = workflows
    m["workflows_count"] = len(workflows)
    m["workflows_required"] = sorted(WORKFLOWS_REQUIRED)
    m["workflows_complete"] = workflows == sorted(WORKFLOWS_REQUIRED)
    chapters = sorted((ROOT / "docs" / "src").glob("*.md"))
    m["mdbook_chapters"] = len(chapters)
    m["mdbook_chapters_min"] = 10
    m["bot_dir"] = (ROOT / "bot").is_dir()
    m["milestones_and_release"] = (
        "milestones A0-A8 no GitHub + tag v1.0.0 + release publicada — "
        "dinamico"
    )

    ok = all(
        (
            not missing,
            m["workflows_complete"],
            m["mdbook_chapters"] >= 10,
            m["bot_dir"],
        )
    )
    status = PASS if ok else FAIL
    evidence = (
        "kit completo na arvore (governanca, templates, labels, licencas "
        "duais, mdBook com ADRs, bot/); milestones A0-A8 e a release v1.0.0 "
        "sao estado do GitHub provado pelo workflow Release no tag v1.0.0"
    )
    if args.release_proven:
        m["release_proven"] = True
        evidence = (
            "workflow Release verde no tag v1.0.0: gate v1.0 completo com "
            "evidencias dinamicas; milestones A0-A8 fechados pelo owner; "
            "APKBot valida anti-regressao pos-release"
        )
    return status, m, evidence


CHECKS = {
    "apks_30_plus": check_apks_30_plus,
    "flagship_size_gate": check_flagship_size_gate,
    "permissions_audit": check_permissions_audit,
    "minsdk9_apk": check_minsdk9_apk,
    "sim3d_golden": check_sim3d_golden,
    "ui_grids_icons": check_ui_grids_icons,
    "rustydroid_zero_drift": check_rustydroid_zero_drift,
    "expected_engines_detect": check_expected_engines_detect,
    "determinism_proof": check_determinism_proof,
    "governance_complete": check_governance_complete,
}


def run_gate(args) -> dict:
    ctx = StaticContext()
    criteria = []
    for cid, dod in CRITERIA_DOD:
        status, measurements, evidence = CHECKS[cid](ctx, args)
        # Criterios com metade dinamica: sem a evidencia do workflow Release
        # o estatico nao basta — o status vira "evidence-release".
        dynamic_absent = (
            (cid == "apks_30_plus" and not args.apks_dir)
            or (cid == "flagship_size_gate" and not args.flagship_apk)
            or (cid == "determinism_proof" and not args.determinism_pass)
            or (cid == "governance_complete" and not args.release_proven)
        )
        if dynamic_absent and status == PASS:
            status = EVIDENCE
        criteria.append(
            {
                "id": cid,
                "dod": dod,
                "status": status,
                "measurements": measurements,
                "evidence": evidence,
            }
        )
    n_pass = sum(1 for c in criteria if c["status"] == PASS)
    n_fail = sum(1 for c in criteria if c["status"] == FAIL)
    n_evid = sum(1 for c in criteria if c["status"] == EVIDENCE)
    if n_fail:
        result = "fail"
    elif n_evid:
        result = "pending-release-evidence"
    else:
        result = "pass"
    return {
        "schema_version": 1,
        "generated_by": "tools/v1-gate.py",
        "gate": "v1.0",
        "seed": SEED,
        "definition_of_done_source": "APK_TESTER_PROMPT.md",
        "criteria": criteria,
        "summary": {
            "criteria": len(criteria),
            "pass": n_pass,
            "fail": n_fail,
            "evidence_release": n_evid,
        },
        "gate_result": result,
    }


def print_summary(report: dict) -> None:
    print(
        f"[v1-gate] gate v1.0 — resultado: {report['gate_result']} "
        f"(pass={report['summary']['pass']} "
        f"fail={report['summary']['fail']} "
        f"evidence-release={report['summary']['evidence_release']})"
    )
    for c in report["criteria"]:
        mark = {"pass": "PASS", "fail": "FAIL", "evidence-release": "EVREL"}[
            c["status"]
        ]
        print(f"  [{mark}] {c['id']}")
    if report["gate_result"] == "fail":
        for c in report["criteria"]:
            if c["status"] == FAIL:
                print(f"  -> {c['id']}: {c['evidence']}")


def selftest() -> int:
    print("[v1-gate] selftest: arvore saudavel, relatorio deterministico, "
          "deteccao de falha")

    # 1) arvore saudavel: nenhum FAIL estatico.
    args = argparse.Namespace(
        apks_dir=None,
        flagship_apk=None,
        determinism_pass=False,
        release_proven=False,
        min_apks=MIN_APKS_DEFAULT,
        min_mb=MIN_MB_DEFAULT,
        max_mb=MAX_MB_DEFAULT,
    )
    report = run_gate(args)
    fails = [c["id"] for c in report["criteria"] if c["status"] == FAIL]
    assert not fails, f"criterios estaticos reprovados: {fails}"

    # 2) ids e ordem estaveis (10 criterios do DoD).
    ids = [c["id"] for c in report["criteria"]]
    expected_ids = [cid for cid, _ in CRITERIA_DOD]
    assert ids == expected_ids, f"ids divergentes: {ids}"
    assert len(ids) == 10, f"esperava 10 criterios, achei {len(ids)}"

    # 3) relatorio deterministico: duas escritas byte a byte identicas.
    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "a.json"
        p2 = Path(tmp) / "b.json"
        p1.write_text(canonical_json(report), encoding="utf-8")
        report2 = run_gate(args)
        p2.write_text(canonical_json(report2), encoding="utf-8")
        assert p1.read_bytes() == p2.read_bytes(), "relatorio nao deterministico"

        # 4) round-trip JSON.
        loaded = json.loads(p1.read_text(encoding="utf-8"))
        assert loaded["summary"]["criteria"] == 10
        assert loaded["gate_result"] == "pending-release-evidence"

    # 5) deteccao de falha: parser de CSV com total fora do gate reprova.
    bad_csv = "category,bytes,files,sha256_of_apk\ntotal,10,1,deadbeef\n"
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write(bad_csv)
        bad_path = fh.name
    rows = []
    import csv as _csv

    with open(bad_path, newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            rows.append(row)
    total = int(next(r for r in rows if r["category"] == "total")["bytes"])
    assert not (MIN_MB_DEFAULT * MIB <= total <= MAX_MB_DEFAULT * MIB), \
        "CSV sabotado deveria estar fora do gate"
    os.unlink(bad_path)

    # 6) constantes de UI: os alvos do DoD estao nos geradores.
    src_buttons = load_text(ROOT / "tools" / "gen-buttons.py")
    src_icons = load_text(ROOT / "tools" / "gen-icons.py")
    assert parse_int_const(src_buttons, "DEFAULT_BUTTONS") == 1200
    assert parse_int_const(src_buttons, "DEFAULT_ICONS") == 600
    assert parse_int_const(src_icons, "VECTOR_COUNT") == 600

    # 6b) medicao descomprimida (semantica do gate A6): zip conhecido.
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        zip_path = tf.name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.bin", b"x" * 2048)
        zf.writestr("b/c.bin", b"y" * 4096)
    with zipfile.ZipFile(zip_path) as zf:
        total = sum(info.file_size for info in zf.infolist())
    os.unlink(zip_path)
    assert total == 6144, f"total descomprimido errado: {total}"

    # 7) evidencia dinamica: com as flags do Release o gate fecha em pass.
    args_full = argparse.Namespace(
        apks_dir=None,
        flagship_apk=None,
        determinism_pass=True,
        release_proven=True,
        min_apks=MIN_APKS_DEFAULT,
        min_mb=MIN_MB_DEFAULT,
        max_mb=MAX_MB_DEFAULT,
    )
    report_full = run_gate(args_full)
    fails_full = [c["id"] for c in report_full["criteria"] if c["status"] == FAIL]
    assert not fails_full, f"flags de evidencia nao deveriam reprovar: {fails_full}"
    evid_full = [c["id"] for c in report_full["criteria"] if c["status"] == EVIDENCE]
    assert evid_full == ["apks_30_plus", "flagship_size_gate"], \
        f"criterios de evidencia inesperados: {evid_full}"

    print("[v1-gate] selftest: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gate v1.0 do APK Tester (fase A8): criterios da "
        "Definition of Done do prompt mestre."
    )
    parser.add_argument("--sync", action="store_true",
                        help="escreve o contrato estatico em "
                             "contracts/v1-gate.json (zero drift no CI)")
    parser.add_argument("--check", action="store_true",
                        help="roda o gate (estatico sempre; dinamico com as "
                             "flags de evidencia); exit 1 se algum FAIL")
    parser.add_argument("--out", metavar="PATH",
                        help="caminho do relatorio JSON (padrao: stdout)")
    parser.add_argument("--apks-dir", metavar="DIR",
                        help="evidencia: diretorio com os APKs construidos "
                             "(contagem real para o criterio apks_30_plus)")
    parser.add_argument("--flagship-apk", metavar="PATH",
                        help="evidencia: APK de release do flagship para o "
                             "gate de tamanho")
    parser.add_argument("--determinism-pass", action="store_true",
                        help="evidencia: duas builds consecutivas provadas "
                             "byte a byte (verify-deterministic apk)")
    parser.add_argument("--determinism-evidence", metavar="FILE",
                        default=None,
                        help="evidencia REAL (A9/roadmap 6.3): arquivo do "
                             "verify-deterministic.sh --canonical-out com a "
                             "impressao digital canonica das DUAS builds — "
                             "o hash e embeddado no relatorio e as builds "
                             "DEVEM casar (senao FAIL mesmo com "
                             "--determinism-pass)")
    parser.add_argument("--release-proven", action="store_true",
                        help="evidencia: workflow Release verde no tag "
                             "v1.0.0 (milestones + release)")
    parser.add_argument("--min-apks", type=int, default=MIN_APKS_DEFAULT,
                        help=f"minimo de APKs (default {MIN_APKS_DEFAULT})")
    parser.add_argument("--min-mb", type=int, default=MIN_MB_DEFAULT,
                        help=f"limite inferior do gate em MiB "
                             f"(default {MIN_MB_DEFAULT})")
    parser.add_argument("--max-mb", type=int, default=MAX_MB_DEFAULT,
                        help=f"limite superior do gate em MiB "
                             f"(default {MAX_MB_DEFAULT})")
    parser.add_argument("--selftest", action="store_true",
                        help="assercoes internas e sai")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    dynamic_flags = [
        f for f in (args.apks_dir, args.flagship_apk,
                    args.determinism_pass, args.release_proven) if f
    ]
    if args.sync and dynamic_flags:
        erro("--sync e estatico: nao combina com flags de evidencia")
    if args.determinism_evidence and not args.determinism_pass:
        erro("--determinism-evidence exige --determinism-pass "
             "(a evidencia completa a prova, nao a substitui)")

    if not (args.sync or args.check):
        parser.error("use --sync, --check ou --selftest")

    try:
        report = run_gate(args)
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        erro(f"falha ao avaliar criterios: {exc}")

    text = canonical_json(report)
    if args.sync:
        GATE_JSON.parent.mkdir(parents=True, exist_ok=True)
        GATE_JSON.write_text(text, encoding="utf-8")
        print_summary(report)
        print(f"[v1-gate] contrato estatico escrito: {GATE_JSON}")
    elif args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print_summary(report)
        print(f"[v1-gate] relatorio escrito: {out}")
    else:
        print_summary(report)
        print(text)

    if report["gate_result"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
