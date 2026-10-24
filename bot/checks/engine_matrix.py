#!/usr/bin/env python3
"""bot/checks/engine_matrix.py — consistência ESTRICTA entre todas as fontes
da matriz de engines.

O CI valida apenas o JSON do contrato. O APKBot cruza TODAS as fontes que
declaram a matriz — drift entre docs e contratos é exatamente o que apodrece
com o tempo:

- Fonte A: contracts/engines/expected-engines.json (dirs; 32 esperados).
  Também valida as chaves obrigatórias de cada entrada (id, dir, language,
  tier, build, rustydroid_engines, detector_artifacts, notes) — entrada
  incompleta vira Finding "regression" ...:{dir}:contrato-incompleto.
- Fonte B: contracts/suites.json — suítes com "apk" sob suites/engines/<dir>.
- Fonte C: docs/src/engine-matrix.md — linhas de tabela '|' contendo
  'engine-', token `engine-\\d+-[a-z0-9-]+` via regex.
- Fonte D: README.md — mesma extração na tabela da matriz.
- Fonte E: diretórios reais em suites/engines/engine-* (pode ser vazio em A0).

Comparações estritas (cada divergência = Finding "regression"
...:{onde}:divergencia com tabela diff PT-BR no corpo): A==B==C==D.
E deve estar CONTIDO em A: diretórios do contrato ausentes no disco são
ESPERADOS até A3/A4/A7 e viram UM ÚNICO Finding "info"
(...:suites:pendentes-fase); diretórios no disco FORA do contrato são
regressão. Sanidade extra: len(suites.json) >= len(A).

learn: {"engines": sorted(A), "count": len(A), "docs_synced": bool}.
Leitura pura — nada é escrito no repositório.
"""

import json
import re
import sys
from pathlib import Path

CHECK_ID = "engine_matrix"

REQUIRED_KEYS = ("id", "dir", "language", "tier", "build",
                 "rustydroid_engines", "detector_artifacts", "notes")
