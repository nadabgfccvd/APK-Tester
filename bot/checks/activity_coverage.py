#!/usr/bin/env python3
"""bot/checks/activity_coverage.py — uma activity por engine (R2.1).

O AUDIT_ROADMAP_V2 (R2.1) exigiu a superfície contratual do flagship:
`contracts/flagship/manifest-audit.md` promete activities >= 30 com UMA
SONDA POR ENGINE (mesmo padrão do `locale_sync`: contrato x artefato
gerado, zero drift). O manifesto é GERADO por `tools/gen-flagship-manifest.py`
a partir da tabela ACTIVITIES — este cheque vigia a PROMESSA contra a
fonte de verdade executável:

1. todo engine de `contracts/engines/expected-engines.json` tem a activity
   correspondente declarada em
   `suites/flagship/app/src/main/AndroidManifest.xml` (classe
   `.engines.Engine<NN>*Activity` — mesmo número NN do engine);
2. nenhuma sonda declarada aponta para engine inexistente na answer key
   (renomear/remover engine sem regenerar o manifesto é regressão);
3. o total declarado atende o alvo contratual (>= 30).

Manifesto ausente ou ilegível é Finding "regression" (árvore quebrada —
o arquivo é commitado e gerado por selftest verde no CI). Leitura pura,
determinística; learn com contagens para diff no relatório.
"""

import json
import re
import sys
from pathlib import Path

CHECK_ID = "activity_coverage"

ACTIVITY_RE = re.compile(r'<activity(?![-\w])[^>]*android:name="([^"]+)"')
PROBE_RE = re.compile(r"^\.engines\.Engine(\d{2})[A-Za-z0-9]*Activity$")
MIN_ACTIVITIES = 30
MAX_DIFF_ROWS = 40

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: arvore bot/ sem pacote "bot"
    from lib.base import CheckResult, Finding


def _engine_numbers(repo: Path):
    """{NN: dir} da answer key; None se o contrato estiver ausente."""
    path = repo / "contracts/engines/expected-engines.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    out = {}
    for entry in data.get("engines", []):
        m = re.match(r"^engine-(\d{2})-", entry.get("dir", ""))
        if m:
            out[m.group(1)] = entry["dir"]
    return out


def _declared_probes(repo: Path):
    """{NN: classe} das sondas declaradas; None se manifesto ilegível."""
    path = repo / "suites/flagship/app/src/main/AndroidManifest.xml"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    out = {}
    for name in ACTIVITY_RE.findall(text):
        m = PROBE_RE.match(name)
        if m:
            out[m.group(1)] = name
    return out


def _ghost_probes(repo: Path, probes: dict):
    """Sondas declaradas SEM classe Java real no módulo :app.

    'Toda classe declarada existe no módulo :app' (lei A1 do manifest-);
    renomear a classe no Java sem regenerar o manifesto deixa sonda
    fantasma — o APK compila, a activity não abre.
    """
    src_root = repo / ("suites/flagship/app/src/main/java"
                       "/dev/apktester/behemoth/engines")
    ghosts = []
    for name in probes.values():
        cls = name.rsplit(".", 1)[-1]
        if not (src_root / f"{cls}.java").is_file():
            ghosts.append(name)
    return ghosts


def _cap(items, limit=MAX_DIFF_ROWS):
    shown = items[:limit]
    extra = len(items) - len(shown)
    suffix = (f"\n- … e mais {extra} (limitado a {limit} linhas)"
              if extra > 0 else "")
    return "\n".join(f"- {i}" for i in shown) + suffix


