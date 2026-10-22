#!/usr/bin/env python3
"""bot/checks/governance.py — anti-regressão da própria governança do repositório.

Audita a ESTRUTURA de governança do APK Tester — o CI valida conteúdo, o bot
valida que a estrutura continua de pé (e que ninguém furou a identidade dos
commits). Requer ``ctx.gh`` (API do GitHub); com ``--local`` (gh=None) =>
CheckResult(ran=False, notes=...).

Sub-verificações:
1. MILESTONES: A0..A8 devem EXISTIR (títulos começando com "A0".."A8"),
   em qualquer estado (open/closed — ``list_milestones(state="all")``;
   se a assinatura não aceitar ``state``, busca open+closed e une).
   Ausente => "regression" ...:milestones:ausente:A{n}.
2. LABELS: labels vivas (gh.list_labels()) vs ``labels.json`` na raiz.
   Só-viva, só-json ou cor divergente na mesma label => UM "drift"
   ...:labels:divergencia com as três listas no corpo.
3. TEMPLATES: .github/ISSUE_TEMPLATE/{bug,fixture_gap,size_regression}.yml +
   config.yml + PULL_REQUEST_TEMPLATE.md — ausente => "regression"
   ...:templates:ausente:{path} por arquivo.
4. WORKFLOWS: os 5 workflows devem existir E conter "on:" e "jobs:"
   (regex multilinha, SEM parse de YAML) — senão "regression"
   ...:workflows:invalido:{name}. A lista inclui o próprio apkbot.yml: o bot
   também guarda a integridade da sua própria automação.
5. AUDITORIA DE COMMITS (guardião de identidade): últimos
   cfg.commit_audit_count (padrão 20) commits; author.name deve estar em
   cfg.allowed_authors (padrão: xisto/xisto-agent/nadabgfccvd, papéis de
   GOVERNANCE.md). Violação => "regression"
   ...:commits:autor-nao-autorizado:{sha7} (orientação: auditar push).
   Merge commits (2+ parents) são pulados — o padrão FORCE não se aplica.
6. CHANGELOG: commits que tocam `contracts/**` também devem tocar
   CHANGELOG.md (Keep a Changelog). A regra é PROSPECTIVA: na primeira
   execução o bot aprende a âncora ``bot_since_sha`` (HEAD do momento) e a
   partir daí audita SOMENTE commits novos em relação à âncora — nada é
   apontado retroativamente (o repositório anterior ao bot não tinha esta
   política). Âncora não encontrada na janela (mais de N commits) => janela
   inteira auditada (fallback seguro). Lista de arquivos via
   gh.get_commit(sha); se o método não existir/falhar, APROXIMAÇÃO
   documentada: mensagem do commit citando "contracts" e "changelog". Se
   nenhum commit novo de contratos tocou o CHANGELOG => UM "drift"
   ...:changelog:contrato-sem-nota.

Toda chamada de API é embrulhada em try/except: falha pontual degrada a
sub-verificação (Finding "info" ...:api-indisponivel quando nada pôde ser
auditado), nunca derruba o bot.
"""

import json
import re
import sys
from pathlib import Path

CHECK_ID = "governance"

COMMIT_AUDIT_COUNT_DEFAULT = 20
ALLOWED_AUTHORS_DEFAULT = ["xisto", "xisto-agent", "nadabgfccvd"]

TEMPLATES = [
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/fixture_gap.yml",
    ".github/ISSUE_TEMPLATE/size_regression.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
]
WORKFLOWS = ["ci.yml", "size-gate.yml", "engines-nightly.yml", "release.yml",
             "apkbot.yml"]
