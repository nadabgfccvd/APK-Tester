#!/usr/bin/env python3
"""APKBot — dispatcher principal do bot anti-regressão do APK Tester.

Bot nativo do repositório (estilo Dependabot, mas para regressão de
fixture/parser): roda checks, aprende baselines com confirmação múltipla
(anti-flake), sincroniza issues no GitHub e commita a memória de estado no
próprio repositório. Implementação 100% python3 stdlib.

Uso:
    python3 bot/apkbot.py                               # execução completa (CI)
    python3 bot/apkbot.py --check determinism,size_drift
    python3 bot/apkbot.py --local --dry-run             # leitura: sem GitHub, sem escrita
    python3 bot/apkbot.py --strict                      # exit 1 se houver regressão

Fluxo: carrega config+estado -> garante labels -> executa checks -> protocolo
de aprendizado -> sincroniza issues -> persiste estado (commit/push) ->
imprime o relatório. Códigos de saída: 0 normal; 1 com --strict e regressão;
2 uso inválido ou configuração ilegível.
"""

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.checks import CHECK_MODULES, discover  # noqa: E402
from bot.lib import report  # noqa: E402
from bot.lib import state as state_lib  # noqa: E402
from bot.lib.base import BotContext, CheckResult, Finding  # noqa: E402
from bot.lib.github_api import GitHubAPI  # noqa: E402

# Severidades que geram/atualizam issue ("new" e "info" ficam só no relatório).
ISSUE_SEVERITIES = ("regression", "drift", "flaky")
DEFAULT_STATE_REL = "bot/state/bot-state.json"
COMMIT_MESSAGE = "apkbot: atualiza estado [skip ci]"
GIT_TIMEOUT_S = 120


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def one_line_error(exc):
    """Resumo de exceção em uma linha (arquivo:linha (função): mensagem)."""
    frames = traceback.extract_tb(exc.__traceback__)
    if frames:
        last = frames[-1]
        return f"{Path(last.filename).name}:{last.lineno} ({last.name}): {exc}"
    return f"{type(exc).__name__}: {exc}"


def last_line(text):
    """Última linha não vazia de uma saída de processo (para notas)."""
    stripped = (text or "").strip()
    return stripped.splitlines()[-1] if stripped else "sem detalhes"


def load_cfg(repo_path):
    """Carrega bot/bot-config.json (essencial; falha propaga para o chamador)."""
    cfg_path = repo_path / "bot" / "bot-config.json"
    with cfg_path.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not isinstance(cfg, dict):
        raise ValueError("bot-config.json não contém um objeto JSON")
    return cfg


def strip_updated(state):
    """Cópia do estado sem a chave 'updated' (para comparação por hash)."""
    return {key: value for key, value in state.items() if key != "updated"}


def parse_args(argv):
    """Argumentos de linha de comando + validação da seleção de checks."""
    parser = argparse.ArgumentParser(
        prog="apkbot",
        description="Bot anti-regressão nativo do repo APK Tester (python3 stdlib).",
    )
    parser.add_argument("--check", default="all",
                        help="checks a executar: all ou ids separados por vírgula (padrão: all)")
    parser.add_argument("--local", action="store_true",
                        help="sem GitHub API (gh=None), sem issues e sem push")
    parser.add_argument("--dry-run", action="store_true",
                        help="nunca grava estado, nunca faz push, nunca toca em issues")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 se qualquer check produzir finding de severidade regression")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""),
                        help="repositório owner/name (padrão: env GITHUB_REPOSITORY)")
    parser.add_argument("--summary-only", action="store_true",
                        help="apenas o relatório final no stdout (notas vão para stderr)")
    args = parser.parse_args(argv)
    if args.check.strip().lower() == "all":
        args.check_list = list(CHECK_MODULES)
        return args
    chosen = []
    for item in args.check.split(","):
        item = item.strip()
        if item and item not in chosen:
            chosen.append(item)
    unknown = [item for item in chosen if item not in CHECK_MODULES]
    if unknown:
        parser.error(
            f"check(s) desconhecido(s): {', '.join(unknown)}; "
            f"válidos: {', '.join(CHECK_MODULES)}"
        )
    if not chosen:
        parser.error("--check vazio; use 'all' ou uma lista separada por vírgula")
    args.check_list = chosen
    return args


