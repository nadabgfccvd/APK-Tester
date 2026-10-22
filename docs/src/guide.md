# Guia — APK Tester

## Visão geral

O **APK Tester** (github.com/nadabgfccvd/APK-Tester) é a suíte oficial de
fixtures ouro do **RustyDroid** (github.com/nadabgfccvd/RustyDroid), um runtime
Rust que parseia e executa APKs reais em Linux x86_64 (sem VM, headless,
agent-first). O repositório produz APKs que NÃO são para a Play Store: eles
existem para stress-testar cada camada do RustyDroid — parsers ZIP/AXML/ARSc/
DEX/ELF, Dalvik VM, permission engine, registro de componentes, detector de
engines, renderização de UI e switches de comportamento por `targetSdk`.

Cada APK é determinístico (geradores com seed, sem rede em runtime, sem SDKs
proprietários), licenciado abertamente (MIT OR Apache-2.0, fontes OFL) e vem
com um **answer key** verificável por máquina, para que
`rustydroid inspect --json` possa ser diffado numericamente (zero-drift).

## Os 5 pilares (requisitos duros)

1. **Um APK por engine de linguagem** — todas as entradas do registry do
   RustyDroid (Apêndice G): 32 diretórios `suites/engines/engine-NN-slug/`.
2. **minSdk 9 existe na suíte** — escada 9, 12, 14, 16, 19, 21, 23, 26, 29, 33,
   35, 36; abaixo do piso 26 do runtime a resposta correta é o erro estruturado
   `BELOW_FLOOR(minSdk=X)`, nunca um crash.
3. **Literalmente toda permissão da plataforma declarada** no flagship
   (1004 strings do snapshot verbatim do AOSP master, incluindo
   `@hide`/internas), mais appops/roles.
4. **3D pesado + shaders** e um **flagship otimizado de 850 MB mínimo a
   1 GB máximo** — tamanho é conteúdo (texturas/meshes/áudio/shaders
   procedurais com seed), nunca padding.
5. **Repositório profissional** no mesmo nível de governança do RustyDroid:
   CI com matriz, size gate, nightly de compatibilidade, docs site, ADRs,
   templates, releases reprodutíveis.

## Layout do repositório

```
apk-tester/
├── suites/
│   ├── flagship/            # "Behemoth" — o APK de 850 MB–1 GB com tudo dentro
│   ├── engines/             # engine-01..engine-32, um APK por linguagem
│   ├── sdk-ladder/          # mesmo app mínimo em minSdk 9,12,...,36
│   └── parser-torture/      # ZIP64, assinaturas v1/v2/v3-only, unknown-perms, arsc gigante
├── tools/                   # geradores python3 stdlib-only, seeded, sem binários commitados
├── contracts/               # ANSWER KEYS consumidos por CI e RustyDroid
│   ├── flagship/            # manifest-audit, permissions-audit, api-probe-registry, size-report
│   ├── engines/             # expected-engines.json (o que `rd engine detect` DEVE responder)
│   └── suites.json          # cenários por APK para `rustydroid test`
├── docs/                    # mdBook (este site) + docs/compat-matrix.md gerada nightly
├── .github/                 # workflows, templates, labels
└── scripts/compat-nightly.sh  # roda o RustyDroid contra cada fixture e agrega a matriz
```

## Como rodar os geradores

Todos os geradores são Python 3 stdlib-only, determinísticos e aceitam o
contrato comum `--seed` / `--out` (use `--help` em cada um; em A0 alguns ainda
são esqueletos que se preenchem em A1–A6):

```bash
python3 tools/gen-dex-stress.py --out suites/parser-torture/dex-65k --seed 42
python3 tools/gen-strings.py   --out suites/flagship/generated    --seed 42
python3 tools/gen-assets.py    --out suites/flagship/assets       --seed 42
python3 tools/gen-icons.py     --out suites/flagship/res          --seed 42
python3 tools/gen-buttons.py   --out suites/flagship/src          --seed 42
python3 tools/gen-shaders.py   --out shader-library               --seed 42
python3 tools/gen-meshes.py    --out suites/flagship/assets/meshes   --seed 42
python3 tools/gen-textures.py  --out suites/flagship/assets/textures --seed 42
python3 tools/gen-audio.py     --out suites/flagship/assets/audio    --seed 42
```

