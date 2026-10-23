# suites/engines — um APK por engine

Um diretório por engine de linguagem da matriz: cada um contém um build real
(Tier A), um build pesado gated ao nightly (Tier B) ou um fixture de detecção
sintético e honesto (Tier C), além de `expected-engines.json` (engine ids que
o RustyDroid DEVE detectar) e um `README.md` próprio.

A matriz espelha o registro de 28 linguagens do Apêndice G de RustyDroid,
mais variantes de plataforma e o fixture híbrido unificado (TST-14) — 32
entradas no total.

## Significado dos tiers

| Tier | Significado | Onde roda |
|---|---|---|
| **A** | build real, com toolchain documentado e artefatos reais (DEX, `.so`, etc.) | `ci.yml` — obrigatório para PR |
| **B** | toolchains pesados (downloads grandes/SDKs proprietários); artefatos reais | `engines-nightly.yml` — job nightly, não bloqueia PR |
| **C** | fixture de detecção sintético e honesto, gerado por `tools/fixture-pack.py`, com layout/marcadores corretos | `ci.yml` (geração é rápida) |

Regra de honestidade dos fixtures Tier C: o README de cada um declara
explicitamente **"fixture de detecção; payload não executável"** — alinhado à
lei do RustyDroid ("detecção não valida payload nem autoriza execução", ADR
003).

## Builds Tier A (fase A4 — entregue)

Cada diretório Tier A tem **fontes commitadas** (`src/`, `native/`,
`gobind/`, `gradle-proj/`, `module.wat`, …), um `build.sh` que delega ao
orquestrador [`tools/build-tier-a.py`](../../tools/build-tier-a.py) e a
toolchain real instalada por
[`tools/setup-tier-a-toolchain.sh`](../../tools/setup-tier-a-toolchain.sh)
(pinos: Kotlin 2.0.20, Compose-MP 1.6.11, Groovy 3.0.21, Go 1.23.4 +
gomobile pinado, NDK r27, Zig 0.13.0, Haxe 4.3.6, wabt 1.0.36, Gradle
8.10.2 + AGP 8.7.3 + Chaquopy 16.1.0, hermes-engine 0.11.0, crates
tauri 2.12 / wry 0.57 / wasmer 7 com Cargo.lock commitado).

O pack usa o MESMO caminho do fixture-pack (aapt2 → javac → d8
`--min-api 26` → zip → zipalign → apksigner v1+v2) e o APK final é
verificado com `build-tier-a.py --verify-apk` contra o contrato
(`detector_artifacts`: caminhos exatos, globs, `dex-strings:*` e
`elf-strings:*`, magic ELF). Os binários NÃO são commitados — o sha256 de
cada build vai para o artefato de CI (`tier-a-<engine>`).

Regra de honestidade: os payloads Tier A são EXECUTÁVEIS (compilados por
javac/kotlinc/groovyc/clang/cargo-ndk/zig/haxe/hermesc/wat2wasm/gradle) —
diferença fundamental vs. Tier C (ADR 0003).

## Diretórios da matriz