# ----------------------------------------------------------------------
# GitHub
# ----------------------------------------------------------------------
def build_gh(args, cfg, notes):
    """Constrói o cliente GitHub ou registra por que ele está indisponível."""
    if args.local:
        notes.append("modo --local: GitHub API desativada (gh=None)")
        return None
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    repo = (args.repo or "").strip()
    if not repo:
        notes.append("gh indisponível: repositório não informado (--repo ou GITHUB_REPOSITORY)")
        return None
    if not token:
        notes.append("gh indisponível: token ausente (defina GH_TOKEN ou GITHUB_TOKEN)")
        return None
    return GitHubAPI(repo, token, timeout=float(cfg.get("http_timeout_s", 15)))


def ensure_labels(gh, cfg, dry_run, notes):
    """Garante as labels do bot no repositório; falha não bloqueia a execução."""
    if gh is None:
        return
    if dry_run:
        notes.append("dry-run: criação/verificação de labels ignorada")
        return
    ok, failed = 0, 0
    for name, color in (cfg.get("labels", {}) or {}).items():
        try:
            if gh.ensure_label(name, color, f"Label automática do APKBot ({name})"):
                ok += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            notes.append(f"falha ao garantir label '{name}': {one_line_error(exc)}")
    if failed:
        notes.append(f"labels garantidas parcialmente ({ok} ok, {failed} com falha); seguindo sem bloquear")


# ----------------------------------------------------------------------
# Execução dos checks
# ----------------------------------------------------------------------
def run_selected_checks(selected, modules, ctx, notes):
    """Executa cada check isolando falhas (uma exceção nunca derruba o resto)."""
    results = []
    for check_id in selected:
        module = modules.get(check_id)
        if module is None:
            results.append(CheckResult(check=check_id, ran=False, notes="módulo ausente"))
            continue
        try:
            result = module.run(ctx)
            if not isinstance(result, CheckResult):
                results.append(CheckResult(
                    check=check_id, ran=False,
                    notes="módulo não seguiu o contrato (run não retornou CheckResult)"))
                continue
            result.check = check_id  # normaliza com o id selecionado
            results.append(result)
        except Exception as exc:
            notes.append(f"check '{check_id}' falhou com exceção: {one_line_error(exc)}")
            results.append(CheckResult(check=check_id, ran=False,
                                       notes=f"exceção: {one_line_error(exc)}"))
    return results


