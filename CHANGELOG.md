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

### Planejado (fases A2–A8)

- A2 — escada `sdk-ladder` (minSdk 9 primeiro) + pacote `parser-torture`;
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
