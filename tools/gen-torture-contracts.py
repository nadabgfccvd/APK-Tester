#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-torture-contracts.py — contratos commitados do pacote parser-torture (A2).

Gerador ENRAIZADO (--out é a raiz do repo, como gen-flagship-manifest.py): é
o renderizador ÚNICO dos contratos commitados do parser-torture. Carrega os
irmãos gen-arsc-stress.py, gen-trap-manifest.py e fixture-pack.py (importlib,
sem executá-los) e renderiza com os MESMOS builders — zero drift por
construção.

Saídas (caminhos relativos a --out):
  contracts/parser-torture/fixtures-audit.md          (visão das 10 fixtures)
  contracts/parser-torture/exported-audit-traps.md    (mesmos bytes de
                                                       gen-trap-manifest)
  contracts/parser-torture/huge-arsc-audit.md         (mesmos bytes de
                                                       gen-arsc-stress)
  contracts/parser-torture/suites-fragment.json       (10 entradas para o
                                                       contracts/suites.json)
  contracts/parser-torture/manifest.json              (ledger artifacts+sha256)
  suites/parser-torture/exported-audit/AndroidManifest.xml
  suites/parser-torture/exported-audit/traps-report.json
  suites/parser-torture/huge-arsc/arsc-report.json    (sha256 do arsc canônico
                                                       computado EM MEMÓRIA —
                                                       o binário NÃO é gravado
                                                       nem commitado)

Determinismo: stdlib only, seed canônica 20261022. --seed é aceito por
contrato de interface com verify-deterministic.sh, mas NÃO altera a saída
(os contratos são âncoras canônicas; idem gen-flagship-manifest.py).

Uso:
  python3 tools/gen-torture-contracts.py --out .      # integração (raiz)
  python3 tools/gen-torture-contracts.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
TOOL = "gen-torture-contracts.py"
DEFAULT_SEED = 20261022