# ----------------------------------------------------------------------
# Protocolo de aprendizado (memória anti-flake)
# ----------------------------------------------------------------------
def learning_protocol(results, state, cfg, now, notes):
    """Confirma e aplica baselines novos (anti-flake) ou os aplica imediatamente.

    Para cada ``CheckResult`` com ``learn`` não vazio:

    - ``learn_mode == "immediate"``: o payload é mesclado (deep_merge) direto
      em ``state["baselines"][check]`` na MESMA execução e pendências antigas
      do check são removidas. Usado por checks cujo payload é fato
      por-execução (durações de flakiness) ou série temporal carregada para
      frente pelo próprio check (samples de size_drift) — neles a confirmação
      por igualdade de payload nunca convergiria e deixaria pendências órfãs.

    - ``learn_mode == "merge"`` (padrão):
      key = f"{check}:{dict_sha256(learn)}";
      - se o payload for igual ao baseline atual do check, nada a fazer
        (pendência equivalente é limpa);
      - senão, a pendência em ``state["confirmations"]`` ganha ``runs_seen += 1``;
      - quando ``runs_seen >= confirmations_for_new``, o payload é mesclado
        (deep_merge) em ``state["baselines"][check]``, a pendência é removida e
        um finding [INFO] "Baseline atualizada" entra no relatório;
      - ao registrar uma pendência nova, pendências ANTERIORES do mesmo check
        são removidas (superadas — só a observação mais recente interessa;
        sem isso, payloads que mudam a cada execução deixariam lixo eterno).

    Findings de severidade "regression" NUNCA são auto-aprendidos.
    """
    needed = int(cfg.get("confirmations_for_new", 2))
    confirmations = state.setdefault("confirmations", {})
    baselines = state.setdefault("baselines", {})
    for result in results:
        if not getattr(result, "ran", False):
            continue
        learn = getattr(result, "learn", None) or {}
        if not isinstance(learn, dict) or not learn:
            continue
        check = result.check
        if any(getattr(f, "severity", "") == "regression" for f in (result.findings or [])):
            notes.append(
                f"aprendizado de '{check}' ignorado: finding [REGRESSÃO] na execução "
                "(regressão nunca é auto-aprendida)")
            continue

        # --- modo imediato: aplica agora e limpa pendências do check -------
        if getattr(result, "learn_mode", "merge") == "immediate":
            state_lib.deep_merge(baselines.setdefault(check, {}), learn)
            for key in [k for k, v in confirmations.items()
                        if isinstance(v, dict) and v.get("check") == check]:
                confirmations.pop(key, None)
            continue

        # --- modo padrão: confirmação múltipla -----------------------------
        key = f"{check}:{state_lib.dict_sha256(learn)}"
        if learn == baselines.get(check):
            confirmations.pop(key, None)
            continue
        previous = confirmations.get(key)
        prev_runs = int(previous.get("runs_seen", 0)) if isinstance(previous, dict) else 0
        first_seen = previous.get("first_seen") if isinstance(previous, dict) else None
        runs_seen = prev_runs + 1
        if runs_seen >= needed:
            state_lib.deep_merge(baselines.setdefault(check, {}), learn)
            confirmations.pop(key, None)
            result.findings.append(Finding(
                check=check, target=check, severity="info",
                title="Baseline atualizada",
                body_md=(f"baseline atualizada (confirmada em {runs_seen} execuções); "
                         f"payload `{key}` mesclado em `baselines.{check}`."),
                fingerprint=f"{check}:{check}:baseline",
            ))
            notes.append(f"baseline de '{check}' atualizada (confirmada em {runs_seen} execuções)")
        else:
            # supera pendências anteriores do MESMO check (apenas a mais
            # recente observação é candidata a baseline)
            for stale in [k for k, v in confirmations.items()
                          if isinstance(v, dict) and v.get("check") == check]:
                confirmations.pop(stale, None)
            confirmations[key] = {
                "check": check,
                "runs_seen": runs_seen,
                "payload": learn,
                "first_seen": first_seen or now,
            }


