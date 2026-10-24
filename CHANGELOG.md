# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/) —
ver [GOVERNANCE.md](GOVERNANCE.md) para a política 0.x → 1.0 (a versão 1.0 é
alcançada somente com a matriz completa verde, o size gate verde e o nightly
de compatibilidade verde).

## [Unreleased]

### Adicionado (AUDIT_ROADMAP_V2 — R0/R1: desbloqueio + compat real)

- `scripts/compat-nightly.sh` (R1.2): bootstrap do CLI RustyDroid — o
  script baixa o snapshot PINADO por sha256 (release
  `rustydroid-cli-snapshot`, ADR 0004), valida a integridade e instala em
  `$WORK_DIR/bin`. Download ou integridade falhando é FAIL explícito — o
  "se disponível" (SKIP=32 em todo nightly desde sempre) era mentira
  documentada e saiu.
- `.github/workflows/rustydroid-snapshot.yml` (R1.1): snapshot do CLI `rd`
  buildado da FONTE pinada (`RD_COMMIT`) no runner e publicado como asset
  fixo do release `rustydroid-cli-snapshot` com sha256 + proveniência
  (commit fonte, toolchain, data do corte). ADR 0004 declara a decisão e
  o fallback ("asset fixo") — o PAT de manutenção não tem escrita no repo
  irmão (403 verificado em 2026-10-24).
- `engines-nightly.yml` (R1.3): a matriz de compat cobre a ESCADA minSdk
  9..36 (12 degraus), as fixtures de tortura de parser (11) e o flagship
  (variante classic — a modern 857 MB segue no release), além dos 32
  engines; alvo contratual OK >= 54, SKIP = 0.
- `.github/workflows/engines-nightly.yml` (R0.2/R3.1): job
  `notify-failure` abre issue `ci` automática em falha de BUILD/INFRA do
  nightly (antes a falha vivia só no log — o PR ficava verde com o
  nightly vermelho há dias, ex. KeyError do engine-04-scala, run
  40076184463). Mecânica validada com canary (issue de teste #22 aberta e
  fechada; job removido após a prova).

### Corrigido (AUDIT_ROADMAP_V2 — R0/R1)

- `tools/build-tier-a.py` (R0.1): guard `SPECS.get(engine, {})` no
  `--verify-apk` — o verificador também valida APKs Tier B, mas o `SPECS`
  é do Tier A: `SPECS[engine]["kind"]` levantava `KeyError:
  engine-04-scala` nos 9 builds do nightly (run 40076184463). Aceite
  comprovado: `verify_apk` sem exceção para Tier B; nightly re-executado
  100% verde (run 40095992749, 12/12 jobs).
- `scripts/compat-nightly.sh`: binário único `rd` (o nome `rustydroid`
  nunca existiu como binário — era o nome do projeto); a dupla
  HAVE_RUSTYDROID/HAVE_RD e o status SKIP estrutural saem da matriz.

### Corrigido (A9 — auditoria de continuidade, roadmap W7)

- `bot/checks/answerkey_drift.py`: corrigido CRASH LATENTE na comparação
  de nomes (roadmap 7.1) — `_covered` recebia a lista ORDENADA de tokens
  e testava `<=` contra conjuntos (`list <= set` → `TypeError`); qualquer
  execução com extração confiante (≥ 20 linhas nomeadas) quebrava o cheque
  (degradado a nota pelo dispatcher). O branch estava morto em produção:
  o candidato da config era o README do irmão, cuja extração nunca atingiu
  o limiar. Na mesma passada, `_TOKEN_RE` perde o `+` da classe — ele é
  SEPARADOR em nomes compostos (`Kotlin+Rust+Hermes+WASM` virava UM token
  único e nunca casava — falso `engine-sumiu-do-irmao` a cada execução
  confiante; `C#`/`C++` continuam inteiros via `#`/recorte). Simulação
  ponta a ponta com fonte canônica: zero falso positivo nas 28×32
  comparações.
- `bot/bot-config.json`: `candidate_paths` do `answerkey_drift` passa a
  preferir `docs/engine-registry.md` (roadmap 7.2) — o registro GERADO do
  irmão (`cargo xtask engine-report` a partir de `data/engines.toml`), que
  extrai com confiança (28 linhas nomeadas vs 0 do README); `README.md`
  segue como fallback. Esperado UMA execução com finding `drift`
  (`arquivo-mudou`) na transição de fonte — comportamento desenhado, o
  baseline recomeça com os nomes agora extraídos.
- `bot/checks/answerkey_drift.py`: o finding de drift do registro ganha
  DIFF DE CONTEÚDO (roadmap 7.3, sugerido no WORK_LOG da iteração 2) —
  em vez de só o par de sha256, o corpo lista "Entraram no registro:" e
  "Saíram do registro:" (diff LITERAL entre as extrações: as duas pontas
  vêm do mesmo extrator, granularidade idêntica; a cobertura por tokens
  seria tolerante demais — renomear "Java" para "Java (OpenJDK)" some no
  dif). Baseline sem nomes (era README) documenta o início do diff.
