#!/usr/bin/env python3
"""bot/checks/flakiness.py — detecção PROBABILÍSTICA de flakes locais.

Um único passe de CI não enxerga flake: ele vê verde (ou vermelho) uma vez.
Este cheque repete cada auto-teste cfg.flake_runs vezes (padrão 3) e analisa:

1. Instabilidade de resultado — qualquer FAIL em qualquer repetição vira
   Finding "regression" ...:selftest-instavel (lista quais repetições
   falharam + cauda do stderr). Um selftest que passa às vezes e falha
   outras é o candidato clássico de flake probabilístico.

2. Oscilação de latência — média + CV (desvio-padrao populacional / média)
   das durações; CV acima de cfg.flake_cv_threshold (padrão 0.5) vira
   Finding "flaky" ...:latencia-oscilante com os números na mão. As durações
   vão para o learn ({"targets": {...}}); a tendência entre runs
   (flap_history) é responsabilidade do dispatcher.

Alvos: todos os tools/gen-*.py --selftest, tools/fixture-pack.py --selftest
e tools/fixture-pack.py --dry-run (equivalente leve com saída em /tmp).

Limitação HONESTA: scripts/compat-nightly.sh é PULADO — ele escreve
docs/compat-matrix.md DENTRO do repositório, e o APKBot nunca modifica o
worktree (contornar exigiria clone/worktree temporário, custo alto para um
cheque local). O registro vai para o learn e um Finding "info" único
documenta a lacuna; a cobertura real fica no job engines-nightly (CI).

Nada é escrito no repositório: saídas efêmeras em mktemp sob /tmp com
limpeza em finally; timeout de 120s por subprocesso (timeout conta como
FAIL da repetição).
"""

import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHECK_ID = "flakiness"

SUBPROCESS_TIMEOUT_S = 120
DEFAULT_FLAKE_RUNS = 3
DEFAULT_CV_THRESHOLD = 0.5
STDERR_TAIL_LINES = 10

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


def _tail(text: str, lines: int = STDERR_TAIL_LINES) -> str:
    chunks = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not chunks:
        return "(sem saída de erro)"
    return "\n".join("    " + ln for ln in chunks[-lines:])


