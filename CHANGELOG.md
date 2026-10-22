# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/) —
ver [GOVERNANCE.md](GOVERNANCE.md) para a política 0.x → 1.0 (a versão 1.0 é
alcançada somente com a matriz completa verde, o size gate verde e o nightly
de compatibilidade verde).

## [Unreleased]

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
