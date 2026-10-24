# ADR 0002 — Tiers de build A/B/C

- Status: accepted
- Data: 2026-10-22 (decisão registrada no commit A0; data placeholder 2024-01-01 removida na A9)
- Decisores: nadabgfccvd, xisto-agent

## Contexto

O registry do RustyDroid (Apêndice G) tem 32 engines. Construir TODOS os APKs
como builds reais no CI significaria instalar dezenas de toolchains pesadas
(Flutter, React Native, Unity, Unreal, Godot, Qt, .NET MAUI, ...), estourando
o tempo e a fragilidade do CI — e várias delas (Unity, Unreal) nem têm build
headless licenciada no GitHub Actions. Por outro lado, eliminar engines do
registry abriria buracos de cobertura na detecção.

Alternativas consideradas:

- Build real de tudo no CI: rejeitado (tempo de CI inviável, toolchains
  proprietárias, flakiness).
- Só fixtures sintéticas para tudo: rejeitado (perde a prova de que o detector
  casa builds REAIS, que têm layouts de artefatos diferentes de stubs).

## Decisão

Três tiers de build, declarados por engine em
`contracts/engines/expected-engines.json` (`build: real | nightly | fixture`):

- **Tier A — real**: build real no CI (`ci.yml`, fase A4). Java, Kotlin, KMP,
  Groovy, C NDK, C++ NDK, Rust, Go, Zig, Tauri, Haxe, Chaquopy, WASM-in-app e
  o híbrido TST-14.
- **Tier B — nightly**: toolchains pesadas, gated no job
  `engines-nightly.yml` (fase A7). Scala, Flutter, React Native, Cordova,
  NativeScript, Lua/Defold, Godot, Qt/QML, Avalonia.
- **Tier C — fixture**: fixtures sintéticas **honestas** geradas por
  `tools/fixture-pack.py` com layout e marcadores corretos (DEX strings, ELF,
  assets) — fase A3. Clojure, ObjC, MAUI/Xamarin, Unity Mono, Unity IL2CPP,
  Unreal, B4X/App Inventor, Kivy/BeeWare, TWA/PWA.

Todo artefato Tier C declara explicitamente no seu README:
**"detection fixture, payload not executable"**. Nada de Tier C finge ser
build real: os stubs são marcados e os contratos dizem `build: "fixture"`.

## Consequências

- CI de PR rápido (só Tier A + lint + contracts); Tier B não bloqueia PRs.
- Cobertura de detecção completa desde A3 (Tier C é barato), antes mesmo das
  builds reais chegarem em A4/A7.
- A coluna `tier` da [Matriz de Engines](../engine-matrix.md) e a matriz
  nightly devem permanecer em sync com `expected-engines.json`.
- Risco aceito: um stub Tier C pode casar a detecção enquanto a build real
  futura divergir — mitigado pelas fases A4/A7 substituindo fixtures por
  builds reais e mantendo o mesmo answer key.
