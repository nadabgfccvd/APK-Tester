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

**Follow-up da mesma iteração** (commit subsequente): a primeira execução
do APKBot no CI pós-clone (run 40076776161, success) mostrou que o
deep_merge do dispatcher preservou o `skipped` legado dentro de
`targets.compat-nightly` junto das durações novas — corrigido com
sobrescrita `skipped: null` nos alvos clone executados (nulo = exercitado;
skip futuro sobrescreve de volta com o motivo). Baseline do
`answerkey_drift` segue em confirmação (merge N=2): a transição de fonte
confirma na próxima execução agendada e o issue #20 fecha sozinho quando o
fingerprint estabilizar — comportamento desenhado, documentado no issue.

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

---

## Iteração 3 — 2026-10-24 — AUDIT_ROADMAP_V2 executado (R0–R4)

**Escopo:** roadmap completo da re-auditoria independente (AUDIT_ROADMAP_V2.md
do dono): R0 desbloqueio, R1 compat real, R2 substância do flagship, R3
observabilidade, R4 reconciliação.

### Executado e verificado

- **R0.1** `tools/build-tier-a.py`: guard `SPECS.get(engine, {})` no
  `--verify-apk` (commit 3bdd73f). KeyError do engine-04-scala nos 9 builds
  Tier B (run 40076184463) eliminado; aceite provado localmente
  (verify_apk sem exceção p/ Tier B) e no nightly 12/12 verde
  (runs 40095992749 e 40099290907).
- **R0.2** `engines-nightly.yml`: job `notify-failure` (R0.2/R3.1) — auto-issue
  label `ci` em falha de build/infra, exclusivo do compat (que tem fixture_gap
  próprio). Mecânica validada com canary em branch de teste: issue #22 aberta
  automaticamente com run/commit no corpo, fechada e removida (run 40095928776).
  Fix descoberto pelo canary: `gh issue create` sem checkout exige `--repo`.
- **R0.3** Release **v1.0.1 CORTADA e PÚBLICA em construção** (tag na
  853553a, run 40100387156): `release.yml` com `draft: false` + extração
  dinâmica de notas da seção da própria tag (awk com casamento exato do
  cabeçalho — `[1.0.1]` não pega `[1.0.10]`); CHANGELOG ganhou `[1.0.1]`.
  A v1.0.0 draft pré-fix segue NÃO publicada.
- **R1.1** `.github/workflows/rustydroid-snapshot.yml`: builda o CLI `rd` da
  FONTE pinada (`RD_COMMIT=89bbe8f…` main do irmão em 2026-10-24; CI do irmão
  vermelho SÓ em clippy de teste — MSRV verde) e publica asset fixo no
  release `rustydroid-cli-snapshot` com sha256+proveniência. PAT sem escrita
  no repo irmão (403 verificado) — o "asset fixo" do roadmap. sha256
  5ff10a9e4b49… (rustc 1.99.1) baixável anonimamente (testado).
- **R1.2** `scripts/compat-nightly.sh`: bootstrap do snapshot pinado (cache
  ~/.cache com sha256 validado SEMPRE); download/integridade falhando = FAIL
  explícito; binário único `rd` (o nome `rustydroid` nunca existiu como
  binário); status SKIP sai da matriz.
- **R1.3** Matriz completa: novos jobs `build-ladder`/`build-torture`/
  `build-flagship-classic` no nightly; compat baixa também os 14 Tier A do
  último ci.yml verde. Aceite SUPERADO: `install: OK (sha256 5ff10a9e4b49…)`
  + `resumo: OK=42 FAIL=0 SKIP=0 SEM_APK=14` (run 40099290907); com Tier A o
  alvo contratual vira OK=56/SEM_APK=0 (próximo run).
