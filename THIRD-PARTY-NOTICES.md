# Third-Party Notices — APK Tester

Este repositório é distribuído sob a dupla licença `MIT OR Apache-2.0`
(ver `LICENSE-MIT` e `LICENSE-APACHE`). **A dupla licença cobre o conteúdo
deste repositório** (geradores, contratos, fixtures-fonte, documentação) —
ela NÃO cobre os runtimes/toolchains de terceiros que são **embutidos ou
usados para construir** os APKs de fixture. Este arquivo lista as notícias
de terceiro aplicáveis, por camada.

## 1. Runtimes/stacks embutidos nos APKs de fixture (builds reais Tier A/B)

| Terceiro | Componente | Licença | Onde aparece |
|---|---|---|---|
| Qt Company / KDE | Qt 6 + QML (`engine-26-qt-qml`) | **LGPLv3** (com exception Qt) | nightly; pode entrar em APK nightly real |
| Python Software Foundation | CPython (`engine-25-python-chaquopy`, `engine-29-kivy-beeware`) | **PSF-2.0** | via Chaquopy (MIT) / BeeWare |
| Google / Chaquopy | plugin Chaquopy | MIT | `engine-25` |
| Google | Go runtime + gomobile (`engine-10-go`) | **BSD-3-Clause** | `libgojni.so` |
| Meta | Hermes JS engine (`engine-14-react-native`, `engine-31-hybrid`) | **MIT** (com partes BSD/Patent grant) | `libhermes.so` |
| JetBrains | Kotlin stdlib (`engine-02`, `engine-03`, `engine-31`) | **Apache-2.0** | `classes*.dex` |
| Microsoft / .NET Foundation | Mono/.NET runtime (`engine-18`, `engine-28`) | **MIT** | `libmonodroid.so`, `assemblies/*.dll` |
| Unity Technologies | runtime Mono/IL2CPP stub (`engine-19`, `engine-20`) | proprietário (stubs estruturais, payload não executável — ADR 0003) | fixtures Tier C |
| Epic Games | Unreal stub (`engine-21-unreal`) | proprietário (stub estrutural, payload não executável — ADR 0003) | fixture Tier C |
| The Rust Project | Rust std (`engine-09`, `engine-31`) | **MIT OR Apache-2.0** | `.so` via cargo-ndk |
| Andrew Kelley / contributors | Zig (`engine-12`) | **MIT** | `zig cc` toolchain |
| Google | WebView assets (`engine-15-cordova`, `engine-32-twa-pwa`) | Apache-2.0 / BSD | `assets/www` |
| Defold Foundation | Defold/Lua stub (`engine-22-lua-defold`) | **CC0 1.0** (engine) | fixture nightly |
| Godot Engine contributors | Godot stub (`engine-23-godot`) | **MIT** | fixture nightly |
| Haxe Foundation | Haxe/HXCPP stub (`engine-24-haxe`) | MIT (compilador) | fixture Tier A |
| Apache / Scala.js community | Scala (`engine-04-scala`) | **Apache-2.0** (Scala) | nightly |
| Rich Hickey / community | Clojure (`engine-05-clojure`) | **EPL-1.0** | fixture Tier C |
| Apache | Groovy (`engine-06-groovy`) | **Apache-2.0** | Tier A |
| WebAssembly/wasi contributors | módulo WASM (`engine-30-wasm-in-app`) | Apache-2.0 / MIT (WABT/wasi) | `assets/*.wasm` |

## 2. Toolchains usadas PARA CONSTRUIR (não distribuídas dentro dos APKs)

| Terceiro | Componente | Licença |
|---|---|---|
| Google | Android SDK build-tools (aapt2, d8, apksigner, zipalign), platform android-36 | Apache-2.0 (partes proprietárias dos termos do SDK) |
| Google | Android NDK 27 (clang, libc++, sysroot) | Apache-2.0 (clang/LLVM: Apache-2.0 com exceptions) |
| Gradle | Gradle 8.11.1 + AGP 8.9.2 | Apache-2.0 |
| JetBrains | kotlin-compiler | Apache-2.0 |
| Khronos | glslang (validação da shader-library) | Apache-2.0 / BSD-3 |
| Eclipse Temurin | JDK 17 (CI) | GPLv2 with Classpath Exception |
| Google | cargo-ndk, gomobile, zig cc — invocados no CI | MIT / BSD / MIT |

## 3. Binários commitados (exceção documentada à lei "sem binários")

- `suites/flagship/gradle/wrapper/gradle-wrapper.jar` e
  `suites/sdk-ladder/gradle/wrapper/gradle-wrapper.jar`: **Gradle Wrapper**
  (Apache-2.0), prática-padrão de projetos Gradle. É a ÚNICA exceção à
  retórica "sem binários commitados" — os geradores (`tools/gen-*.py`) e os
  contratos seguem stdlib-only/texto (ADR 0001/0002); a integridade de cada
  wrapper JAR é verificável pelo `.sha256` commitado ao lado
  (`gradle-wrapper.jar.sha256`). O download real da distribuição Gradle é
  feito pelo wrapper no primeiro build (nada do runtime do Gradle é
  commitado).

## 4. Nota sobre os payloads Tier C

As fixtures Tier C (detecção, `engine-05/11/18/19/20/21/27/32`) contêm
**stubs estruturais** (assinaturas ELF/PE/metadata que imitam a forma dos
runtimes) com payload NÃO executável (ADR 0003): não incorporam código de
terceiros executável, apenas marcadores determinísticos gerados por
`tools/gen-engine-fixtures.py`. As marcas registradas dos nomes citados
pertencem aos respectivos donos.

## 5. Como atualizar este arquivo

Qualquer nova stack de engine OU toolchain pinada nova (`setup-tier-a-toolchain.sh`,
`build-tier-*.py`) DEVE ganhar linha aqui no mesmo PR (revisão do owner —
ver `CODEOWNERS`). O APKBot (`bot/checks/governance.py`) guarda a estrutura
de governança; novas dependências embutidas em APKs distribuídos em release
também devem ser auditadas quanto a compatibilidade de licença (ex.: LGPLv3
do Qt exige link dinâmico e aviso de disponibilidade dos fontes).
