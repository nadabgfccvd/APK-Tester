#!/usr/bin/env python3
"""bot/checks/answerkey_drift.py — drift do answer key de engines vs RustyDroid.

Verificação que o CI NÃO consegue fazer: compara o catálogo local
(``contracts/engines/expected-engines.json``, campo ``language``) com o
registro de engines do repositório IRMÃO RustyDroid (Apêndice G), buscado
via API do GitHub em tempo de execução (``ctx.gh.get_file_contents``).

Regras:
- Percorre ``cfg.rustydroid.candidate_paths`` em ordem; usa o PRIMEIRO
  arquivo que baixar OK. O sha256 do conteúdo bruto vai para ``learn``.
- Extração PRAGMÁTICA: coleta as linhas de tabela markdown do arquivo
  escolhido; a coluna de nomes é detectada pelo cabeçalho
  (linguagem/language/engine/framework). Linhas fora de tabela que casam
  ``engine[_ -]?(id|name)?s?[:|]`` alimentam apenas a união de tokens.
- Só compara com confiança se houver >= 20 linhas nomeadas; caso contrário
  emite Finding "info" (...:registry:extracao-inconclusiva) e guarda o sha
  para diff futuro. NUNCA é falha: fonte inacessível (privado/movido/offline)
  => CheckResult(ran=False).
- Correspondência de nomes é por TOKENS (3 níveis: subconjunto mútuo,
  união, token de cabeça) — tolera granularidade diferente entre os dois
  repositórios (ex.: "Scala / Clojure / Groovy" numa linha só no irmão).
  A señal confiável de mudança é o sha256 do arquivo vs baseline.

Além do sha BRUTO, a mudança de arquivo ganha DIFF DE CONTEÚDO: os nomes
de engine extraídos são comparados LITERALMENTE com os nomes do baseline
(as duas pontas vêm do mesmo extrator — granularidade idêntica) e o corpo
do finding lista "entraram"/"saíram" — o alinhamento humano começa sabendo
O QUE mudou, não apenas que o arquivo mudou.

Findings:
- "new"        ...:registry:engine-novo-em-rustydroid (fixture precisa ser criada, A3/A4)
- "regression" ...:registry:engine-sumiu-do-irmao    (drift do answer key vs fonte da verdade)
- "drift"      ...:registry:arquivo-mudou            (re-executar alinhamento humano)
- "info"       ...:registry:extracao-inconclusiva    (extração fraca; sha guardado)
"""

import json
import re
import sys
import hashlib
from pathlib import Path

CHECK_ID = "answerkey_drift"

# Defaults inline (usados quando cfg.rustydroid ausente no bot-config.json).
# ATENÇÃO (A9/roadmap 4.6): candidate_paths são caminhos REMOTOS no repo
# IRMÃO nadabgfccvd/RustyDroid (baixados via ctx.gh.get_file_contents) —
# NÃO arquivos locais deste repositório; um auditor standalone não deve
# tentar resolvê-los em disco (data/engines.toml vive no irmão, não aqui).
RUSTYDROID_DEFAULTS = {
    "owner": "nadabgfccvd",
    "repo": "RustyDroid",
    "branch": "main",
    "candidate_paths": [
        "docs/engine-registry.md",   # registro gerado (Apêndice G) do irmão
        "README.md",                 # seção Apêndice G no README
        "data/engines.toml",         # fonte bruta do registro (remoto, irmão)
        "docs/src/apendice-g.md",
        "APENDICE-G.md",
    ],
}

MIN_NAMED_ROWS = 20          # confiança mínima para comparar nomes
MAX_LIST_BODY = 40           # nomes exibidos por finding (resto é contado)
MAX_LEARN_NAMES = 80         # learn "names" capsulado para não inflar o estado

_HEADER_HINTS = ("linguagem", "language", "engine", "framework")
_LINE_KEYS_RE = re.compile(r"(?i)\bengine[_ -]?(?:id|name)?s?\s*[:|]\s*(.+)")
_SEP_ROW_RE = re.compile(r"^:?-{3,}:?$")
# "+" FORA da classe: ele é SEPARADOR em nomes compostos do answer key
# (ex.: "Kotlin+Rust+Hermes+WASM" → kotlin/rust/hermes/wasm). Dentro dele,
# o nome virava UM token único e a cobertura por tokens nunca casava
# (falso "engine-sumiu-do-irmao" a cada execução confiante). "C#" e "C++"
# continuam inteiros via "#" e recorte em "+" ("c++" → "c", cabeça válida).
_TOKEN_RE = re.compile(r"[a-z0-9#]+")
# Palavras de ligação/decoração descartadas na normalização dos dois lados.
_STOPWORDS = {
    "in", "app", "host", "embutido", "cross", "via", "outra", "outras",
    "linguagem", "linguagens", "language", "languages", "other", "others",
    "and", "ou", "e", "de", "da", "do", "em", "runtime",
}
# Mesmo conceito, grafia diferente entre os repositórios.
_SYNONYMS = {"webassembly": "wasm", "javascript": "js"}

