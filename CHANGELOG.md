# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/) —
ver [GOVERNANCE.md](GOVERNANCE.md) para a política 0.x → 1.0 (a versão 1.0 é
alcançada somente com a matriz completa verde, o size gate verde e o nightly
de compatibilidade verde).

## [Unreleased]

Nada ainda — o desenvolvimento pós-1.0 entra aqui (SemVer estrito a partir
de agora, ver [GOVERNANCE.md](GOVERNANCE.md)).

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
