# Gate v1.0 — a Definition of Done como contrato executável

Status: **entregue (A8)**. A publicação da versão **1.0.0** é regida por um
gate sistemático: os **10 critérios da Definition of Done** do prompt mestre
(`APK_TESTER_PROMPT.md`) são avaliados por uma ferramenta executável —
`tools/v1-gate.py` — cujo relatório é um contrato de máquina
(`contracts/v1-gate.json`, zero drift no CI) e cuja parte dinâmica é provada
**dentro do workflow Release** antes de qualquer artefato ser publicado.

## A política 0.x → 1.0

Conforme [GOVERNANCE.md](https://github.com/nadabgfccvd/APK-Tester/blob/main/GOVERNANCE.md),
a `1.0.0` somente é publicada quando, simultaneamente:

1. a **matriz completa de engines** está verde (Tier A no CI, Tier B no
   nightly, Tier C consistente com `expected-engines.json`);
2. o **size gate** está verde (flagship release ∈ [850 MB, 1000 MB]);
3. o nightly de compatibilidade (`compat-nightly`) está verde.

O gate v1.0 formaliza exatamente isso — e adiciona a prova de determinismo
das duas builds de release consecutivas exigida pela Definition of Done.

## Os 10 critérios

| id | critério (DoD) | prova estática (árvore) | prova dinâmica (workflow Release) |
|---|---|---|---|
| `apks_30_plus` | ≥ 30 APKs buildáveis de checkout limpo | 63 slots contados da árvore (32 engines + 2 flavors + 18 degraus (D2) + 11 fixtures + minSdk9) | contagem real dos APKs construídos no run |
| `flagship_size_gate` | flagship ∈ [850, 1000] MiB, R8, CSV concilia | baseline commitado `size-report.csv` | medição fresca do APK — bytes **descomprimidos** por entrada (semântica do gate A6: tamanho é conteúdo) + `size-budget.sh` |
| `permissions_audit` | contagens por protectionLevel casam com o manifesto | registry == auditoria == manifesto (1004 strings AOSP verbatim) | — (estática por construção) |
| `minsdk9_apk` | APK minSdk 9 aceito pelo caminho de build | flavor `minsdk09` + fixture `minSdk9` + suite `sdk-ladder-09` | — |
| `sim3d_golden` | golden reprodutível + probes GLES estruturados | contrato golden + registry de probes | — (byte a byte no job `flagship-3d`) |
| `ui_grids_icons` | ButtonGrid 1200 + IconGrid 600 + 500+ drawables | selftests dos geradores + constantes | — |
| `rustydroid_zero_drift` | inspect difere numericamente contra a auditoria | contratos coerentes (suites.json, zero drift semântico) | — |
| `expected_engines_detect` | expected-engines.json casa com `rd engine detect` | answer key completo (32 dirs) + `--verify-apk` verde nos builds | — |
| `determinism_proof` | duas builds de release byte-identicas | ferramenta `verify-deterministic.sh` (modos apk/generators) | **build do modern 2× com `clean` entre elas** |
| `governance_complete` | kit de governança + docs + 5 workflows + milestones + release | 35 artefatos de governança na árvore | workflow verde no tag `v1.0.0` |

Verdades duras embutidas nos critérios (honestidade de contrato):

- o prompt cita **~160 permissões** — o AOSP master define **1004**; o
  flagship declara o snapshot verbatim completo (a auditoria documenta o
  subconjunto público);
- o prompt cita **31 engines** — a matriz entrega **32 diretórios**
  (hibrido #31 + TWA/PWA #32), todos com contrato por diretório;
- `rd engine detect` e `rd inspect` rodam no **runtime RustyDroid**
  (repositório irmão); aqui provamos os answer keys por zero drift
  estrutural + verificação artefato-nível (`--verify-apk`) em cada build.

## A ferramenta (`tools/v1-gate.py`)

Python3 stdlib-only, determinístico (sem timestamps, semente `20261022`,
JSON canônico `indent=2` + `sort_keys`), PT-BR nas mensagens:

```console
$ python3 tools/v1-gate.py --selftest        # asserções internas
$ python3 tools/v1-gate.py --sync            # (re)escreve contracts/v1-gate.json
$ python3 tools/v1-gate.py --check           # roda o gate (estático)
$ python3 tools/v1-gate.py --check \
    --apks-dir dist/apks \
    --flagship-apk dist/apks/flagship-modern-release.apk \
    --determinism-pass --release-proven \
    --out dist/v1-gate.json                  # gate com evidências dinâmicas
```

Statuses por critério: `pass`, `fail` (exit 1) ou `evidence-release` — a
metade dinâmica só existe dentro do workflow Release. O contrato commitado
tem `gate_result: pending-release-evidence`; o relatório gerado no workflow,
com todas as evidências, sai `gate_result: pass` e é anexado à release.

## O workflow Release (`release.yml`)

Trigger: tag `v*` (ou `workflow_dispatch` para dry-run sem publicar).

```
static-gate    → selftest + zero drift do contrato + geradores 2× (falha rápida)
build-flagship → classic release (bulk quick) + modern release (bulk full) DUAS
                 VEZES com `gradlew clean` entre elas → verify-deterministic
                 --mode apk (conteúdo idêntico entrada a entrada, META-INF
                 ignorado) + size gate fresco + sha256
build-tier-a   → matriz dos 14 engines reais (toolchains pinadas, igual ao CI)
build-tier-c   → 9 fixtures honestas + --verify-apk
build-ladder   → 18 degraus (12 minSdk 9..36 + 6 targetSdk 23..35, D2)
build-torture  → 11 fixtures de tortura (inclui minSdk9)
fetch-tier-b   → 9 APKs do ÚLTIMO nightly verde, re-verificados contra o contrato
v1-release     → baixa tudo (≥ 30 APKs), roda o gate COM evidências,
                 empacota contratos + suite, cria o draft release
```

O draft é publicado pelo owner após inspeção. Anexos da release
`v1.0.0`:

- `flagship-modern-release.apk` (o APK de ~916 MiB dentro do gate) e
  `flagship-classic-release.apk` (variante de execução minSdk 9);
- `apk-tester-suite-apks-1.0.0.tar.gz` (os demais 55 APKs: engines Tier A/B/C,
  escada completa, fixtures de tortura);
- `apk-tester-contracts-1.0.0.tar.gz` (contratos + `v1-gate.json` + provas,
  para `rustydroid test contracts/suites.json` diffar sem clonar);
- `v1-gate.json`, `size-report.csv`, `determinism-proof.txt`, `sha256sums.txt`.

## Prova de determinismo (o critério mais forte)

Duas builds de release **consecutivas e independentes** do flavor `modern`
(bulk `full`, R8 full + resource shrinking, assinatura com keystore de
fixture):

1. `./gradlew --no-daemon :app:assembleModernRelease` (build 1 — saída
   guardada fora da árvore de build);
2. `./gradlew --no-daemon clean && ./gradlew --no-daemon
   :app:assembleModernRelease` (build 2 — árvores `gen/` e saídas
   regeneradas do zero);
3. `tools/verify-deterministic.sh --mode apk --apk1 ... --apk2 ...` compara
   o **sha256 do conteúdo de cada entrada** do ZIP — nomes, conjuntos e
   bytes — ignorando apenas `META-INF/*` (assinatura/mtimes, exatamente o
   "byte-identical exceto assinatura" da Definition of Done).

O mesmo modo apk já provava fixtures (Tier C, zig) no CI; o modo
`generators` (todos os `tools/gen-*.py` duas vezes, byte a byte) roda no
`static-gate` do Release e localmente via
`tools/verify-deterministic.sh --mode generators`.