# ----------------------------------------------------------------------
# Sincronização de issues (tolerante a falhas)
# ----------------------------------------------------------------------
def issue_sync(results, state, gh, cfg, now, run_info, notes):
    """Cria/comenta/fecha issues conforme os findings desta execução.

    - severity in (regression, drift, flaky): fingerprint novo => cria issue;
      já aberto => 1 comentário com evidência fresca + flap_history;
    - fingerprint aberto ausente nesta execução => comentário de resolução,
      fechamento e remoção de ``state["open_issues"]``;
    - dedup: no máximo 1 operação por fingerprint por execução;
    - qualquer falha de API vira nota, nunca derruba a execução.
    """
    current = {}
    for result in results:
        for finding in getattr(result, "findings", []) or []:
            severity = getattr(finding, "severity", "")
            fp = getattr(finding, "fingerprint", "")
            if severity in ISSUE_SEVERITIES and fp and fp not in current:
                current[fp] = finding
    open_issues = state.setdefault("open_issues", {})
    labels_cfg = cfg.get("labels", {}) or {}

    # 1) findings presentes: cria ou atualiza issue
    for fp, finding in current.items():
        entry = open_issues.get(fp)
        if entry is None:
            wanted = [name for name in ("apkbot", f"apkbot:{finding.severity}") if name in labels_cfg]
            try:
                issue = gh.create_issue(f"[apkbot] {finding.title}",
                                        report.issue_body(finding, run_info),
                                        wanted or ["apkbot"])
                open_issues[fp] = {
                    "number": issue.get("number"),
                    "title": finding.title,
                    "url": issue.get("html_url", ""),
                    "check": finding.check,
                    "target": finding.target,
                    "severity": finding.severity,
                    "first_seen": now,
                }
                notes.append(f"issue criado para `{fp}`: #{issue.get('number')}")
            except Exception as exc:
                notes.append(f"falha ao criar issue para `{fp}`: {one_line_error(exc)}")
        else:
            try:
                gh.add_issue_comment(entry.get("number"), report.comment_body(finding))
                flaps = state.setdefault("flap_history", {})
                previous = flaps.get(fp) if isinstance(flaps.get(fp), dict) else {}
                flaps[fp] = {
                    "count": int(previous.get("count", 0)) + 1,
                    "last_seen": now,
                    "title": finding.title,
                }
                notes.append(f"evidência atualizada no issue #{entry.get('number')} (`{fp}`)")
            except Exception as exc:
                notes.append(f"falha ao comentar issue `{fp}`: {one_line_error(exc)}")

    # 2) fingerprints que sumiram: comenta e fecha
    for fp in list(open_issues.keys()):
        if fp in current:
            continue
        entry = open_issues.get(fp) or {}
        number = entry.get("number")
        ghost = Finding(
            check=entry.get("check", ""),
            target=entry.get("target", ""),
            severity=entry.get("severity", "info"),
            title=entry.get("title", ""),
            body_md="",
            fingerprint=fp,
        )
        try:
            gh.add_issue_comment(number, f"Resolvido na execução {now}.\n\n" + report.close_comment(ghost))
            gh.update_issue(number, state="closed")
            open_issues.pop(fp, None)
            notes.append(f"issue #{number} fechado (`{fp}` ausente nesta execução)")
        except Exception as exc:
            notes.append(f"falha ao fechar issue `{fp}`: {one_line_error(exc)}")


