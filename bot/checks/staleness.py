#!/usr/bin/env python3
"""bot/checks/staleness.py — higiene do repositório que o CI ignora.

Três regras locais, todas read-only:

1. Links relativos mortos em *.md (repo inteiro, pulando node_modules,
   .git e docs/book): extrai links markdown [texto](alvo) e refs de imagem
   com caminho RELATIVO (ignora http/https/#/mailto/absolutos), resolve
   contra o diretório do arquivo e reporta alvo inexistente — um Finding
   "drift" por arquivo (...:{arquivo}:link-morto). Docs que apodrecem são
   o clássico que nenhum CI valida.

2. Marcadores de dívida TODO/FIXME/XXX/WORKAROUND em arquivos de texto
   rastreados (.py .sh .md .yml .yaml .json .toml, pulando .git,
   __pycache__ e node_modules): UM ÚNICO Finding "info"
   (...:todos:resumo) com contagens por marcador e lista arquivo:linha
   (máx. 30 linhas). A fonte do próprio checker (bot/checks/) fica fora
   desta varredura: ela precisa conter os nomes dos marcadores por
   definição, e auto-reportar-se a cada run seria falso positivo
   permanente.

3. Deriva de agendamento: se ctx.state.runs não está vazio e a última
   execução (state.runs[-1]["date"]) é mais antiga que 3 dias a partir de
   ctx.now, Finding "info" (...:schedule:ultima-execucao) — o bot deixou
   de rodar no ritmo esperado. (A regra de idade do baseline determinism
   foi descartada por falta de cfg.stale_days no esquema atual.)

Nenhuma escrita no repositório.
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHECK_ID = "staleness"

STALE_RUN_DAYS = 3
MAX_LINK_ROWS = 20
MAX_TODO_LINES = 30
MAX_SNIPPET_CHARS = 120

# Pastas sempre ignoradas nas varreduras ("book" cobre docs/book, gerado).
WALK_SKIP = {".git", "node_modules", "__pycache__", "book"}
# A fonte do próprio checker contém os nomes dos marcadores por definição
# (regex/constantes/docstring) — auto-referência não é dívida.
TODO_SKIP_RELS = ("bot/checks/",)
# Extensões rastreadas para a varredura de marcadores.
TODO_EXTS = {".py", ".sh", ".md", ".yml", ".yaml", ".json", ".toml"}

_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|WORKAROUND)\b")
_MARKERS = ("TODO", "FIXME", "XXX", "WORKAROUND")

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _walk_files(repo: Path):
    """Todos os arquivos do repo, podando as pastas ignoradas."""
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in WALK_SKIP)
        base = Path(root)
        for name in sorted(files):
            yield base / name


def _is_external(target: str) -> bool:
    low = target.lower()
    if low.startswith("mailto:"):
        return True
    if "://" in target:
        return True
    return False


def _broken_links(md_path: Path) -> list:
    """[(linha, alvo)] de links markdown relativos sem destino no disco."""
    broken = []
    seen = set()
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return broken
    for lineno, line in enumerate(text.splitlines(), 1):
        for raw in _MD_LINK_RE.findall(line):
            target = raw.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            target = target.split()[0] if target.split() else ""
            if not target or target.startswith("#") or target.startswith("/"):
                continue  # âncora pura / caminho absoluto: fora do escopo
            if _is_external(target):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue  # link apenas com âncora no mesmo arquivo
            resolved = md_path.parent / path_part
            if not resolved.exists() and (lineno, target) not in seen:
                seen.add((lineno, target))
                broken.append((lineno, target))
    return broken


def _parse_iso(value):
    """datetime com fuso (assumindo UTC quando naive) ou None."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    state = dict(ctx.state or {})
    repo = Path(ctx.repo_path).resolve()

    findings = []
    n_md = 0
    n_broken_files = 0
    todo_hits = []          # (rel, linha, snippet)
    todo_counts = {m: 0 for m in _MARKERS}
    n_todo_files = 0

    for path in _walk_files(repo):
        rel = path.relative_to(repo).as_posix()
        ext = path.suffix.lower()

        if ext == ".md":
            n_md += 1
            broken = _broken_links(path)
            if broken:
                n_broken_files += 1
                rows = [(str(ln), tgt) for ln, tgt in broken[:MAX_LINK_ROWS]]
                extra = ""
                if len(broken) > MAX_LINK_ROWS:
                    extra = (f"\n\n… e mais {len(broken) - MAX_LINK_ROWS} "
                             "link(s) morto(s) neste arquivo.")
                findings.append(Finding(
                    check=CHECK_ID, target=rel, severity="drift",
                    title=f"links mortos: {rel}",
                    body_md=(
                        f"{len(broken)} link(s) markdown relativo(s) sem "
                        f"destino no disco em `{rel}`.\n\n"
                        "| Linha | Alvo quebrado |\n|---|---|\n" +
                        "\n".join(f"| {a} | `{b}` |" for a, b in rows) +
                        extra +
                        "\n\nLinks http/https/mailto/âncoras e caminhos "
                        "absolutos são ignorados; alvos relativos são "
                        "resolvidos a partir do diretório do arquivo. Docs "
                        "apodrecem silenciosamente — conserte ou remova o "
                        "alvo."),
                    fingerprint=f"{CHECK_ID}:{rel}:link-morto"))

        if ext in TODO_EXTS and not rel.startswith(TODO_SKIP_RELS):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            file_hits = 0
            for lineno, line in enumerate(text.splitlines(), 1):
                matches = _TODO_RE.findall(line)
                if not matches:
                    continue
                snippet = line.strip()[:MAX_SNIPPET_CHARS]
                todo_hits.append((rel, lineno, snippet))
                for marker in matches:
                    todo_counts[marker] += 1
                file_hits += len(matches)
            if file_hits:
                n_todo_files += 1

    total_todos = sum(todo_counts.values())
    todo_lines = [
        f"- `{rel}:{lineno}`: {snippet}"
        for rel, lineno, snippet in todo_hits[:MAX_TODO_LINES]
    ]
    todo_extra = ""
    if len(todo_hits) > MAX_TODO_LINES:
        todo_extra = (f"\n\n… e mais {len(todo_hits) - MAX_TODO_LINES} "
                      "ocorrência(s) não listadas.")
    findings.append(Finding(
        check=CHECK_ID, target="todos", severity="info",
        title="marcadores de dívida (TODO/FIXME/XXX/WORKAROUND)",
        body_md=(
            "Varredura de marcadores de dívida em arquivos de texto "
            "rastreados (.py .sh .md .yml .yaml .json .toml), pulando "
            ".git, __pycache__ e node_modules (e a fonte do próprio "
            "checker em bot/checks/, que contém os nomes dos marcadores "
            "por definição).\n\n"
            f"- TOTAL: {total_todos} ocorrência(s) em {n_todo_files} "
            f"arquivo(s)\n"
            f"- TODO: {todo_counts['TODO']} | FIXME: {todo_counts['FIXME']} "
            f"| XXX: {todo_counts['XXX']} | WORKAROUND: "
            f"{todo_counts['WORKAROUND']}\n\n" +
            ("Primeiras ocorrências (máx. 30):\n\n" + "\n".join(todo_lines)
             if todo_lines else "Nenhum marcador encontrado — worktree limpo.")
            + todo_extra),
        fingerprint=f"{CHECK_ID}:todos:resumo"))

    # Deriva de agendamento: última execução do bot registrada no estado.
    runs = state.get("runs")
    if isinstance(runs, list) and runs:
        last = runs[-1]
        date_val = last.get("date") if isinstance(last, dict) else None
        last_dt = _parse_iso(date_val)
        now_dt = _parse_iso(getattr(ctx, "now", None)) or datetime.now(timezone.utc)
        if last_dt and now_dt:
            delta = now_dt - last_dt
            if delta > timedelta(days=STALE_RUN_DAYS):
                findings.append(Finding(
                    check=CHECK_ID, target="schedule", severity="info",
                    title=f"bot sem executar há {delta.days} dias",
                    body_md=(
                        "A última execução registrada do bot foi em "
                        f"`{date_val}` — há {delta.days} dias (limiar: "
                        f"{STALE_RUN_DAYS} dias).\n\n"
                        "A cadência de execução derivou do previsto: com o "
                        "bot parado, regressões de determinismo, flakes e "
                        "drift de docs/contratos passam sem detecção. "
                        "Dispare uma passada do APKBot para reancorar a "
                        "linha do tempo."),
                    fingerprint=f"{CHECK_ID}:schedule:ultima-execucao"))

    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn={},
        ran=True,
        notes=(f"{n_md} arquivo(s) .md varrido(s); {n_broken_files} com links "
               f"mortos; {total_todos} marcador(es) de dívida; "
               "regra de idade de baseline descartada (sem cfg.stale_days)"),
    )
