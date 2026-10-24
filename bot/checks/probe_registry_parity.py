#!/usr/bin/env python3
"""bot/checks/probe_registry_parity.py — paridade registry de probes X catalogo.

O registry ``contracts/flagship/api-probe-registry.json`` e a answer key
dos probes do flagship Behemoth; o ``ProbeCatalog.java`` (e o wiring em
``ProbeRunner.java``/instrumentacao) e o codigo. Num repositorio obcecado
por zero-drift, answer key prometendo mais do que o codigo entrega e
exatamente o tipo de drift que o bot deve pegar (D3): 17 probes no
registry contra 9 no catalogo passou despercebido ate a auditoria.

Regras:
- Extrai os ids do registry (campo ``id`` de cada entrada de ``probes``).
- Extrai os ids do ProbeCatalog.java pela constante de especificacao
  (primeiro argumento string de todo ``new ProbeSpec(...)``, regex sobre
  o texto — sem parse de Java, stdlib only).
- registry-only => Finding "regression" ...:probe-sem-wiring (answer key
  sem ProbeSpec no catalogo: ou wiring falta ou o registry promete demais).
- catalog-only  => Finding "new" ...:probe-sem-contrato (codigo a frente
  do contrato: o registry precisa da entrada).
- Em ambos os casos o corpo lista os ids com modulo/dominio quando
  disponivel no registry, capado em MAX_LIST_BODY.
- Paridade perfeita => zero findings; o payload ``learn`` carrega os dois
  conjuntos ordenados (diff humano comecando pelo que mudou, se um dia
  divergir em shape).

Arquivos ausentes => CheckResult(ran=False) (estrutura apagada e assunto
para governance, nao para este check).
"""

import json
import re
import sys
from pathlib import Path

CHECK_ID = "probe_registry_parity"

REGISTRY_PATH = Path("contracts/flagship/api-probe-registry.json")
CATALOG_PATH = Path(
    "suites/flagship/app/src/main/java/dev/apktester/behemoth/probe/"
    "ProbeCatalog.java")

# Primeiro argumento string de todo "new ProbeSpec(" no catalogo.
PROBE_SPEC_RE = re.compile(
    r'new\s+ProbeSpec\(\s*\n?\s*"([A-Z]{2,8}-[A-Z]{2,4}-\d{3})"')
MAX_LIST_BODY = 24

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _short(ids_by_meta: dict, missing: list) -> str:
    """Lista capada "id (modulo/dominio)" para o corpo do finding."""
    rows = []
    for probe_id in missing[:MAX_LIST_BODY]:
        meta = ids_by_meta.get(probe_id)
        if meta:
            rows.append(f"- `{probe_id}` ({meta})")
        else:
            rows.append(f"- `{probe_id}`")
    extra = len(missing) - len(rows)
    if extra > 0:
        rows.append(f"- ... e mais {extra} ids")
    return "\n".join(rows)


# ---------------------------------------------------------------------- run
def run(ctx):
    repo = Path(ctx.repo_path)
    registry_file = repo / REGISTRY_PATH
    catalog_file = repo / CATALOG_PATH
    if not registry_file.is_file() or not catalog_file.is_file():
        return CheckResult(
            check=CHECK_ID, ran=False,
            notes="registry ou ProbeCatalog ausentes (estrutura mudou?)")

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    probes = registry.get("probes", [])
    ids_by_meta = {}
    registry_ids = []
    for probe in probes:
        probe_id = str(probe.get("id", ""))
        if not probe_id:
            continue
        registry_ids.append(probe_id)
        ids_by_meta[probe_id] = (
            f"{probe.get('module_id', '?')}/{probe.get('domain', '?')}")

    catalog_text = catalog_file.read_text(encoding="utf-8")
    catalog_ids = list(dict.fromkeys(PROBE_SPEC_RE.findall(catalog_text)))

    registry_set = set(registry_ids)
    catalog_set = set(catalog_ids)
    without_wiring = sorted(registry_set - catalog_set)
    without_contract = sorted(catalog_set - registry_set)

    findings = []
    if without_wiring:
        findings.append(Finding(
            check=CHECK_ID,
            target=str(REGISTRY_PATH),
            severity="regression",
            title="probes no registry sem ProbeSpec no catalogo "
                  "(answer key > codigo)",
            body_md=(
                "O registry declara "
                f"{len(registry_ids)} probes; o ProbeCatalog.java tem "
                f"{len(catalog_ids)} ProbeSpecs. Sem wiring no catalogo, a "
                "answer key promete mais do que o codigo entrega "
                "(drift D3).\n\nSem ProbeSpec:\n"
                + _short(ids_by_meta, without_wiring)),
            fingerprint=f"{CHECK_ID}:probes:sem-wiring"))
    if without_contract:
        findings.append(Finding(
            check=CHECK_ID,
            target=str(CATALOG_PATH),
            severity="new",
            title="probes no catalogo sem entrada no registry "
                  "(codigo > answer key)",
            body_md=(
                "ProbeSpecs no ProbeCatalog.java sem entrada correspondente "
                "no registry (todo probe novo passa ANTES pelo registry).\n\n"
                "Sem contrato:\n" + _short(ids_by_meta, without_contract)),
            fingerprint=f"{CHECK_ID}:probes:sem-contrato"))

    learn = {
        "registry_ids": sorted(registry_ids),
        "catalog_ids": sorted(catalog_ids),
    }
    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn=learn,
        ran=True,
        notes="" if findings else
        f"paridade ok: {len(registry_ids)} probes no registry, "
        f"{len(catalog_ids)} ProbeSpecs no catalogo")