- `bot/checks/flakiness.py`: o cheque local de flakiness EXERCITA o
  `scripts/compat-nightly.sh` (roadmap 7.4, sugerido no WORK_LOG da
  iteração 2) — o script roda dentro de um clone raso TEMPORÁRIO do
  repositório (`git clone --depth 1` para mktemp; `docs/compat-matrix.md`
  é escrito dentro do clone, descartado no finally; a lei "o APKBot nunca
  modifica o worktree" segue valendo e o clone copia o HEAD commitado,
  exatamente o que o nightly exercita). Eliminado o finding INFO
  permanente `flakiness:compat-nightly:execucao-pulada` (a única lacuna
  de cobertura honesta que restava ao cheque local); sem `rustydroid`/`rd`
  no PATH as linhas viram SKIP e a estabilidade exercitada é a do pipeline
  do script (parse da answer key, laço das fixtures, agregação do markdown,
  contrato do exit code); git indisponível/clone falho degrada para INFO
  único com o motivo — nunca falha. Medição local: 32 engines, ~30 ms por
  execução, CV 0.05. O legado `targets.compat-nightly.skipped` do baseline
  pré-clone é limpo na primeira execução pós-clone (`skipped: null` — o
  deep_merge do dispatcher nunca apaga chaves; nulo = exercitado, string =
  motivo do skip, o par reflete sempre a última execução).

### Adicionado (A9 — CI hardening, roadmap W6)

- Lint REAL de Python no CI (roadmap 6.1): job de lint ganha `ruff`
  (pinado 0.17.2, seleção explícita E4/E7/E9+F no novo `ruff.toml`) —
  os 20 achados reais da árvore foram corrigidos (3 imports mortos, 6
  variáveis atribuídas e nunca usadas, 5 nomes ambíguos `l`, f-strings
  vazias, lambda-assignment). A decisão de FORMATO está documentada no
  `ruff.toml`: SEM formatador automático (o estilo é parte da identidade
  do código de fixture; o diff é o revisor); UP/PERF/SIM ficam
  deliberadamente desligados (opiniões de refatoração, não erros).
- Novo job `gen-selftests` (roadmap 6.2): TODOS os selftests de
  `tools/*.py` rodam a cada PR — antes 11 geradores (KTX2, WAV 5.1,
  ladder, arsc, dex-stress, strings, icons, buttons, trap-manifest,
  torture-contracts, snapshot-aosp) só rodavam localmente. Inclui o
  APKBot `--local --check-list locale_sync` para exercitar checks do bot
  em cada PR.
- Prova de determinismo com hashes EMBUTIDOS (roadmap 6.3): o
  `verify-deterministic.sh --mode apk` ganha `--canonical-out` — a
  impressão digital canônica de cada build (sha256 sobre nome+sha de
  cada entrada, ordenados, META-INF ignorado). O `v1-gate.py` ganha
  `--determinism-evidence FILE`: com a evidência, a prova deixa de ser
  flag de confiança — o hash vai no relatório e builds divergentes
  REPROVAM (verificado: par igual passa, par divergente exit 1). O
  workflow Release passa o arquivo real e, em tag, commita
  `contracts/determinism-baseline.txt` em main (log de release por
  design: atualizado a cada tag, fora do zero-drift).
- Escada assinada com keystore de fixture (roadmap 6.4): os 12 degraus
  da sdk-ladder assinam com `ladder-test.keystore.b64` commitado como
  texto base64 (mesmo padrão A6 do flagship) — debug E release. Antes os
  APKs da escada anexados à release carregavam o
  `~/.android/debug.keystore` (variável por host), quebrando a
  comparabilidade dos sha256sums entre rebuilds. Configuração do Gradle
  validada localmente (decodeKeystore + validateSigning para os 12
  rungs).
- Política de testes documentada (roadmap 6.5) no CONTRIBUTING: os
  `--selftest` SÃO a suíte de testes unitários (lei stdlib-only se aplica
  aos testes; sem pytest) — parsers de contratos cobertos nos selftests
  das próprias ferramentas (zero-drift, round-trip, corrupção detectada);
  job `gen-selftests` executa tudo no CI.
- Decisões documentadas: determinismo é garantia POR-RUNNER (ADR 0001,
  roadmap 6.6 — prova cross-platform/macOS é gap registrado, não
  silêncio); `gen-buttons.py` é âncora de contrato/referência, não passo
  de build (roadmap 6.7 — o Kotlin A0 foi superseded pelas Activities
  Java commitadas do A1; o gerador segue como fonte da convenção de
  nomes + alvo do cheque determinism).

### Corrigido (A9 — governança e higiene, roadmap W5)

- Política de binários × gradle-wrapper: a exceção agora é EXPLÍCITA e
  verificável (roadmap 5.1) — os dois `gradle/wrapper/gradle-wrapper.jar`
  (flagship + sdk-ladder, idênticos, sha256
  `2db75c40…4880446`) ganham sidecars `gradle-wrapper.jar.sha256` para
  `sha256sum -c`; a exceção está documentada no ADR 0001 (praxe padrão do
  ecossistema Gradle: o wrapper é o bootstrap auditável do build; a
  distribuição Gradle em si segue NÃO commitada, pinada no
  gradle-wrapper.properties) e no checklist de PR do CONTRIBUTING.md.
- `bot/apkbot.py`: persistência do estado para de gerar commit a cada 6 h
  sem mudança real (roadmap 5.2) — o hash de comparação agora ignora o
  histórico `runs` (apêndice que muda toda rodada); o estado só é
  commitado quando o NÚCLEO muda (baselines/issues/confirmações) ou quando
  a execução teve findings. Runs avançam no arquivo apenas quando algo
  digno de memória aconteceu.
