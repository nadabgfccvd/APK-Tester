# Work Log

Registro de execuções do agente de desenvolvimento autônomo. Cada iteração
completa exatamente uma tarefa delimitada, verifica, commita e deixa notas
para a próxima execução. Formato por entrada: data, foco, mudanças, checagens
e resultados, status no GitHub, problemas conhecidos e a próxima tarefa útil.

---

## 2026-10-24 — iteração 3: roadmap W7 — answerkey_drift vivo e flakiness completo

**Foco escolhido.** "Solve all of this roadmap": as duas tarefas apontadas
pelo WORK_LOG da iteração 2 (cheque `flakiness` exercitar o
`scripts/compat-nightly.sh`; `answerkey_drift` diffar CONTEÚDO e não só o
sha do README) + a auditoria de continuidade pós-sandbox (clone novo,
PAT novo, árvore avançada a A9/W6 por iterações entre tanto).

**Achados da auditoria (antes de qualquer mudança).**
1. CRASH LATENTE em `bot/checks/answerkey_drift.py`: `_covered` recebia a
   lista ordenada de tokens e testava `<=` contra conjuntos (`list <= set`
   → `TypeError`). O branch de comparação de nomes era morto em produção —
   a config apontava o README do irmão (extração inconclusiva, branch
   nunca executado), então o crash nunca veio à tona.
2. `_TOKEN_RE` incluía `+` na classe: `Kotlin+Rust+Hermes+WASM` virava UM
   token único; com o branch vivo, viraria falso `engine-sumiu-do-irmao`
   a cada execução confiante.
3. `bot/bot-config.json` ignorava `docs/engine-registry.md` (o registro
   GERADO do irmão, presente nos defaults do código desde o 4.6): extração
   do README = 0 linhas nomeadas; do registry = 28 (confiante).

**Mudanças** (4 arquivos; nenhum byte de artefato/contrato mudou):
- `bot/checks/answerkey_drift.py`: `_covered` converte para conjunto
  internamente (lista segue alimentando o token de cabeça); `_TOKEN_RE`
  perde o `+` (é SEPARADOR em nomes compostos; `C#`/`C++` inteiros via
  `#`/recorte); o finding de drift do registro ganha DIFF DE CONTEÚDO
  (entraram/saíram, diff LITERAL — as duas pontas vêm do mesmo extrator;
  token coverage esconderia renomear "Java" → "Java (OpenJDK)"); docstring
  atualizada.
- `bot/bot-config.json`: `candidate_paths` passa a preferir
  `docs/engine-registry.md` (README segue como fallback).
- `bot/checks/flakiness.py`: novo modo "clone" de alvo — o
  `compat-nightly.sh` roda em clone raso TEMPORÁRIO (`git clone --depth 1`
  para mktemp; escrita de `docs/compat-matrix.md` fica dentro do clone,
  descartado no finally; a lei "o APKBot nunca modifica o worktree"
  segue valendo). Sem git/clone falho → INFO único com o motivo (nunca
  falha). Eliminado o finding INFO permanente
  `flakiness:compat-nightly:execucao-pulada`.
- `CHANGELOG.md`: seção `[Unreleased] / Corrigido (A9 — auditoria de
  continuidade, roadmap W7)` com as quatro entradas.

**Checagens e resultados.**
- Simulação ponta a ponta do `answerkey_drift` com `gh` falso e a fonte
  canônica: execução limpa (0 findings, 28 nomes, confiante — antes:
  crash); segunda execução estável (0 findings); terceira com registro
  modificado → drift com diff exato (`Java (OpenJDK)`/`Rust` entraram;
  `Java`/`Rust (cargo-ndk/xbuild)` saíram).
- Simulação do `flakiness` (2 reps): 19 alvos, 0 findings,
  `compat-nightly` com durações reais (~30 ms por execução, CV 0.05) e
  `git status` limpo após a execução (worktree intocado); path de
  degradação simulado (git indisponível) → INFO com motivo.
- `ruff check bot/ tools/` (0.17.2, seleção do repo): All checks passed.
- `python3 bot/apkbot.py --local`: `flakiness` [OK] (0) — era [ACHOU]
  com INFO permanente; findings totais da rodada local 9 → 6 (o resto:
  4 `determinism` transitórios de evolução de fonte pendentes de
  confirmação no CI + INFO de marcadores de dívida (0 ocorrências) +
  `size_drift` já re-baselado no CI). Estado local restaurado ao HEAD
  após cada diagnóstico (`git checkout -- bot/state/bot-state.json`).
- `py_compile` nos módulos alterados: OK.