ENGINE_DIR_RE = re.compile(r"engine-\d+-[a-z0-9-]+")
ENGINES_APK_PREFIX = "suites/engines/"
MAX_DIFF_ROWS = 40

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _load_json(path: Path):
    """Conteúdo parseado, None se ausente/ilegível."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_text(path: Path):
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _md_engine_dirs(text: str) -> set:
    """Tokens `engine-NN-slug` em linhas de tabela '|' (1º token por linha)."""
    dirs = set()
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("|") and "engine-" in line:
            match = ENGINE_DIR_RE.search(line)
            if match:
                dirs.add(match.group(0))
    return dirs


def _divergencia(repo_rel: str, where: str, name_a: str, set_a: set,
                 name_b: str, set_b: set) -> Finding:
    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)
    rows = [f"| `{d}` | sim | — |" for d in only_a]
    rows += [f"| `{d}` | — | sim |" for d in only_b]
    shown = rows[:MAX_DIFF_ROWS]
    extra = ""
    if len(rows) > MAX_DIFF_ROWS:
        extra = f"\n\n… e mais {len(rows) - MAX_DIFF_ROWS} linha(s)."
    return Finding(
        check=CHECK_ID, target=where, severity="regression",
        title=f"divergência de matriz de engines: {name_a} vs {name_b}",
        body_md=(
            f"As fontes `{name_a}` e `{name_b}` declaram conjuntos de "
            "diretórios de engines DIFERENTES.\n\n"
            f"- presentes só em `{name_a}`: {len(only_a)}\n"
            f"- presentes só em `{name_b}`: {len(only_b)}\n\n"
            "| Diretório | " + name_a + " | " + name_b + " |\n"
            "|---|---|---|\n" + "\n".join(shown) + extra +
            "\n\nAs quatro fontes (contrato, suites.json, matriz nos docs e "
            "README) devem listar EXATAMENTE os mesmos diretórios: o contrato "
            "é a answer key do `rd engine detect` e o CI valida só o JSON — "
            "drift entre documentos é o que apodrece sem este cheque."),
        fingerprint=f"{CHECK_ID}:{where}:divergencia")


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    repo = Path(ctx.repo_path).resolve()
    findings = []

    # ---- Fonte A: contrato canônico ---------------------------------------
    contract = _load_json(repo / "contracts" / "engines"
                          / "expected-engines.json")
    contract_ok = contract is not None
    entries = []
    set_a = set()
    if contract is None:
        findings.append(Finding(
            check=CHECK_ID, target="contrato", severity="regression",
            title="contracts/engines/expected-engines.json ausente ou ilegível",
            body_md=(
                "A answer key `contracts/engines/expected-engines.json` não "
                "existe ou não é JSON válido. Sem ela não há gabarito para o "
                "`rd engine detect`, o compat-nightly nem para este cheque "
                "multi-fonte."),
            fingerprint=f"{CHECK_ID}:contrato:contrato-ausente"))
    else:
        entries = contract.get("engines") or []
        if not isinstance(entries, list):
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            edir = entry.get("dir")
            missing = [key for key in REQUIRED_KEYS if key not in entry]
            if missing:
                target = str(edir or entry.get("id") or "entrada-sem-dir")
                findings.append(Finding(
                    check=CHECK_ID, target=target, severity="regression",
                    title=f"contrato incompleto: {target}",
                    body_md=(
                        f"Entrada `{target}` de "
                        "`contracts/engines/expected-engines.json` está "
                        "incompleta.\n\n"
                        f"- chaves ausentes: {', '.join(missing)}\n"
                        "- chaves exigidas em toda entrada: "
                        + ", ".join(REQUIRED_KEYS) +
                        "\n\nO contrato é a answer key do detector; entrada "
                        "incompleta quebra o diff numérico e o "
                        "compat-nightly."),
                    fingerprint=f"{CHECK_ID}:{target}:contrato-incompleto"))
            if isinstance(edir, str) and edir:
                set_a.add(edir)

    # ---- Fonte B: suites.json ---------------------------------------------
    suites_data = _load_json(repo / "contracts" / "suites.json")
    suites_ok = suites_data is not None
    suites = []
    set_b = set()
    if suites_data is not None:
        suites = suites_data.get("suites") or []
        if not isinstance(suites, list):
            suites = []
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            apk = str(suite.get("apk") or "")
            if apk.startswith(ENGINES_APK_PREFIX):
                engine_dir = apk[len(ENGINES_APK_PREFIX):].strip("/")
                if engine_dir:
                    set_b.add(engine_dir)
    else:
        findings.append(Finding(
            check=CHECK_ID, target="suites-json", severity="regression",
            title="contracts/suites.json ausente ou ilegível",
            body_md=(
                "`contracts/suites.json` não existe ou não é JSON válido. "
                "As suítes run_scenario são a fonte B da matriz; sem elas o "
                "`rustydroid test contracts/suites.json` perde o gabarito."),
            fingerprint=f"{CHECK_ID}:suites-json:contrato-ausente"))

    # ---- Fontes C e D: docs e README --------------------------------------
    docs_text = _read_text(repo / "docs" / "src" / "engine-matrix.md")
    set_c = None
    if docs_text is None:
        findings.append(Finding(
            check=CHECK_ID, target="docs-engine-matrix", severity="regression",
            title="docs/src/engine-matrix.md ausente",
            body_md=(
                "A matriz de engines nos docs mdBook não existe. É a fonte C "
                "da matriz e o espelho público do registry do RustyDroid "
                "(Apêndice G)."),
            fingerprint=f"{CHECK_ID}:docs-engine-matrix:doc-ausente"))
    else:
        set_c = _md_engine_dirs(docs_text)

    readme_text = _read_text(repo / "README.md")
    set_d = None
    if readme_text is None:
        findings.append(Finding(
            check=CHECK_ID, target="readme", severity="regression",
            title="README.md ausente",
            body_md=(
                "O README principal não existe. É a fonte D da matriz "
                "(tabela de engines) e a porta de entrada do repositório."),
            fingerprint=f"{CHECK_ID}:readme:doc-ausente"))
    else:
        set_d = _md_engine_dirs(readme_text)

    # ---- Fonte E: discos reais --------------------------------------------
    engines_root = repo / "suites" / "engines"
    set_e = set()
    if engines_root.is_dir():
        set_e = {p.name for p in engines_root.glob("engine-*") if p.is_dir()}

    # ---- Comparações estritas A == B == C == D ----------------------------
    if contract_ok and suites_ok and set_a != set_b:
        findings.append(_divergencia(
            "contracts/engines/expected-engines.json", "suites-json",
            "expected-engines.json", set_a, "contracts/suites.json", set_b))
    if contract_ok and set_c is not None and set_a != set_c:
        findings.append(_divergencia(
            "docs-engine-matrix", "docs-engine-matrix",
            "expected-engines.json", set_a, "docs/src/engine-matrix.md",
            set_c))
    if contract_ok and set_d is not None and set_a != set_d:
        findings.append(_divergencia(
            "readme", "readme",
            "expected-engines.json", set_a, "README.md", set_d))

    # ---- E deve estar contido em A ----------------------------------------
    extras = set_e - set_a
    if extras:
        findings.append(_divergencia(
            "suites-engines-disk", "suites-engines-disk",
            "suites/engines/ no disco", set_e,
            "expected-engines.json", set_a))
    pending = sorted(set_a - set_e)
    if pending:
        shown = ", ".join(f"`{d}`" for d in pending)
        findings.append(Finding(
            check=CHECK_ID, target="suites", severity="info",
            title=f"{len(pending)} engine dir(s) ainda sem fixture no disco",
            body_md=(
                "Diretórios declarados no contrato que AINDA não existem em "
                "`suites/engines/`:\n\n" + shown +
                "\n\nIsto é ESPERADO até as fases de preenchimento: fixtures "
                "Tier C chegam em A3, builds Tier A em A4 e Tier B em A7. "
                "Registro único para acompanhar o preenchimento da matriz — "
                "não é regressão; vira regressão apenas o caminho inverso "
                "(diretório no disco fora do contrato)."),
            fingerprint=f"{CHECK_ID}:suites:pendentes-fase"))

    # ---- Sanidade de contagem de suítes ------------------------------------
    if suites_ok and set_a:
        if len(suites) < len(set_a):
            findings.append(Finding(
                check=CHECK_ID, target="suites-json", severity="regression",
                title="suites.json com menos suítes que engines no contrato",
                body_md=(
                    f"`contracts/suites.json` declara {len(suites)} suíte(s), "
                    f"mas o contrato de engines lista {len(set_a)} diretório"
                    "(s). Cada engine precisa de ao menos uma suíte "
                    "run_scenario — suítes faltantes deixam engines sem "
                    "gabarito executável."),
                fingerprint=f"{CHECK_ID}:suites-json:contagem-insuficiente"))

    docs_synced = bool(
        contract_ok and suites_ok and set_a
        and not any(f.severity == "regression" for f in findings))
    learn = {
        "engines": sorted(set_a),
        "count": len(set_a),
        "docs_synced": docs_synced,
    }
    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn=learn,
        ran=True,
        notes=("fontes: contrato={0} suites={1} docs={2} readme={3} "
               "disco={4}".format(
                   len(set_a), len(set_b),
                   len(set_c) if set_c is not None else -1,
                   len(set_d) if set_d is not None else -1,
                   len(set_e))),
    )
