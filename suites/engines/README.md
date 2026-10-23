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

## Diretórios da matriz

| Diretório | Linguagem / stack | Tier | Fase |
|---|---|---|---|
| `engine-01-java` | Java (DEX, multi-dex, invoke-custom) | A | A4 |
| `engine-02-kotlin` | Kotlin | A | A4 |
| `engine-03-kmp` | Kotlin Multiplatform / Compose MP | A | A4 |
| `engine-04-scala` | Scala | B | A7 |
| `engine-05-clojure` | Clojure | C | A3 |
| `engine-06-groovy` | Groovy | A | A4 |
| `engine-07-c-ndk` | C (NDK) | A | A4 |
| `engine-08-cpp-ndk` | C++ (NDK + STL) | A | A4 |
| `engine-09-rust` | Rust (cargo-ndk, crate JNI) | A | A4 |
| `engine-10-go` | Go (gomobile bind) | A | A4 |
| `engine-11-objc` | Objective-C | C | A3 |
| `engine-12-zig` | Zig (`zig cc` .so) | A | A4 |
| `engine-13-flutter` | Flutter (libapp.so + flutter_assets) | B | A7 |
| `engine-14-react-native` | React Native (bundle Hermes) | B | A7 |
| `engine-15-cordova` | Cordova (assets/www) | B | A7 |
| `engine-16-tauri` | Tauri v2 | A | A4 |
| `engine-17-nativescript` | NativeScript | B | A7 |
| `engine-18-maui-xamarin` | .NET MAUI / Xamarin (assemblies stub) | C | A3 |
| `engine-19-unity-mono` | Unity Mono (Assembly-CSharp.dll stub) | C | A3 |
| `engine-20-unity-il2cpp` | Unity IL2CPP (libil2cpp.so + global-metadata stubs) | C | A3 |
| `engine-21-unreal` | Unreal (libUE4.so stub + pak) | C | A3 |
| `engine-22-lua-defold` | Lua (Defold) | B | A7 |
| `engine-23-godot` | Godot (export headless .pck + libgodot) | B | A7 |
| `engine-24-haxe` | Haxe | A | A4 |
| `engine-25-python-chaquopy` | Python (Chaquopy) | A | A4 |
| `engine-26-qt-qml` | Qt / QML | B | A7 |
| `engine-27-b4x-appinventor` | B4X / App Inventor | C | A3 |
| `engine-28-avalonia-dotnet` | Avalonia (.NET) | B | A7 |
| `engine-29-python-kivy-beeware` | Python (Kivy/BeeWare) | C | A3 |
| `engine-30-wasm-in-app` | WASM in-app (módulo em assets + host JS/JNI) | A | A4 |
| `engine-31-hybrid` | Híbrido Kotlin+Rust+Hermes+WASM em UM APK (TST-14) | A | A4 |
| `engine-32-twa-pwa` | TWA / PWA (assetlinks + manifest markers) | C | A3 |

## Status

- **Tier C:** diretórios populados na fase **A3** (fixtures + contratos).
- **Tier A (inclui `engine-31-hybrid`):** builds reais na fase **A4**.
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
