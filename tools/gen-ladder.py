#!/usr/bin/env python3
"""Gerador da escada sdk-ladder e dos contratos de answer key (A2 + D2).

Fonte unica de verdade: as constantes MIN_SDK_RUNGS e TARGET_SDK_RUNGS
deste arquivo (18 degraus em dois eixos). O arquivo de flavors do Gradle
(rungs.properties), o asset de runtime do app (ladder/rungs.json) e os
contratos de auditoria (answer-key.json + ladder-audit.md) saem TODOS das
mesmas listas — zero drift por construcao: os flavors NUNCA podem divergir
do gabarito, e qualquer divergencia e regressao do gerador (corrige-se a
ferramenta, nunca o arquivo gerado).

Eixo 1 (A2): minSdk varia, targetSdk fixo em 36 — 12 degraus "minsdkNN".
Eixo 2 (D2): targetSdk varia — 6 degraus "targetsdkNN", exercitando de
verdade os switches de comportamento governados pelo targetSdk (a promessa
doc que antes era falsa: com targetSdk 36 constante, nenhum switch era
diferente entre degraus).

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

# Eixo 1: targetSdk fixo em TODOS os degraus minsdkNN; a variavel em teste
# e APENAS o minSdk.
TARGET_SDK = 36

APPLICATION_ID_BASE = "dev.apktester.ladder"

# Eixo 1 da escada: (minSdk, flavor). O id do flavor e "minsdk" + minSdk
# com 2 digitos; o diretorio contratado (contracts/suites.json) e
# "minsdk-" + minSdk com 2 digitos. MinSdk 9 e o teste: abaixo do piso,
# resultado estruturado, nunca crash.
MIN_SDK_RUNGS = [
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

# Eixo 2 da escada (D2): (targetSdk, minSdk), flavor "targetsdk" + targetSdk
# com 2 digitos, diretorio contratado "targetsdk-NN". O minSdk de cada
# degrau e o maior piso valido (contrato da toolchain: targetSdk >= minSdk):
# targetSdk 23 usa minSdk 23 (abaixo do piso 26 do RustyDroid — a lei do
# piso se aplica e o resultado esperado e BELOW_FLOOR estruturado; o degrau
# prova que o targetSdk baixo nao engana o piso) e targetSdk 29..35 usam
# minSdk 26 (execucao real com switches de comportamento DIFERENTES por
# degrau — o que o eixo 1 nunca pode exercitar).
TARGET_SDK_RUNGS = [
    (23, 23),
    (29, 26),
    (31, 26),
    (33, 26),
    (34, 26),
    (35, 26),
]

# Compatibilidade com leitores antigos da constante (selftest interno usa
# os dois eixos explicitamente).
RUNGS = list(MIN_SDK_RUNGS)

# O app minimo declarado em todo degrau (nenhum componente alem destes,
# nenhuma permissao declarada).
COMPONENTS = ["activity", "service", "receiver", "provider"]


# ------------------------------------------------------------------ rungs
def rung_records() -> list:
    """Registros derivados dos DOIS eixos, ordenados por (eixo, sdk).

    Segundo a lei do piso: minSdk < FLOOR_RUSTYDROID => "BELOW_FLOOR"
    (erro estruturado do RustyDroid); caso contrario "EXECUTE". No eixo 2
    (targetsdkNN) o minSdk pode estar no piso 26 com targetSdk diferente
    em cada degrau — os switches de comportamento passam a variar de verdade.
    """
    records = []
    for min_sdk, flavor in sorted(MIN_SDK_RUNGS):
        records.append({
            "kind": "minsdk",
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
    for target_sdk, min_sdk in sorted(TARGET_SDK_RUNGS):
        flavor = "targetsdk%02d" % target_sdk
        records.append({
            "kind": "targetsdk",
            "flavor": flavor,
            "dir": "targetsdk-%02d" % target_sdk,
            "min_sdk": min_sdk,
            "target_sdk": target_sdk,
            "application_id": APPLICATION_ID_BASE + "." + flavor,
            "version_code": target_sdk,
            "version_name": "1.0.0-ts%d" % target_sdk,
            "rustydroid": "BELOW_FLOOR" if min_sdk < FLOOR_RUSTYDROID
            else "EXECUTE",
        })
    return records


def expected_detail(min_sdk: int, target_sdk: int = TARGET_SDK) -> str:
    """Texto do resultado esperado por degrau (answer key e auditoria)."""
    if min_sdk < FLOOR_RUSTYDROID:
        return "BELOW_FLOOR(minSdk=%d) estruturado — nunca crash" % min_sdk
    return "execução (switches de comportamento por targetSdk=%d)" % target_sdk


# ---------------------------------------------------------------- builders
def build_rungs_properties() -> str:
    """Fonte dos product flavors do Gradle (lida no configure-time).

    Degraus targetsdkNN declaram TAMBEM o .targetSdk (o Gradle consome os
    dois); degraus minsdkNN usam o default 36 do modulo :app.
    """
    lines = ["# gerado; NAO editar a mao — regenere com tools/gen-ladder.py"]
    for rec in rung_records():
        lines.append("%s.minSdk=%d" % (rec["flavor"], rec["min_sdk"]))
        if rec["kind"] == "targetsdk":
            lines.append("%s.targetSdk=%d" % (rec["flavor"],
                                              rec["target_sdk"]))
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


def rung_id(rec: dict) -> str:
    """Id estavel do degrau: sdk-ladder-NN (eixo 1) ou sdk-ladder-tsNN (eixo 2)."""
    if rec["kind"] == "targetsdk":
        return "sdk-ladder-ts%02d" % rec["target_sdk"]
    return "sdk-ladder-%02d" % rec["min_sdk"]


def build_answer_key(seed: int) -> str:
    """Gabarito da escada (contracts/sdk-ladder/answer-key.json)."""
    rungs = []
    for rec in rung_records():
        rungs.append({
            "id": rung_id(rec),
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
                "detail": expected_detail(rec["min_sdk"],
                                          rec["target_sdk"]),
            },
        })
    doc = {
        "schema_version": 2,
        "description": "gabarito da escada sdk-ladder: o mesmo app mínimo "
                       "(1 activity, 1 service, 1 receiver, 1 provider, 0 "
                       "permissões) construído em 18 degraus de dois eixos: "
                       "12 de minSdk (9..36, targetSdk 36) e 6 de targetSdk "
                       "(23/29/31/33/34/35) — abaixo do piso 26 do "
                       "RustyDroid a resposta é o erro estruturado "
                       "BELOW_FLOOR — minSdk 9 É o teste — e a partir de 26 "
                       "o app executa com switches de comportamento que "
                       "agora VARIAAM por degrau no eixo targetSdk",
        "generated_by": "tools/gen-ladder.py",
        "seed": seed,
        "rustydroid_floor": FLOOR_RUSTYDROID,
        "rungs": rungs,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build_ladder_audit() -> str:
    """Auditoria PT-BR da escada (answer key legivel por humanos)."""
    lines = []
    add = lines.append

    add("# SDK Ladder Audit \u2014 dois eixos: minSdk 9 \u2192 36 e targetSdk "
        "23 \u2192 35 (dev.apktester.ladder.*)")
    add("")
    add("STATUS: **preenchida em A2, estendida em D2** \u2014 answer key dos 18")
    add("degraus da escada (12 de minSdk + 6 de targetSdk), gerada por")
    add("`tools/gen-ladder.py` a partir das constantes `MIN_SDK_RUNGS` e")
    add("`TARGET_SDK_RUNGS` (fonte \u00fanica). O projeto Gradle consome")
    add("`suites/sdk-ladder/rungs.properties` em tempo de configura\u00e7\u00e3o, o app")
    add("consome o asset `ladder/rungs.json` em tempo de execu\u00e7\u00e3o e este")
    add("documento consolida o gabarito: todos saem das mesmas listas \u2014 zero")
    add("drift por constru\u00e7\u00e3o.")
    add("")
    add("## A lei do piso")
    add("")
    add("O RustyDroid tem piso de execu\u00e7\u00e3o em **minSdk 26**. Para um APK com")
    add("`minSdk < 26` a resposta esperada \u00e9 o erro estruturado")
    add("`BELOW_FLOOR(minSdk=\u2026)` \u2014 lei de erro, **nunca crash**. Para")
    add("`minSdk >= 26` o app executa e os switches de comportamento passam a")
    add("ser governados pelo targetSdk \u2014 e no eixo 2 da escada o targetSdk")
    add("VARIA de verdade (23/29/31/33/34/35), exercitando os switches que o")
    add("eixo 1 (targetSdk 36 constante) jamais exercitaria.")
    add("")
    add("**minSdk 9 \u00e9 o teste:** o degrau mais baixo existe exatamente para")
    add("provar a lei do piso \u2014 nenhuma su\u00edte pode omiti-lo.")
    add("")
    add("## Os doze degraus do eixo minSdk (targetSdk 36)")
    add("")
    add("| Degrau | Flavor | minSdk | versionCode | applicationId | "
        "Resultado esperado |")
    add("|--------|--------|--------|-------------|---------------|"
        "--------------------|")
    for rec in rung_records():
        if rec["kind"] != "minsdk":
            continue
        add("| sdk-ladder-%02d | %s | %d | %d | %s | %s |" % (
            rec["min_sdk"], rec["flavor"], rec["min_sdk"],
            rec["version_code"], rec["application_id"],
            expected_detail(rec["min_sdk"], rec["target_sdk"])))
    add("")
    add("## Os seis degraus do eixo targetSdk (D2)")
    add("")
    add("| Degrau | Flavor | minSdk | targetSdk | versionCode | "
        "applicationId | Resultado esperado |")
    add("|--------|--------|--------|-----------|-------------|"
        "---------------|--------------------|")
    for rec in rung_records():
        if rec["kind"] != "targetsdk":
            continue
        add("| sdk-ladder-ts%02d | %s | %d | %d | %d | %s | %s |" % (
            rec["target_sdk"], rec["flavor"], rec["min_sdk"],
            rec["target_sdk"], rec["version_code"], rec["application_id"],
            expected_detail(rec["min_sdk"], rec["target_sdk"])))
    add("")
    add("Nota honesta do degrau `targetsdk23`: targetSdk 23 exige minSdk 23")
    add("(contrato da toolchain: targetSdk >= minSdk), ent\u00e3o o degrau fica")
    add("ABAIXO do piso 26 do RustyDroid \u2014 a resposta esperada \u00e9 o")
    add("BELOW_FLOOR(minSdk=23) estruturado. O degrau prova que o targetSdk")
    add("baixo n\u00e3o engana a lei do piso; os switches de comportamento por")
    add("targetSdk s\u00e3o exercitados de verdade pelos cinco degraus 29..35")
    add("(minSdk 26, execu\u00e7\u00e3o real, targetSdk diferente em cada um).")
    add("")
    add("## Como \u00e9 constru\u00eddo")
    add("")
    add("- **AGP 8.9.2 + compileSdk 36 + Gradle 8.11.1** (a mesma ferramenta")
    add("  comprovada em CI pelo flagship, que j\u00e1 constr\u00f3i minSdk 9 no flavor")
    add("  classic; AGP 8 n\u00e3o recusa minSdk baixo \u2014 ele recusa apenas")
    add("  atributos de manifesto antigos, que a escada n\u00e3o usa).")
    add("- **18 product flavors** na dimens\u00e3o `rung`, lidos de")
    add("  `rungs.properties` no configure-time do Gradle: `minSdk`,")
    add("  `targetSdk` (eixo 2), `applicationId`, `versionCode`,")
    add("  `versionName` e o `resValue` `rung_label` de cada degrau v\u00eam do")
    add("  arquivo gerado.")
    add("- **Zero drift por constru\u00e7\u00e3o:** flavors, asset de runtime e answer")
    add("  key saem das mesmas constantes do gerador \u2014 os flavors NUNCA")
    add("  podem divergir do gabarito; qualquer diverg\u00eancia \u00e9 regress\u00e3o do")
    add("  gerador (corrige-se a ferramenta, nunca o arquivo gerado).")
    add("- Um flavor por APK: `:app:assemble<Flavor>Debug` produz o degrau")
    add("  correspondente; o par flavor/diret\u00f3rio contratado \u00e9")
    add("  `minsdkNN`/`minsdk-NN` (eixo 1) e `targetsdkNN`/`targetsdk-NN`")
    add("  (eixo 2) \u2014 18 APKs, ids em `contracts/sdk-ladder/answer-key.json`.")
    add("")
    add("## O app m\u00ednimo")
    add("")
    add("Cada degrau \u00e9 a MESMA aplica\u00e7\u00e3o com exatamente:")
    add("")
    add("- 1 activity (`LadderActivity`, exported, filtro MAIN/LAUNCHER);")
    add("- 1 service (`LadderService`, n\u00e3o-exportado, binder local);")
    add("- 1 receiver (`LadderReceiver`, exported, action de probe);")
    add("- 1 provider (`LadderProvider`, n\u00e3o-exportado, stub determin\u00edstico")
    add("  sobre MatrixCursor).")
    add("")
    add("- **0 permiss\u00f5es declaradas** (nenhum `uses-permission`; afirmado em")
    add("  CI: `grep \'E: uses-permission\' == 0` no bin\u00e1rio).")
    add("- Framework-only, sem androidx \u2014 a API m\u00ednima real do c\u00f3digo \u00e9 o")
    add("  pr\u00f3prio minSdk declarado; guardas `Build.VERSION.SDK_INT` no estilo")
    add("  do flagship classic (java.io puro com charset por nome, sem")
    add("  try-with-resources, sem `org.json`, `String.format` sempre com")
    add("  `Locale.US`).")
    add("- Eixo 1: `targetSdk 36` em todos os degraus minsdkNN (a vari\u00e1vel em")
    add("  teste \u00e9 **apenas** o minSdk; os switches de comportamento N\u00c3O s\u00e3o")
    add("  exercitados neste eixo \u2014 promessa em contr\u00e1rio era falsa e foi")
    add("  corrigida em D2 com o eixo 2).")
    add("- Eixo 2: `minSdk` fixo (23 no degrau ts23; 26 nos demais) e")
    add("  `targetSdk` 23/29/31/33/34/35 \u2014 a vari\u00e1vel em teste \u00e9 o targetSdk.")
    add("")
    add("## Regras duras")
    add("")
    add("1. O degrau minSdk 9 precisa existir de qualquer forma (requisito duro")
    add("   da su\u00edte; se um futuro AGP recusar minSdk < 19, o degrau \u00e9")
    add("   constru\u00eddo com AGP pinado em 7.4.2 ou empacotado por")
    add("   `tools/fixture-pack.py` \u2014 aapt2 + d8 + zip direto).")
    add("2. Nenhum degrau pode derrubar o runtime: `BELOW_FLOOR` \u00e9 erro")
    add("   estruturado, nunca crash.")
    add("3. O diff entre `rustydroid inspect --json` e `answer-key.json` deve")
    add("   ser zero-drift (18 degraus, 4 componentes por degrau, 0 permiss\u00f5es,")
    add("   targetSdk por degrau conforme o eixo).")
    add("4. Entradas espelhadas em `contracts/suites.json` (`sdk-ladder-09` at\u00e9")
    add("   `sdk-ladder-36` e `sdk-ladder-ts23` at\u00e9 `sdk-ladder-ts35`, caminhos")
    add("   `suites/sdk-ladder/minsdk-NN` e `suites/sdk-ladder/targetsdk-NN`):")
    add("   o APKBot e o CI consomem os dois gabaritos, que saem da mesma")
    add("   fonte.")
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
        assert answer["schema_version"] == 2
        assert rungs_json["schema_version"] == 1
        assert answer["rustydroid_floor"] == FLOOR_RUSTYDROID
        assert rungs_json["floor_rustydroid"] == FLOOR_RUSTYDROID
        assert len(answer["rungs"]) == 18
        assert len(rungs_json["rungs"]) == 18
        minsdk = [r for r in answer["rungs"]
                  if r["id"].startswith("sdk-ladder-")
                  and not r["id"].startswith("sdk-ladder-ts")]
        targetsdk = [r for r in answer["rungs"] if r["id"].startswith("sdk-ladder-ts")]
        assert len(minsdk) == 12 and len(targetsdk) == 6

        # Eixo 1: os 12 degraus minsdkNN (targetSdk 36 fixo).
        for rec_key, rec_asset, (min_sdk, flavor) in zip(
                minsdk, [r for r in rungs_json["rungs"]
                         if r["kind"] == "minsdk"], sorted(MIN_SDK_RUNGS)):
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

        # Eixo 2 (D2): os 6 degraus targetsdkNN (targetSdk varia, minSdk piso).
        pairs = {(ts, m) for ts, m in TARGET_SDK_RUNGS}
        for rec_key, rec_asset in zip(
                targetsdk, [r for r in rungs_json["rungs"]
                            if r["kind"] == "targetsdk"]):
            ts = rec_key["target_sdk"]
            m = rec_key["min_sdk"]
            assert (ts, m) in pairs, f"par (targetSdk, minSdk) inesperado: {ts},{m}"
            flavor = "targetsdk%02d" % ts
            assert rec_key["flavor"] == rec_asset["flavor"] == flavor
            assert rec_asset["dir"] == "targetsdk-%02d" % ts
            assert rec_key["apk"] == "suites/sdk-ladder/targetsdk-%02d" % ts
            assert rec_key["id"] == "sdk-ladder-ts%02d" % ts
            assert rec_key["application_id"] == rec_asset["application_id"] == \
                APPLICATION_ID_BASE + "." + flavor
            assert rec_key["version_code"] == rec_asset["version_code"] == ts
            assert rec_key["version_name"] == rec_asset["version_name"] == \
                "1.0.0-ts%d" % ts
            expected = "BELOW_FLOOR" if m < FLOOR_RUSTYDROID else "EXECUTE"
            assert rec_key["expected"]["rustydroid"] == expected
            assert rec_asset["rustydroid"] == expected
            assert rec_key["target_sdk"] >= rec_key["min_sdk"], (
                "contrato da toolchain violado: targetSdk < minSdk")
            assert rec_key["components"] == COMPONENTS
            assert rec_key["permissions_count"] == 0

        # rungs.properties: ordenado, coerente com os dois eixos, parseavel.
        props_text = a["outputs"]["suites/sdk-ladder/rungs.properties"]
        prop_lines = [line for line in props_text.splitlines()
                      if line and not line.startswith("#")]
        assert len(prop_lines) == 12 + 6 + 6, (
            "rungs.properties deveria ter 24 linhas (18 minSdk + 6 "
            "targetSdk), tem %d" % len(prop_lines))
        parsed = {}
        for line in prop_lines:
            key, value = line.split("=", 1)
            parsed[key] = int(value)
        keys = sorted(k for k in parsed if k.endswith(".minSdk"))
        assert keys == ["minsdk%02d.minSdk" % m for m, _f in sorted(MIN_SDK_RUNGS)] + \
            ["targetsdk%02d.minSdk" % ts for ts, _m in sorted(TARGET_SDK_RUNGS)]
        for ts, m in TARGET_SDK_RUNGS:
            key = "targetsdk%02d.targetSdk" % ts
            assert parsed[key] == ts, f"{key} = {parsed[key]}, esperado {ts}"

        # Auditoria: tabelas com exatamente 12 + 6 linhas de dados.
        audit = a["outputs"]["contracts/sdk-ladder/ladder-audit.md"]
        data_rows = [line for line in audit.splitlines()
                     if line.startswith("| sdk-ladder-")]
        assert len(data_rows) == 18, (
            "tabelas do audit tem %d linhas, esperado 18" % len(data_rows))
        ts_rows = [line for line in audit.splitlines()
                   if line.startswith("| sdk-ladder-ts")]
        assert len(ts_rows) == 6, (
            "tabela targetSdk do audit tem %d linhas, esperado 6" % len(ts_rows))
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
                assert entry["expects"]["target_sdk"] == rec["target_sdk"], (
                    f"target_sdk divergente em {rec['id']}")
                assert entry["expects"]["below_floor_allowed"] == \
                    (rec["min_sdk"] < FLOOR_RUSTYDROID)
                if rec["min_sdk"] < FLOOR_RUSTYDROID:
                    assert entry["expects"]["expected_result"] == \
                        rec["expected"]["detail"], (
                            f"detail divergente em {rec['id']}")
                else:
                    assert entry["expects"]["expected_result"].startswith(
                        "execu\u00e7\u00e3o")

    print("[gen-ladder] OK: 18 degraus (12 minSdk 9..36 + 6 targetSdk "
          "23..35), rungs.properties com os dois eixos, tabelas do audit "
          "com 12+6 linhas, ledger sha256 verificado e zero drift com "
          "contracts/suites.json")
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