def _load(name: str):
    """Carrega um irmão de tools/ por caminho (hífens impedem import normal)."""
    spec = importlib.util.spec_from_file_location(name, str(TOOLS_DIR / f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture_pack = _load("fixture-pack")
gen_arsc = _load("gen-arsc-stress")
gen_trap = _load("gen-trap-manifest")

# Ordem canônica das 10 fixtures (a da tabela do suites/parser-torture/README).
TORTURE_ORDER = (
    "sig-v1-only", "sig-v2-only", "sig-v3-only", "unaligned", "zip64",
    "huge-arsc", "multidex-8", "unknown-perms", "exported-audit", "obfuscated",
)

PATOLOGIA = {
    "sig-v1-only": "apenas assinatura v1 (JAR) presente",
    "sig-v2-only": "apenas assinatura v2 (APK Signing Block)",
    "sig-v3-only": "apenas assinatura v3 (rotação de chave)",
    "unaligned": "entradas sem zipalign",
    "zip64": ">65.535 entradas (Zip64 EOCD) como data entries",
    "huge-arsc": "resources.arsc sintético: 10k entradas x 40 locales + 7 densidades",
    "multidex-8": "8 arquivos classesN.dex (multidex nativo, minSdk 21)",
    "unknown-perms": "strings de permissão inventadas dev.apktester.fake.*",
    "exported-audit": "9 componentes-armadilha (exported/permissões mal declaradas)",
    "obfuscated": "nomes minificados determinísticos + mapping.txt",
}

EXPECTED_RESULTS = {
    "sig-v1-only": "parser lê esquema v1 isolado",
    "sig-v2-only": "parser lê esquema v2 sem v1",
    "sig-v3-only": "parser lê esquema v3 sem v1/v2",
    "unaligned": "entradas desalinhadas parseadas",
    "zip64": "offsets/contagens Zip64 corretos",
    "huge-arsc": "ARSc 10k x 40 locales parseado sem OOM/timeout",
    "multidex-8": "8 classesN.dex carregados",
    "unknown-perms": "permissões desconhecidas classificadas como unknown — nunca crash",
    "exported-audit": "9 armadilhas reportadas na auditoria",
    "obfuscated": "nomes ofuscados resolvidos via mapping.txt",
}


def apk_name(mode: str) -> str:
    """Nome do APK final (APK_NAMES do fixture-pack; demais: <modo>.apk)."""
    return fixture_pack.APK_NAMES.get(mode, f"{mode}.apk")


def suite_entries() -> list:
    """As 10 entradas do fragmento (mesma ordem de TORTURE_ORDER)."""
    entries = []
    for mode in TORTURE_ORDER:
        cfg = fixture_pack.MODES[mode]
        entries.append({
            "id": f"torture-{mode}",
            "apk": f"suites/parser-torture/{apk_name(mode)[:-4]}",
            "scenario": "install+inspect",
            "expects": {
                "rustydroid_engines": ["java"],
                "min_sdk": cfg["min_sdk"],
                "below_floor_allowed": cfg["min_sdk"] < 26,
                "expected_result": EXPECTED_RESULTS[mode],
            },
        })
    return entries


def build_suites_fragment() -> str:
    doc = {
        "schema_version": 1,
        "note": "fragmento: entradas a inserir em contracts/suites.json "
                "(o CI compara este fragmento com as entradas reais)",
        "suites": suite_entries(),
    }
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_fixtures_audit() -> str:
    """fixtures-audit.md — visão PT-BR das 10 fixtures do pacote."""
    lines = []
    add = lines.append
    add("# Fixtures Audit — pacote parser-torture (10 fixtures)")
    add("")
    add(f"Gerado por `tools/{TOOL}` (seed {DEFAULT_SEED}) lendo a tabela MODES")
    add("de `tools/fixture-pack.py` — zero drift entre esta auditoria, o")
    add("fragmento de suites e as ferramentas que empacotam os APKs.")
    add("")
    add("Cada fixture ataca UMA suposição perigosa dos parsers do RustyDroid")
    add("(ZIP, assinaturas, AXML, ARSc, DEX, manifest) e é empacotada por")
    add("`tools/fixture-pack.py` (aapt2 + d8 + zip + apksigner, sem gradle).")
    add("")
    add("| Modo | APK | minSdk | targetSdk | v1 | v2 | v3 | Patologia | Resultado esperado no RustyDroid |")
    add("|---|---|---|---|---|---|---|---|---|")
    for mode in TORTURE_ORDER:
        cfg = fixture_pack.MODES[mode]
        sig = lambda flag: "sim" if cfg[flag] else "nao"
        add(f"| `{mode}` | `{apk_name(mode)}` | {cfg['min_sdk']} | "
            f"{cfg['target_sdk']} | {sig('v1')} | {sig('v2')} | {sig('v3')} | "
            f"{PATOLOGIA[mode]} | {EXPECTED_RESULTS[mode]} |")
    add("")
    add("## Notas do pacote")
    add("")
    add("- POJOs sem imports `android.*`: o javac do pack roda sem android.jar;")
    add("  a verdade de componentes é o AndroidManifest.xml (CORE-12).")
    add("- Determinismo: seed canônica 20261022, stdlib-only; duas execuções")
    add("  dos geradores produzem bytes idênticos (`verify-deterministic.sh`).")
    add("- `unknown-perms` é o ÚNICO lugar do repo com strings de permissão")
    add("  inventadas — nunca no flagship.")
    add("- `exported-audit` é INTENCIONAL: as violações de exported/permissões")
    add("  estão documentadas em [exported-audit-traps.md](exported-audit-traps.md)")
    add("  e em `traps-report.json` (2 baselines de contraprova).")
    add("- `obfuscated-r8` é proxy honesto de ofuscação: nomes minificados")
    add("  determinísticos + `mapping.txt` DENTRO do APK em `assets/mapping.txt`")
    add("  (R8 real chega nos builds Tier A / release A6).")
    add("- `huge-arsc`: o resources.arsc sintético é gerado no pack e NÃO é")
    add("  commitado — o sha256 canônico em `arsc-report.json` (e a auditoria")
    add("  [h[huge-arsc-audit.md](huge-arsc-audit.md)) é a âncora.")
    add("- `multidex-8`: corpus do `gen-dex-stress` fatiado em 8 lotes")
    add("  contíguos -> classes.dex..classes8.dex na raiz do APK.")
    add("- `sig-v1-only` (minSdk 9), `sig-v2-only` (minSdk 24) e `multidex-8`")
    add("  (minSdk 21) ficam abaixo do piso 26 do RustyDroid: `below_floor_allowed`")
    add("  cobre o BELOW_FLOOR estruturado — nunca crash.")
    add("- Verificação de assinatura no CI limita o range de plataformas do")
    add("  `apksigner verify` (`--min-sdk-version`/`--max-sdk-version`): o")
    add("  apksigner simula INSTALAÇÃO (API 24+ exige v2 \"ou posterior\") e")
    add("  estas fixtures são alvos de PARSER, não de instalação — v1-only")
    add("  se verifica contra 9..23, v2-only contra 24+, v3-only contra 28+.")
    add("")
    add("## Contratos deste diretório")
    add("")
    add("| arquivo | conteúdo |")
    add("|---|---|")
    add("| `fixtures-audit.md` | esta visão geral |")
    add("| `exported-audit-traps.md` | tabela das 9 armadilhas (idem `gen-trap-manifest`) |")
    add("| `huge-arsc-audit.md` | contagens + validação do ARSc sintético |")
    add("| `suites-fragment.json` | as 10 entradas de `contracts/suites.json` |")
    add("| `manifest.json` | ledger com sha256 de cada arquivo gerado |")
    return "\n".join(lines) + "\n"


def build_outputs() -> dict:
    """Renderiza os 8 arquivos (rel -> texto); o binário do arsc nunca sai."""
    arsc = gen_arsc.build_arsc(gen_arsc.DEFAULT_ENTRIES, DEFAULT_SEED)
    arsc_report = gen_arsc.build_report(gen_arsc.DEFAULT_ENTRIES, DEFAULT_SEED,
                                        arsc)
    del arsc
    outputs = {
        "contracts/parser-torture/fixtures-audit.md": build_fixtures_audit(),
        "contracts/parser-torture/exported-audit-traps.md":
            gen_trap.build_audit_md(),
        "contracts/parser-torture/huge-arsc-audit.md":
            gen_arsc.build_audit_md(arsc_report),
        "contracts/parser-torture/suites-fragment.json": build_suites_fragment(),
        "suites/parser-torture/exported-audit/AndroidManifest.xml":
            gen_trap.build_manifest_xml(),
        "suites/parser-torture/exported-audit/traps-report.json":
            gen_trap.build_report_json(),
        "suites/parser-torture/huge-arsc/arsc-report.json":
            gen_arsc.report_json(arsc_report),
    }
    ledger = {
        "tool": f"tools/{TOOL}",
        "seed": DEFAULT_SEED,
        "note": "gerado; NAO editar a mao — regenere com a ferramenta",
        "artifacts": [
            {"path": rel, "sha256": hashlib.sha256(
                outputs[rel].encode("utf-8")).hexdigest()}
            for rel in sorted(outputs)
        ],
    }
    outputs["contracts/parser-torture/manifest.json"] = json.dumps(
        ledger, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    return outputs


def generate(out_dir: Path) -> dict:
    outputs = build_outputs()
    for rel, text in outputs.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return outputs


def selftest() -> int:
    """Renderiza em tmp 2x, valida JSONs, ledger e a tabela MODES (11 modos)."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = generate(root / "a")
            b = generate(root / "b")
            for rel, text in a.items():
                assert text == b[rel], f"determinismo quebrado em {rel}"
                assert (root / "a" / rel).read_text(encoding="utf-8") == text

            fragment = json.loads(a["contracts/parser-torture/suites-fragment.json"])
            suites = fragment["suites"]
            assert len(suites) == 10, f"esperado 10 suites, veio {len(suites)}"
            assert [s["id"] for s in suites] == \
                [f"torture-{m}" for m in TORTURE_ORDER], "ordem/ids divergem"
            assert [s["apk"] for s in suites] == [
                "suites/parser-torture/sig-v1-only",
                "suites/parser-torture/sig-v2-only",
                "suites/parser-torture/sig-v3-only",
                "suites/parser-torture/unaligned",
                "suites/parser-torture/zip64-65k",
                "suites/parser-torture/huge-arsc",
                "suites/parser-torture/multidex-8",
                "suites/parser-torture/unknown-perms",
                "suites/parser-torture/exported-audit",
                "suites/parser-torture/obfuscated-r8",
            ], "apks divergem"
            floor = {s["id"]: s["expects"]["below_floor_allowed"] for s in suites}
            assert floor == {
                "torture-sig-v1-only": True, "torture-sig-v2-only": True,
                "torture-sig-v3-only": False, "torture-unaligned": False,
                "torture-zip64": False, "torture-huge-arsc": False,
                "torture-multidex-8": True, "torture-unknown-perms": False,
                "torture-exported-audit": False, "torture-obfuscated": False,
            }, f"below_floor_allowed divergiu: {floor}"

            traps = json.loads(
                a["suites/parser-torture/exported-audit/traps-report.json"])
            assert len(traps["traps"]) == 9 and traps["baselines"] == 2
            assert gen_trap.build_manifest_xml() == \
                a["suites/parser-torture/exported-audit/AndroidManifest.xml"]
            assert gen_trap.build_audit_md() == \
                a["contracts/parser-torture/exported-audit-traps.md"]
            assert "INTENCIONAIS" in \
                a["contracts/parser-torture/exported-audit-traps.md"]

            arsc_report = json.loads(
                a["suites/parser-torture/huge-arsc/arsc-report.json"])
            assert arsc_report["seed"] == DEFAULT_SEED
            assert arsc_report["entries"] == 10000
            assert arsc_report["locales_count"] == 40
            assert arsc_report["string_entries_total"] == 400000
            assert arsc_report["integer_entries_total"] == 84
            assert len(arsc_report["sha256"]) == 64
            assert gen_arsc.build_audit_md(arsc_report) == \
                a["contracts/parser-torture/huge-arsc-audit.md"]

            ledger = json.loads(a["contracts/parser-torture/manifest.json"])
            paths = {e["path"] for e in ledger["artifacts"]}
            assert paths == {rel for rel in a
                             if rel != "contracts/parser-torture/manifest.json"}, \
                "ledger não cobre exatamente os demais arquivos"
            for entry in ledger["artifacts"]:
                disk = (root / "a" / entry["path"]).read_bytes()
                assert hashlib.sha256(disk).hexdigest() == entry["sha256"], \
                    f"sha256 diverge em {entry['path']}"

        assert len(fixture_pack.MODES) == 11, \
            f"MODES deveria ter 11 modos, tem {len(fixture_pack.MODES)}"
        audit = a["contracts/parser-torture/fixtures-audit.md"]
        for mode in TORTURE_ORDER:
            assert apk_name(mode) in audit and f"`{mode}`" in audit
        print(f"[{TOOL}] selftest OK: 10 suites no fragmento, ledger com "
              f"{len(ledger['artifacts'])} artifacts batendo com os bytes, "
              f"renderizações idênticas ao gen-trap-manifest/gen-arsc-stress, "
              f"MODES={len(fixture_pack.MODES)} modos")
        return 0
    except AssertionError as exc:
        print(f"[{TOOL}] selftest FALHOU: {exc}", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Contratos commitados do pacote parser-torture (A2).")
    parser.add_argument("--out", default=str(REPO_ROOT),
                        help="raiz onde os caminhos relativos sao gravados")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="aceito por contrato de interface (nao altera a "
                             "saida; contratos sao canônicos na seed "
                             f"{DEFAULT_SEED})")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    out_dir = Path(args.out)
    outputs = generate(out_dir)
    digest = hashlib.sha256("".join(outputs[k] for k in sorted(outputs))
                            .encode("utf-8")).hexdigest()
    print(f"[{TOOL}] {len(outputs)} arquivos gravados sob {out_dir} "
          f"(sha256 conjunto {digest[:12]}, seed {DEFAULT_SEED} — saída "
          "independente de --seed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
