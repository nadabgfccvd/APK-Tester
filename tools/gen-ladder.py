#!/usr/bin/env python3
"""Gerador da escada sdk-ladder e dos contratos de answer key (A2).

Fonte unica de verdade: a constante RUNGS deste arquivo (12 degraus, minSdk
9 -> 36). O arquivo de flavors do Gradle (rungs.properties), o asset de
runtime do app (ladder/rungs.json) e os contratos de auditoria
(answer-key.json + ladder-audit.md) saem TODOS da mesma lista — zero drift
por construcao: os flavors NUNCA podem divergir do gabarito, e qualquer
divergencia e regressao do gerador (corrige-se a ferramenta, nunca o
arquivo gerado).

Saidas (caminhos relativos a --out; na integracao, --out e a raiz do repo):
  suites/sdk-ladder/rungs.properties                       (fonte dos flavors)
  suites/sdk-ladder/app/src/main/assets/ladder/rungs.json  (dado de runtime)
  contracts/sdk-ladder/answer-key.json                     (gabarito)
  contracts/sdk-ladder/ladder-audit.md                     (auditoria PT-BR)
  contracts/sdk-ladder/manifest.json                       (ledger sha256)

Determinismo: mesma entrada => mesmos bytes (sem timestamps, sem rede, sem
aleatoriedade). --seed e aceito por contrato de interface com
tools/verify-deterministic.sh e apenas registrado nos JSON.

Uso:
    python3 tools/gen-ladder.py --out .            # integracao (raiz do repo)
    python3 tools/gen-ladder.py --out /tmp/out     # sandbox
    python3 tools/gen-ladder.py --selftest
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SEED = 20261022

# Piso de execucao do RustyDroid: minSdk < 26 => BELOW_FLOOR estruturado.
FLOOR_RUSTYDROID = 26

# Todos os degraus compartilham o mesmo targetSdk: a variavel em teste e
# APENAS o minSdk.
TARGET_SDK = 36

APPLICATION_ID_BASE = "dev.apktester.ladder"

# A escada: (minSdk, flavor). O id do flavor e "minsdk" + minSdk com 2
# digitos; o diretorio contratado (contracts/suites.json) e "minsdk-" +
# minSdk com 2 digitos. MinSdk 9 e o teste: abaixo do piso, resultado
# estruturado, nunca crash.
RUNGS = [
    (9, "minsdk09"),
    (12, "minsdk12"),
    (14, "minsdk14"),
    (16, "minsdk16"),
    (19, "minsdk19"),
    (21, "minsdk21"),
    (23, "minsdk23"),
    (26, "minsdk26"),
    (29, "minsdk29"),
    (33, "minsdk33"),
    (35, "minsdk35"),
    (36, "minsdk36"),
]

# O app minimo declarado em todo degrau (nenhum componente alem destes,
# nenhuma permissao declarada).
COMPONENTS = ["activity", "service", "receiver", "provider"]


# ------------------------------------------------------------------ rungs
def rung_records() -> list:
    """Registros derivados da RUNGS, ordenados por minSdk.

    Segundo a lei do piso: minSdk < FLOOR_RUSTYDROID => "BELOW_FLOOR"
    (erro estruturado do RustyDroid); caso contrario "EXECUTE".
    """
    records = []
    for min_sdk, flavor in sorted(RUNGS):
        records.append({
            "flavor": flavor,
            "dir": "minsdk-%02d" % min_sdk,
            "min_sdk": min_sdk,
            "target_sdk": TARGET_SDK,
            "application_id": APPLICATION_ID_BASE + "." + flavor,
            "version_code": min_sdk,
            "version_name": "1.0.0-min%d" % min_sdk,
            "rustydroid": "BELOW_FLOOR" if min_sdk < FLOOR_RUSTYDROID
            else "EXECUTE",
        })
    return records


def expected_detail(min_sdk: int) -> str:
    """Texto do resultado esperado por degrau (answer key e auditoria)."""
    if min_sdk < FLOOR_RUSTYDROID:
        return "BELOW_FLOOR(minSdk=%d) estruturado — nunca crash" % min_sdk
    return "execução (piso/switches por targetSdk)"


# ---------------------------------------------------------------- builders
def build_rungs_properties() -> str:
    """Fonte dos product flavors do Gradle (lida no configure-time)."""
    lines = ["# gerado; NAO editar a mao — regenere com tools/gen-ladder.py"]
    for rec in rung_records():
        lines.append("%s.minSdk=%d" % (rec["flavor"], rec["min_sdk"]))
    return "\n".join(lines) + "\n"


def build_rungs_json(seed: int) -> str:
    """Asset de runtime consumido pela LadderActivity (app minimo)."""
    doc = {
        "schema_version": 1,
        "generated_by": "tools/gen-ladder.py",
        "seed": seed,
        "floor_rustydroid": FLOOR_RUSTYDROID,
        "rungs": rung_records(),
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_answer_key(seed: int) -> str:
    """Gabarito da escada (contracts/sdk-ladder/answer-key.json)."""
    rungs = []
    for rec in rung_records():
        rungs.append({
            "id": "sdk-ladder-%02d" % rec["min_sdk"],
            "apk": "suites/sdk-ladder/" + rec["dir"],
            "flavor": rec["flavor"],
            "min_sdk": rec["min_sdk"],
            "target_sdk": rec["target_sdk"],
            "application_id": rec["application_id"],
            "version_code": rec["version_code"],
            "version_name": rec["version_name"],
            "components": list(COMPONENTS),
            "permissions_count": 0,
            "expected": {
                "rustydroid": rec["rustydroid"],
                "detail": expected_detail(rec["min_sdk"]),
            },
        })
    doc = {
        "schema_version": 1,
        "description": "gabarito da escada sdk-ladder: o mesmo app mínimo "
                       "(1 activity, 1 service, 1 receiver, 1 provider, 0 "
                       "permissões) construído em doze níveis de minSdk; "
                       "abaixo do piso 26 do RustyDroid a resposta é o erro "
                       "estruturado BELOW_FLOOR — minSdk 9 É o teste — e a "
                       "partir de 26 o app executa",
        "generated_by": "tools/gen-ladder.py",
        "seed": seed,
        "rustydroid_floor": FLOOR_RUSTYDROID,
        "rungs": rungs,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_ladder_audit() -> str:
    """Auditoria PT-BR da escada (answer key legível por humanos)."""
    lines = []
    add = lines.append

    add("# SDK Ladder Audit — escada minSdk 9 → 36 (dev.apktester.ladder.*)")
    add("")
    add("STATUS: **preenchida em A2** — answer key dos 12 degraus da escada,")
    add("gerada por `tools/gen-ladder.py` a partir da constante `RUNGS` (fonte")
    add("única). O projeto Gradle consome `suites/sdk-ladder/rungs.properties`")
    add("em tempo de configuração, o app consome o asset `ladder/rungs.json` em")
    add("tempo de execução e este documento consolida o gabarito: todos saem da")
    add("mesma lista — zero drift por construção.")
    add("")
    add("## A lei do piso")
    add("")
    add("O RustyDroid tem piso de execução em **minSdk 26**. Para um APK com")
    add("`minSdk < 26` a resposta esperada é o erro estruturado")
    add("`BELOW_FLOOR(minSdk=…)` — lei de erro, **nunca crash**. Para")
    add("`minSdk >= 26` o app executa e os switches de comportamento passam a")
    add("ser governados pelo targetSdk (36 em todos os degraus).")
    add("")
    add("**minSdk 9 é o teste:** o degrau mais baixo existe exatamente para")
    add("provar a lei do piso — nenhuma suíte pode omiti-lo.")
    add("")
    add("## Os doze degraus")
    add("")
    add("| Degrau | Flavor | minSdk | versionCode | applicationId | "
        "Resultado esperado |")
    add("|--------|--------|--------|-------------|---------------|"
        "--------------------|")
    for rec in rung_records():
        add("| sdk-ladder-%02d | %s | %d | %d | %s | %s |" % (
            rec["min_sdk"], rec["flavor"], rec["min_sdk"],
            rec["version_code"], rec["application_id"],
            expected_detail(rec["min_sdk"])))
    add("")
    add("## Como é construído")
    add("")
    add("- **AGP 8.9.2 + compileSdk 36 + Gradle 8.11.1** (a mesma ferramenta")
    add("  comprovada em CI pelo flagship, que já constrói minSdk 9 no flavor")
    add("  classic; AGP 8 não recusa minSdk baixo — ele recusa apenas")
    add("  atributos de manifesto antigos, que a escada não usa).")
    add("- **12 product flavors** na dimensão `rung`, lidos de")
    add("  `rungs.properties` no configure-time do Gradle: `minSdk`,")
    add("  `applicationId`, `versionCode`, `versionName` e o `resValue`")
    add("  `rung_label` de cada degrau vêm do arquivo gerado.")
    add("- **Zero drift por construção:** flavors, asset de runtime e answer")
    add("  key saem da mesma constante `RUNGS` do gerador — os flavors NUNCA")
    add("  podem divergir do gabarito; qualquer divergência é regressão do")
    add("  gerador (corrige-se a ferramenta, nunca o arquivo gerado).")
    add("- Um flavor por APK: `:app:assemble<Flavor>Debug` produz o degrau")
    add("  correspondente; o par flavor/diretório contratado é")
    add("  `minsdkNN`/`minsdk-NN` (12 APKs, ids em")
    add("  `contracts/sdk-ladder/answer-key.json`).")
    add("")
    add("## O app mínimo")
    add("")
    add("Cada degrau é a MESMA aplicação com exatamente:")
    add("")
    add("- 1 activity (`LadderActivity`, exported, filtro MAIN/LAUNCHER);")
    add("- 1 service (`LadderService`, não-exportado, binder local);")
    add("- 1 receiver (`LadderReceiver`, exported, action de probe);")
    add("- 1 provider (`LadderProvider`, não-exportado, stub determinístico")
    add("  sobre MatrixCursor).")
    add("")
    add("- **0 permissões declaradas** (nenhum `uses-permission`; afirmado em")
    add("  CI: `grep 'E: uses-permission' == 0` no binário).")
    add("- Framework-only, sem androidx — a API mínima real do código é o")
    add("  próprio minSdk declarado; guardas `Build.VERSION.SDK_INT` no estilo")
    add("  do flagship classic (java.io puro com charset por nome, sem")
    add("  try-with-resources, sem `org.json`, `String.format` sempre com")
    add("  `Locale.US`).")
    add("- `targetSdk 36` em todos os degraus: a variável em teste é **apenas**")
    add("  o minSdk.")
    add("")
    add("## Regras duras")
    add("")
    add("1. O degrau minSdk 9 precisa existir de qualquer forma (requisito duro")
    add("   da suíte; se um futuro AGP recusar minSdk < 19, o degrau é")
    add("   construído com AGP pinado em 7.4.2 ou empacotado por")
    add("   `tools/fixture-pack.py` — aapt2 + d8 + zip direto).")
    add("2. Nenhum degrau pode derrubar o runtime: `BELOW_FLOOR` é erro")
    add("   estruturado, nunca crash.")
    add("3. O diff entre `rustydroid inspect --json` e `answer-key.json` deve")
    add("   ser zero-drift (12 degraus, 4 componentes por degrau, 0 permissões).")
    add("4. Entradas espelhadas em `contracts/suites.json` (`sdk-ladder-09` até")
    add("   `sdk-ladder-36`, caminhos `suites/sdk-ladder/minsdk-NN`): o APKBot")
    add("   e o CI consomem os dois gabaritos, que saem da mesma fonte.")
    return "\n".join(lines) + "\n"


def build_gen_manifest(outputs: dict, seed: int) -> str:
    """Ledger de integridade: sha256 de cada arquivo gerado.

    Convencao do repositorio (bot/checks/determinism.py): todo gen-*.py grava
    um manifest.json com entradas artifacts [{path, sha256}]. Fica versionado
    em contracts/sdk-ladder/ ao lado do answer key.
    """
    doc = {
        "tool": "tools/gen-ladder.py",
        "seed": seed,
        "note": "gerado; NAO editar a mao — regenere com a ferramenta",
        "artifacts": [
            {"path": rel,
             "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
            for rel, text in sorted(outputs.items())
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- generate
GENERATED_FILES = [
    "suites/sdk-ladder/rungs.properties",
    "suites/sdk-ladder/app/src/main/assets/ladder/rungs.json",
    "contracts/sdk-ladder/answer-key.json",
    "contracts/sdk-ladder/ladder-audit.md",
]


def generate(out_dir: Path, seed: int = SEED) -> dict:
    outputs = {
        "suites/sdk-ladder/rungs.properties": build_rungs_properties(),
        "suites/sdk-ladder/app/src/main/assets/ladder/rungs.json":
            build_rungs_json(seed),
        "contracts/sdk-ladder/answer-key.json": build_answer_key(seed),
        "contracts/sdk-ladder/ladder-audit.md": build_ladder_audit(),
    }
    outputs["contracts/sdk-ladder/manifest.json"] = build_gen_manifest(
        outputs, seed)
    for rel, text in outputs.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {"outputs": outputs}


# ---------------------------------------------------------------- selftest
def run_selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out_a = Path(tmp) / "a"
        out_b = Path(tmp) / "b"
        a = generate(out_a, SEED)
        b = generate(out_b, SEED)
        for rel, text in a["outputs"].items():
            assert text == b["outputs"][rel], f"determinismo quebrado: {rel}"
            assert (out_a / rel).read_text(encoding="utf-8") == text
            assert (out_b / rel).read_text(encoding="utf-8") == text

        answer = json.loads(a["outputs"]["contracts/sdk-ladder/answer-key.json"])
        rungs_json = json.loads(
            a["outputs"]["suites/sdk-ladder/app/src/main/assets/ladder/rungs.json"])
        assert answer["schema_version"] == 1
        assert rungs_json["schema_version"] == 1
        assert answer["rustydroid_floor"] == FLOOR_RUSTYDROID
        assert rungs_json["floor_rustydroid"] == FLOOR_RUSTYDROID
        assert len(answer["rungs"]) == 12
        assert len(rungs_json["rungs"]) == 12
        assert [r["min_sdk"] for r in answer["rungs"]] == \
            sorted(r["min_sdk"] for r in answer["rungs"])

        for rec_key, rec_asset, (min_sdk, flavor) in zip(
                answer["rungs"], rungs_json["rungs"], sorted(RUNGS)):
            assert rec_key["min_sdk"] == rec_asset["min_sdk"] == min_sdk
            assert rec_key["flavor"] == rec_asset["flavor"] == flavor
            assert flavor == "minsdk%02d" % min_sdk, (
                "flavor fora do contrato de 2 digitos: %s" % flavor)
            assert rec_asset["dir"] == "minsdk-%02d" % min_sdk
            assert rec_key["apk"] == "suites/sdk-ladder/minsdk-%02d" % min_sdk
            assert rec_key["application_id"] == rec_asset["application_id"] == \
                APPLICATION_ID_BASE + "." + flavor
            assert rec_key["version_code"] == rec_asset["version_code"] == min_sdk
            assert rec_key["version_name"] == rec_asset["version_name"] == \
                "1.0.0-min%d" % min_sdk
            assert rec_key["target_sdk"] == rec_asset["target_sdk"] == TARGET_SDK
            expected = "BELOW_FLOOR" if min_sdk < FLOOR_RUSTYDROID else "EXECUTE"
            assert rec_key["expected"]["rustydroid"] == expected
            assert rec_asset["rustydroid"] == expected
            assert rec_key["components"] == COMPONENTS
            assert rec_key["permissions_count"] == 0

        # rungs.properties: ordenado, coerente com RUNGS, parseavel.
        props_text = a["outputs"]["suites/sdk-ladder/rungs.properties"]
        prop_lines = [line for line in props_text.splitlines()
                      if line and not line.startswith("#")]
        assert len(prop_lines) == 12
        parsed = []
        for line in prop_lines:
            key, value = line.split("=", 1)
            parsed.append((key, int(value)))
        keys = [k for k, _v in parsed]
        assert keys == sorted(keys), "rungs.properties fora de ordem"
        assert parsed == [("minsdk%02d.minSdk" % m, m)
                          for m, _f in sorted(RUNGS)]

        # Auditoria: tabela com exatamente 12 linhas de dados.
        audit = a["outputs"]["contracts/sdk-ladder/ladder-audit.md"]
        data_rows = [line for line in audit.splitlines()
                     if line.startswith("| sdk-ladder-")]
        assert len(data_rows) == 12, (
            "tabela do audit tem %d linhas, esperado 12" % len(data_rows))
        for rec in answer["rungs"]:
            assert rec["id"] in audit
            assert rec["application_id"] in audit

        # Ledger: cada sha256 bate com os bytes reais gravados.
        ledger = json.loads(a["outputs"]["contracts/sdk-ladder/manifest.json"])
        assert ledger["tool"] == "tools/gen-ladder.py"
        ledger_paths = [e["path"] for e in ledger["artifacts"]]
        assert ledger_paths == sorted(GENERATED_FILES)
        for entry in ledger["artifacts"]:
            actual = hashlib.sha256(
                (out_a / entry["path"]).read_bytes()).hexdigest()
            assert entry["sha256"] == actual, (
                "sha256 divergente: %s" % entry["path"])

        # Zero drift com contracts/suites.json (quando visivel a partir do
        # repositorio): mesmos ids, caminhos e lei do piso.
        suites_path = REPO_ROOT / "contracts" / "suites.json"
        if suites_path.is_file():
            suites = json.loads(suites_path.read_text(encoding="utf-8"))
            by_id = {s["id"]: s for s in suites["suites"]
                     if s["id"].startswith("sdk-ladder-")}
            for rec in answer["rungs"]:
                entry = by_id.get(rec["id"])
                assert entry is not None, f"{rec['id']} ausente em suites.json"
                assert entry["apk"] == rec["apk"], (
                    f"apk divergente em {rec['id']}: {entry['apk']} != {rec['apk']}")
                assert entry["expects"]["min_sdk"] == rec["min_sdk"]
                assert entry["expects"]["below_floor_allowed"] == \
                    (rec["min_sdk"] < FLOOR_RUSTYDROID)
                if rec["min_sdk"] < FLOOR_RUSTYDROID:
                    assert entry["expects"]["expected_result"] == \
                        rec["expected"]["detail"], (
                            f"detail divergente em {rec['id']}")
                else:
                    assert entry["expects"]["expected_result"].startswith("execução")

    print("[gen-ladder] OK: 12 degraus (minSdk 9..36), rungs.properties "
          "ordenado, tabela do audit com 12 linhas, ledger sha256 verificado "
          "e zero drift com contracts/suites.json")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera a escada sdk-ladder + contratos (A2).")
    parser.add_argument("--out", default=str(REPO_ROOT),
                        help="raiz onde os caminhos relativos sao gravados")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="registrado nos JSON (o gerador nao usa "
                             "aleatoriedade; saida estavel)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    out_dir = Path(args.out)
    result = generate(out_dir, args.seed)
    total = len(result["outputs"])
    digest = hashlib.sha256(
        "".join(result["outputs"][k] for k in sorted(result["outputs"])).encode()
    ).hexdigest()
    print(f"[gen-ladder] {total} arquivos gravados sob {out_dir} "
          f"(sha256 conjunto {digest[:12]}, seed {args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
