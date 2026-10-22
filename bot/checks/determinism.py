#!/usr/bin/env python3
"""bot/checks/determinism.py — sonda de determinismo entre-execuções E entre-tempos.

O CI (tools/verify-deterministic.sh) compara apenas DUAS execuções na MESMA
máquina, no MESMO commit, no MESMO ambiente. O APKBot cobre o que o CI não vê:

1. AGORA — roda cada tools/gen-*.py N vezes (cfg.determinism_runs, padrão 2)
   com o seed padrão (20261022) em diretórios mktemp frescos e compara os
   sha256 por artefato declarados no manifest.json de cada execução.
   Divergência entre duas execuções IMEDIATAS = não-determinismo agora
   (Finding "regression" ...:nao-deterministico-agora).

2. ENTRE-TEMPOS — consolida o mapa {caminho: sha256} das execuções e compara
   contra o baseline em ctx.state.baselines.determinism.{tool}. Se divergir:
   - commit de tools/{tool}.py mudou desde o baseline (via `git log -1`) =>
     Finding "new" ...:saida-mudou-fonte-mudou (evolução esperada; o learn
     carrega os novos artefatos + o novo commit, e SÓ o dispatcher confirma
     o merge do baseline);
   - commit INTACTO mas saída mudou => Finding "regression"
     ...:saida-mudou-sem-mudanca-de-fonte — creep de ambiente: outra versão
     de Python/stdlib alterando bytes de fixture em silêncio.
     Lei do repositório: geradores devem ser byte-estáveis entre execuções E
     entre ambientes (docs/src/adr/adr-0001-geradores-python-stdlib.md).

Primeira execução (sem baseline): nenhum finding de drift, apenas learn.
Ferramenta sem manifest.json legível após a execução: Finding "info" por
ferramenta (...:sem-manifest-json) e pulada (sem comparação, sem learn).

Nada é escrito no repositório: tudo em mktemp sob /tmp com limpeza em
finally. Timeout de 120s por subprocesso; timeout vira Finding
(...:gerador-travou). Os args de redução de carga replicam 1:1 o mapa
canônico de tools/verify-deterministic.sh (não alteram o determinismo do
seed — apenas encolhem o workload), e são FIXOS neste módulo para que o
mapa de artefatos permaneça comparável entre execuções do bot.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECK_ID = "determinism"

DEFAULT_SEED = 20261022
SUBPROCESS_TIMEOUT_S = 120
GIT_TIMEOUT_S = 30
MAX_DIFF_ROWS = 15

# Mesmos args canônicos de tools/verify-deterministic.sh (chave = stem da
# ferramenta). Fixos de propósito: mudar aqui invalida baselines antigos.
TURBO_ARGS = {
    "gen-textures": ("--size", "64"),
    "gen-meshes": ("--terrain-res", "32", "--crowd", "200",
                   "--profile-samples", "3", "--radial", "8"),
    "gen-buttons": ("--buttons", "32", "--icons", "16"),
    "gen-strings": ("--buttons", "32"),
}

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _decode(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _tail(text: str, lines: int = 10) -> str:
    chunks = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not chunks:
        return "(sem saída de erro)"
    return "\n".join("    " + ln for ln in chunks[-lines:])


def _git_commit(repo: Path, relpath: str):
    """Último commit que tocou o arquivo (None se git indisponível)."""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", relpath],
            cwd=str(repo), timeout=GIT_TIMEOUT_S,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    return sha or None


def _collect_artifacts(out_dir: Path):
    """Mapa {caminho: sha256} consolidando TODOS os manifest.json da saída.

    Alguns geradores gravam em <out>/manifest.json, outros em subpastas
    (gen-audio => audio/manifest.json, gen-textures => textures/manifest.json).
    Retorna None se nenhum manifest legível declarar artefatos.
    """
    manifests = sorted(Path(out_dir).rglob("manifest.json"),
                       key=lambda p: (len(p.parts), str(p)))
    amap = {}
    for mpath in manifests:
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries = data.get("artifacts") or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path, sha = entry.get("path"), entry.get("sha256")
            if isinstance(path, str) and isinstance(sha, str):
                amap[path] = sha
    return amap or None


def _diff_rows(base_map: dict, other_map: dict) -> list:
    rows = []
    for path in sorted(set(base_map) | set(other_map)):
        if base_map.get(path) != other_map.get(path):
            rows.append((path, base_map.get(path, "—"), other_map.get(path, "—")))
    return rows


def _fmt_table(header: str, rows: list, sep: str = "|---|---|---|") -> str:
    if not rows:
        return "(sem linhas)"
    body = "\n".join("| {} | {} | {} |".format(*r) for r in rows)
    return f"| {header} |\n{sep}\n{body}"


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    cfg = dict(ctx.cfg or {})
    state = dict(ctx.state or {})
    repo = Path(ctx.repo_path).resolve()
    runs_n = max(1, int(cfg.get("determinism_runs") or 2))

    baselines = (state.get("baselines") or {}).get(CHECK_ID) or {}
    # Tolerante aos dois formatos de armazenamento do dispatcher:
    # {"tools": {tool: {...}}} (learn cru) ou {tool: {...}} (achatado).
    base_tools = baselines.get("tools") if isinstance(baselines, dict) else None
    if not isinstance(base_tools, dict):
        base_tools = baselines if isinstance(baselines, dict) else {}

    tools = sorted((repo / "tools").glob("gen-*.py"))
    if not tools:
        return CheckResult(
            check=CHECK_ID, findings=[], learn={"tools": {}}, ran=True,
            notes="nenhum tools/gen-*.py encontrado — nada a sondar")

    findings = []
    learn_tools = {}
    n_baseline = 0

    for tool in tools:
        tname = tool.stem                      # ex.: "gen-strings"
        run_maps = []
        tmp_dirs = []
        tool_commit = _git_commit(repo, f"tools/{tname}.py")
        try:
            aborted = False
            for _ in range(runs_n):
                out_dir = tempfile.mkdtemp(prefix=f"apkbot-det-{tname}-")
                tmp_dirs.append(out_dir)
                argv = [sys.executable, str(tool), "--out", out_dir,
                        "--seed", str(DEFAULT_SEED)]
                argv.extend(TURBO_ARGS.get(tname, ()))
                try:
                    proc = subprocess.run(
                        argv, cwd=str(repo), timeout=SUBPROCESS_TIMEOUT_S,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                except subprocess.TimeoutExpired:
                    findings.append(Finding(
                        check=CHECK_ID, target=tname, severity="regression",
                        title=f"gerador travou: {tname}",
                        body_md=(
                            f"`tools/{tname}.py` excedeu o timeout de "
                            f"{SUBPROCESS_TIMEOUT_S}s ao gerar saída com o seed "
                            f"padrão {DEFAULT_SEED}.\n\n"
                            "Um gerador determinístico deve terminar em segundos "
                            "com a carga reduzida do bot; travar agora indica "
                            "regressão (loop infinito, espera de rede, "
                            "dependência interativa). Corrija antes de confiar "
                            "nos fixtures."),
                        fingerprint=f"{CHECK_ID}:{tname}:gerador-travou"))
                    aborted = True
                    break
                if proc.returncode != 0:
                    findings.append(Finding(
                        check=CHECK_ID, target=tname, severity="regression",
                        title=f"gerador falhou na execução: {tname}",
                        body_md=(
                            f"`tools/{tname}.py` saiu com código "
                            f"{proc.returncode} (seed {DEFAULT_SEED}).\n\n"
                            "Cauda do stderr:\n\n" + _tail(_decode(proc.stderr)) +
                            "\n\nSem execução bem-sucedida não há manifest.json "
                            "para comparar — a ferramenta fica fora do learn "
                            "desta passada."),
                        fingerprint=f"{CHECK_ID}:{tname}:falha-na-execucao"))
                    aborted = True
                    break
                amap = _collect_artifacts(Path(out_dir))
                if amap is None:
                    findings.append(Finding(
                        check=CHECK_ID, target=tname, severity="info",
                        title=f"sem manifest.json: {tname}",
                        body_md=(
                            "Após a execução com o seed padrão, nenhum "
                            "`manifest.json` legível (com entradas em "
                            "`artifacts`) foi encontrado na saída.\n\n"
                            "Convenção do repositório: todo gen-*.py grava um "
                            "manifest.json com sha256 por artefato. A ferramenta "
                            "é pulada nesta passada (sem comparação, sem learn)."),
                        fingerprint=f"{CHECK_ID}:{tname}:sem-manifest-json"))
                    aborted = True
                    break
                run_maps.append(amap)

            if aborted or not run_maps:
                continue

            # 1) não-determinismo AGORA (entre execuções imediatas)
            if len(run_maps) >= 2:
                first = run_maps[0]
                all_rows = []
                for idx, other in enumerate(run_maps[1:], start=2):
                    all_rows.extend(
                        (p, a, f"exec {idx}: {b}") for p, a, b in
                        _diff_rows(first, other))
                if all_rows:
                    shown = all_rows[:MAX_DIFF_ROWS]
                    shown = [(p, a, b) for p, a, b in shown]
                    findings.append(Finding(
                        check=CHECK_ID, target=tname, severity="regression",
                        title=f"não-determinístico agora: {tname}",
                        body_md=(
                            "**Lei do repositório:** mesmo seed => mesmos bytes. "
                            f"Duas execuções IMEDIATAS de `tools/{tname}.py` "
                            f"(seed {DEFAULT_SEED}) produziram saídas diferentes "
                            "— isto é não-determinismo no ambiente atual, não "
                            "drift de ambiente entre tempos.\n\n" +
                            _fmt_table("Artefato | sha256 exec 1 | sha256 exec 2",
                                       shown) +
                            f"\n\nTotal: {len(all_rows)} divergência(s) entre "
                            f"{len(run_maps)} execuções."
                            + (" (lista truncada)" if len(all_rows) > MAX_DIFF_ROWS else "")),
                        fingerprint=f"{CHECK_ID}:{tname}:nao-deterministico-agora"))

            # mapa consolidado para o learn e para a comparação entre-tempos
            merged = dict(run_maps[0])
            for other in run_maps[1:]:
                merged.update(other)

            # 2) drift ENTRE-TEMPOS contra o baseline
            base = base_tools.get(tname) if isinstance(base_tools, dict) else None
            if isinstance(base, dict):
                base_artifacts = base.get("artifacts")
                if isinstance(base_artifacts, dict) and base_artifacts:
                    n_baseline += 1
                    if base_artifacts != merged:
                        rows = _diff_rows(base_artifacts, merged)
                        shown = [(p, a, b) for p, a, b in rows[:MAX_DIFF_ROWS]]
                        base_commit = base.get("tool_commit")
                        source_changed = bool(
                            tool_commit and base_commit
                            and tool_commit != base_commit)
                        if source_changed:
                            findings.append(Finding(
                                check=CHECK_ID, target=tname, severity="new",
                                title=f"saída mudou com mudança de fonte: {tname}",
                                body_md=(
                                    "A saída do gerador divergiu do baseline, "
                                    "MAS a fonte da ferramenta também mudou — "
                                    "evolução esperada, não regressão.\n\n"
                                    f"- commit no baseline: `{base_commit}`\n"
                                    f"- commit atual de `tools/{tname}.py`: "
                                    f"`{tool_commit}`\n"
                                    f"- artefatos divergentes: {len(rows)} de "
                                    f"{len(merged)}\n\n" +
                                    _fmt_table("Artefato | baseline | atual",
                                               shown) +
                                    "\n\nO learn desta passada carrega os novos "
                                    "artefatos e o novo commit; só o dispatcher "
                                    "confirma o merge do baseline."),
                                fingerprint=(
                                    f"{CHECK_ID}:{tname}:saida-mudou-fonte-mudou")))
                        else:
                            caveat = ""
                            if not tool_commit or not base_commit:
                                caveat = ("\n\nAtenção: não foi possível confirmar "
                                          "o commit atual via git — trate como "
                                          "regressão até verificação manual.\n")
                            findings.append(Finding(
                                check=CHECK_ID, target=tname, severity="regression",
                                title=("saída mudou sem mudança de fonte: "
                                       + tname),
                                body_md=(
                                    "**Lei:** geradores devem ser byte-estáveis "
                                    "entre execuções E entre ambientes "
                                    "(docs/src/adr/adr-0001-geradores-python-"
                                    "stdlib.md).\n\n"
                                    f"A saída de `tools/{tname}.py` divergiu do "
                                    "baseline sem NENHUMA mudança na fonte "
                                    f"(commit da ferramenta inalterado: "
                                    f"`{base_commit or 'desconhecido'}`). Causa "
                                    "provável: creep de ambiente — outra versão "
                                    "de Python/stdlib alterando silenciosamente "
                                    "os bytes dos fixtures.\n" + caveat + "\n" +
                                    _fmt_table("Artefato | baseline | atual",
                                               shown) +
                                    f"\n\nTotal: {len(rows)} divergência(s) de "
                                    f"{len(merged)} artefatos."),
                                fingerprint=(
                                    f"{CHECK_ID}:{tname}:"
                                    "saida-mudou-sem-mudanca-de-fonte")))

            learn_tools[tname] = {
                "artifacts": merged,
                "tool_commit": tool_commit,
            }
        finally:
            for d in tmp_dirs:
                shutil.rmtree(d, ignore_errors=True)

    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn={"tools": learn_tools},
        ran=True,
        notes=(f"{len(tools)} gerador(es) sondado(s) x{runs_n} execução(ões) "
               f"(seed {DEFAULT_SEED}); {n_baseline} com baseline entre-tempos; "
               f"{len(learn_tools)} com learn confirmável"),
    )