- Identidade git (roadmap 5.3): tag **v1.0.0 recriada** no mesmo commit
  da release com a identidade declarada do agente
  (`xisto <xisto@users.noreply.github.com>`) — a original carregava a
  identidade default do contêiner (`Z User <z@container>`, não
  declarada). GOVERNANCE.md agora documenta a identidade git PRATICADA
  (`xisto`, no `allowed_authors`), o incidente corrigido e a prevenção
  (automações devem configurar user.name/user.email explicitamente; o
  workflow do APKBot já configura `apkbot[bot]`), e ganha a nota sobre o
  histórico squashed pré-1.0 (roadmap 5.6: intencional, registrado para
  auditorias).
- `tools/gen-engine-fixtures.py`: o contrato por diretório
  (`suites/engines/<e>/expected-engines.json`) usa o MESMO schema do
  contrato canônico e do build-tier-a (roadmap 5.4) — chaves `id` e
  `notes` (antes `engine`/`note`: dois schemas para o mesmo artefato).
  Os 9 contratos regenerados via `--sync-contracts` (zero drift).
- `scripts/pack-tier-c.sh` (novo): o laço de empacotar+verificar as 9
  fixtures Tier C, duplicado em triplicata nos workflows `ci.yml`,
  `engines-nightly.yml` e `release.yml` (roadmap 5.5), virou um script
  compartilhado (pack + verify por engine, toolcheck de build-tools,
  exit != 0 na primeira falha). Os três workflows passam a chamá-lo.

### Corrigido (A9 — consistência de docs, roadmap W4)

- `docs/assets/logo.svg`: o logotipo referenciado pelos dois READMEs agora
  EXISTE (era `<img>` com alt-text confessando "placeholder" — roadmap
  4.1). SVG vetorial determinístico do repositório (badge hexagonal com
  circuito de fixture), sem dependências externas.
- `README.en.md`: sincronizado com a realidade (roadmap 4.2) — "~160"
  permissões corrigido para **1004 verbatim do snapshot AOSP master**;
  as 9 engines Tier C "planned (A3)" viram "**delivered (A3)**".
- `README.md` + `README.en.md`: quick-start aponta para
  `contracts/flagship/manifest-audit.md` (o `.json` nunca existiu —
  roadmap 4.3).
- Novo check do APKBot `locale_sync` (roadmap 4.2, "ideal"): vigia drift
  de tradução PT/EN nos READMEs — conjunto de engines da tabela, fase de
  entrega `(AX)` por engine e status "planned/planejado" (a classe exata
  do bug corrigido). Números-chave vão para o learn (relatório sem
  issue-spam). Registrado no catálogo do bot/README.md.
- ADRs 0001-0003: data placeholder `2024-01-01 (A0)` substituída pela
  data real `2026-10-22` (data do commit A0 que registrou as decisões —
  roadmap 4.4).
- `APK_TESTER_PROMPT.md`: nota de reconciliação no topo (roadmap 4.5) —
  o documento é a especificação histórica; onde diz "30 APKs"/"31 engine
  APKs", a resolução entregue é a matriz de 32 engines
  (`contracts/engines/expected-engines.json` é a verdade canônica).
- `bot/checks/answerkey_drift.py`: comentário deixa explícito que
  `candidate_paths` são caminhos REMOTOS no repo irmão RustyDroid (via
  API do GitHub) — auditor standalone não deve tentar resolvê-los em
  disco (roadmap 4.6).
