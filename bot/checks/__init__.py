"""Registro e descoberta dos checks do APKBot.

Cada check vive em ``bot/checks/<id>.py`` e segue o contrato de
``bot/lib/base.py``: define ``CHECK_ID`` e ``run(ctx) -> CheckResult``.
A descoberta é tolerante: módulo ausente, quebrado ou fora do contrato não
derruba a execução — vira nota no relatório.
"""

import importlib

CHECK_MODULES = [
    "determinism",
    "flakiness",
    "staleness",
    "engine_matrix",
    "answerkey_drift",
    "permission_drift",
    "size_drift",
    "governance",
    "locale_sync",
    "activity_coverage",
]


def discover(check_ids=None):
    """Importa cada check de forma tolerante.

    Retorna ``(loaded, notes)``:
    - ``loaded``: dict ``id -> módulo ou None`` (None = indisponível);
    - ``notes``: mensagens PT-BR explicando cada indisponibilidade
      ("módulo ausente", falha de import ou descumprimento do contrato).
    """
    ids = list(check_ids) if check_ids else list(CHECK_MODULES)
    loaded, notes = {}, []
    for check_id in ids:
        try:
            module = importlib.import_module(f"bot.checks.{check_id}")
        except ImportError as exc:
            loaded[check_id] = None
            notes.append(f"check '{check_id}': módulo ausente ({exc})")
            continue
        except Exception as exc:  # erro de sintaxe/execução durante o import
            loaded[check_id] = None
            notes.append(f"check '{check_id}': falha ao importar ({type(exc).__name__}: {exc})")
            continue
        if not hasattr(module, "CHECK_ID") or not callable(getattr(module, "run", None)):
            loaded[check_id] = None
            notes.append(f"check '{check_id}': não segue o contrato (CHECK_ID/run ausentes)")
            continue
        loaded[check_id] = module
    return loaded, notes
