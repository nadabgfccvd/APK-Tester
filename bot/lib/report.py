"""Renderização dos relatórios do APKBot (markdown PT-BR, sem emojis).

Funções:
- ``summary_md``: relatório da execução (uma seção por check + contagens);
- ``issue_body``: corpo padrão de issue aberta pelo bot;
- ``comment_body``: comentário de atualização com evidência fresca;
- ``close_comment``: comentário de fechamento (o dispatcher prefixa a data).

As tags de severidade são textuais (nada de emojis):
``[REGRESSÃO]``, ``[DRIFT]``, ``[NOVO]``, ``[FLAKY]``, ``[INFO]``.
"""

SEVERITY_TAGS = {
    "regression": "[REGRESSÃO]",
    "drift": "[DRIFT]",
    "new": "[NOVO]",
    "flaky": "[FLAKY]",
    "info": "[INFO]",
}
SEVERITY_ORDER = ("regression", "drift", "new", "flaky", "info")
STATUS_OK = "[OK]"
STATUS_FOUND = "[ACHOU]"
STATUS_SKIPPED = "[NÃO EXECUTADO]"


def _tag(severity):
    return SEVERITY_TAGS.get(severity, "[INFO]")


def _counts(results):
    """Contagem de findings por severidade (todas as chaves, zeradas inclusive)."""
    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for result in results:
        for finding in getattr(result, "findings", []) or []:
            severity = getattr(finding, "severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
    return counts


def summary_md(results, state, cfg):
    """Relatório da execução: cabeçalho, contagens e uma seção por check."""
    counts = _counts(results)
    total = sum(counts.values())
    ran_count = sum(1 for result in results if getattr(result, "ran", False))
    runs = state.get("runs") or []
    date = runs[-1].get("date", "?") if runs else "?"
    lines = [
        "# Relatório do APKBot",
        "",
        f"- Data (UTC): {date}",
        f"- Bot: `{state.get('bot', 'apkbot')}` · execução nº {len(runs)} registrada no estado",
        f"- Checks: {ran_count}/{len(results)} executados · findings: {total}",
        "",
        "## Contagens por severidade",
        "",
        "| Severidade | Quantidade |",
        "|---|---|",
    ]
    for severity in SEVERITY_ORDER:
        lines.append(f"| {_tag(severity)} `{severity}` | {counts.get(severity, 0)} |")
    lines.append("")
    for result in results:
        check = getattr(result, "check", "?")
        lines.append(f"## Check: {check}")
        lines.append("")
        if not getattr(result, "ran", False):
            lines.append(f"Status: {STATUS_SKIPPED}")
            note = getattr(result, "notes", "") or "sem detalhes"
            lines.append(f"Nota: {note}")
            lines.append("")
            continue
        findings = getattr(result, "findings", []) or []
        lines.append(f"Status: {STATUS_FOUND if findings else STATUS_OK} ({len(findings)} finding(s))")
        for finding in findings:
            title = getattr(finding, "title", "")
            target = getattr(finding, "target", "")
            fingerprint = getattr(finding, "fingerprint", "")
            severity = getattr(finding, "severity", "info")
            lines.append(
                f"- **{_tag(severity)}** {title} — alvo: `{target}` · fingerprint: `{fingerprint}`"
            )
            body = (getattr(finding, "body_md", "") or "").strip()
            if body:
                for body_line in body.splitlines():
                    lines.append(f"  {body_line}" if body_line else "")
        note = getattr(result, "notes", "")
        if note:
            lines.append(f"Nota: {note}")
        lines.append("")
    lines.append("---")
    lines.append(
        f"Configuração: `bot/bot-config.json` (state_path `{cfg.get('state_path', 'bot/state/bot-state.json')}`, "
        f"confirmações para novo baseline: {cfg.get('confirmations_for_new', 2)})."
    )
    lines.append("")
    return "\n".join(lines)


def issue_body(finding, run_info):
    """Corpo padrão do issue: evidência + execução + instruções de triagem."""
    run_id = (run_info or {}).get("run_id", "local")
    date = (run_info or {}).get("date", "desconhecida")
    tag = _tag(getattr(finding, "severity", "info"))
    check = getattr(finding, "check", "")
    parts = [
        f"## {tag} {getattr(finding, 'title', '')}",
        "",
        f"- **Check:** `{check}`",
        f"- **Alvo:** `{getattr(finding, 'target', '')}`",
        f"- **Severidade:** `{getattr(finding, 'severity', 'info')}`",
        f"- **Fingerprint:** `{getattr(finding, 'fingerprint', '')}`",
        "",
        "### Evidência",
        "",
        (getattr(finding, "body_md", "") or "").strip() or "_sem evidência adicional_",
        "",
        "---",
        "",
        f"Gerado pelo APKBot — execução `{run_id}` em {date}.",
        "",
        "### Instruções de triagem",
        f"1. Reproduza localmente: `python3 bot/apkbot.py --local --dry-run --check {check}`.",
        "2. Se for regressão real, corrija no código/gerador: o APKBot fecha este issue",
        "   automaticamente quando o fingerprint deixar de aparecer.",
        "3. Se for mudança esperada, atualize o baseline em `bot/state/bot-state.json`",
        "   (o protocolo de aprendizado confirma o novo baseline em N execuções — ver bot/README.md).",
        "4. Não feche manualmente: o mesmo fingerprint reabre o acompanhamento se voltar.",
    ]
    return "\n".join(parts) + "\n"


def comment_body(finding):
    """Comentário de atualização: evidência fresca para um issue já aberto."""
    tag = _tag(getattr(finding, "severity", "info"))
    parts = [
        f"### Evidência atualizada {tag}",
        "",
        (getattr(finding, "body_md", "") or "").strip() or "_sem evidência adicional nesta execução_",
        "",
        "---",
        f"Comentário automático do APKBot · fingerprint `{getattr(finding, 'fingerprint', '')}`.",
    ]
    return "\n".join(parts) + "\n"


def close_comment(finding):
    """Comentário de fechamento; o chamador prefixa a data (\"Resolvido na execução ...\")."""
    tag = _tag(getattr(finding, "severity", "info"))
    parts = [
        f"### {tag} não reproduzido",
        "",
        f"O fingerprint `{getattr(finding, 'fingerprint', '')}` (alvo `{getattr(finding, 'target', '')}`)",
        "não apareceu nos resultados da execução mais recente. O issue é fechado",
        "automaticamente; se o fingerprint voltar a aparecer, o APKBot registra a",
        "reincidência em `flap_history` e abre acompanhamento novo.",
    ]
    return "\n".join(parts) + "\n"