_CHECKS_DIR = Path(__file__).resolve()
for _p in (_CHECKS_DIR.parents[2], _CHECKS_DIR.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from bot.lib.base import CheckResult, Finding
except ImportError:  # fallback: árvore bot/ sem o pacote "bot" (layout antigo)
    from lib.base import CheckResult, Finding  # type: ignore


# ------------------------------------------------------------------ helpers
def _tokens(name: str):
    """Tokens normalizados (lista ordenada + conjunto) de um nome de engine."""
    toks = []
    for raw in _TOKEN_RE.findall(name.lower()):
        tok = _SYNONYMS.get(raw, raw)
        if tok in _STOPWORDS or tok.isdigit():
            continue
        if tok not in toks:
            toks.append(tok)
    return toks, set(toks)


def _covered(toks, toksets, union):
    """Nome está "presente" do outro lado? (3 níveis pragmáticos).

    ``toks`` é a lista ORDENADA de tokens de ``_tokens(name)[0]``; os testes
    de subconjunto usam o conjunto derivado dela e o token de cabeça usa a
    própria lista (só listas fatiam). (A9: antes convertia errado e qualquer
    execução com extração confiante crashava — branch morto em produção.)
    """
    if not toks:
        return False
    tokset = set(toks)
    for other in toksets:
        if tokset <= other or other <= tokset:
            return True
    if tokset <= union:
        return True
    return any(t in union for t in toks[:2])  # token de cabeça (família)


def _norm_name(name: str) -> str:
    """Normalização literal leve para diff (caixa + espaços internos)."""
    return " ".join(name.lower().split())


def _names_diff(current, previous):
    """Diff LITERAL de nomes extraídos (entraram, saíram).

    As duas pontas vêm do MESMO extrator (baseline guarda a extração desta
    própria verificação), logo a granularidade é idêntica — a comparação
    correta aqui é a literal. (Cobertura por tokens seria tolerante demais:
    renomear "Java" para "Java (OpenJDK)" não apareceria como mudança, e o
    propósito do diff é justamente mostrar o que mudou no registro.)
    """
    prev_set = {_norm_name(n) for n in previous}
    cur_set = {_norm_name(n) for n in current}
    entraram = [n for n in current if _norm_name(n) not in prev_set]
    sairam = [n for n in previous if _norm_name(n) not in cur_set]
    return entraram, sairam


def _table_blocks(text: str):
    """Blocos de tabela markdown: lista de linhas já divididas em células."""
    blocks, current = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            current.append(cells)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def _split_rows(block):
    """Separa cabeçalho de linhas de dados (pula linha separadora ---)."""
    if not block:
        return [], []
    header, rows = block[0], []
    for cells in block[1:]:
        if cells and all(_SEP_ROW_RE.match(c) for c in cells if c != ""):
            continue
        if cells and any(c for c in cells):
            rows.append(cells)
    return header, rows


def _extract_registry(text: str):
    """Extrai (nomes_da_coluna, união_de_tokens, linhas_nomeadas) do arquivo.

    Estratégia pragmática: procura a tabela cujo cabeçalho cita
    linguagem/engine/framework e usa essa coluna como lista canônica;
    TODAS as células de TODAS as tabelas alimentam a união de tokens
    (necessário para fixtures híbridas, ex. Kotlin+Rust+Hermes+WASM).
    """
    all_cells = []
    best = None  # (qtd_linhas, nomes)
    for block in _table_blocks(text):
        header, rows = _split_rows(block)
        for cells in block:
            all_cells.extend(cells)
        idx = None
        for i, cell in enumerate(header):
            if any(h in cell.lower() for h in _HEADER_HINTS):
                idx = i
                break
        if idx is None or not rows:
            continue
        names = [r[idx] for r in rows if idx < len(r) and r[idx].strip()]
        if best is None or len(names) > len(best[1]):
            best = (len(rows), names)
    extra = []
    for line in text.splitlines():
        m = _LINE_KEYS_RE.search(line)
        if m and not line.strip().startswith("|"):
            for part in re.split(r"[,;|/]", m.group(1)):
                part = part.strip()
                if part:
                    extra.append(part)
    union = set()
    for cell in all_cells:
        union |= _tokens(cell)[1]
    for name in extra:
        union |= _tokens(name)[1]
    if best is not None:
        named_rows, names = best
    else:
        named_rows, names = 0, []
    return names, union, named_rows


def _load_local_names(repo_path: Path):
    """Nomes de linguagem do answer key local; (None, erro) se ilegível."""
    path = repo_path / "contracts" / "engines" / "expected-engines.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    engines = data.get("engines") if isinstance(data, dict) else None
    if not isinstance(engines, list):
        return None, "JSON sem lista 'engines'"
    names = sorted({
        e.get("language") for e in engines
        if isinstance(e, dict) and isinstance(e.get("language"), str) and e.get("language").strip()
    })
    return names, None


def _cap(items, limit=MAX_LIST_BODY):
    items = list(items)
    if len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


# ---------------------------------------------------------------------- run
def run(ctx) -> CheckResult:
    repo = Path(str(ctx.repo_path))
    findings = []
    learn = {}

    if ctx.gh is None:
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes="modo local (--local): RustyDroid requer "
                                 "acesso GitHub; verificação pulada")

    cfg_r = dict(RUSTYDROID_DEFAULTS)
    cfg_r.update(ctx.cfg.get("rustydroid") or {})
    owner = cfg_r.get("owner") or RUSTYDROID_DEFAULTS["owner"]
    repo_name = cfg_r.get("repo") or RUSTYDROID_DEFAULTS["repo"]
    branch = cfg_r.get("branch") or RUSTYDROID_DEFAULTS["branch"]
    paths = cfg_r.get("candidate_paths") or RUSTYDROID_DEFAULTS["candidate_paths"]

    # 1) Busca: primeiro arquivo candidado que baixar OK (nunca lança).
    text, source_path = None, None
    for cand in paths:
        try:
            content = ctx.gh.get_file_contents(owner, repo_name, cand, branch)
        except Exception:
            content = None
        if isinstance(content, str) and content.strip():
            text, source_path = content, cand
            break
        if isinstance(content, bytes) and content.strip():
            text = content.decode("utf-8", "replace")
            source_path = cand
            break
    if text is None:
        return CheckResult(check=CHECK_ID, findings=[], learn={},
                           ran=False,
                           notes="RustyDroid inacessível (privado/movido): "
                                 "verificação pulada")

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # 2) Answer key local.
    local_names, err = _load_local_names(repo)
    if err is not None:
        findings.append(Finding(
            check=CHECK_ID, target="contracts/engines/expected-engines.json",
            severity="info",
            title="Answer key local ilegível — comparação de engines pulada",
            body_md=(
                "Não foi possível ler `contracts/engines/expected-engines.json` "
                f"({err}). O sha do registro remoto segue em `learn` para diff "
                "futuro, mas a comparação de nomes ficou indisponível nesta "
                "execução."),
            fingerprint=f"{CHECK_ID}:local:answerkey-ilegivel"))

    # 3) Extração do registro remoto.
    names, reg_union, named_rows = _extract_registry(text)
    confident = named_rows >= MIN_NAMED_ROWS and bool(names)

    # 4) Drift do arquivo vs baseline (sempre; independe da confiança).
    #    A9: a evidência ganhou DIFF DE CONTEÚDO — nomes extraídos agora vs
    #    nomes guardados no baseline (diff literal; extração idêntica nas
    #    duas pontas), para que o alinhamento humano comece sabendo O QUE
    #    mudou no Apêndice G.
    baseline = (ctx.state.get("baselines") or {}).get(CHECK_ID, {}) \
        if isinstance(ctx.state, dict) else {}
    old_sha = baseline.get("registry_sha")
    if old_sha and old_sha != sha:
        old_names = [n for n in (baseline.get("names") or [])
                     if isinstance(n, str) and n.strip()]
        entraram, sairam = _names_diff(names, old_names)
        diff_md = ""
        if not old_names:
            diff_md = (
                "\n\nO baseline não carrega nomes extraídos (fonte anterior "
                "sem tabela confiável) — o diff de conteúdo começa nesta "
                "execução; as próximas mudanças trazem entraram/saíram.")
        else:
            shown_in, extra_in = _cap(entraram)
            shown_out, extra_out = _cap(sairam)
            entraram_txt = "".join(f"- `{n}`\n" for n in shown_in) \
                or "- (nenhum)\n"
            sairam_txt = "".join(f"- `{n}`\n" for n in shown_out) \
                or "- (nenhum)\n"
            diff_md = (
                "\n\n**Diff de conteúdo do registro** (nomes extraídos agora vs "
                "nomes do baseline — extração idêntica nas duas pontas, "
                "diff literal):\n\n"
                "Entraram no registro:\n" + entraram_txt)
            if extra_in:
                diff_md += f"\n(e mais {extra_in} entradas)\n"
            diff_md += "\nSaíram do registro:\n" + sairam_txt
            if extra_out:
                diff_md += f"\n(e mais {extra_out} saídas)\n"
        findings.append(Finding(
            check=CHECK_ID, target=f"rustydroid:{source_path}",
            severity="drift",
            title="Arquivo do registro de engines do irmão mudou",
            body_md=(
                f"O sha256 de `{source_path}` (RustyDroid `{owner}/{repo_name}`) "
                f"mudou desde a última execução do bot:\n\n"
                f"- baseline: `{old_sha}`\n- atual: `{sha}`\n\n"
                + diff_md +
                "\nAção: re-executar o alinhamento humano Apêndice G vs "
                "`contracts/engines/expected-engines.json` e conferir se novas "
                "fixtures (A3/A4) ou remoções precisam entrar no answer key."),
            fingerprint=f"{CHECK_ID}:registry:arquivo-mudou"))

    # 5) Comparação de nomes (só com confiança >= 20 linhas nomeadas).
    if confident and local_names is not None:
        local_toksets = [_tokens(n)[1] for n in local_names]
        local_union = set()
        for n in local_names:
            local_union |= _tokens(n)[1]
        reg_toksets, seen = [], set()
        for n in names:
            key = n.lower()
            if key in seen:
                continue
            seen.add(key)
            reg_toksets.append(_tokens(n)[1])

        novos, sumidos = [], []
        for n in names:
            if n.lower() in {name.lower() for name in local_names}:
                continue
            if not _covered(_tokens(n)[0], local_toksets, local_union):
                novos.append(n)
        for n in local_names:
            if not _covered(_tokens(n)[0], reg_toksets, reg_union):
                sumidos.append(n)

        if novos:
            shown, extra = _cap(novos)
            extra_txt = f"\n\n(e mais {extra} novos…)" if extra else ""
            findings.append(Finding(
                check=CHECK_ID, target=f"rustydroid:{source_path}",
                severity="new",
                title="Novo engine no registro do RustyDroid (Apêndice G)",
                body_md=(
                    "Estes engines apareceram no Apêndice G do irmão e não "
                    "existem no answer key local; **fixture precisa ser criada "
                    "(A3/A4)** e `expected-engines.json` atualizado:\n\n"
                    + "\n".join(f"- `{n}`" for n in shown)
                    + extra_txt + f"\n\nFonte: `{source_path}` (sha `{sha[:12]}…`)."),
                fingerprint=f"{CHECK_ID}:registry:engine-novo-em-rustydroid"))
        if sumidos:
            shown, extra = _cap(sumidos)
            extra_txt = f"\n\n(e mais {extra} locais…)" if extra else ""
            findings.append(Finding(
                check=CHECK_ID,
                target="contracts/engines/expected-engines.json",
                severity="regression",
                title="Engine do answer key local ausente no registro do irmão",
                body_md=(
                    "Estes engines existem em `expected-engines.json` mas não "
                    "foram encontrados no registro do RustyDroid — **drift do "
                    "answer key vs fonte da verdade**. Ou o irmão removeu/"
                    "renomeou o engine, ou o nome local está desalinhado:\n\n"
                    + "\n".join(f"- `{n}`" for n in shown)
                    + extra_txt + f"\n\nFonte: `{source_path}` (sha `{sha[:12]}…`)."),
                fingerprint=f"{CHECK_ID}:registry:engine-sumiu-do-irmao"))
    elif local_names is not None:
        findings.append(Finding(
            check=CHECK_ID, target=f"rustydroid:{source_path}",
            severity="info",
            title="Extração do registro remoto inconclusiva",
            body_md=(
                f"O arquivo `{source_path}` foi baixado, mas a extração não "
                f"atingiu o limiar de confiança ({named_rows} linhas nomeadas; "
                f"mínimo {MIN_NAMED_ROWS}). A comparação de nomes foi pulada "
                "para evitar falsos positivos; o sha256 bruto foi registrado "
                "em `learn` — na próxima execução com baseline, qualquer "
                "mudança no arquivo dispara o finding de drift e re-execução "
                "do alinhamento humano."),
            fingerprint=f"{CHECK_ID}:registry:extracao-inconclusiva"))

    learn = {
        "registry_sha": sha,
        "names": [n for n in names][:MAX_LEARN_NAMES],
        "source_path": source_path,
        "named_rows": named_rows,
        "confident": confident,
        "local_names_count": (len(local_names) if local_names is not None else 0),
    }
    notes = (f"RustyDroid {owner}/{repo_name}@{branch} via `{source_path}`; "
             f"{named_rows} linhas nomeadas; confiança="
             f"{'ok' if confident else 'baixa'}")
    return CheckResult(check=CHECK_ID, findings=findings, learn=learn,
                       ran=True, notes=notes)
