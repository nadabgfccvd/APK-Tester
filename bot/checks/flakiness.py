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

Alvos: todos os tools/gen-*.py --selftest, tools/fixture-pack.py --selftest,
tools/fixture-pack.py --dry-run (equivalente leve com saída em /tmp) e
scripts/compat-nightly.sh — este último DENTRO de um clone raso TEMPORÁRIO
do próprio repositório: `git clone --depth 1` para <tmp>/clone e o script
roda a partir do clone, de modo que docs/compat-matrix.md é escrito DENTRO
do clone descartável e a lei "o APKBot nunca modifica o worktree" segue
valendo (o clone copia o HEAD commitado — exatamente o que o nightly do CI
exercita). Sem `rustydroid`/`rd` no PATH todas as linhas viram SKIP e o
script sai 0: a estabilidade exercitada localmente é a do PIPELINE do
script (parse da answer key, laço das 32 fixtures, agregação do markdown,
contrato do exit code); os caminhos FAIL dependem do runtime irmão e
continuem cobertos pelo job engines-nightly no CI.

A PRIMEIRA execução do alvo clone é um AQUECIMENTO não cronometrado e com
resultado IGNORADO: ela bootstrap o snapshot do `rd` no ~/.cache (download
+ validação sha256), e as repetições cronometradas medem o regime estável.
Medir cold-start junto estoura CV sem ser flake: a mesma rodada de CI que
abriu o issue #35 mediu [0.614, 0.042, 0.099] (CV 1.02) — só a primeira
repetição pagou o bootstrap; aquecido, o mesmo alvo roda com CV ~0.05.
Se o script estiver quebrado DE VERDADE, as repetições cronometradas pegam
(aquecimento não é evidência; cold-start transitório não vira regression
falso).

Se o git não estiver disponível ou o clone falhar (disco cheio, permissão),
o alvo degrada para um Finding "info" único documentando o motivo — a
lacuna volta a ser honesta e NUNCA é falha.

Nada é escrito no repositório: saídas efêmeras em mktemp sob /tmp com
limpeza em finally; timeout de 120s por subprocesso (timeout conta como
FAIL da repetição; o clone tem o mesmo teto).
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
CLONE_TIMEOUT_S = 120
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
    """[(target, argv, mode)] — argv pronto; mode em {"plain", "out", "clone"}.

    - "plain": roda argv como está (selftests dos geradores);
    - "out": acrescenta --out <tmp> por repetição (fixture-pack:dry-run);
    - "clone": o argv aponta para a CÓPIA rasa do repositório (ver
      _prepare_clone) — alvo que escreve dentro da própria raiz, como o
      compat-nightly.
    """
    targets = []
    for tool in sorted((repo / "tools").glob("gen-*.py")):
        targets.append((tool.stem,
                        [sys.executable, str(tool), "--selftest"], "plain"))
    fp = repo / "tools" / "fixture-pack.py"
    if fp.exists():
        targets.append(("fixture-pack:selftest",
                        [sys.executable, str(fp), "--selftest"], "plain"))
        # Equivalente leve: plano JSON do modo canônico minSdk9, --out em /tmp.
        targets.append(("fixture-pack:dry-run",
                        [sys.executable, str(fp), "--fixture", "minSdk9",
                         "--dry-run"], "out"))
    cn = repo / "scripts" / "compat-nightly.sh"
    if cn.exists():
        targets.append(("compat-nightly", ["bash", str(cn)], "clone"))
    return targets


def _prepare_clone(repo: Path, tmp_root: str):
    """Clone raso do HEAD commitado em <tmp_root>/clone.

    Retorna (caminho_do_clone | None, motivo_do_skip | None). Qualquer
    falha é motivo de skip honesto, nunca exceção.
    """
    git = shutil.which("git")
    if git is None:
        return None, "git não disponível no PATH"
    clone = Path(tmp_root) / "clone"
    try:
        proc = subprocess.run(
            [git, "clone", "--quiet", "--depth", "1", str(repo), str(clone)],
            cwd=str(repo), timeout=CLONE_TIMEOUT_S,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"clone falhou: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return None, (f"clone falhou (exit {proc.returncode}): "
                      f"{_tail(proc.stderr, 3)}")
    if not (clone / "scripts" / "compat-nightly.sh").exists():
        return None, "clone sem scripts/compat-nightly.sh (HEAD inesperado)"
    return clone, None


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

    for target, argv, mode in targets:
        durations = []
        failures = []  # (repetição, motivo, cauda de stderr)
        tmp_dirs = []
        skip_reason = None
        try:
            argv_base = list(argv)
            if mode == "clone":
                clone_root = tempfile.mkdtemp(prefix="apkbot-flake-compat-")
                tmp_dirs.append(clone_root)
                clone, err = _prepare_clone(repo, clone_root)
                if err is not None:
                    skip_reason = err
                else:
                    # Rodar o script DO CLONE: o caminho do BASH_SOURCE
                    # vira a raiz do pipeline — toda escrita fica no clone.
                    argv_base = ["bash",
                                 str(clone / "scripts" / "compat-nightly.sh")]

            if mode == "clone" and skip_reason is None:
                # Aquecimento NÃO cronometrado (issue #35): a 1a execução
                # bootstrap o snapshot do rd no ~/.cache; cronometrar esse
                # cold-start junto das repetições mistura dois regimes e
                # fabrica CV alto sem instabilidade real. Resultado e
                # exceção IGNORADOS de propósito — as repetições
                # cronometradas abaixo são a evidência.
                try:
                    subprocess.run(
                        argv_base, cwd=str(repo),
                        timeout=SUBPROCESS_TIMEOUT_S,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True)
                except (subprocess.TimeoutExpired, OSError):
                    pass

            if skip_reason is None:
                for i in range(reps):
                    argv_rep = list(argv_base)
                    if mode == "out":
                        out_dir = tempfile.mkdtemp(prefix=f"apkbot-flake-{i + 1}-")
                        tmp_dirs.append(out_dir)
                        argv_rep += ["--out", out_dir]
                    t0 = time.perf_counter()
                    try:
                        proc = subprocess.run(
                            argv_rep, cwd=str(repo),
                            timeout=SUBPROCESS_TIMEOUT_S,
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
        finally:
            for d in tmp_dirs:
                shutil.rmtree(d, ignore_errors=True)

        # ---- pós-processamento do alvo (fora do try: tmp já limpo) ----
        if skip_reason is not None:
            learn_targets[target] = {"skipped": skip_reason}
            findings.append(Finding(
                check=CHECK_ID, target=target, severity="info",
                title=f"{target} não exercitado no cheque local de flakiness",
                body_md=(
                    f"O alvo `{target}` (clone raso temporário do repositório) "
                    "não pôde ser executado neste ambiente:\n\n"
                    f"- motivo: {skip_reason}\n\n"
                    "A lacuna é documentada como info (nunca falha); a "
                    "cobertura real segue no job `engines-nightly.yml` (CI). "
                    "O registro fica no learn como "
                    f"`targets.{target}.skipped`."),
                fingerprint=f"{CHECK_ID}:{target}:execucao-pulada"))
            continue

        entry = {"durations_s": [round(d, 3) for d in durations]}
        if mode == "clone":
            # deep_merge do dispatcher NUNCA apaga chaves: o legado pré-clone
            # deixou "skipped" no baseline; nulo explícito = alvo exercitado
            # (e sobrescreve a string antiga; um skip futuro sobrescreve de
            # volta com o motivo — o par sempre reflete a última execução).
            entry["skipped"] = None
        learn_targets[target] = entry

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
               "(compat-nightly em clone raso temporário)"),
    )
