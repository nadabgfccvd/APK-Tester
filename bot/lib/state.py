"""Persistência e utilidades de estado do APKBot (bot/state/bot-state.json).

O estado é a memória do bot entre execuções e é commitado no próprio
repositório. Tudo aqui é tolerante: estado ausente ou corrompido nunca derruba
a execução — um esquema novo é iniciado e a ocorrência é registrada como nota.

Convenções de formato:
- JSON ordenado por chave (``sort_keys``), indentado, ``ensure_ascii=False``
  e com newline final (diff estável);
- ``updated`` recebe a data ISO UTC no momento de cada gravação.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path

SCHEMA_VERSION = 1
LOAD_NOTES_KEY = "_load_notes"  # notas de carga; consumidas e removidas pelo dispatcher


def utcnow_iso():
    """Data ISO UTC compacta (ex.: 2026-02-01T12:00:00Z)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fresh_state():
    """Esquema inicial do estado (versão 1)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "bot": "apkbot",
        "updated": None,
        "runs": [],
        "baselines": {},
        "confirmations": {},
        "open_issues": {},
        "flap_history": {},
    }


def load_state(path):
    """Carrega o estado de forma tolerante.

    - arquivo ausente: esquema novo;
    - JSON corrompido/ilegível/raiz inválida: esquema novo + nota em
      ``state[LOAD_NOTES_KEY]`` (o dispatcher consome e remove a chave antes
      de persistir, então a nota aparece uma única vez);
    - chaves novas do esquema são preservadas mesmo ausentes no arquivo.
    """
    file_path = Path(path)
    if not file_path.exists():
        return fresh_state()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("raiz do estado não é um objeto JSON")
    except (OSError, ValueError) as exc:
        loaded = fresh_state()
        loaded[LOAD_NOTES_KEY] = [
            f"estado anterior ilegível ou corrompido ({exc}); esquema novo iniciado"
        ]
        return loaded
    state = fresh_state()
    deep_merge(state, data)
    return state


def save_state(path, state):
    """Grava o estado (escrita atômica) e carimba ``updated`` em ISO UTC."""
    state["updated"] = utcnow_iso()
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    tmp_path = file_path.with_name(file_path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, file_path)
    return state


def deep_merge(dst, src):
    """Mescla recursivamente ``src`` em ``dst`` (dicts recursivos; resto substitui)."""
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def dict_sha256(obj):
    """Hash estável de um objeto serializável (json sort_keys + sha256)."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cap_runs(state, n=30):
    """Mantém apenas as últimas ``n`` execuções em ``state["runs"]``."""
    runs = state.get("runs")
    if not isinstance(runs, list):
        runs = []
    state["runs"] = runs[-int(n):]
    return state
