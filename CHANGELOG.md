# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/) —
ver [GOVERNANCE.md](GOVERNANCE.md) para a política 0.x → 1.0 (a versão 1.0 é
alcançada somente com a matriz completa verde, o size gate verde e o nightly
de compatibilidade verde).

## [Unreleased]

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

### Planejado (fases A3–A8)

- A3 — fixtures Tier C da matriz de engines + `expected-engines.json`;
- A4 — builds reais Tier A (Java, Kotlin, C/C++, Rust, Go, Zig, WASM, …);
- A5 — pilar 3D/shaders (`:sim3d` golden + shader-library + texturas/meshes/áudio);
- A6 — engenharia de tamanho até o gate [850 MB, 1000 MB] + `size-report.csv`;
- A7 — jobs nightly Tier B + `compat-nightly` + site de docs (mdBook);
- A8 — gate v1.0: matriz completa verde, determinismo provado, release v1.0.0.

## [0.1.0] — A0 (em progresso)

### Adicionado

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

[Unreleased]: https://github.com/nadabgfccvd/APK-Tester/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nadabgfccvd/APK-Tester/releases/tag/v0.1.0