- **R1.3-drift** O answer key `rustydroid_engines` era ASPIRACIONAL e
  divergia do registro real em 9 entradas (maui-xamarin→dotnet-maui,
  lua-defold→lua-engines, avalonia-dotnet→avalonia, python-kivy-beeware→
  python-engines, + kmp/c/cpp/rust/go/objc/zig). Alguns "passavam" por
  substring do nome de pacote (engine04scala continha "scala"). Commit
  879041c: answer key = conjunto EMITIDO real do detector, verificado contra
  os 32 APKs dos artefatos CI; matcher ancorado em linhas row-start; GAPs do
  detector documentados por entrada (tauri não dispara, libdmengine.so vs
  libdefold.so, twa-pwa sem asset_statements, scala/clojure/groovy/b4x sem
  registro). Issue #23 documentada e fechada.
- **R2.1** 32 sondas `.engines.Engine<NN>*Activity` (framework-only minSdk 9)
  + base `EngineProbeActivity` no :app; manifest-audit regenerado: **39
  activities, alvo >= 30 ATINGIDO**; cheque novo
  `bot/checks/activity_coverage.py` (engine-sem-sonda, sonda-sem-engine,
  SONDAS FANTOMAS — classe Java ausente; alvo contratual vigiado). Bot local:
  32x32 OK.
- **R2.2** Módulos reais: `:native` (libnative_probe.so, CMake/NDK
  27.2.12479018, 1 JNI C puro), `:rust` (librust_probe.so, cargo-ndk,
  zero deps), `:compose` (1 tela Compose real, modern-only via
  `modernImplementation`, Kotlin 2.0.20 + BOM 2024.10.01). CI: setup pinnado
  NDK+cmake+rust+cargo-ndk nos 3 jobs de flagship. Correção de percurso:
  cargo-ndk 3.5.7 YANKED no crates.io → repin 4.1.2.
- **R2.3** `gen-strings.py` emite `assets/locales/<tag>/strings.properties`
  (12 locales) e as sondas LEEM em runtime (fallback pt-BR→pt→en, UTF-8,
  framework-only): a categoria "locales" do size-report passa a ter bytes
  REAIS e usados. Saída 12→24 artefatos, selftest atualizado, determinismo 2x.
- **R3.2** Badge do nightly já existia nos dois READMEs (verificado — nada a
  fazer). **R3.3** size-gate abre issue `ci` em falha (mesma mecânica R0.2).
- **R4.2** READMEs PT+EN reconciliados: seção "Re-auditoria (AUDIT_ROADMAP_V2)"
  com fatos de CI, 10 checks do APKBot, 6 workflows, comandos `rd` reais.

### Pendências honestas (próxima iteração)

1. **Re-baseline do size-report.csv** pelo artefato do primeiro size-gate
   verde com os módulos (padrão A9: medido, nunca estimado).
2. **v1.0.1**: confirmar release pública + download anônimo do flagship
   (aceite: `GET /releases` >= 1 public; `curl -L` sem token → 200).
3. **Matriz compat com Tier A**: confirmar OK=56/SEM_APK=0 no próximo nightly.
4. Renomear título da draft v1.0.0 para marcar "superada" (dono decide).
5. GAPs do detector documentados virarem issues NO repo irmão (sem acesso de
   escrita via PAT — doar pelo dono).

### Fechamento da iteração 3 (mesmo dia, 2026-10-24) — tudo verde

- **v1.0.1 PUBLICA** (release run 40104034422, tag re-cortada duas vezes até
  o estado correto — o zero-drift do CI pegou o v1-gate.json velho e o
  flagship antigo pegou o drift de dex; padrão A9 seguido à risca): 8 assets
  (flagship modern 819 MB + classic 70 MB anexados), `draft: false`, download
  anônimo provado (`curl -L` sem token → 200, magic PK), notas extraídas da
  seção `[1.0.1]`, `contracts/determinism-baseline.txt` commitado pelo
  workflow (2fe4119). A draft v1.0.0 renomeada "[ARQUIVADA] — não publicar".
- **Canário do size-gate pegou 3 problemas reais antes do release** (o motivo
  de existir): cargo-ndk 3.5.7 YANKED → repin 4.1.2; piso do NDK 27 = API 21
  (CXX1110) → módulos :native/:rust/:compose modern-only; rustup target add
  para os alvos android (E0463). Todos documentados e corrigidos.
