"""Contrato base do APKBot — tipos compartilhados entre dispatcher e checks.

Este módulo é a interface congelada do APKBot: os módulos em ``bot/checks/``
são escritos contra EXATAMENTE estas estruturas, portanto qualquer mudança
aqui exige revisão de todos os checks.

- ``Finding``: um achado individual (regressão, drift, novo, flaky, info);
- ``CheckResult``: retorno obrigatório de ``run(ctx)`` de cada check;
- ``BotContext``: contexto injetado pelo dispatcher (repo, estado, cfg, gh).

Convenção do projeto: identificadores em inglês, textos/evidências em PT-BR,
sem emojis, apenas python3 stdlib.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Finding:
    check: str          # CHECK_ID do módulo
    target: str         # alvo (ex.: "gen-textures.py", "engine-13-flutter", "labels")
    severity: str       # "regression" | "drift" | "new" | "flaky" | "info"
    title: str          # curto, PT-BR
    body_md: str        # evidência em markdown PT-BR
    fingerprint: str    # chave estável única: f"{check}:{target}:{kind}"


@dataclass
class CheckResult:
    check: str
    findings: list = field(default_factory=list)   # list[Finding]
    learn: dict = field(default_factory=dict)      # baseline novo p/ este check (mesclado no estado)
    ran: bool = True
    notes: str = ""     # PT-BR; preencher quando ran=False (ex.: "sem rede", "gh indisponível")
    # Política de aprendizado do payload ``learn``:
    # - "merge" (padrão): confirmação múltipla anti-flake — o payload só vira
    #   baseline após N execuções idênticas (cfg.confirmations_for_new);
    # - "immediate": aplicado na mesma execução, SEM confirmação — usar quando
    #   o payload é fato por-execução ou série temporal carregada para frente
    #   pelo próprio check (ex.: samples de size_drift), onde confirmação por
    #   igualdade de payload nunca convergiria.
    learn_mode: str = "merge"


@dataclass
class BotContext:
    repo_path: Any      # pathlib.Path do checkout
    state: dict         # bot/state/bot-state.json carregado ({} se ausente)
    now: str            # data ISO UTC desta execução
    gh: Optional[Any]   # bot.lib.github_api.GitHubAPI ou None (modo --local)
    cfg: dict           # bot/bot-config.json carregado
    dry_run: bool = False