- `CODE_OF_CONDUCT.md`: erro de tradução corrigido ("comportamento
  abusivo, abusivo em relação a dados" → "comportamento abusivo, de
  assédio" — "abusive, harassing"; roadmap 4.7).
- `docs/src/compat-matrix.md`: removido o link em loop (página que
  apontava para si mesma — roadmap 4.8); "Ver agora" aponta para o
  artefato `compat-matrix` do workflow. E a página entra no `SUMMARY.md`
  do mdBook (roadmap 1.4): agora RENDERIZA no site.

### Corrigido (A9 — formatos de arquivo, roadmap W3)

- `tools/gen-textures.py` + `tools/gen-bulk.py`: containers KTX2
  spec-completos de verdade (auditoria A9/roadmap 3.1). O header real do
  KTX 2.0 tem **80 B** (12 magic + 9 u32 + 4 u32 + 2 u64 sgd — os campos
  sgd são u64, não u32; os dois geradores gravavam 72 B com o level index
  deslocado, o que um parser spec lê como sgdByteLength corrompido);
  level index imediatamente após o header; DFD obrigatório (o gen-bulk
  gravava dfdByteLength=0); canal alpha do RGBSDA corrigido de 3 para 15;
  vkFormat do gen-bulk corrigido de 65 (A2B10G10R10_SNORM_PACK32 — valor
  errado) para **4** (VK_FORMAT_R5G6B5_UNORM_PACK16); stubs etc1/astc
  ganham DFD de formato comprimido (modelos ETC2=161/ASTC=162, bloco
  4x4, samples cosited) + payload de blocos de ruído no byte-count exato
  (antes os stubs declaravam byteLength=0 e carregavam bytes RGBA não
  declarados); mipPadding por formato (lcm(bytes do bloco, 4): 4/8/16).
  Os 48 KTX2 do genTextures e os 3 do genBulk agora passam no validador
  oficial **ktx2check 4.4.2** (KhronosGroup/KTX-Software) com zero
  erros — validação integrada ao job flagship-skeleton do CI (download
  pinado v4.4.2, `-q` para exit code) e selftests estruturais campo a
  campo. BULK_SLACK documentado sobe de 128 para 512 B (container
  ~260 B por arquivo).
- `tools/gen-audio.py`: loops 5.1 (6 canais) agora saem em
  **WAVE_FORMAT_EXTENSIBLE** (0xFFFE) com channel mask
  FL|FR|FC|LFE|BL|BR (0x3F) e SubFormat GUID KSDATAFORMAT_SUBTYPE_PCM —
  header manual de 68 B (fmt de 40 B). O fmt clássico de 44 B não
  descreve layout 5.1 (roadmap 3.2). Estéreo/mono seguem clássicos
  (layouts triviais); selftest valida o fmt estendido campo a campo e
  lê de volta via módulo wave (suporta EXTENSIBLE desde o 3.12).
- `tools/fixture-pack.py`: novo modo **multidex-8-full** (roadmap 3.3) —
  o corpus-fonte COMPLETO do gen-dex-stress (650 classes x 101 rotinas
  = 65.650 method refs, acima do limite 65.536 de um único dex)
  atravessando o d8 de verdade, fatiado em 8 lotes contíguos. Verificado
  end-to-end com toolchain real: APK com classes.dex..classes8.dex e
  66.569 method_ids somados (dexdump). Modo registrado no nightly
  (engines-nightly.yml) com a mesma prova de contagem — o CI de PR segue
  com o modo reduzido. MODES agora tem 21 modos (12 parser-torture + 9
  engines).
- `tools/build-tier-a.py`: o módulo WASM do engine-30 é **instanciado de
  verdade** no --verify-apk (roadmap 3.4) — antes o runtime wasmer só
  era linkado. Validação estrutural stdlib (parser de seções WASM com
  LEB128: magic/version/exports/data) + execução no WebAssembly do node
  (add(2,3)==5, checksum()==20261022, memória[0:24] ==
  "apktester-wasm/engine-30"). Selftest prova os checkers num módulo
  válido construído à mão (sem wat2wasm) + negativos (magic/export/data
  truncados nunca derrubam o parser).
- `contracts/parser-torture/fixtures-audit.md`: a não-instalabilidade do
  `zip64-65k.apk` vira decisão TESTADA e documentada (roadmap 3.5):
  `apksigner sign --v2-only` sobre o APK com EOCD Zip64 falha com
  "Unused space at the end of ZIP Central Directory" (apksig trata
  EOCD64+locator como lixo) — assinar pós-augment não é viável sem
  vendorizar apksig com patch; o padrão v1-antes-do-augment permanece e
  também é um caso real de APK reempacotado.
- `tools/gen-flagship-manifest.py`: `CUSTOM_NORMAL` deixa de ser permissão
  orfa (roadmap 3.6) — novo terceiro provider
  `.providers.GuardedNormalProvider` (exported, autoridade
  `dev.apktester.behemoth.guarded.normal`) com
  `android:readPermission=CUSTOM_NORMAL`; classe Java de fixture
  correspondente. O par normal/signature dos dois níveis custom fica
  exercitado no parser de permissões.

### Corrigido (auditoria ponta a ponta pós-1.0)

- `bot/checks/size_drift.py`: a previsão de breach do size gate agora ajusta
  a reta SOMENTE sobre amostras de build real (total >= 1 MiB) e não roda
  na era placeholder do esqueleto A0. Antes, as 12 amostras ~0 bytes da era
  A0 misturadas aos builds reais de ~916 MiB fabricavam slope artificial
  (aumentando a cada execução: +398, +422 MB/execução) e previsão de breach
  falsa que nunca convergia sozinha — o fingerprint
  `size_drift:total:previsao-breach` disparava em toda execução mesmo com
  a série real perfeitamente plana e dentro do gate (issue #4).
- `docs/src/compat-matrix.md`: dois links quebrados corrigidos — o link do
  `compat-nightly.sh` apontava para `../scripts/` (inexistente a partir de
  `docs/src/`) e o link do workflow era um constructo markdown inválido
  (quebra de linha entre `]` e `(` não é link no CommonMark — renderizava
  como texto cru); ambos viram URLs absolutas do repositório, na convenção
  já usada por `docs/src/compat-nightly.md` (issue #18).
- `bot/state/bot-state.json`: baseline do check `answerkey_drift` atualizada
  para o sha256 atual do README do RustyDroid (`d63720e8…`) com o
  alinhamento humano executado: `data/engines.toml` do irmão não muda desde
  2026-10-20 (antes do nightly verde) e o Engines Nightly #9 validou os 32
  fixtures contra exatamente este registro de 28 engines — a mudança do
  README é de documentação (Apêndice C/status), não de detecção (issue #19).
- `bot/checks/determinism.py` + `tools/gen-engine-fixtures.py`: o cheque
  `determinism` do APKBot cobre agora 16/16 geradores (eram 14). O leitor
  de manifest passa a aceitar também a forma `"files"` (mesmo par
  `{path, sha256}`) usada pelo `gen-bulk` — o maior gerador (768 MiB de
  conteúdo do flagship) ficava de fora da memória de determinismo
  entre-tempos; e o `gen-engine-fixtures` passa a gravar também um
  `manifest.json` no formato convencional (além do
  `tier-c-payload-report.json`, que continua sendo a âncora commitada e
  revalidada pelo selftest). Eliminados os findings INFO
  `determinism:gen-bulk:sem-manifest-json` e
  `determinism:gen-engine-fixtures:sem-manifest-json`, que reportavam a
  lacuna de cobertura em toda execução; o determinismo byte a byte dos 16
  geradores segue provado por `tools/verify-deterministic.sh` (16/16 PASS).

## [1.0.1]

### Corrigido

- `maxSdkVersion` da `GET_TASKS`/`USE_FINGERPRINT` no manifesto do
  flagship (W0) — as answer keys de permissão erradas congeladas na tag
  v1.0.0 (pré-fix) são corrigidas aqui; a v1.0.0 segue draft arquivada e
  NÃO é publicada.
- Formatos spec-completos no flagship: KTX2/WAV/multidex/WASM (W3).
- `tools/build-tier-a.py`: guard `SPECS.get()` no `--verify-apk` (R0.1) —
  KeyError nos 9 builds Tier B do nightly.
- Observabilidade do nightly: auto-issue em falha de build/infra (R0.2) e
  compat REAL com snapshot pinado do RustyDroid (R1.1/R1.2).

## [1.0.0] - 2026-10-23

Primeira release pública do APK Tester — a suíte completa de *golden
fixtures* do RustyDroid: 32 engines (Tier A real no CI, Tier B real no
nightly, Tier C fixtures honestas), flagship "Behemoth" de ~916 MiB dentro
do gate [850, 1000] MiB com as 1004 permissões verbatim do AOSP, pilar
3D/shaders com golden byte a byte e paridade nativa Java==C++, escada
minSdk 9–36, 11 fixtures de tortura de parser e o kit de governança
completo (docs mdBook, ADRs, APKBot). O **gate v1.0** (`tools/v1-gate.py`)
prova os 10 critérios da Definition of Done — incluindo o determinismo:
duas builds de release consecutivas do flagship são byte-idênticas
entrada a entrada (exceto assinatura).

### Adicionado (A8 — gate v1.0 + release 1.0.0)

- Ferramenta `tools/v1-gate.py`: checker sistemático dos 10 critérios da
  Definition of Done do prompt mestre (python3 stdlib-only, determinístico,
  sem timestamps, PT-BR nos textos). Modos `--selftest`/`--sync`/`--check`;
  critérios com metade dinâmica ficam `evidence-release` no contrato
  estático e só fecham em `pass` dentro do workflow Release
  (`--apks-dir`, `--flagship-apk`, `--determinism-pass`,
  `--release-proven`).
- Contrato `contracts/v1-gate.json` (gerado por `--sync`, JSON canônico
  indent=2/sort_keys): medições estáticas de todos os critérios + provas
  documentadas; zero drift garantido no CI pelo job novo `v1-gate`
  (selftest + sync + `git diff --exit-code`).
- Workflow `release.yml` reescrito do esqueleto A0 para o pipeline real:
  `static-gate` (DoD + zero drift + determinismo dos geradores 2×),
  `build-flagship` (classic release bulk quick + modern release bulk full
  DUAS VEZES com `gradlew clean` entre elas →
  `verify-deterministic.sh --mode apk` + size gate fresco + sha256),
  `build-tier-a` (matriz dos 14 engines reais com toolchains pinadas),
  `build-tier-c` (9 fixtures + `--verify-apk`), `build-ladder` (12 degraus
  minSdk 9–36), `build-torture` (11 fixtures com sanidade de ZIP),
  `fetch-tier-b` (9 APKs do último nightly VERDE, re-verificados contra o
  contrato canônico) e `v1-release` (baixa tudo — 57 APKs, ≥ 30 exigido —
  roda o gate com evidências dinâmicas, empacota contratos + suite e cria
  o draft release com todos os artefatos; publicação pelo owner após
  inspeção).
- Release `v1.0.0` (tag): `flagship-modern-release.apk` (~916 MiB, gate
  verde) e `flagship-classic-release.apk` anexados direto +
  `apk-tester-suite-apks-1.0.0.tar.gz` (55 APKs das 6 famílias) +
  `apk-tester-contracts-1.0.0.tar.gz` (contratos + provas, para
  `rustydroid test contracts/suites.json` sem clonar) + `v1-gate.json` +
  `size-report.csv` + `determinism-proof.txt` + `sha256sums.txt`.
- Docs: capítulo novo `docs/src/v1-gate.md` (a política 0.x→1.0 como
  contrato executável — os 10 critérios, a ferramenta, o workflow e a
  metodologia da prova de determinismo) + entrada no SUMMARY.md;
  READMEs PT/EN com A8 entregue e badge semver 1.0.0; GOVERNANCE.md com o
  status da 1.0.0 publicada.

### Adicionado (A7 — Tier B nightly + compat-nightly + docs site)

- Orquestrador `tools/build-tier-b.py`: builds REAIS dos 9 engines Tier B
  com toolchains pesadas **pinadas e baixadas da fonte oficial** para a
  árvore de trabalho (Maven Central, npm registry, NuGet, GitHub Releases,
  aqtinstall/Qt, Flutter SDK) — nada de binário commitado. Empacota pelo
  mesmo caminho do Tier A/fixture-pack (aapt2 → d8 → zipalign → apksigner
  v1+v2); para Flutter e Godot a própria toolchain produz o APK final.
  Mesmo contrato CLI do `build-tier-a.py` (`--engine/--out/--plan-only/
  --verify-apk/--sync-contracts/--selftest/--report`), com selftest de
  zero drift contra o contrato canônico.
- Estratégias por engine (detalhes nos READMEs dos diretórios):
  engine-04-scala (scalac 2.13.15 real + scala-library no DEX),
  engine-13-flutter (SDK 3.24.5 estável + `flutter build apk --release
  --target-platform android-x64`), engine-14-react-native (hermesc 0.76.9
  do npm → bytecode Hermes real + libhermes.so do AAR hermes-android +
  classes.dex do react-android), engine-15-cordova (cordova.js real do
  template cordova-android@14.0.1 + www do fixture + cordova_plugins.js
  canônico), engine-17-nativescript (libNativeScript.so real do AAR
  @nativescript/android@8.8.2), engine-22-lua-defold (bob.jar 1.9.8:
  game.arcd/game.arci do pipeline de conteúdo + libdmengine release
  embutido no bob.jar), engine-23-godot (Godot 4.3-stable headless +
  export templates: `--export-release` Android com preset commitado),
  engine-26-qt-qml (kit Qt 6.6.3 android_x86_64 via aqtinstall 3.3.0),
  engine-28-avalonia-dotnet (assemblies Avalonia 11.2.2 + libSkiaSharp +
  runtime .NET android, NuGet pinado).
- `engines-nightly.yml` reescrito (A7): matriz `tier-b-matrix` de 9 jobs
  reais (JDK 21 para defold; `fail-fast: false`, timeout 100 min), job
  `tier-c-fixtures` re-empacotando as 9 fixtures Tier C, job
  `compat-nightly` rodando `scripts/compat-nightly.sh` contra TODOS os
  fixtures com APK (artifact wiring dos dois jobs) e abrindo issue
  `fixture_gap` em regressão, e job `docs-pages` publicando o site mdBook
  COMPLETO + `docs/compat-matrix.md` fresca no GH Pages (mdbook 0.4.40
  pinado).
- CI de PR ganha o job `tier-b-contracts` (selftest do orquestrador +
  sync de contratos com `git diff --exit-code` + plan-only smoke via
  `build.sh` de cada engine) — builds pesadas continuam fora do PR
  (ADR 0002).
- `scripts/compat-nightly.sh` ganha o candidato
  `suites/engines/<engine>/<engine>.apk` (layout usado pelo job Tier C
  do ci.yml desde A3).
- Docs: capítulo novo `docs/src/compat-nightly.md` (lei do nightly, como
  rodar localmente, refinamentos do answer key), página stub
  `docs/src/compat-matrix.md` substituída pela matriz fresca a cada
  deploy do site, Matriz de Engines atualizada (status/estratégia dos 9
  Tier B) e READMEs PT/EN com A7 entregue.
- Answer key refinado contra os artefatos REAIS descobertos nas sondas da
  fase (honestidade do contrato > previsão A3):
  engine-17 `lib/x86_64/libNativeScript.so` (S maiúsculo), engine-22
  `lib/arm64-v8a/libdmengine.so` (ABI real embutida no bob.jar), engine-28
  `lib/x86_64/libSkiaSharp.so` + `lib/x86_64/libmono-android.release.so`
  (.NET 8 renomeou o antigo libmonodroid.so).

### Adicionado (A6 — Engenharia de tamanho)

- Gate de tamanho REAL do flagship: `tools/size-budget.sh` mede o APK
  (bytes descomprimidos por categoria: textures/meshes/shaders/audio/dex/
  arsc/so/locales/resources/other), emite `contracts/flagship/size-report.csv`
  e aplica o gate [850, 1000] MiB + drift por categoria de ±2% contra o CSV
  commitado (`--baseline`; categorias zeradas são SKIP no bootstrap,
  `--no-gate` para diagnósticos de debug). Workflow `size-gate.yml` compila
  o release `modern` e executa o gate (novo job de autoridade de tamanho).
- Gerador de carga determinística `tools/gen-bulk.py`: ~768 MiB em
  `assets/bulk/{textures,meshes,audio,data}` (KTX2/PLY/WAV estruturalmente
  válidos com payload keystream `shake_256(seed:kind:ordinal)` + blobs
  `APKT-BULK1`), `manifest.json` dentro do APK com sha256/`synthetic: true`
  por arquivo, `--verify` (round-trip contra o manifest) e `--selftest`
  (9 provas de determinismo). Presets `full` (768 MiB, release) e `quick`
  (15 MiB, debugs do CI via `-PbulkPreset=quick`) — total esperado do
  release ≈ 916 MiB, dentro do gate.
- Release "fully optimized": R8 full + resource shrinking (com
  `res/raw/keep.xml` preservando as 1.800 famílias `btn_label_*`/`ic_vector_*`
  resolvidas via `getIdentifier()`), dex resultante ~57 KB, `vcsInfo`
  desligado, libs nativas descomprimidas (`useLegacyPackaging = false`).
- Assinatura release determinística: keystore de fixture commitado como
  texto base64 (`suites/flagship/keystore/behemoth-test.keystore.b64`,
  PKCS12 RSA-2048, não-segredo documentado) + tarefa `decodeKeystore` —
  builds release byte-reproduzíveis entre máquinas.
- `tools/verify-deterministic.sh`: gen-bulk integrado ao modo turbo
  (`--preset quick`).
- Docs: `docs/src/size-engineering.md` (modelo de tamanho, honestidade da
  carga, gate/drift, assinatura determinística); READMEs e CHANGELOG
  atualizados; `size-report.README.md` reescrito para o estado A6.

### Adicionado (A5 — Pilar 3D/Shaders)

- Módulo `:sim3d` (biblioteca Java pura, Q16.16 somente-inteiro): malha procedural de 1.048.576 vértices,
  rasterizador de software com correção de perspectiva e z-buffer (4 frames × 1536 triângulos macro),
  física de 10.000 corpos rígidos (120 passos fixos, grade uniforme, sono), 100.000 partículas CPU,
  terreno por marching cubes (grade 48³, decomposição canônica em 6 tetraedros) e esqueleto animado
  (16 juntas, 30 frames, skinning) — tudo com checksums FNV-1a 64 por passo.
- Contrato `contracts/flagship/sim3d-golden.json` (2,4 KB) com zero drift no CI (`:sim3d:goldenVerify`
  + `git diff --exit-code`) — execução de referência em 1,6 s no JVM.
- Paridade nativa Java == C++ da física (`sim3d_native.cpp` + JNI, provada no CI via `--parity`).
- shader-library: 239 programas GLSL ES 3.1 (215 gráficos + 24 compute com `barrier()`), blobs
  SPIR-V style sintéticos honestos, `index.json` com sha256/uniforms/stage — todos validados pelo
  `glslangValidator` no CI.
- Ativos 3D build-time empacotados no flagship: texturas PBR KTX2 (raw R8G8B8A8 real; ETC1/ASTC
  stubs honestos), malhas teapot/terreno 1024² (OBJ+GLB)/crowd 50k (glTF instanciado), áudio 5.1 WAV.
- Telas `Sim3dActivity` (probe `MEDIA-SM-001`, rota CPU executa de verdade) e `GlesProbeActivity`
  (probe `MEDIA-GX-001`, compila/linka toda a shader-library via GLES 3.1 com resultado estruturado;
  lei: nunca crash). Manifesto/auditorias regeneradas (7 activities).
- `contracts/suites.json`: +3 suites do flagship (sim3d-golden, sim3d-cpu, gles-probes).
- CI: job `flagship-3d` (selftest, zero drift, paridade nativa, glslang, build + asseguração de
  ativos no APK binário). Docs: `docs/src/sim3d.md`.

### Adicionado (A4 — Builds reais Tier A)

- 14 engines Tier A com build REAL (payload executável — sem stubs, ADR
  0002/0003): `engine-01-java` (multi-dex >64k refs + invoke-custom),
  `engine-02-kotlin`, `engine-03-kmp` (expect/actual + runtime Compose-MP
  1.6.11 no mesmo DEX), `engine-06-groovy` (runtime 3.0.21 dexado),
  `engine-07-c-ndk`/`engine-08-cpp-ndk` (clang do NDK r27 +
  libc++_shared.so), `engine-09-rust` (cargo-ndk, panic=unwind,
  rust_begin_unwind no ELF), `engine-10-go` (gomobile bind pinado),
  `engine-12-zig` (zig cc 0.13 freestanding), `engine-16-tauri` (cdylibs
  reais da stack tauri 2.12 + wry 0.57), `engine-24-haxe` (target -java
  via hxjava+ant), `engine-25-python-chaquopy` (Gradle 8.10.2 + AGP 8.7.3
  + Chaquopy 16.1.0), `engine-30-wasm-in-app` (wat2wasm + host wasmer 7)
  e `engine-31-hybrid` (TST-14: Kotlin+Rust+Hermes+WASM em UM APK);
- `tools/build-tier-a.py`: orquestrador com planos JSON auditáveis,
  pack pelo mesmo caminho do fixture-pack (aapt2 → javac → d8
  `--min-api 26` → zip → zipalign → apksigner v1+v2), `--verify-apk`
  (detector_artifacts: caminhos/globs/dex-strings/elf-strings + magic
  ELF), `--sync-contracts` (14 contratos por diretório, zero drift) e
  `--selftest`;
- `tools/setup-tier-a-toolchain.sh`: instalação pinada das toolchains por
  engine (Kotlin 2.0.20, Compose-MP 1.6.11, Groovy 3.0.21, Go 1.23.4 +
  x/mobile pinado, Zig 0.13.0, Haxe 4.3.6, wabt 1.0.36, Gradle 8.10.2,
  hermes-engine 0.11.0, cargo-ndk 3.5.0) com persistência em GITHUB_ENV;
- `Cargo.lock` commitado para os crates nativos (tauri/wry workspace e
  host wasmer) — grafo de dependências pinado;
- `ci.yml`: job `tier-a-engines` (matriz de 14 jobs: selftest → sync de
  contratos + `git diff --exit-code` → build real → `--verify-apk` →
  determinismo do pack no zig → upload `tier-a-<engine>`); lint passou a
  cobrir os `build.sh` dos engines;
- `build.sh` + README + fontes commitadas em cada diretório Tier A
  (`src/`, `native/`, `gobind/`, `gradle-proj/`, `module.wat`,
  `assets-src/`).

### Adicionado (A3 — Engines Tier C)

- 9 fixtures de detecção Tier C (payload NÃO executável, ADR 0003):
  `engine-05-clojure`, `engine-11-objc`, `engine-18-maui-xamarin`,
  `engine-19-unity-mono`, `engine-20-unity-il2cpp`, `engine-21-unreal`,
  `engine-27-b4x-appinventor`, `engine-29-python-kivy-beeware`,
  `engine-32-twa-pwa`;
- Ferramenta `tools/gen-engine-fixtures.py` (fonte única das specs Tier C):
  stubs ELF64 (`.rodata` com marcadores, tabela de seções válida), PE+BSJB
  (assemblies Mono/Unity), `global-metadata.dat` (magic 0xFAB11BAF), `.pak`
  (magic 0x5A6F12E1), `assets/fixture-marker.txt` e entrypoint Python — tudo
  determinístico (seed 20261022) com filler derivado de sha256;
- Classes marcador Java por engine (pacotes `clojure.lang`,
  `anywheresoftware.b4a`, `com.google.appinventor.components.runtime`,
  `androidx.browser.trusted`) ancorando os `dex-strings:*` do contrato;
- `tools/fixture-pack.py`: 9 modos `engine-*` (pipeline aapt2+javac+d8+
  zip+zipalign+apksigner com passos `gen-engine-payload` e
  `zip-engine-payload`); TWA recebe `meta-data asset_statements` +
  `@string/asset_statements`;
- Contratos: `expected-engines.json` por diretório (gerados por
  `--sync-contracts`, zero drift contra o contrato canônico) +
  `contracts/engines/tier-c-payload-report.json` (sha256 canônico dos
  payloads, âncora da verificação);
- Verificação `--verify-apk`: cruza os artefatos do contrato (caminhos com
  glob, `dex-strings:*`, conteúdo do marcador de honestidade) contra o APK
  empacotado e os sha256 do report;
- CI: job `tier-c-engines` (selftests, zero drift, empacotamento das 9,
  verificação por contrato, determinismo de duas passadas, artefato
  `tier-c-apks`);
- READMEs por engine com a declaração de honestidade e tabelas de
  artefatos/payloads.

### Adicionado

- Flagship esqueleto: registry canônico de permissões
  (`contracts/flagship/permissions-registry.json`, snapshot verbatim do
  AOSP master, 1004 strings) + ferramenta `tools/snapshot-aosp-permissions.py`;
- Flagship esqueleto: gerador `tools/gen-flagship-manifest.py` (manifesto
  completo + `permissions-audit.md` + `manifest-audit.md` + assets de
  runtime + ledger `contracts/flagship/manifest.json`);
- Flagship esqueleto: módulo `:app` Gradle (AGP 8.9.2, Gradle 8.11.1,
  JDK 17; flavors classic minSdk 9 / modern minSdk 26) com probe harness
  (`MAXPROBE/<MODULE_ID>` + `maxprobe-report.json`), PermissionsHub (1
  botão por permissão, 1004), ButtonGrid 1200, IconGrid 600, 17 services,
  10 receivers, 2 providers, 2 widgets, instrumentation;
- CI: job `flagship-skeleton` (build real classic/modern + zero-drift do
  manifesto + cross-check de contagens + aapt2 no APK binário);
- APKBot: bot autônomo anti-regressão (8 verificações: determinismo entre
  execuções, flakiness, staleness, consistência da matriz de engines, drift do
  registro do RustyDroid, drift do AOSP, previsão de breach do gate de tamanho,
  auditoria de governança), memória persistente em `bot/state/`, issues
  deduplicadas por fingerprint.
- APKBot: labels padrão do GitHub (accessibility, documentation, duplicate,
  enhancement, invalid, question, wontfix) espelhadas em `labels.json` —
  divergência detectada pelo próprio bot na primeira execução.

- Escada sdk-ladder (A2): projeto Gradle com 12 product flavors
  (minSdk 9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36 — minSdk 9 primeiro)
  criados em tempo de configuração a partir de `rungs.properties` gerado;
  app mínimo framework-only (1 activity, 1 service, 1 receiver, 1 provider,
  0 permissões, `ladder-report.json`), applicationId
  `dev.apktester.ladder.minsdkNN`, versionCode = minSdk;
- Escada sdk-ladder (A2): gerador `tools/gen-ladder.py` (rungs.properties +
  asset de runtime + `contracts/sdk-ladder/{answer-key.json,ladder-audit.md}`
  + ledger, zero drift por construção) e job CI `sdk-ladder` (build dos 12
  flavors + validação aapt2 badging de cada APK + zero permissões afirmada);
- Pacote parser-torture (A2): `tools/fixture-pack.py` com 11 modos (os 10
  do pacote + `minSdk9` da escada) — sig-v1/v2/v3-only, unaligned,
  zip64-65k, huge-arsc, multidex-8, unknown-perms, exported-audit,
  obfuscated-r8 (+ `assets/mapping.txt` dentro do APK);
- Pacote parser-torture (A2): geradores `tools/gen-arsc-stress.py`
  (resources.arsc sintético: 10.000 entradas × 40 locales + 7 densidades,
  com `--verify` re-parser independente), `tools/gen-trap-manifest.py`
  (9 armadilhas intencionais de exported/permissões + POJOs + auditoria) e
  `tools/gen-torture-contracts.py` (contracts/parser-torture/ zero drift +
  fragmento de suites.json);
- Pacote parser-torture (A2): job CI `parser-torture` (empacota as 10
  fixtures com toolchain real e valida cada uma: esquemas de assinatura por
  apksigner, reprovação esperada do zipalign, contagem Zip64, 8 dex,
  sha256 + re-parse do arsc, permissões falsas, armadilhas no binário,
  mapping + classes ofuscadas) e 10 novas suites em `contracts/suites.json`
  (total 55).

### Adicionado (A0 — scaffold e governança)

- Scaffold de repositório: layout `suites/` (flagship, engines, sdk-ladder,
  parser-torture), `tools/`, `contracts/`, `docs/`, `.github/workflows/`,
  `scripts/`;
- Kit de governança: README (PT/EN), CONTRIBUTING, SECURITY,
  CODE_OF_CONDUCT, GOVERNANCE, SUPPORT, CHANGELOG, LICENSE-MIT,
  LICENSE-APACHE;
- Esqueletos de CI: `ci.yml`, `size-gate.yml`, `engines-nightly.yml`,
  `release.yml`;
- Geradores determinísticos em `tools/` (python3 stdlib-only, seeded, sem
  binários commitados);
- Contratos iniciais (gabaritos consumidos por CI e RustyDroid).

[Unreleased]: https://github.com/nadabgfccvd/APK-Tester/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nadabgfccvd/APK-Tester/releases/tag/v1.0.0