REQUIRED_PHASES = [f"A{n}" for n in range(9)]
_MAX_LIST_BODY = 30

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _g(obj, key, default=None):
    """Acesso dict-ou-atributo (respostas da API podem vir dos dois jeitos)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, default)
    return default if value is None else value


def _first_line(message: str) -> str:
    return (message or "").strip().splitlines()[0] if (message or "").strip() else "(sem mensagem)"


def _cap_lines(items, limit=_MAX_LIST_BODY):
    items = list(items)
    if len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


def _list_milestones(gh):
    """Milestones em todos os estados (ou None se a API falhou).

    O cliente canônico (bot.lib.github_api.GitHubAPI) não aceita ``state`` e
    já devolve TODOS os estados; os fallbacks cobrem assinaturas variantes
    (com ``state=`` ou posicional) sem nunca levantar exceção para fora.
    """
    try:
        return list(gh.list_milestones(state="all") or [])
    except TypeError:
        pass
    except Exception:
        return None
    for opened_attempt in (lambda: list(gh.list_milestones() or []),
                           lambda: list(gh.list_milestones("all") or [])):
        try:
            opened = opened_attempt()
        except Exception:
            continue
        try:
            closed = list(gh.list_milestones(state="closed") or [])
        except Exception:
            closed = []
        seen, out = set(), []
        for m in opened + closed:
            num = _g(m, "number")
            if num not in seen:
                seen.add(num)
                out.append(m)
        return out
    return None


def _commit_files(gh, sha):
    """Lista de arquivos de um commit via get_commit, ou None se indisponível."""
    getter = getattr(gh, "get_commit", None)
    if not callable(getter):
        return None
    try:
        detail = getter(sha)
    except Exception:
        return None
    files = _g(detail, "files") or []
    names = []
    for f in files:
        name = _g(f, "filename")
        if isinstance(name, str):
            names.append(name)
    return names


def _commit_message(commit_obj) -> str:
    msg = _g(commit_obj, "message")
    if isinstance(msg, str):
        return msg
    return ""


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    findings = []
    learn = {"milestones_ok": True, "labels_count": 0, "last_audited_sha": ""}

    if ctx.gh is None:
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes="modo local (--local): auditoria de "
                                 "governança requer API do GitHub")

    repo = Path(str(ctx.repo_path))
    api_failures = 0

    # ---------------------------------------------------------- 1) milestones
    milestones = _list_milestones(ctx.gh)
    titles = set()
    if milestones is None:
        api_failures += 1
    else:
        for m in milestones:
            title = _g(m, "title")
            if isinstance(title, str):
                titles.add(title.strip())
    presentes = set()
    for title in titles:
        m = re.match(r"^A([0-8])(?![0-9])", title)
        if m:
            presentes.add(f"A{m.group(1)}")
    faltando = [p for p in REQUIRED_PHASES if p not in presentes]
    for fase in faltando:
        findings.append(Finding(
            check=CHECK_ID, target=f"milestone:{fase}",
            severity="regression",
            title=f"Milestone {fase} ausente no GitHub",
            body_md=(
                f"O milestone **{fase}** não existe mais no repositório "
                "(buscado em todos os estados, open e closed). O ciclo de "
                "fases A0–A8 é lei em GOVERNANCE.md; recriar o milestone com "
                "o título começando por "
                f"`{fase}` e o escopo/critério de saída do documento."),
            fingerprint=f"{CHECK_ID}:milestones:ausente:{fase}"))
    learn["milestones_ok"] = not faltando

    # ------------------------------------------------------------- 2) labels
    live_labels = None
    try:
        live_labels = list(ctx.gh.list_labels() or [])
    except Exception:
        api_failures += 1
    labels_json = None
    try:
        data = json.loads((repo / "labels.json").read_text(encoding="utf-8"))
        if isinstance(data, list):
            labels_json = [d for d in data if isinstance(d, dict)]
        else:
            labels_json = None
    except (OSError, ValueError):
        labels_json = None

    if labels_json is None:
        findings.append(Finding(
            check=CHECK_ID, target="labels.json",
            severity="info",
            title="labels.json ausente ou ilegível na raiz",
            body_md="O espelho canônico de labels (`labels.json`) não pôde "
                    "ser lido; a comparação live vs json foi pulada nesta "
                    "execução.",
            fingerprint=f"{CHECK_ID}:labels:json-ausente"))
        live_map = {}
        if live_labels is not None:
            for lb in live_labels:
                name = _g(lb, "name")
                if isinstance(name, str):
                    live_map[name.lower()] = (_g(lb, "color") or "")
        learn["labels_count"] = len(live_map)
    else:
        json_map = {}
        for d in labels_json:
            name = d.get("name")
            if isinstance(name, str) and name.strip():
                json_map[name.lower()] = (name, str(d.get("color") or "").lower())
        live_map = {}
        if live_labels is None:
            api_failures += 1
        else:
            for lb in live_labels:
                name = _g(lb, "name")
                if isinstance(name, str) and name.strip():
                    live_map[name.lower()] = (name, str(_g(lb, "color") or "").lower())
        learn["labels_count"] = len(live_map)

        so_live = sorted(live_map[k][0] for k in live_map.keys() - json_map.keys())
        so_json = sorted(json_map[k][0] for k in json_map.keys() - live_map.keys())
        cor_diff = []
        for key in sorted(live_map.keys() & json_map.keys()):
            live_color = live_map[key][1].lower()
            json_color = json_map[key][1]
            if live_color != json_color:
                cor_diff.append(
                    f"{json_map[key][0]} (json #{json_color} vs live #{live_color})")
        if so_live or so_json or cor_diff:
            def _bullet_block(title, rows):
                if not rows:
                    return ""
                shown, extra = _cap_lines(rows)
                txt = "\n".join(f"- `{r}`" for r in shown)
                if extra:
                    txt += f"\n- … e mais {extra}"
                return f"\n\n**{title}** ({len(rows)}):\n{txt}"

            body = ("Divergência entre as labels vivas do GitHub e o espelho "
                    "canônico `labels.json` na raiz."
                    + _bullet_block("Só no GitHub (sem json)", so_live)
                    + _bullet_block("Só no labels.json (não criada/atualizada)",
                                    so_json)
                    + _bullet_block("Cor divergente no mesmo nome", cor_diff)
                    + "\n\nAção: sincronizar com o bot (create_label/"
                      "ensure_label) e reespeitar `labels.json` como fonte.")
            findings.append(Finding(
                check=CHECK_ID, target="labels.json",
                severity="drift",
                title="Labels do GitHub divergem de labels.json",
                body_md=body,
                fingerprint=f"{CHECK_ID}:labels:divergencia"))

    # ---------------------------------------------------------- 3) templates
    for rel in TEMPLATES:
        if not (repo / rel).is_file():
            findings.append(Finding(
                check=CHECK_ID, target=rel,
                severity="regression",
                title=f"Template de governança ausente: {rel}",
                body_md=(
                    f"O arquivo `{rel}` não existe mais. Os templates de issue "
                    "(bug / fixture_gap / size_regression), o config.yml e o "
                    "template de PR fazem parte do kit de governança "
                    "(SUPPORT.md, CONTRIBUTING.md); restaurar o arquivo "
                    "original para não quebrar o reporte de defeitos e o "
                    "fluxo de PRs."),
                fingerprint=f"{CHECK_ID}:templates:ausente:{rel}"))

    # ---------------------------------------------------------- 4) workflows
    wf_on_re = re.compile(r"^on:", re.M)
    wf_jobs_re = re.compile(r"^jobs:", re.M)
    for name in WORKFLOWS:
        path = repo / ".github" / "workflows" / name
        text = None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = None
        if text is None:
            findings.append(Finding(
                check=CHECK_ID, target=f".github/workflows/{name}",
                severity="regression",
                title=f"Workflow ausente: {name}",
                body_md=(
                    f"`.github/workflows/{name}` não existe. Os 5 workflows "
                    "(ci, size-gate, engines-nightly, release, apkbot) são o "
                    "pilar 5 da suíte; restaurar o esqueleto original."),
                fingerprint=f"{CHECK_ID}:workflows:invalido:{name}"))
            continue
        tem_on = bool(wf_on_re.search(text))
        tem_jobs = bool(wf_jobs_re.search(text))
        if not (tem_on and tem_jobs):
            faltam = []
            if not tem_on:
                faltam.append("`on:`")
            if not tem_jobs:
                faltam.append("`jobs:`")
            findings.append(Finding(
                check=CHECK_ID, target=f".github/workflows/{name}",
                severity="regression",
                title=f"Workflow malformado: {name}",
                body_md=(
                    f"`.github/workflows/{name}` existe mas não contém "
                    f"{' e '.join(faltam)} no nível raiz (busca por regex "
                    "multilinha, sem parse de YAML — arquivo vazio, "
                    "comentado ou truncado). Revisar o workflow."),
                fingerprint=f"{CHECK_ID}:workflows:invalido:{name}"))

    # ------------------------------------------------- 5) auditoria de commits
    try:
        count = int(ctx.cfg.get("commit_audit_count")
                    or COMMIT_AUDIT_COUNT_DEFAULT)
    except (TypeError, ValueError):
        count = COMMIT_AUDIT_COUNT_DEFAULT
    allowed = {a.strip() for a in
               (ctx.cfg.get("allowed_authors") or ALLOWED_AUTHORS_DEFAULT)
               if isinstance(a, str) and a.strip()}

    commits = None
    try:
        commits = list(ctx.gh.list_commits(count) or [])
    except TypeError:
        try:
            commits = list(ctx.gh.list_commits() or [])
        except Exception:
            commits = None
    except Exception:
        commits = None
    if commits is None:
        api_failures += 1
        commits = []

    changelog_mode = "arquivos"
    if commits:
        learn["last_audited_sha"] = str(_g(commits[0], "sha") or "")[:40]
        # Âncora PROSPECTIVA da regra do CHANGELOG: na primeira execução com
        # histórico disponível, a âncora é o commit mais recente auditado;
        # depois, só commits NOVOS em relação à âncora são auditados (nada
        # retroativo — o repo pré-bot nunca teve esta política). Âncora fora
        # da janela (mais de N commits) => janela inteira (fallback seguro).
        baseline_gov = (ctx.state.get("baselines") or {}).get(CHECK_ID, {}) \
            if isinstance(ctx.state, dict) else {}
        anchor = str(baseline_gov.get("bot_since_sha") or "") \
            if isinstance(baseline_gov, dict) else ""
        if not anchor:
            anchor = str(_g(commits[0], "sha") or "")
            learn["bot_since_sha"] = anchor
        window = []
        for c in commits:
            if anchor and str(_g(c, "sha") or "") == anchor:
                break
            window.append(c)
        contract_rows, changelog_ok = [], False
        files_mode = True
        parsed = []
        for c in window:
            sha = str(_g(c, "sha") or "")
            commit_obj = _g(c, "commit") or {}
            message = _commit_message(commit_obj)
            files = _commit_files(ctx.gh, sha) if sha else None
            if files is None:
                files_mode = False
            parsed.append((sha, message, files or []))
        if not files_mode:
            changelog_mode = "mensagens (aproximação documentada)"
        for sha, message, files in parsed:
            touches_contracts = (
                any(f.startswith("contracts/") for f in files) if files_mode
                else "contracts" in message)
            touches_changelog = (
                ("CHANGELOG.md" in files) if files_mode
                else "changelog" in message.lower())
            if touches_contracts:
                contract_rows.append((sha, message, touches_changelog))
                changelog_ok = changelog_ok or touches_changelog
        if contract_rows and not changelog_ok:
            rows, extra = _cap_lines(
                [f"{sha[:7]} — {_first_line(msg)}" for sha, msg, _ in contract_rows])
            extra_txt = f"\n- … e mais {extra} commits" if extra else ""
            findings.append(Finding(
                check=CHECK_ID, target="CHANGELOG.md",
                severity="drift",
                title="Mudanças em contracts/** sem nota no CHANGELOG",
                body_md=(
                    f"Entre os {len(parsed)} commits NOVOS auditados (desde a "
                    "âncora do bot), "
                    f"{len(contract_rows)} tocaram `contracts/**` e NENHUM "
                    "deles atualizou o `CHANGELOG.md` (Keep a Changelog é "
                    "política de GOVERNANCE.md; mudanças em contratos exigem "
                    "aprovação humana e nota pública):\n\n"
                    + "\n".join(f"- {r}" for r in rows) + extra_txt
                    + "\n\nAção: abrir commit de changelog descrevendo a "
                      "mudança de contrato na seção [Unreleased]."),
                fingerprint=f"{CHECK_ID}:changelog:contrato-sem-nota"))

        for c in commits:
            sha = str(_g(c, "sha") or "")
            if len(_g(c, "parents") or []) >= 2:
                continue  # merge commit — padrão FORCE não se aplica
            commit_obj = _g(c, "commit") or {}
            author = _g(commit_obj, "author") or {}
            name = _g(author, "name")
            name = name.strip() if isinstance(name, str) else ""
            if name in allowed:
                continue
            rotulo = name if name else "(sem autor — commit órfão/rewritten)"
            findings.append(Finding(
                check=CHECK_ID, target=f"commit:{sha[:7]}",
                severity="regression",
                title=f"Commit de autor não autorizado: {sha[:7]}",
                body_md=(
                    f"O commit `{sha[:7]}` foi criado por **{rotulo}**, que "
                    "não está em `allowed_authors` (papéis legítimos: "
                    f"{', '.join(sorted(allowed))} — ver GOVERNANCE.md).\n\n"
                    f"- sha: `{sha}`\n"
                    f"- autor: `{rotulo}`\n"
                    f"- mensagem: {_first_line(_commit_message(commit_obj))}\n\n"
                    "Orientação: **auditar o push imediatamente** — conferir "
                    "se houve force-push/commit forjado, rever o reflog do "
                    "remoto e reescrever o histórico se a identidade não "
                    "for legítima."),
                fingerprint=f"{CHECK_ID}:commits:autor-nao-autorizado:{sha[:7]}"))

    # ------------------------------------------------------------- resumo
    if api_failures and not findings:
        findings.append(Finding(
            check=CHECK_ID, target="github-api",
            severity="info",
            title="API do GitHub indisponível — governança parcial",
            body_md=(
                f"{api_failures} chamada(s) à API do GitHub falharam "
                "(rate limit/rede/instabilidade) e NENHUMA sub-verificação "
                "que depende de API produziu resultado. As verificações "
                "somente-arquivo (templates/workflows) foram executadas. "
                "Re-executar o bot quando a API responder."),
            fingerprint=f"{CHECK_ID}:api-indisponivel"))

    notes = (f"milestones_ok={learn['milestones_ok']}; "
             f"labels vivas={learn['labels_count']}; "
             f"commits auditados={len(commits)}; "
             f"changelog via {changelog_mode}; "
             f"falhas de API={api_failures}")
    # "immediate": o payload carrega fatos por-execução (labels_count,
    # last_audited_sha) e a âncora prospectiva bot_since_sha, que PRECISA
    # persistir na primeira execução — confirmação por igualdade de payload
    # nunca convergiria aqui.
    return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                       ran=True, learn_mode="immediate", notes=notes)