def run(ctx) -> CheckResult:
    repo = Path(ctx.repo_path).resolve()

    engines = _engine_numbers(repo)
    probes = _declared_probes(repo)

    if engines is None:
        return CheckResult(
            check=CHECK_ID, ran=True, findings=[Finding(
                check=CHECK_ID, target="expected-engines.json",
                severity="regression",
                title="answer key de engines ausente ou ilegível",
                body_md=(
                    "`contracts/engines/expected-engines.json` não pôde ser "
                    "lido — sem a fonte canônica a cobertura de activities "
                    "não é verificável (árvore fora do contrato)."),
                fingerprint=f"{CHECK_ID}:answer-key:ausente")],
            learn={}, ran_mode="state", notes="answer key ausente")

    if probes is None:
        return CheckResult(
            check=CHECK_ID, ran=True, findings=[Finding(
                check=CHECK_ID, target="AndroidManifest.xml",
                severity="regression",
                title="manifesto do flagship ausente ou sem sondas legíveis",
                body_md=(
                    "`suites/flagship/app/src/main/AndroidManifest.xml` não "
                    "pôde ser lido — é commitado e gerado por "
                    "`tools/gen-flagship-manifest.py` (selftest verde no "
                    "CI); ausência é árvore quebrada."),
                fingerprint=f"{CHECK_ID}:manifesto:ausente")],
            learn={}, ran_mode="state", notes="manifesto ausente")

    findings = []
    missing = [engines[nn] for nn in sorted(set(engines) - set(probes))]
    stray = [probes[nn] for nn in sorted(set(probes) - set(engines))]
    ghosts = _ghost_probes(repo, probes)

    if missing:
        findings.append(Finding(
            check=CHECK_ID, target="manifest-coverage", severity="regression",
            title=f"{len(missing)} engine(s) sem activity declarada",
            body_md=(
                "R2.1 (AUDIT_ROADMAP_V2): todo engine da answer key tem "
                "uma sonda `.engines.Engine<NN>*Activity` declarada no "
                "manifesto do flagship. Ausentes:\n\n"
                + _cap(missing) +
                "\n\nCorreção: regenerar com "
                "`python3 tools/gen-flagship-manifest.py` (a tabela "
                "ACTIVITIES é a fonte; zero drift por construção)."),
            fingerprint=f"{CHECK_ID}:manifesto:engine-sem-activity"))

    if stray:
        findings.append(Finding(
            check=CHECK_ID, target="manifest-coverage", severity="regression",
            title=f"{len(stray)} sonda(s) sem engine correspondente",
            body_md=(
                "Sondas `.engines.Engine<NN>*Activity` declaradas para "
                "números que NÃO existem na answer key "
                "(renomeação/remoção sem regenerar o manifesto):\n\n"
                + _cap(stray) +
                "\n\nCorreção: regenerar com "
                "`python3 tools/gen-flagship-manifest.py`."),
            fingerprint=f"{CHECK_ID}:manifesto:sonda-sem-engine"))

    if ghosts:
        findings.append(Finding(
            check=CHECK_ID, target="manifest-coverage", severity="regression",
            title=f"{len(ghosts)} sonda(s) sem classe Java no módulo :app",
            body_md=(
                "Lei A1 (manifest-as-truth): toda classe declarada existe "
                "no módulo :app. Sondas fantasma (o manifesto aponta para "
                "classe Java inexistente em "
                "app/src/main/java/dev/apktester/behemoth/engines/):\n\n"
                + _cap(ghosts) +
                "\n\nCorreção: regenerar com "
                "`python3 tools/gen-flagship-manifest.py`."),
            fingerprint=f"{CHECK_ID}:manifesto:sonda-fantasma"))

    total = len(ACTIVITY_RE.findall(
        (repo / "suites/flagship/app/src/main/AndroidManifest.xml")
        .read_text(encoding="utf-8")))
    if total < MIN_ACTIVITIES:
        findings.append(Finding(
            check=CHECK_ID, target="manifest-coverage", severity="drift",
            title=f"activities declaradas ({total}) abaixo do alvo contratual",
            body_md=(
                f"`contracts/flagship/manifest-audit.md` promete activities "
                f">= {MIN_ACTIVITIES}; o manifesto declara {total}. "
                "Superfície contratual do flagship (R2.1)."),
            fingerprint=f"{CHECK_ID}:manifesto:abaixo-do-alvo"))

    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn={
            "engines_na_answer_key": len(engines),
            "sondas_declaradas": len(probes),
            "activities_totais": total,
            "cobertura_completa": not missing and not stray,
        },
        ran=True,
        learn_mode="immediate",
        notes=(f"{len(probes)} sondas x {len(engines)} engines; "
               f"{total} activities no manifesto"),
    )