# ----------------------------------------------------------------------
# Persistência
# ----------------------------------------------------------------------
def record_run(results, state, now):
    """Registra o resumo desta execução em ``state["runs"]`` (antes de persistir)."""
    counts = {severity: 0 for severity in report.SEVERITY_ORDER}
    for result in results:
        for finding in getattr(result, "findings", []) or []:
            severity = getattr(finding, "severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
    state.setdefault("runs", []).append({
        "date": now,
        "findings_count": counts,
        "checks_ran": sum(1 for result in results if getattr(result, "ran", False)),
    })
    state_lib.cap_runs(state, 30)
    return counts


def persist_state(repo_path, cfg, state, initial_hash, dry_run, notes):
    """Salva o estado somente se o conteúdo mudou (hash ignora 'updated')."""
    if dry_run:
        notes.append("dry-run: estado não persistido")
        return False
    if state_lib.dict_sha256(strip_updated(state)) == initial_hash:
        notes.append("estado inalterado; nada a persistir")
        return False
    state_rel = cfg.get("state_path", DEFAULT_STATE_REL)
    state_lib.save_state(repo_path / state_rel, state)
    notes.append(f"estado salvo em {state_rel}")
    return True


def push_state(repo_path, cfg, saved, notes):
    """Commita e envia o estado ([skip ci]); cada falha é tolerada com nota."""
    if not saved:
        return
    state_rel = cfg.get("state_path", DEFAULT_STATE_REL)

    def git(*argv, env=None):
        return subprocess.run(["git", *argv], cwd=str(repo_path), capture_output=True,
                              text=True, timeout=GIT_TIMEOUT_S, env=env)

    try:
        inside = git("rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            notes.append("push ignorado: diretório não é um checkout git")
            return
        status = git("status", "--porcelain", "--", state_rel)
        if status.returncode != 0:
            notes.append(f"push ignorado: git status falhou ({last_line(status.stderr)})")
            return
        if not status.stdout.strip():
            notes.append("nada a commitar no estado")
            return
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = os.environ.get("BOT_AUTHOR_NAME", "apkbot[bot]")
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = os.environ.get(
            "BOT_AUTHOR_EMAIL", "apkbot@users.noreply.github.com")
        git("add", "--", state_rel)
        commit = git("commit", "-m", COMMIT_MESSAGE, env=env)
        if commit.returncode != 0:
            notes.append(f"commit do estado falhou: {last_line(commit.stderr or commit.stdout)}")
            return
        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
        if branch in ("HEAD", ""):
            branch = "main"
        push = git("push", "origin", f"HEAD:{branch}")
        if push.returncode != 0:
            # não-fast-forward: outro commit chegou a origin durante a execução
            # (ex.: rodada cron sobreposta a um dispatch). Rebaseia o commit do
            # estado sobre o remoto e tenta UMA vez a mais.
            git("fetch", "origin", branch)
            rebase = git("rebase", f"origin/{branch}")
            if rebase.returncode != 0:
                git("rebase", "--abort")
                notes.append(f"push do estado falhou (rebase impossível): "
                             f"{last_line(push.stderr or push.stdout)}")
                return
            push = git("push", "origin", f"HEAD:{branch}")
            if push.returncode != 0:
                notes.append(f"push do estado falhou após rebase: "
                             f"{last_line(push.stderr or push.stdout)}")
                return
        notes.append(
            f"estado commitado e enviado para origin/{branch} "
            "(mensagem com [skip ci]; push via GITHUB_TOKEN não dispara outros workflows)")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        notes.append(f"push do estado ignorado ({type(exc).__name__}: {exc})")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main(argv=None):
    args = parse_args(argv)
    notes = []
    repo_path = REPO_ROOT
    try:
        cfg = load_cfg(repo_path)
    except Exception as exc:
        print(f"apkbot: configuração ilegível ({one_line_error(exc)})", file=sys.stderr)
        return 2

    state_path = repo_path / cfg.get("state_path", DEFAULT_STATE_REL)
    state = state_lib.load_state(state_path)
    notes.extend(state.pop(state_lib.LOAD_NOTES_KEY, []))
    initial_hash = state_lib.dict_sha256(strip_updated(state))
    now = state_lib.utcnow_iso()

    gh = build_gh(args, cfg, notes)
    ensure_labels(gh, cfg, args.dry_run, notes)

    modules, discover_notes = discover(args.check_list)
    notes.extend(discover_notes)
    ctx = BotContext(repo_path=repo_path, state=state, now=now,
                     gh=gh, cfg=cfg, dry_run=args.dry_run)
    results = run_selected_checks(args.check_list, modules, ctx, notes)

    learning_protocol(results, state, cfg, now, notes)

    run_info = {"run_id": os.environ.get("GITHUB_RUN_ID", "local"), "date": now}
    if args.dry_run:
        notes.append("dry-run: sincronização de issues ignorada")
    elif gh is not None:
        issue_sync(results, state, gh, cfg, now, run_info, notes)
    elif not args.local:
        notes.append("sincronização de issues ignorada: gh indisponível")

    record_run(results, state, now)
    saved = persist_state(repo_path, cfg, state, initial_hash, args.dry_run, notes)
    if not args.local and not args.dry_run:
        push_state(repo_path, cfg, saved, notes)

    print(report.summary_md(results, state, cfg))
    if args.summary_only:
        for note in notes:
            print(f"nota: {note}", file=sys.stderr)
    elif notes:
        print("## Notas da execução\n")
        for note in notes:
            print(f"- {note}")

    has_regression = any(
        getattr(finding, "severity", "") == "regression"
        for result in results
        for finding in (getattr(result, "findings", []) or [])
    )
    if args.strict and has_regression:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
