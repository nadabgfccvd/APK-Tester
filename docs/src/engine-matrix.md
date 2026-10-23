# Matriz de Engines

Espelho exato do registry do RustyDroid (Apêndice G): **32 diretórios** em
`suites/engines/engine-NN-slug/`, um APK por linguagem.

- **Tier A** — build real no CI (fase A4).
- **Tier B** — toolchains pesadas, gated no job nightly (fase A7).
- **Tier C** — fixtures sintéticas honestas: *"detection fixture, payload not
  executable"* (fase A3; ver ADR 0002 e ADR 0003).

A coluna **Artefatos** lista o que o detector do RustyDroid DEVE casar
(answer key canônica em `contracts/engines/expected-engines.json`); para Tier C
os artefatos são stubs honestos com o layout/marcadores corretos.

| Diretório | Linguagem | Tier | Estratégia de build | Artefatos que o detector deve casar | Status |
|-----------|-----------|------|---------------------|--------------------------------------|--------|
| engine-01-java | Java | A | build real no CI | `classes.dex` + `classes2.dex` (multi-dex, invoke-custom) | entregue (A4, build real) |
| engine-02-kotlin | Kotlin | A | build real no CI | `classes.dex` + `META-INF/*.kotlin_module` + strings `kotlin.jvm.internal` | entregue (A4, build real) |
| engine-03-kmp | Kotlin Multiplatform | A | build real no CI | `classes.dex` + `META-INF/*.kotlin_module` (shared/compose) | entregue (A4, build real) |
| engine-04-scala | Scala | B | nightly — scalac 2.13.15 real (Maven Central) + d8 com scala-library | `classes.dex` + strings `scala.runtime` | **entregue (A7)** |
| engine-05-clojure | Clojure | C | fixture sintético honesto | `classes.dex` stub + strings `clojure.lang` + marcador de fixture | **entregue A3** |
| engine-06-groovy | Groovy | A | build real no CI | `classes.dex` + strings `org.codehaus.groovy` | entregue (A4, build real) |
| engine-07-c-ndk | C (NDK) | A | build real no CI | `lib/*/libnative-c.so` (ELF com JNI `Java_*`) | entregue (A4, build real) |
| engine-08-cpp-ndk | C++ (NDK) | A | build real no CI | `lib/*/libnative-cpp.so` + `libc++_shared.so` | entregue (A4, build real) |
| engine-09-rust | Rust | A | build real no CI (cargo-ndk) | `lib/*/librust_*.so` + marcador ELF (`rust_begin_unwind`) | entregue (A4, build real) |
| engine-10-go | Go | A | build real no CI (gomobile) | `lib/*/libgojni.so` + strings `go.Seq` | entregue (A4, build real) |
| engine-11-objc | Objective-C | C | fixture sintético honesto | `lib/*/libobjc-fixture.so` stub + marcador de fixture | **entregue A3** |
| engine-12-zig | Zig | A | build real no CI (zig cc) | `lib/*/libzig-*.so` (seção `.comment` zig) | entregue (A4, build real) |
| engine-13-flutter | Dart/Flutter | B | nightly — Flutter SDK 3.24.5 estável, `flutter build apk --release --target-platform android-x64` | `libflutter.so` + `libapp.so` + `assets/flutter_assets/` | **entregue (A7)** |
| engine-14-react-native | JS/React Native | B | nightly — hermesc 0.76.9 (npm) + AARs hermes-android/react-android (Maven Central) | `libhermes.so` + `assets/index.android.bundle` (bytecode Hermes) | **entregue (A7)** |
| engine-15-cordova | JS/Cordova | B | nightly — cordova.js real do template cordova-android@14.0.1 (npm) + www do fixture | `assets/www/index.html` + `cordova.js` + `cordova_plugins.js` | **entregue (A7)** |
| engine-16-tauri | Rust/Tauri v2 | A | build real no CI | `lib/*/libtauri*.so` + marcadores wry | entregue (A4, build real) |
| engine-17-nativescript | JS/NativeScript | B | nightly — libNativeScript.so real do AAR @nativescript/android@8.8.2 (npm) | `lib/*/libNativeScript.so` + `assets/app/` | **entregue (A7)** |
| engine-18-maui-xamarin | C#/MAUI/Xamarin | C | fixture sintético honesto | `assemblies/*.dll` stubs + `libmonodroid.so` | **entregue A3** |
| engine-19-unity-mono | C#/Unity Mono | C | fixture sintético honesto | `Assembly-CSharp.dll` stub + `libunity.so` + `libmonobdwgc-2.0.so` | **entregue A3** |
| engine-20-unity-il2cpp | C#/Unity IL2CPP | C | fixture sintético honesto | `libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat` stubs | **entregue A3** |
| engine-21-unreal | C++/Unreal | C | fixture sintético honesto | `libUE4.so` stub + `assets/*.pak` | **entregue A3** |
| engine-22-lua-defold | Lua/Defold | B | nightly — bob.jar 1.9.8 (pipeline de conteúdo) + libdmengine release embutido | `libdmengine.so` + `game.arcd`/`game.arci` | **entregue (A7)** |
| engine-23-godot | GDScript/Godot | B | nightly — Godot 4.3-stable headless: `--export-release` (libs do template) + `--export-pack` (pck real) | `libgodot_android.so` + `assets/*.pck` | **entregue (A7)** |
| engine-24-haxe | Haxe | A | build real no CI | `classes.dex` + strings `haxe.root` | entregue (A4, build real) |
| engine-25-python-chaquopy | Python/Chaquopy | A | build real no CI | `classes.dex` + `lib/*/libpython3*.so` + `assets/chaquopy/` | entregue (A4, build real) |
| engine-26-qt-qml | QML/Qt | B | nightly — kit Qt 6.6.3 android_x86_64 via aqtinstall 3.3.0 | `lib/*/libQt6Core*.so` + `assets/qml/` | **entregue (A7)** |
| engine-27-b4x-appinventor | B4X/App Inventor | C | fixture sintético honesto | `classes.dex` stub + strings `anywheresoftware.b4a` | **entregue A3** |
| engine-28-avalonia-dotnet | C#/Avalonia | B | nightly — assemblies Avalonia 11.2.2 + nativos oficiais (NuGet pinado) | `assemblies/Avalonia.*.dll` + `libSkiaSharp.so` + `libmono-android.release.so` | **entregue (A7)** |
| engine-29-python-kivy-beeware | Python/Kivy/BeeWare | C | fixture sintético honesto | `lib/*/libpython3*.so` stub + `assets/python/main.py` | **entregue A3** |
| engine-30-wasm-in-app | Rust/WASM (host embutido) | A | build real no CI | `assets/module.wasm` + host `libwasmer*.so` + bridge JNI | entregue (A4, build real) |
| engine-31-hybrid | Kotlin+Rust+Hermes+WASM | A | build real no CI (TST-14) | os quatro marcadores no MESMO APK: `classes.dex` + `librust_*.so` + `index.android.bundle` + `module.wasm` | entregue (A4, build real) |
| engine-32-twa-pwa | TWA/PWA | C | fixture sintético honesto | strings `asset_statements` + `androidx.browser.trusted` + activity vazia + marcador | **entregue A3** |

Notas:

- O **engine-31-hybrid** (TST-14) é o teste de cobertura unificada: Kotlin,
  Rust, Hermes e WASM num único APK. Se o detector casa os quatro marcadores,
  ele casa os sinais básicos das famílias nativas/JS/bytecode/WASM.
- Fixtures Tier C são geradas por `tools/fixture-pack.py` (payloads por
  `tools/gen-engine-fixtures.py` — stubs ELF64/PE+BSJB/metadata/pak e classes
  marcador Java) com layout e marcadores ELF/DEX corretos, e o README de cada
  diretório declara explicitamente: *"detection fixture, payload not
  executable"*.
- Entregue na fase A3: 9 APKs empacotados no CI (`tier-c-engines`) e
  verificados contra o contrato (`--verify-apk` cruza os artefatos de
  `expected-engines.json` e os sha256 de
  `contracts/engines/tier-c-payload-report.json`).
- O resultado da detecção é verificado a cada nightly por
  `scripts/compat-nightly.sh` contra `contracts/engines/expected-engines.json`;
  drift abre issue com label `fixture_gap`.
