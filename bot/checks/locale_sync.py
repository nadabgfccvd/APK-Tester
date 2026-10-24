#!/usr/bin/env python3
"""bot/checks/locale_sync.py — drift de tradução PT/EN nos READMEs.

O repositório é bilíngue por design (README.md PT-BR + README.en.md EN) e
a auditoria externa A9 (roadmap 4.2) achou o EN desatualizado: dizia "~160"
permissões (o real é 1004, verbatim do snapshot AOSP) e 9 engines Tier C
"planned (A3)" quando já estavam entregues. Um README que mente em outro
idioma é o mesmo problema de um contrato com drift — só que o CI não
compara traduções.

O que este check vigia (tabela de engines dos dois arquivos):
1. CONJUNTO de ids: as linhas ``| `engine-XX-nome` | ... |`` do PT e do EN
   declararem o MESMO conjunto de engines (linha faltando/sobrando em um
   dos idiomas => Finding "drift");
2. STATUS por engine: o marcador ``(AX)`` (fase de entrega) extraído da
   célula de status deve ser IGUAL nos dois idiomas, e a palavra
   "planned"/"planejado" em qualquer deles é drift (a matriz completa está
   entregue desde a 1.0.0 — status futuro volta a ser válido quando uma
   fase nova abrir, daí "drift" e não "regression");
3. NÚMEROS-CHAVE (>= 100) de cada README vão para o ``learn`` (visíveis no
   relatório, sem abrir issue): diferenças numéricas entre traduções são
   revisadas por humano na hora do diff, não automatizadas — contagens de
   permissões/engine mudam juntas com os contratos e os checks dedicados
   (engine_matrix/permission_drift) já vigiam a verdade canônica.

Arquivos lidos: README.md e README.en.md na raiz do repositório. Ausência
de um deles => CheckResult(ran=False) com nota (não é erro de rede, é
layout de repo inesperado). Nada é escrito em disco; sem rede, sem API —
check puramente local e determinístico.
"""

import re
import sys
from pathlib import Path

CHECK_ID = "locale_sync"

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore

# Linha de engine na tabela: | `engine-XX-nome` | linguagem | tier | status |
_ENGINE_ROW_RE = re.compile(
    r"^\|\s*`(engine-\d{2}-[a-z0-9-]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", re.M)
_PHASE_RE = re.compile(r"\((A\d+)\)")
_PLANNED_RE = re.compile(r"\bplanned\b|\bplanejad[oa]\b", re.I)
_NUMBER_RE = re.compile(r"\b\d{3,}\b")


def _engine_rows(text: str) -> dict:
    """{engine_id: (fase_ou_None, planejado?)} da tabela de engines."""
    rows = {}
    for match in _ENGINE_ROW_RE.finditer(text):
        engine_id = match.group(1)
        status = match.group(4) or ""
        phase = _PHASE_RE.search(status)
        rows[engine_id] = (phase.group(1) if phase else None,
                           bool(_PLANNED_RE.search(status)))
    return rows


def _numbers(text: str) -> set:
    """Números >= 100 (3+ dígitos) do arquivo — para o learn comparativo."""
    return set(_NUMBER_RE.findall(text))


def _read(repo: Path, name: str):
    try:
        return (repo / name).read_text(encoding="utf-8")
    except OSError:
        return None


def _cap_block(title, items, limit=40):
    shown = list(items)[:limit]
    extra = len(items) - len(shown)
    body = "\n".join(f"- `{i}`" for i in shown)
    if extra > 0:
        body += f"\n- … e mais {extra}"
    return f"\n\n**{title}** ({len(items)}):\n{body}" if items else ""


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    repo = Path(str(ctx.repo_path))
    findings = []

    pt = _read(repo, "README.md")
    en = _read(repo, "README.en.md")
    if pt is None or en is None:
        missing = [n for n, t in (("README.md", pt), ("README.en.md", en))
                   if t is None]
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes="READMEs ausentes no layout esperado: "
                                 + ", ".join(missing))

    rows_pt = _engine_rows(pt)
    rows_en = _engine_rows(en)

    learn = {
        "pt_engines": len(rows_pt),
        "en_engines": len(rows_en),
        "pt_numbers": sorted(_numbers(pt))[:80],
        "en_numbers": sorted(_numbers(en))[:80],
    }

    # 1) mesmo conjunto de ids
    ids_pt, ids_en = set(rows_pt), set(rows_en)
    if ids_pt != ids_en:
        only_pt = sorted(ids_pt - ids_en)
        only_en = sorted(ids_en - ids_pt)
        findings.append(Finding(
            check=CHECK_ID, target="README.md / README.en.md",
            severity="drift",
            title="Tabela de engines diverge entre PT e EN",
            body_md=(
                "A tabela de engines do README PT-BR e do README EN não "
                "declaram o mesmo conjunto — uma tradução foi editada e a "
                "outra não:"
                + _cap_block("Só no PT (faltam no EN)", only_pt)
                + _cap_block("Só no EN (faltam no PT)", only_en) +
                "\n\nSincronizar as duas tabelas (a verdade canônica é "
                "`contracts/engines/expected-engines.json`)."),
            fingerprint=f"{CHECK_ID}:readmes:conjunto-de-engines"))

    # 2) mesma fase de entrega por engine + nada "planned"
    phase_drift, planned = [], []
    for engine_id in sorted(ids_pt & ids_en):
        phase_pt, planned_pt = rows_pt[engine_id]
        phase_en, planned_en = rows_en[engine_id]
        if phase_pt != phase_en:
            phase_drift.append(f"- `{engine_id}`: PT={phase_pt} EN={phase_en}")
        if planned_pt or planned_en:
            planned.append(f"- `{engine_id}`: "
                           + ("PT " if planned_pt else "")
                           + ("EN " if planned_en else "")
                           + "ainda diz 'planned/planejado'")
    if phase_drift:
        findings.append(Finding(
            check=CHECK_ID, target="README.md / README.en.md",
            severity="drift",
            title="Fase de entrega por engine diverge entre PT e EN",
            body_md=(
                "O marcador de fase ``(AX)`` da célula de status não é o "
                "mesmo nos dois idiomas — típico de entrega registrada só "
                "na tradução de origem:\n\n" + "\n".join(phase_drift) +
                "\n\nSincronizar (verdade canônica: "
                "`contracts/engines/expected-engines.json`)."),
            fingerprint=f"{CHECK_ID}:readmes:fase-por-engine"))
    if planned:
        findings.append(Finding(
            check=CHECK_ID, target="README.md / README.en.md",
            severity="drift",
            title="Engine marcada como 'planned' no README",
            body_md=(
                "A matriz de engines está COMPLETA desde a 1.0.0 — nenhuma "
                "linha deveria dizer 'planned/planejado' (bug da auditoria "
                "A9: 9 engines Tier C ficaram 'planned (A3)' no EN depois "
                "de entregues):\n\n" + "\n".join(planned) +
                "\n\nTrocar pelo status entregue correspondente "
                "(entregue/delivered)."),
            fingerprint=f"{CHECK_ID}:readmes:status-planned"))

    num_diff = sorted(set(learn["pt_numbers"]) ^ set(learn["en_numbers"]))
    notes = (f"PT: {len(rows_pt)} engines / {len(learn['pt_numbers'])} "
             f"números-chave; EN: {len(rows_en)} engines / "
             f"{len(learn['en_numbers'])} números-chave")
    if num_diff:
        notes += (f"; diferença numérica PT/EN ({len(num_diff)}): "
                  f"{', '.join(num_diff[:12])}")
    return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                       ran=True, notes=notes)