- **R2.2/R2.3 verificados em CI**: size-gate verde com os módulos
  (`so` 977.960 B/8 arquivos, `locales` 9.130 B/12, dex 1.089.440 B com
  Compose, total 912.18 MB PASS na janela [850,1000]); re-baseline medido
  commitado (padrão A9); issue #34 do size-gate (R3.3 funcionando) aberta e
  fechada com o diagnóstico.
- **R1.3 aceito no SUPERALVO**: nightly 40105414707 — 15 jobs verdes,
  `APKs de engine na árvore: 32`, `install: OK (sha256 5ff10a9e4b49…)`,
  **`resumo: OK=56 FAIL=0 SKIP=0 SEM_APK=0`** (meta do roadmap era OK>=54;
  32 engines + 12 escada + 11 tortura + 1 flagship, TODAS as linhas
  exercitadas de verdade pelo snapshot pinado).
- **ci.yml** verde com os jobs flagship do CI também buildando os módulos
  (setup de NDK/CMake/cargo-ndk adicionado aos 2 jobs flagship do CI — o
  terceiro lugar que empacota o flagship, além do nightly e do release).
- **R4.3** SUPPORT.md linka M10-M12 do irmão + GAPs documentados.
- Pendência restante (dono): publicar as issues dos GAPs de detecção NO repo
  irmão (sem acesso de escrita via PAT) — tudo documentado no answer key.

---

## Iteração R5 — 2026-10-24 — roadmap R5 curto: #35–#40 via learn, NDK 27
nos READMEs, drafts de GAPs, v1.0.2