**Status no GitHub.** Commit na `main` (push direto, convenção do repo).
Esperado na PRÓXIMA execução do APKBot no CI: UMA finding `drift`
(`answerkey_drift:registry:arquivo-mudou`) — a transição de fonte
(README → engine-registry) muda o sha monitorado por design; o corpo do
finding já nasce com o diff de conteúdo (28 entradas) e a baseline
recomeça com nomes extraídos, habilitando diffs acionáveis dali em
diante.

**Próxima tarefa útil sugerida.** Roadmap W7 concluído; sem lacunas
conhecidas de cobertura no bot. Candidatos: (a) mover a extração do
`answerkey_drift` para consumir também `data/engines.toml` direto (a
fonte bruta — exigiria parser TOML stdlib; python 3.11+ tem tomllib,
pinar runtime), (b) versionar o schema do estado do bot (state v1 → v2)
se novos checks exigirem campos novos, (c) revisitar M10–M12 do irmão
quando o RustyDroid retomar (fora do escopo deste repo).
: cobertura do cheque determinism (16/16 geradores)

**Foco escolhido.** Auditoria ponta a ponta da árvore (estado, CI, issues,
milestones, selftests) apontou como defeito mais importante uma lacuna de
monitoramento: o cheque `determinism` do APKBot — a memória de drift
entre-tempos dos geradores — cobria 14 de 16 geradores. Os dois excluídos
eram justamente `gen-bulk` (o maior, 768 MiB de conteúdo do flagship) e
`gen-engine-fixtures` (payloads Tier C), reportados como findings INFO
`determinism:*:sem-manifest-json` em toda execução, sem baseline e sem learn.

**Causa raiz.**
1. `bot/checks/determinism.py::_collect_artifacts` só lia a chave
   `"artifacts"`; o manifest do `gen-bulk` declara os mesmos pares
   `{path, sha256}` sob a chave `"files"`.
2. `tools/gen-engine-fixtures.py` gravava apenas `tier-c-payload-report.json`
   (formato próprio, âncora commitada) — nenhum `manifest.json` convencional.

**Mudanças** (3 arquivos; nenhum byte de artefato existente mudou):
- `bot/checks/determinism.py`: `_collect_artifacts` aceita `"artifacts"` ou
  `"files"` (mesma forma de entrada); docstring documenta as duas formas.
- `tools/gen-engine-fixtures.py`: nova `write_out_manifest()` grava
  `<out>/manifest.json` no formato convencional (chave `"artifacts"`, paths
  relativos a `--out` com "/", sort_keys/indent 2, sem timestamps), cobrindo
  payloads + classes marcador Java e excluindo o próprio manifest e o report
  (mesmo com `--report` customizado); docstring e mensagem final atualizados;
  selftest ganhou prova "manifest ok": 2 escritas byte-idênticas, contagem
  exata (23 payloads + 7 java = 30 artefatos), sha256 re-verificado por
  entrada, chaves exatas e paths únicos.
- `CHANGELOG.md`: entrada em `[Unreleased] / Corrigido`.

**Checagens e resultados.**
- `python3 tools/gen-engine-fixtures.py --selftest` → OK (5/5 + 2 extras).
- Simulação do leitor do bot contra saídas reais: `gen-engine-fixtures` → 30
  artefatos; `gen-bulk` → 29 (antes: `None` nos dois).
- `bash tools/verify-deterministic.sh --mode generators` → PASS 16/16
  (zero FAIL; gen-engine-fixtures agora 32 arquivos idênticos ×2 execuções).
- `python3 bot/apkbot.py --local` → cheque `determinism` de `[ACHOU] (2 INFO)`
  para `[OK] (0)`; 16 geradores sondados, 16 com learn confirmável; findings
  totais 4 → 3 (restantes: notas INFO documentadas — skip do compat-nightly
  no cheque local e resumo de marcadores de dívida).
- 21 selftests dos gen-* + tier-a/tier-b/v1-gate → todos exit 0.
- APKBot --local executado 4× nesta iteração como diagnóstico; o estado local
  (`bot/state/bot-state.json`) foi restaurado ao HEAD após cada uso — o
  estado real é gerenciado pelo workflow APKBot no CI.

**Status no GitHub.** Commit `fix: auditoria ... determinism 16/16` na
`main` (push direto, convenção do repositório). CI/acompanhamento: ver
comentário da execução; CI anterior ao commit já estava verde (run
40049163653), release v1.0.0 publicada, milestones A0–A8 fechados, zero
issues abertas.

**Próxima tarefa útil sugerida.** O cheque `flakiness` pula
`scripts/compat-nightly.sh` no modo local porque o script escreve
`docs/compat-matrix.md` dentro do worktree (nota INFO documentada); rodá-lo
em clone temporário raso eliminaria a única cobertura honesta que falta ao
cheque local — custo moderado, benefício direto para a estabilidade do
nightly. Alternativa: ampliar `answerkey_drift` para diffar o conteúdo dos
Apêndices do RustyDroid e não apenas o sha do README.
