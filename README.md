# APK Tester

<p align="center">
  <img src="docs/assets/logo.svg" alt="Logotipo do APK Tester" width="320">
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/ci.yml/badge.svg"></a>
  <a href=".github/workflows/size-gate.yml"><img alt="Size Gate" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/size-gate.yml/badge.svg"></a>
  <a href=".github/workflows/engines-nightly.yml"><img alt="Engines Nightly" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/engines-nightly.yml/badge.svg"></a>
  <a href=".github/workflows/apkbot.yml"><img alt="APKBot" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/apkbot.yml/badge.svg"></a>
  <a href="LICENSE-MIT"><img alt="Licenca: MIT OR Apache-2.0" src="https://img.shields.io/badge/licen%C3%A7a-MIT%20OR%20Apache--2.0-blue"></a>
  <a href="GOVERNANCE.md"><img alt="SemVer 1.0.0" src="https://img.shields.io/badge/semver-1.0.0-brightgreen"></a>
</p>

> **The objective is to test any program that uses APK to its absolute limits.**
> ("O objetivo é testar qualquer programa que usa APK até seus limites absolutos.")

**APK Tester** é a suíte oficial de *golden fixtures* do
[RustyDroid](https://github.com/nadabgfccvd/RustyDroid) — o runtime em Rust que
parseia e executa APKs reais em Linux x86_64, sem VM, headless e *agent-first*
(piso minSdk 26 com `BELOW_FLOOR` estruturado para APKs mais antigos, registro
de 28 linguagens no Apêndice G, permission engine como dado e
manifest-as-truth CORE-12). A suíte produz dezenas de APKs determinísticos,
cada um com um gabarito (*answer key*) machine-checkable, para que
`rustydroid inspect --json` possa ser diffado numericamente contra os
contratos.

Os APKs daqui estressam todas as camadas do RustyDroid: parsers
ZIP/AXML/ARSc/DEX/ELF, VM Dalvik, permission engine, registro de componentes,
detector de engine, renderização de UI e switches de comportamento por
targetSdk.

Documentação em inglês: [README.en.md](README.en.md) · Site de documentação
(mdBook): [`docs/`](docs/) · Versão em PT-BR deste arquivo: você está aqui.

## O que é / o que NÃO é

**É:**

- uma suíte de *golden fixtures* determinística: geradores em `tools/`
  (python3, stdlib-only, seeded), sem binários commitados;
- um APK por engine de linguagem (matriz de 32), escada minSdk 9→36, pacote
  *parser-torture* e o flagship "Behemoth" de 850 MB–1 GB;
- gabaritos machine-checkable em `contracts/` para diff numérico contra
  `rustydroid inspect --json`, detecção de engines e suítes de cenários;
- governança de repositório profissional, no mesmo nível do RustyDroid
  (CI, size gate, nightly de compat, docs em mdBook, ADRs, templates, releases).

**NÃO é:**

- material para Google Play ou qualquer loja de aplicativos — estes APKs são
  fixtures de sideload/teste e não devem ser instalados em dispositivos
  pessoais ou de produção;
- malware: nada aqui explora ou ataca sistemas; os fixtures estressam parsers
  e superfícies de manifest dentro de ambientes de teste controlados;
- um SDK ou biblioteca para aplicações finais;
- um substituto de QA de aplicações reais.

## Os 5 pilares

1. **Um APK por engine de linguagem** — matriz de 32 entradas espelhando o
   registro de 28 linguagens do Apêndice G de RustyDroid, mais variantes de
   plataforma e o fixture híbrido unificado (TST-14).
2. **minSdk 9 existe na suíte** — escada completa 9→36, não apenas o piso 26.
3. **Literalmente todas as permissões de plataforma** declaradas em algum
   lugar: o flagship declara o conjunto completo do snapshot verbatim do
   AOSP master (1004 strings, incluindo `@hide`/internas), mais cobertura
   de appops e roles.
4. **3D pesado + shaders** e flagship totalmente otimizado de 850 MB–1 GB:
   tamanho é conteúdo (texturas/meshes/áudio/shaders procedurais) — nunca
   lixo de *padding*.
5. **Governança de repositório profissional** igual à do próprio RustyDroid
   (CI matrix, size gate, job nightly de compat, site de docs, ADRs,
   templates, releases).

## Layout do repositório

```
apk-tester/
├── suites/
│   ├── flagship/              # "Behemoth" — o APK completo de 850 MB–1 GB
│   ├── engines/               # 32 dirs, UM APK POR ENGINE (engine-01…engine-32)
│   │   ├── engine-01-java/    # … cada um: build real OU fixture de detecção (por tier)
│   │   └── …
│   ├── sdk-ladder/            # mesmo app mínimo em minSdk 9,12,14,16,19,21,23,26,29,33,35,36
│   └── parser-torture/        # ZIP64, assinaturas v1/v2/v3 isoladas, unknown-perms, arsc gigante, obfuscado
├── tools/                     # TODOS os geradores (python3, stdlib-only, seeded, sem binários commitados)
│   ├── gen-dex-stress.py      gen-strings.py       gen-assets.py
│   ├── gen-icons.py           gen-buttons.py       gen-shaders.py
│   ├── gen-meshes.py          gen-textures.py      gen-audio.py
│   ├── fixture-pack.py        # empacotador aapt2+d8+zip para minSdk 9 / ZIP64 / fixtures de borda
│   ├── build-variants.sh      size-budget.sh       verify-deterministic.sh
├── contracts/                 # GABARITOS consumidos por CI e RustyDroid
│   ├── flagship/manifest-audit.md        flagship/permissions-audit.md
│   ├── flagship/api-probe-registry.json  flagship/size-report.csv
│   ├── engines/expected-engines.json     # por APK: engine ids que o RustyDroid DEVE detectar
│   └── suites.json                       # suítes run_scenario por APK
├── docs/                      # site mdBook: guia, matriz de engines, matriz de permissões, ADRs
├── .github/workflows/         # ci.yml, size-gate.yml, engines-nightly.yml, release.yml
├── CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  GOVERNANCE.md  SUPPORT.md
├── README.md (PT+EN)  CHANGELOG.md  LICENSE-MIT  LICENSE-APACHE
└── scripts/compat-nightly.sh  # roda o rustydroid contra todos os fixtures
```

## Matriz de engines (32)

Um APK por engine. Tiers: **A** = build real em CI; **B** = toolchain pesado,
build gated para job nightly; **C** = fixture de detecção sintético e honesto
(gerado por `tools/fixture-pack.py`; "fixture de detecção, payload não
executável"). Detalhes em [`suites/engines/README.md`](suites/engines/README.md).

| Diretório | Linguagem / stack | Tier | Status |
|---|---|---|---|
| `engine-01-java` | Java (DEX, multi-dex, invoke-custom) | A | **entregue (A4)** |
| `engine-02-kotlin` | Kotlin | A | **entregue (A4)** |
| `engine-03-kmp` | Kotlin Multiplatform / Compose MP | A | **entregue (A4)** |
| `engine-04-scala` | Scala | B | **entregue (A7, nightly)** |
| `engine-05-clojure` | Clojure | C | **entregue (A3)** |
| `engine-06-groovy` | Groovy | A | **entregue (A4)** |
| `engine-07-c-ndk` | C (NDK) | A | **entregue (A4)** |
| `engine-08-cpp-ndk` | C++ (NDK + STL) | A | **entregue (A4)** |
| `engine-09-rust` | Rust (cargo-ndk, crate JNI) | A | **entregue (A4)** |
| `engine-10-go` | Go (gomobile bind) | A | **entregue (A4)** |
| `engine-11-objc` | Objective-C | C | **entregue (A3)** |
| `engine-12-zig` | Zig (`zig cc` .so) | A | **entregue (A4)** |
| `engine-13-flutter` | Flutter (Dart) | B | **entregue (A7, nightly)** |
| `engine-14-react-native` | React Native (Hermes) | B | **entregue (A7, nightly)** |
| `engine-15-cordova` | Cordova (assets/www) | B | **entregue (A7, nightly)** |
| `engine-16-tauri` | Tauri v2 | A | **entregue (A4)** |
| `engine-17-nativescript` | NativeScript | B | **entregue (A7, nightly)** |
| `engine-18-maui-xamarin` | .NET MAUI / Xamarin | C | **entregue (A3)** |
| `engine-19-unity-mono` | Unity (Mono) | C | **entregue (A3)** |
| `engine-20-unity-il2cpp` | Unity (IL2CPP) | C | **entregue (A3)** |
| `engine-21-unreal` | Unreal | C | **entregue (A3)** |
| `engine-22-lua-defold` | Lua (Defold) | B | **entregue (A7, nightly)** |
| `engine-23-godot` | Godot | B | **entregue (A7, nightly)** |
| `engine-24-haxe` | Haxe | A | **entregue (A4)** |
| `engine-25-python-chaquopy` | Python (Chaquopy) | A | **entregue (A4)** |
| `engine-26-qt-qml` | Qt / QML | B | **entregue (A7, nightly)** |
| `engine-27-b4x-appinventor` | B4X / App Inventor | C | **entregue (A3)** |
| `engine-28-avalonia-dotnet` | Avalonia (.NET) | B | **entregue (A7, nightly)** |
| `engine-29-python-kivy-beeware` | Python (Kivy/BeeWare) | C | **entregue (A3)** |
| `engine-30-wasm-in-app` | WASM in-app (módulo + host JS/JNI) | A | **entregue (A4)** |
| `engine-31-hybrid` | Híbrido Kotlin+Rust+Hermes+WASM (TST-14) | A | **entregue (A4)** |
| `engine-32-twa-pwa` | TWA / PWA | C | **entregue (A3)** |

## Fases de entrega (A0–A8)

Cada fase termina compilando verde. Critérios de saída detalhados em
[GOVERNANCE.md](GOVERNANCE.md).

| Fase | Escopo | Status |
|---|---|---|
| **A0** | Scaffold do repositório + kit de governança + esqueletos de CI + geradores `tools/` | **entregue** |
| **A1** | Esqueleto do flagship (probe harness, manifest completo com TODAS as permissões, PermissionsHub, ButtonGrid, IconGrid) | **entregue (A1)** — módulo `:app` Gradle (classic minSdk 9 / modern minSdk 26), 1004 permissões com registry verbatim do AOSP master e build real no CI |
| **A2** | `sdk-ladder` (minSdk 9 primeiro!) + pacote `parser-torture` | **entregue (A2)** — 12 flavors a partir de `rungs.properties` gerado (minSdk 9 primeiro, 0 permissões, CI `sdk-ladder`) + 10 fixtures de tortura empacotadas pela toolchain real (CI `parser-torture`) |
| **A3** | Fixtures Tier C da matriz de engines + `expected-engines.json` | **entregue (A3)** — 9 fixtures de detecção (payload não executável, ADR 0003) empacotadas por `tools/fixture-pack.py` com payloads de `tools/gen-engine-fixtures.py`, contratos por diretório com zero drift e verificação `--verify-apk` no CI (`tier-c-engines`) |
| **A4** | Builds reais Tier A (Java, Kotlin, C/C++, Rust, Go, Zig, WASM, …) | **entregue (A4)** — 14 engines com build REAL: orquestrador `tools/build-tier-a.py` + toolchains pinadas (`tools/setup-tier-a-toolchain.sh`), pack pelo mesmo caminho do fixture-pack e verificação `--verify-apk` contra o contrato (CI `tier-a-engines`, matriz de 14 jobs) |
| **A5** | Pilar 3D/shaders (`:sim3d` golden + shader-library + texturas/meshes/áudio) | **entregue (A5)** — motor `:sim3d` 100% Q16 inteiro (rasterizador perspectiva-correto, física 10k, partículas 100k, marching cubes, esqueleto) com golden byte a byte (`contracts/flagship/sim3d-golden.json`), paridade nativa Java==C++ provada no CI, shader-library de 239 programas GLSL ES 3.1 (215 gráficos + 24 compute) validados por glslang, texturas PBR KTX2 + malhas (teapot/terreno 1024²/crowd 50k) + áudio 5.1 empacotados no APK (CI `flagship-3d`) |
| **A6** | Engenharia de tamanho até o gate [850 MB, 1000 MB] + `size-report.csv` | **entregue (A6)** — release `modern` "fully optimized" (R8 full, resource shrinking com keep.xml das 1.800 famílias por `getIdentifier`, vcsInfo off, assinatura determinística via keystore de fixture b64) + carga determinística `gen-bulk.py` de 768 MiB em `assets/bulk/` (KTX2/PLY/WAV válidos + `APKT-BULK1`, manifest com sha256/synthetic, presets full/quick) e gate real [850, 1000] MiB com drift ±2% por categoria (`size-budget.sh --baseline`, workflow Size Gate) |
| A7 | Jobs nightly Tier B + `compat-nightly` + site de docs (mdBook) | **entregue** |
| A8 | Gate v1.0: matriz completa verde, build determinístico provado, release v1.0.0 | **entregue (A8)** — `tools/v1-gate.py` avalia os 10 critérios da Definition of Done (contrato `contracts/v1-gate.json` com zero drift no CI); o workflow `Release` constrói as 6 famílias (flagship classic+modern, Tier A 14, Tier B 9 re-verificados do nightly verde, Tier C 9, escada 12, tortura 11 = 57 APKs), prova o determinismo com DUAS builds de release consecutivas do modern (`gradlew clean` entre elas, `verify-deterministic.sh --mode apk`), roda o gate com evidências dinâmicas e publica a release v1.0.0 com APKs + contratos anexados |

## APKBot — bot anti-regressão

O [APKBot](.github/workflows/apkbot.yml) é o bot autônomo anti-regressão do
repositório: a cada 6 horas (ou sob demanda) executa 8 verificações —
determinismo entre execuções, flakiness, staleness, consistência da matriz de
engines, drift do registro do RustyDroid, drift do AOSP, previsão de breach do
gate de tamanho e auditoria de governança — com memória persistente em
`bot/state/` e issues deduplicadas por fingerprint sob as labels `apkbot:*`.
Escopo, limites e como desativar: [GOVERNANCE.md](GOVERNANCE.md); operação:
[bot/README.md](bot/README.md).

## Hard-truths

- **minSdk 9 está abaixo do piso do RustyDroid (26):** o resultado esperado é
  o erro estruturado `BELOW_FLOOR(minSdk=9)` — esse É o teste (lei de erro,
  nunca crash).
- **Fixtures Tier C são honestos:** alvos de detecção sintéticos, com a lei do
  RustyDroid declarada ("detecção não valida payload nem autoriza execução" —
  ADR 003). O README de cada fixture Tier C diz isso explicitamente.
- **Permissões `signature`/`@hide` não são obtíveis em dispositivos reais:**
  o flagship testa a *classificação* feita pelo RustyDroid, não a
  instalabilidade em device.
- **APKs de 850 MB+ são escala de sideload apenas** (limite do Play ~200 MB de
  base) — aceitável, pois aqui são fixtures, não produtos de loja.

## Início rápido: integrando com o RustyDroid

```bash
# 1) Auditoria estrutural: diff numérico do inspect contra o gabarito do fixture
rustydroid inspect --json suites/flagship/behemoth.apk > /tmp/behemoth.json
diff /tmp/behemoth.json contracts/flagship/manifest-audit.md

# 2) Detector de engines: o resultado DEVE casar com os engine ids esperados
rd engine detect suites/engines/engine-09-rust/*.apk \
  --expect contracts/engines/expected-engines.json

# 3) Suítes de cenários por APK (run_scenario)
rustydroid test contracts/suites.json
```

Nota: os caminhos acima assumem artefatos construídos pelas fases A1–A4; os
formatos finais de contrato e as flags exatas da CLI são documentados no site
de docs (`docs/`).

## Documentação

- [README.en.md](README.en.md) — versão completa em inglês.
- [`docs/`](docs/) — site mdBook: guia, matriz de engines, matriz de
  permissões, tabela da escada minSdk, guia de integração RustyDroid e ADRs
  (`docs/src/adr/`).
- [CONTRIBUTING.md](CONTRIBUTING.md) — toolchains por tier, geradores,
  convenções de commit e checklist de PR.
- [GOVERNANCE.md](GOVERNANCE.md) — papéis, processo ADR-first, fases A0–A8 e
  política de versionamento.
- [SECURITY.md](SECURITY.md) — reporte de vulnerabilidades e escopo.
- [SUPPORT.md](SUPPORT.md) — onde perguntar e o que incluir em um relato.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — código de conduta.
- [CHANGELOG.md](CHANGELOG.md) — histórico de mudanças (Keep a Changelog).

## Licença

Dupla licença: **MIT OR Apache-2.0** (arquivos
[LICENSE-MIT](LICENSE-MIT) e [LICENSE-APACHE](LICENSE-APACHE)).
`SPDX-License-Identifier: MIT OR Apache-2.0`. Fontes incluídas nos fixtures
usam OFL quando aplicável. Toda contribuição é licenciada sob os mesmos
termos — ver [CONTRIBUTING.md](CONTRIBUTING.md).