def _build_targets(repo: Path) -> list:
    """[(target, argv, needs_out)] — argv sem --out quando needs_out."""
    targets = []
    for tool in sorted((repo / "tools").glob("gen-*.py")):
        targets.append((tool.stem,
                        [sys.executable, str(tool), "--selftest"], False))
    fp = repo / "tools" / "fixture-pack.py"
    if fp.exists():
        targets.append(("fixture-pack:selftest",
                        [sys.executable, str(fp), "--selftest"], False))
        # Equivalente leve: plano JSON do modo canônico minSdk9, --out em /tmp.
        targets.append(("fixture-pack:dry-run",
                        [sys.executable, str(fp), "--fixture", "minSdk9",
                         "--dry-run"], True))
    return targets


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    cfg = dict(ctx.cfg or {})
    repo = Path(ctx.repo_path).resolve()
    reps = max(1, int(cfg.get("flake_runs") or DEFAULT_FLAKE_RUNS))
    try:
        cv_threshold = float(cfg.get("flake_cv_threshold", DEFAULT_CV_THRESHOLD))
    except (TypeError, ValueError):
        cv_threshold = DEFAULT_CV_THRESHOLD

    findings = []
    learn_targets = {}
    executed = 0

    targets = _build_targets(repo)
    if not targets:
        return CheckResult(
            check=CHECK_ID, findings=[], learn={"targets": {}}, ran=True,
            notes="nenhum alvo de selftest encontrado (tools/gen-*.py ausentes)")

    for target, argv, needs_out in targets:
        durations = []
        failures = []  # (repetição, motivo, cauda de stderr)
        tmp_dirs = []
        try:
            for i in range(reps):
                argv_rep = list(argv)
                if needs_out:
                    out_dir = tempfile.mkdtemp(prefix=f"apkbot-flake-{i + 1}-")
                    tmp_dirs.append(out_dir)
                    argv_rep += ["--out", out_dir]
                t0 = time.perf_counter()
                try:
                    proc = subprocess.run(
                        argv_rep, cwd=str(repo), timeout=SUBPROCESS_TIMEOUT_S,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True)
                    dur = time.perf_counter() - t0
                    durations.append(dur)
                    if proc.returncode != 0:
                        failures.append((i + 1, f"exit {proc.returncode}",
                                         _tail(proc.stderr)))
                except subprocess.TimeoutExpired:
                    dur = time.perf_counter() - t0
                    durations.append(dur)
                    failures.append(
                        (i + 1, f"timeout {SUBPROCESS_TIMEOUT_S}s", ""))
            executed += 1

            learn_targets[target] = {
                "durations_s": [round(d, 3) for d in durations],
            }

            # 1) qualquer FAIL em qualquer repetição
            if failures:
                status_rows = []
                failed_reps = {rep for rep, _, _ in failures}
                for i in range(reps):
                    dur = durations[i] if i < len(durations) else 0.0
                    if (i + 1) in failed_reps:
                        motivo = next(m for rep, m, _ in failures
                                      if rep == i + 1)
                        status_rows.append(
                            (f"repetição {i + 1}", f"FALHOU ({motivo}, {dur:.3f}s)"))
                    else:
                        status_rows.append(
                            (f"repetição {i + 1}", f"OK ({dur:.3f}s)"))
                first_tail = failures[0][2]
                findings.append(Finding(
                    check=CHECK_ID, target=target, severity="regression",
                    title=f"selftest instável: {target}",
                    body_md=(
                        f"`{target}` falhou em {len(failures)} de {reps} "
                        "repetições CONSECUTIVAS no mesmo ambiente — um único "
                        "passe de CI não distinguiria isto de um verde "
                        "confiável.\n\n" +
                        "| Repetição | Resultado |\n|---|---|\n" +
                        "\n".join(f"| {a} | {b} |" for a, b in status_rows) +
                        "\n\nCauda do stderr da primeira falha:\n\n"
                        + first_tail +
                        "\n\nSelftest que passa às vezes e falha outras = flake "
                        "probabilístico (ordem de dict, tempo, arredondamento, "
                        "estado compartilhado). Corrija antes de confiar nos "
                        "fixtures."),
                    fingerprint=f"{CHECK_ID}:{target}:selftest-instavel"))

            # 2) análise de latência (média + CV)
            if len(durations) >= 2:
                mean = statistics.mean(durations)
                std = statistics.pstdev(durations)
                if mean > 0:
                    cv = std / mean
                    learn_targets[target]["cv"] = round(cv, 4)
                    if cv > cv_threshold:
                        durs = ", ".join(f"{d:.3f}" for d in durations)
                        findings.append(Finding(
                            check=CHECK_ID, target=target, severity="flaky",
                            title=f"latência oscilante: {target}",
                            body_md=(
                                f"Durações das {reps} repetições de `{target}` "
                                "oscilam além do limiar.\n\n"
                                f"- durações (s): {durs}\n"
                                f"- média: {mean:.3f}s | desvio-padrao "
                                f"(populacional): {std:.3f}s | CV: {cv:.2f}\n"
                                f"- limiar: CV <= {cv_threshold:.2f} "
                                "(CV = desvio-padrao / média; ajustável via "
                                "cfg.flake_cv_threshold)\n\n"
                                "CV alto em selftests rápidos pode ser ruído de "
                                "máquina compartilhada; investigue se persistir "
                                "entre runs do bot (a tendência entre execuções "
                                "é acumulada pelo dispatcher em flap_history)."),
                            fingerprint=(
                                f"{CHECK_ID}:{target}:latencia-oscilante")))
        finally:
            for d in tmp_dirs:
                shutil.rmtree(d, ignore_errors=True)

    # 3) limitação honesta: compat-nightly escreve dentro do repositório
    learn_targets["compat-nightly"] = {
        "skipped": "escreve em docs/ no repo",
    }
    findings.append(Finding(
        check=CHECK_ID, target="compat-nightly", severity="info",
        title="compat-nightly.sh pulado no cheque local de flakiness",
        body_md=(
            "`scripts/compat-nightly.sh` escreve `docs/compat-matrix.md` "
            "DENTRO do repositório. O APKBot nunca modifica o worktree, e "
            "contornar isso exigiria clone/worktree temporário — custo alto "
            "para um cheque local.\n\n"
            "Limitação honesta: a estabilidade do compat-nightly NÃO é "
            "exercitada por este cheque; a cobertura real fica no job "
            "`engines-nightly.yml` (CI), que roda o script sem a restrição de "
            "worktree. Alternativa futura: rodar o script em clone temporário "
            "raso e descartá-lo.\n\n"
            "O registro fica no learn como "
            "`targets.compat-nightly.skipped` para o dispatcher acompanhar."),
        fingerprint=f"{CHECK_ID}:compat-nightly:execucao-pulada"))

    return CheckResult(
        check=CHECK_ID,
        findings=findings,
        learn={"targets": learn_targets},
        ran=True,
        # "immediate": durações são fato por-execução (mudam toda rodada) —
        # confirmação por igualdade de payload nunca convergiria e deixaria
        # pendências órfãs no estado. O baseline guarda a última rodada.
        learn_mode="immediate",
        notes=(f"{executed} alvo(s) x{reps} repetição(ões); "
               f"{len(learn_targets)} entradas no learn "
               "(compat-nightly pulado por escrever em docs/)"),
    )