Empacotamento e verificação:

```bash
# fixture packer (aapt2+d8+zip) para minSdk 9, ZIP64 e edges de parser
python3 tools/fixture-pack.py --manifest AndroidManifest.xml --out suites/sdk-ladder/minsdk-09

# builds por engine/variant
bash tools/build-variants.sh --engine engine-01-java
bash tools/build-variants.sh --variant flagship

# gates
bash tools/size-budget.sh --apk dist/flagship.apk --min-mb 850 --max-mb 1000
bash tools/verify-deterministic.sh

# compat matrix local (sem rustydroid instalado: linhas SKIP, exit 0)
bash scripts/compat-nightly.sh
```

## Build do flagship (A1)

O esqueleto do flagship "Behemoth" é um módulo Gradle completo
(`suites/flagship/`):

```bash
cd suites/flagship
./gradlew :app:assembleClassicDebug :app:assembleModernDebug
```

Requisitos: JDK 17, Android SDK (platform 36 + build-tools 35.0.0),
AGP 8.9.2 e Gradle 8.11.1 (via wrapper `./gradlew`). Strings, ícones e
assets do app são gerados em tempo de build pelos Exec tasks do Gradle
(`gen-strings` / `gen-icons` / `gen-assets`, seed 20261022) — nada disso
fica commitado; o manifesto e as auditorias são regenerados por
`tools/gen-flagship-manifest.py` e o CI prova zero-drift com
`git diff --exit-code` contra o que está commitado.

## Fases A0–A8

| Fase | Escopo | Critério de "green" | Status |
|------|--------|---------------------|--------|
| A0 | scaffold + governança + CI esqueleto + geradores | CI esqueleto verde, contracts válidos, docs compilam | **entregue** |
| A1 | flagship skeleton (probe harness, manifest com TODAS as permissões, PermissionsHub + ButtonGrid + IconGrid) | flagship ~30 MB roda no RustyDroid com probes OK/NOT_IMPLEMENTED | **entregue** (build real classic/modern no CI; diff no RustyDroid com o runtime) |
| A2 | sdk-ladder (minSdk 9 primeiro) + parser-torture | `BELOW_FLOOR(minSdk=9)` estruturado; torturas parseadas sem crash | planejado |
| A3 | engines Tier C (fixtures sintéticas honestas) + expected-engines.json | detector casa os 32 | planejado |
| A4 | engines Tier A (builds reais: Java, Kotlin, KMP, Groovy, C, C++, Rust, Go, Zig, Tauri, Haxe, Chaquopy, WASM) | matriz Tier A verde no CI | planejado |
| A5 | 3D/shaders (:sim3d golden sim + shader-library) | checksums golden reprodutíveis; GLES = erro estruturado | planejado |
| A6 | engenharia de tamanho até o gate [850, 1000] MB | size-report.csv reconcilia bytes; gate passa | planejado |
| A7 | Tier B nightly + compat-nightly + docs site | matriz publicada no Pages; issues fixture_gap automáticas | planejado |
| A8 | gate v1.0 | matriz completa verde, determinismo provado, release v1.0.0 | planejado |

## Hard-truths (leia antes de contribuir)

- **minSdk 9 está abaixo do piso do runtime**: o resultado esperado é o erro
  estruturado `BELOW_FLOOR(minSdk=9)` — isso É o teste (lei de erro, nunca crash).
- **Fixtures Tier C são alvos sintéticos honestos de detecção** (lei do
  RustyDroid: "detecção não valida payload nem autoriza execução" — ADR 0003).
- **Permissões signature/`@hide` são inobtíveis em dispositivo real**; o
  flagship testa a *classificação* do RustyDroid, não instalabilidade em device.
- **APKs de 850 MB+ são sideload apenas** (limite Play ~200 MB base) — fine,
  isto é uma fixture.
- **Permissões inventadas** (strings inexistentes) vivem SOMENTE em
  `parser-torture/unknown-perms` — jamais no flagship nem nos audits.