| Diretório | Linguagem / stack | Tier | Fase | Status |
|---|---|---|---|---|
| `engine-01-java` | Java (DEX, multi-dex, invoke-custom) | A | A4 | **entregue** |
| `engine-02-kotlin` | Kotlin | A | A4 | **entregue** |
| `engine-03-kmp` | Kotlin Multiplatform / Compose MP | A | A4 | **entregue** |
| `engine-04-scala` | Scala | B | A7 | pendente |
| `engine-05-clojure` | Clojure | C | A3 | **entregue** |
| `engine-06-groovy` | Groovy | A | A4 | **entregue** |
| `engine-07-c-ndk` | C (NDK) | A | A4 | **entregue** |
| `engine-08-cpp-ndk` | C++ (NDK + STL) | A | A4 | **entregue** |
| `engine-09-rust` | Rust (cargo-ndk, crate JNI) | A | A4 | **entregue** |
| `engine-10-go` | Go (gomobile bind) | A | A4 | **entregue** |
| `engine-11-objc` | Objective-C | C | A3 | **entregue** |
| `engine-12-zig` | Zig (`zig cc` .so) | A | A4 | **entregue** |
| `engine-13-flutter` | Flutter (libapp.so + flutter_assets) | B | A7 | pendente |
| `engine-14-react-native` | React Native (bundle Hermes) | B | A7 | pendente |
| `engine-15-cordova` | Cordova (assets/www) | B | A7 | pendente |
| `engine-16-tauri` | Tauri v2 | A | A4 | **entregue** |
| `engine-17-nativescript` | NativeScript | B | A7 | pendente |
| `engine-18-maui-xamarin` | .NET MAUI / Xamarin (assemblies stub) | C | A3 | **entregue** |
| `engine-19-unity-mono` | Unity Mono (Assembly-CSharp.dll stub) | C | A3 | **entregue** |
| `engine-20-unity-il2cpp` | Unity IL2CPP (libil2cpp.so + global-metadata stubs) | C | A3 | **entregue** |
| `engine-21-unreal` | Unreal (libUE4.so stub + pak) | C | A3 | **entregue** |
| `engine-22-lua-defold` | Lua (Defold) | B | A7 | pendente |
| `engine-23-godot` | Godot (export headless .pck + libgodot) | B | A7 | pendente |
| `engine-24-haxe` | Haxe | A | A4 | **entregue** |
| `engine-25-python-chaquopy` | Python (Chaquopy) | A | A4 | **entregue** |
| `engine-26-qt-qml` | Qt / QML | B | A7 | pendente |
| `engine-27-b4x-appinventor` | B4X / App Inventor | C | A3 | **entregue** |
| `engine-28-avalonia-dotnet` | Avalonia (.NET) | B | A7 | pendente |
| `engine-29-python-kivy-beeware` | Python (Kivy/BeeWare) | C | A3 | **entregue** |
| `engine-30-wasm-in-app` | WASM in-app (módulo em assets + host JS/JNI) | A | A4 | **entregue** |
| `engine-31-hybrid` | Híbrido Kotlin+Rust+Hermes+WASM em UM APK (TST-14) | A | A4 | **entregue** |
| `engine-32-twa-pwa` | TWA / PWA (assetlinks + manifest markers) | C | A3 | **entregue** |

## Status

- **Tier C:** entregue na fase **A3** (9 fixtures + contratos por
  diretório, zero drift).
- **Tier A (inclui `engine-31-hybrid`):** ENTREGUE na fase **A4** — os 14
  diretórios populados com fontes + `build.sh` + builds reais no CI
  (`tier-a-engines`, matriz de 14 jobs) e verificação por contrato.
- **Tier B:** builds nightly na fase **A7** (`engines-nightly.yml` +
  `scripts/compat-nightly.sh`).

Tier C **populado na fase A3**: os 9 diretórios (`engine-05-clojure`,
`engine-11-objc`, `engine-18-maui-xamarin`, `engine-19-unity-mono`,
`engine-20-unity-il2cpp`, `engine-21-unreal`, `engine-27-b4x-appinventor`,
`engine-29-python-kivy-beeware`, `engine-32-twa-pwa`) contêm
`expected-engines.json` (gerado por `tools/gen-engine-fixtures.py
--sync-contracts`, zero drift contra o contrato canônico
`contracts/engines/expected-engines.json`) e um README próprio com a
declaração de honestidade. Os APKs são empacotados pela toolchain real no CI
(job `tier-c-engines`) e verificados contra
`contracts/engines/tier-c-payload-report.json`.

Tier A/B: diretórios populados nas fases A4/A7. Ver a matriz consolidada e o
[README.md](../../README.md) raiz para o contexto geral.