**Escopo pedido (R5 "o que resta").** As 6 issues vivas do APKBot (#35
latência do compat-nightly + #36–40 drift arsc/dex/locales/resources/so)
confirmadas no ciclo de learn ou re-baselineadas (padrão A9); GAPs do
detector para o repo irmão (PAT sem escrita); destino da draft v1.0.0;
piso do NDK 27 nos READMEs; e release atualizada.

### Executado e verificado

- **#35 — causa raiz medida e corrigida** (`bot/checks/flakiness.py`):
  a 1ª repetição do alvo `compat-nightly` (modo clone) bootstrap o
  snapshot do `rd` no `~/.cache` e cronometrar esse cold-start junto das
  3 repetições fabricou CV 1.02 ([0.614, 0.042, 0.099] no run 23 do
  APKBot) sem instabilidade real. Correção: UMA execução de AQUECIMENTO
  não cronometrada (resultado e exceção ignorados) antes das repetições.
  Prova controlada no sandbox: script fake com cold-start de 0.6 s —
  sem aquecimento CV 1.40 (assinatura exata do #35); com aquecimento,
  0 findings e CV <= 0.6. Docstring, bot/README.md e CHANGELOG
  atualizados.
- **#36–40 — re-baseline JÁ medido; issues fechadas pelo próprio
  learn.** A run 23 do APKBot (transição dos módulos R2.2/R2.3) aprendeu
  a amostra nova por `learn_mode immediate` e abriu as 5 issues de
  drift; o CSV commitado é idêntico à última amostra (verificado: 0
  drift no bot local 2x). APKBot disparado por `workflow_dispatch` (run
  24, commit b8a7170): as SEIS issues fecharam sozinhas às 16:57 UTC
  com o comentário padrão "Resolvido na execução … não reproduzido" —
  mecânica desenhada, zero intervenção manual.
- **GAPs do detector → irmão: 403 REVERIFICADO com o PAT novo.** O
  `GET /repos` do irmão mostra `permissions: push/admin true` — que
  reflete o USUÁRIO, não os escopos do token; o probe real
  (`POST /issues` com payload inválido) volta 403 "Resource not
  accessible by personal access token". Entregável:
  `docs/src/rustydroid-gaps.md` (novo, 13º capítulo do mdBook) com 4
  drafts prontas para o dono colar como issues — tauri (marcadores
  divergem do layout cargo-ndk), defold (`libdefold.so` vs
  `libdmengine.so` real), twa-pwa (minimal marker set não documentado)
  e scala/clojure/groovy/b4x (sem registro no detector de 28 ids) —
  título e corpo em inglês, convenção das issues do irmão.
- **Draft v1.0.0 — destino CONFIRMADO (não sumiu):** existe como draft
  arquivada (id 422425698, renomeada "[ARQUIVADA] v1.0.0 (pré-fix,
  draft) — NÃO publicar; superada pela v1.0.1", 8 assets, tag
  desanexada `untagged-97f15be75446ceefe3e4` — o esperado após o
  re-cut da v1.0.1). Drafts só aparecem em lista AUTENTICADA; na UI
  fica sob o filtro de drafts. Registrado no CHANGELOG [1.0.2].
- **Piso NDK 27 nos READMEs (nativo é modern-only):** README.md (PT) e
  README.en.md (seção R2) agora dizem explicitamente "todos modern-only
  (piso do NDK 27 = API 21, CXX1110; classic minSdk 9 framework-only,
  SEM código nativo)"; `suites/flagship/README.md` marca `:native` e
  `:rust` como "só modern" na tabela de módulos, remove o "stub
  fallback" (mecanismo pré-R2.2 que não existe mais) e declara que
  `:sim3d` é Java puro nos DOIS flavors; `docs/src/size-engineering.md`
  perdeu o "quando `:native` entrar (A7+)" defasado.
- **v1.0.2 cortada** (tag re-apontada para 7ff7bf5, mesmo padrão da
  v1.0.1): CHANGELOG ganhou seção `[1.0.2]` (Corrigido / Adicionado /
  Confirmado) e o Release workflow publica com as notas extraídas dela.

### Correção de percurso (o sistema pegando o próprio agente)

- O CI no b8a7170 FALHOU no "Gate v1.0" (e o Release no "Gate estático")
  com zero-drift do contrato: a página nova do mdBook fez
  `mdbook_chapters` ir de 12 para 13 e o `contracts/v1-gate.json`
  commitado dizia 12 — o drift gate fazendo exatamente o seu trabalho.
  Re-sincronizado por medição (`tools/v1-gate.py --sync`): diff de UMA
  linha (12 → 13), commit 7ff7bf5, tag v1.0.2 re-cortada nele.

### Mudanças do dono preservadas

- `c206299 "Remove section from README"` (dono, 17:00 UTC) removeu a
  seção "Re-auditoria independente (AUDIT_ROADMAP_V2)" do README.md PT,
  e `ff2fc6c` (17:03 UTC) removeu a equivalente do README.en.md —
  INTENCIONAIS e intocados por esta iteração; PT/EN ficaram SIMÉTRICOS
  de novo (a observação de assimetria que esta entrada ia registrar
  ficou obsoleta em 3 minutos: o dono resolveu os dois lados).

### Checagens e resultados

- `ruff check bot/` → All checks passed; `py_compile` OK.
- Bot `--local` 2x (estado restaurado ao HEAD após cada uso): flakiness
  [OK] 0 (antes [ACHOU] com o #35), size_drift [OK] 0, 32x32
  activity_coverage OK.
- APKBot run 24 (workflow_dispatch, b8a7170): success; #35–#40 fechadas
  automaticamente; estado commitado (ac37a54).
- Size Gate no b8a7170: success (zero drift do size-report.csv).
- v1-gate selftest OK após o re-sync; contrato com diff de 1 linha.

### Status no GitHub

- main: 7ff7bf5 (b8a7170 R5 → ac37a54 estado do bot → c206299 dono →
  7ff7bf5 re-sync). Issues abertas: 0 (seis fechadas às 16:57 UTC).
- Release v1.0.2: tag re-cortada em 7ff7bf5; run 40114342424 em
  andamento (flagship 2x para a prova de determinismo — acompanhar o
  resultado antes de declarar publicada).

### Próxima tarefa útil sugerida

1. Confirmar a Release v1.0.2 publicada (run 40114342424) + download
   anônimo do flagship (aceite: `GET /releases` >= 1 public pós-tag;
   `curl -L` sem token → 200).
2. Dono: colar as 4 drafts de `docs/src/rustydroid-gaps.md` como issues
   no irmão (PAT segue sem escopo de Issues lá) e marcar aqui os
   números criados.
3. Dono: revisar os itens M10–M12 do irmão quando o RustyDroid retomar
   (fora do escopo deste repo).

---

## Iteração D1–D6 (roadmap "o que resta, curto" — auditoria forense do dono)

Data: 2026-10-24 · HEAD inicial: aecfce1 · Autor: xisto (xisto-agent)

### D1 — trigger do size-gate.yml: FALSO POSITIVO (forense de blob)

- O dono reportou `branches: ain]` (o `[m` "devorado") no HEAD, confirmado
  pelo blob 099001f0. Verificação BYTE A BYTE (hex, imune a canal de
  exibição) do blob LOCAL e do blob do GitHub via API: o conteúdo real do
  line 18 é `20 20 20 20 62 72 61 6e 63 68 65 73 3a 20 5b 6d 61 69 6e 5d`
  = `    branches: [main]`. O blob 099001f0 é idêntico local/remoto e
  CONTÉM `[main]` — a corrupção NUNCA existiu em nenhum commit
  (`git log -S'branches: ain]'` vazio desde 306a05f).
- Causa-raiz da ilusão: o canal de exibição consome a sequência literal
  `[m` (reproduzido no sandbox: `printf 'branches: [main]'` renderiza
  `branches: ain]`). O run de push das 16:55 disparou porque o trigger
  sempre foi válido — nenhuma mudança de código necessária.
- Evidência guardada: hexdump do blob + contagens (`has_open_bracket_main: 1`,
  `has_corrupted: 0`) em ambas as pontas.

### Nit R02 — runs órfãos do canary apagados

- Os 2 runs falhos do workflow removido `r02-canary.yml` (runs
  40095928776 e 40095833531) foram apagados via API (DELETE 204 2x).

### D2 — escada de dois eixos (commit 5e5a189)

- `tools/gen-ladder.py`: `MIN_SDK_RUNGS` (12) + `TARGET_SDK_RUNGS`
  (6: targetSdk 23/29/31/33/34/35), `rung_id()` (sdk-ladder-tsNN),
  answer-key schema 2 com 18 degraus, rungs.properties com `.targetSdk`,
  auditoria com as duas tabelas + nota honesta do targetsdk23
  (minSdk 23 → BELOW_FLOOR: o targetSdk baixo não engana a lei do piso).
- `suites/sdk-ladder/app/build.gradle.kts`: consome `.targetSdk`
  (default 36); versionCode/versionName/label por eixo.
- CI `sdk-ladder` valida 18 APKs com eixo por flavor; release e nightly
  coletam `ladder-minsdk-NN.apk` + `ladder-targetsdk-NN.apk` (18).
- `contracts/suites.json` com `target_sdk` nos 18 entries; v1-gate
  re-sincronizado (ladder_rungs 18, total 63); READMEs/docs atualizados.
- CI: job `SDK Ladder (A2+D2): 18 degraus` VERDE no primeiro commit.

### D3 — wiring completo dos probes (commit 34964d6)

- `ProbeCatalog.java` 17/17 (8 adicionados verbatim do registry);
  `ProbeRunner.java` novo com wiring REAL dos 8 orfos: SQLite CRUD,
  HttpURLConnection record/replay (URLStreamHandler próprio, zero
  rede), MediaPlayer/AudioTrack sobre WAV determinístico, Camera2 stub
  (guarda API 21, subclass anônima — Proxy não faz classe abstrata),
  SensorManager TYPE_ALL, LocationManager, TelephonyManager, matriz JNI
  via reflexão (classic → NOT_IMPLEMENTED estruturado, honesto com
  "nativo é modern-only").
- `ProbeReporter.recordResult()` com a lei completa (OK /
  NOT_IMPLEMENTED / ERROR); instrumentação roda o runner e finaliza
  RESULT_OK com resumo nos extras.
- `native_probe.c`: matriz JNI real + correção do símbolo latente
  `nativeSum` → `sum` (UnsatisfiedLinkError garantido antes).
- APKBot: check novo `probe_registry_parity` (registry-only =
  regression; catalog-only = new); paridade 17↔17; CHECK_MODULES
  atualizado; teste negativo provou a detecção.

### D4 — corpus adversarial-malformed (commits b4a2bf7, 1f06e65, 6d391c5, 090448c)

- 6 fixtures no `fixture-pack.py` (27 modos): zip-slip, duplicate-entries,
  axml-truncated, arsc-type-collision (ARSc sintético estruturalmente
  honesto: 3 pools + 2 TypeSpec + 2 Type com ids 1/2 e MESMO nome
  "string" — colisão real, validada por parser próprio), dex-corrupted
  (checksum zerado + map_off 0xFFFFFFFF), v3-rotation-lineage.
- Mutação pós-build determinística (`--malformed-mutate`, mtimes 1980);
  unsigned de propósito, exceto a rotação.
- Rotacao v3 validada LOCALMENTE contra o apksigner 35.0.0 REAL
  (build-tools r35 baixado): `rotate --out lineage.bin --old-signer --ks A
  --new-signer --ks B` + `sign --ks A --next-signer --ks B --lineage
  lineage.bin --v3-only` → Verifies, v3=true, --print-certs mostra
  A(24..32) e B(33..) — as opções --in-old-keystore/--out-lineage/
  --lineage-min-sdk-version NÃO existem no 35.0.0.
- CI `parser-torture`: 17 fixtures empacotadas e validadas com prova por
  patologia (traversal no CD, duplicatas, declared>bytes + aapt2 reprova,
  colisão + aapt2 reprova, checksum/map_off + d8 reprova, e v3 com os
  DOIS certificados da rotação via print-certs).
- Contratos: TORTURE_ORDER 16, fragment/audit regenerados, suites.json
  70 entradas, v1-gate re-sincronizado (torture 16, total 69); release
  coleta 17; docs/READMEs atualizados.

### D5 + D6 + nit wrapper (commit e72d329)

- `CODEOWNERS` (owner default @nadabgfccvd; agente NUNCA auto-aprova).
- `THIRD-PARTY-NOTICES.md`: a dupla licença cobre o repositório, não os
  runtimes embutidos (Qt LGPLv3, CPython PSF-2.0, Go BSD-3, Hermes MIT,
  Clojure EPL-1.0, Defold CC0, toolchains, stubs Tier C, wrapper jar).
- D6: nota explícita PT/EN de que o gate [850, 1000] MiB mede bytes
  DESCOMPRIMIDOS (912.18 MiB no CSV), não o arquivo .apk (859.7 MB).
- Nit: gradle-wrapper.jar declarado como ÚNICA exceção a "sem binários",
  com .sha256 e link para as notices.

### Checagens e resultados

- Selftests: gen-ladder (18), fixture-pack (27 modos), gen-torture-contracts
  (16 suites), v1-gate, verify-deterministic.sh 16/16 PASS.
- Bot `--local` (estado restaurado): 0 findings; probe_registry_parity
  paridade 17↔17.
- CI no HEAD: Lint, Contratos, Gate estático, Selftests, SDK Ladder
  (18 degraus), Parser Torture (17 fixtures), Tier A, Tier C, Tier B
  contratos → verdes. Jobs restantes (flagship 2x, Tier A stragglers)
  em andamento na escrita deste log.
- Correções de CI durante a iteração: F841 (variável morta), sintaxe do
  apksigner rotate/sign (--out, --next-signer + --lineage) — sempre com
  validação local antes do push.

### Status no GitHub

- main: 090448c (5e5a189 D2 → 34964d6 D3 → b4a2bf7 D4 → e72d329 D5+D6 →
  1f06e65/6d391c5/090448c fixes de CI com prova local).
- Issues abertas: 0; runs órfãos do canary: 0.
