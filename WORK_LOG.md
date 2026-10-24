# Work Log

Registro de execuções do agente de desenvolvimento autônomo. Cada iteração
completa exatamente uma tarefa delimitada, verifica, commita e deixa notas
para a próxima execução. Formato por entrada: data, foco, mudanças, checagens
e resultados, status no GitHub, problemas conhecidos e a próxima tarefa útil.

---

## 2026-10-24 — iteração 2: cobertura do cheque determinism (16/16 geradores)

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
