# APK Tester

<p align="center">
  <img src="docs/assets/logo.svg" alt="APK Tester logo (placeholder)" width="320">
</p>

<p align="center">
  <a href=".github/workflows/ci.yml"><img alt="CI" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/ci.yml/badge.svg"></a>
  <a href=".github/workflows/size-gate.yml"><img alt="Size Gate" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/size-gate.yml/badge.svg"></a>
  <a href=".github/workflows/engines-nightly.yml"><img alt="Engines Nightly" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/engines-nightly.yml/badge.svg"></a>
  <a href=".github/workflows/apkbot.yml"><img alt="APKBot" src="https://github.com/nadabgfccvd/APK-Tester/actions/workflows/apkbot.yml/badge.svg"></a>
  <a href="LICENSE-MIT"><img alt="License: MIT OR Apache-2.0" src="https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue"></a>
  <a href="GOVERNANCE.md"><img alt="SemVer 0.x to 1.0" src="https://img.shields.io/badge/semver-0.x%20%E2%86%92%201.0-orange"></a>
</p>

> **The objective is to test any program that uses APK to its absolute limits.**

**APK Tester** is the official *golden fixture* suite for
[RustyDroid](https://github.com/nadabgfccvd/RustyDroid) — the Rust runtime that
parses and executes real APKs on Linux x86_64, no VM, headless and
*agent-first* (minSdk floor 26 with structured `BELOW_FLOOR` for older targets,
a 28-language engine registry in its Apêndice G, permission engine as data, and
manifest-as-truth CORE-12). The suite produces dozens of deterministic APKs,
each with a machine-checkable *answer key*, so that
`rustydroid inspect --json` can be numerically diffed against the contracts.

These APKs stress every layer of RustyDroid: ZIP/AXML/ARSc/DEX/ELF parsers,
the Dalvik VM, the permission engine, the component registry, the engine
detector, UI rendering, and behavior switches per targetSdk.

Portuguese documentation: [README.md](README.md) · Documentation site (mdBook):
[`docs/`](docs/) · You are reading the English version.

## What it is / what it is NOT

**It is:**

- a deterministic golden-fixture suite: generators in `tools/` (python3,
  stdlib-only, seeded), no committed binaries;
- one APK per language engine (a 32-entry matrix), a minSdk 9→36 ladder, a
  *parser-torture* pack, and the 850 MB–1 GB flagship "Behemoth";
- machine-checkable answer keys in `contracts/` for numeric diffing against
  `rustydroid inspect --json`, engine detection, and scenario suites;
- professional repository governance on par with RustyDroid itself
  (CI, size gate, nightly compat job, mdBook docs, ADRs, templates, releases).

**It is NOT:**

- material for Google Play or any app store — these APKs are
  sideload/test fixtures and must not be installed on personal or production
  devices;
- malware: nothing here exploits or attacks systems; fixtures stress parsers
  and manifest surfaces inside controlled test environments;
- an SDK or library for end-user applications;
- a substitute for QA of real applications.

## The 5 pillars

1. **One APK per language engine** — a 32-entry matrix mirroring RustyDroid's
   28-language registry (Apêndice G), plus platform variants and the unified
   hybrid fixture (TST-14).
2. **minSdk 9 exists in the suite** — the full ladder 9→36, not just floor 26.
3. **Literally every platform permission** declared somewhere: the flagship
   declares the complete set (~160, including `@hide`/internal strings), plus
   appops and roles coverage.
4. **Heavy 3D + shaders** and a fully optimized 850 MB–1 GB flagship: size is
   content (procedural textures/meshes/audio/shaders) — never padding garbage.
5. **Professional repository governance** equal to RustyDroid itself
   (CI matrix, size gate, nightly compat job, docs site, ADRs, templates,
   releases).

## Repository layout

```
apk-tester/
├── suites/
│   ├── flagship/              # "Behemoth" — the 850MB–1GB, everything APK
│   ├── engines/               # 32 dirs, ONE APK PER ENGINE (engine-01…engine-32)
│   │   ├── engine-01-java/    # … each: real build OR detection fixture (tiered)
│   │   └── …
│   ├── sdk-ladder/            # same minimal app built at minSdk 9,12,14,16,19,21,23,26,29,33,35,36
│   └── parser-torture/        # ZIP64, v1/v2/v3-only sigs, unknown-perms, huge-arsc, obfuscated
├── tools/                     # ALL generators (python3, stdlib-only, seeded, no binaries committed)
│   ├── gen-dex-stress.py      gen-strings.py       gen-assets.py
│   ├── gen-icons.py           gen-buttons.py       gen-shaders.py
│   ├── gen-meshes.py          gen-textures.py      gen-audio.py
│   ├── fixture-pack.py        # aapt2+d8+zip packer for minSdk 9 / ZIP64 / edge fixtures
│   ├── build-variants.sh      size-budget.sh       verify-deterministic.sh
├── contracts/                 # ANSWER KEYS consumed by CI and RustyDroid
│   ├── flagship/manifest-audit.md        flagship/permissions-audit.md
│   ├── flagship/api-probe-registry.json  flagship/size-report.csv
│   ├── engines/expected-engines.json     # per-APK: engine ids RustyDroid MUST detect
│   └── suites.json                       # run_scenario suites per APK
├── docs/                      # mdBook site: guide, engine matrix, permission matrix, ADRs
├── .github/workflows/         # ci.yml, size-gate.yml, engines-nightly.yml, release.yml
├── CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  GOVERNANCE.md  SUPPORT.md
├── README.md (PT+EN)  CHANGELOG.md  LICENSE-MIT  LICENSE-APACHE
└── scripts/compat-nightly.sh  # runs rustydroid against every fixture
```

## Engine matrix (32)

One APK per engine. Tiers: **A** = real CI builds; **B** = heavy toolchains,
gated to nightly jobs; **C** = honest synthetic detection fixtures (generated
by `tools/fixture-pack.py`; "detection fixture, payload not executable").
Details in [`suites/engines/README.md`](suites/engines/README.md).

| Directory | Language / stack | Tier | Status |
|---|---|---|---|
| `engine-01-java` | Java (DEX, multi-dex, invoke-custom) | A | **delivered (A4)** |
| `engine-02-kotlin` | Kotlin | A | **delivered (A4)** |
| `engine-03-kmp` | Kotlin Multiplatform / Compose MP | A | **delivered (A4)** |
| `engine-04-scala` | Scala | B | planned (A7) |
| `engine-05-clojure` | Clojure | C | planned (A3) |
| `engine-06-groovy` | Groovy | A | **delivered (A4)** |
| `engine-07-c-ndk` | C (NDK) | A | **delivered (A4)** |
| `engine-08-cpp-ndk` | C++ (NDK + STL) | A | **delivered (A4)** |
| `engine-09-rust` | Rust (cargo-ndk, JNI crate) | A | **delivered (A4)** |
| `engine-10-go` | Go (gomobile bind) | A | **delivered (A4)** |
| `engine-11-objc` | Objective-C | C | planned (A3) |
| `engine-12-zig` | Zig (`zig cc` .so) | A | **delivered (A4)** |
| `engine-13-flutter` | Flutter (Dart) | B | planned (A7) |
| `engine-14-react-native` | React Native (Hermes) | B | planned (A7) |
| `engine-15-cordova` | Cordova (assets/www) | B | planned (A7) |
| `engine-16-tauri` | Tauri v2 | A | **delivered (A4)** |
| `engine-17-nativescript` | NativeScript | B | planned (A7) |
| `engine-18-maui-xamarin` | .NET MAUI / Xamarin | C | planned (A3) |
| `engine-19-unity-mono` | Unity (Mono) | C | planned (A3) |
| `engine-20-unity-il2cpp` | Unity (IL2CPP) | C | planned (A3) |
| `engine-21-unreal` | Unreal | C | planned (A3) |
| `engine-22-lua-defold` | Lua (Defold) | B | planned (A7) |
| `engine-23-godot` | Godot | B | planned (A7) |
| `engine-24-haxe` | Haxe | A | **delivered (A4)** |
| `engine-25-python-chaquopy` | Python (Chaquopy) | A | **delivered (A4)** |
| `engine-26-qt-qml` | Qt / QML | B | planned (A7) |
| `engine-27-b4x-appinventor` | B4X / App Inventor | C | planned (A3) |
| `engine-28-avalonia-dotnet` | Avalonia (.NET) | B | planned (A7) |
| `engine-29-python-kivy-beeware` | Python (Kivy/BeeWare) | C | planned (A3) |
| `engine-30-wasm-in-app` | WASM in-app (module + JS/JNI host) | A | **delivered (A4)** |
| `engine-31-hybrid` | Hybrid Kotlin+Rust+Hermes+WASM (TST-14) | A | **delivered (A4)** |
| `engine-32-twa-pwa` | TWA / PWA | C | planned (A3) |

## Delivery phases (A0–A8)

Every phase ends compiling green. Detailed exit criteria in
[GOVERNANCE.md](GOVERNANCE.md).

| Phase | Scope | Status |
|---|---|---|
| **A0** | Repo scaffold + governance kit + CI skeletons + `tools/` generators | **in progress** |
| A1 | Flagship skeleton (probe harness, manifest-complete with EVERY permission, PermissionsHub, ButtonGrid, IconGrid) | planned |
| A2 | `sdk-ladder` (minSdk 9 first!) + `parser-torture` pack | planned |
| A3 | Tier C engine fixtures + `expected-engines.json` | planned |
| **A4** | Tier A real builds (Java, Kotlin, C/C++, Rust, Go, Zig, WASM, …) | **delivered (A4)** — 14 engines with REAL builds: orchestrator `tools/build-tier-a.py` + pinned toolchains (`tools/setup-tier-a-toolchain.sh`), packaging through the same fixture-pack path and `--verify-apk` contract check (CI `tier-a-engines`, 14-job matrix) |
| A5 | 3D/shader pillar (`:sim3d` golden + shader-library + textures/meshes/audio) | planned |
| A6 | Size engineering to the [850 MB, 1000 MB] gate + `size-report.csv` | planned |
| A7 | Tier B nightly jobs + `compat-nightly` + docs site (mdBook) | planned |
| A8 | v1.0 gate: full matrix green, deterministic build proven, v1.0.0 release | planned |

## APKBot — anti-regression bot

[APKBot](.github/workflows/apkbot.yml) is the repository's autonomous
anti-regression bot: every 6 hours (or on demand) it runs 8 checks —
determinism across runs, flakiness, staleness, engine-matrix consistency,
RustyDroid registry drift, AOSP drift, size-gate breach forecast, and
governance audit — with persistent memory in `bot/state/` and issues
deduplicated by fingerprint under the `apkbot:*` labels. Scope, limits, and
how to disable it: [GOVERNANCE.md](GOVERNANCE.md); operation:
[bot/README.md](bot/README.md).

## Hard-truths

- **minSdk 9 is below RustyDroid's floor (26):** the expected result is the
  structured error `BELOW_FLOOR(minSdk=9)` — that IS the test (error law,
  never a crash).
- **Tier C fixtures are honest:** synthetic detection targets, aligned with
  RustyDroid's own law ("detection does not validate the payload nor authorize
  execution" — ADR 003). Each Tier C fixture README states this explicitly.
- **`signature`/`@hide` permissions are unobtainable on real devices:** the
  flagship tests RustyDroid's *classification*, not device installability.
- **850 MB+ APKs are sideload-scale only** (Play base-size limit ~200 MB) —
  fine, because these are fixtures, not store products.

## Quick start: integrating with RustyDroid

```bash
# 1) Structural audit: numeric diff of inspect against the fixture answer key
rustydroid inspect --json suites/flagship/behemoth.apk > /tmp/behemoth.json
diff /tmp/behemoth.json contracts/flagship/manifest-audit.json

# 2) Engine detector: the result MUST match the expected engine ids
rd engine detect suites/engines/engine-09-rust/*.apk \
  --expect contracts/engines/expected-engines.json

# 3) Scenario suites per APK (run_scenario)
rustydroid test contracts/suites.json
```

Note: the paths above assume artifacts built during phases A1–A4; final
contract formats and exact CLI flags are documented on the docs site
(`docs/`).

## Documentation

- [README.md](README.md) — full Portuguese version.
- [`docs/`](docs/) — mdBook site: guide, engine matrix, permission matrix,
  minSdk ladder table, RustyDroid integration guide, and ADRs
  (`docs/src/adr/`).
- [CONTRIBUTING.md](CONTRIBUTING.md) — per-tier toolchains, generators,
  commit conventions, PR checklist (Portuguese).
- [GOVERNANCE.md](GOVERNANCE.md) — roles, ADR-first process, phases A0–A8,
  versioning policy (Portuguese).
- [SECURITY.md](SECURITY.md) — vulnerability reporting and scope (Portuguese).
- [SUPPORT.md](SUPPORT.md) — where to ask and what to include (Portuguese).
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — code of conduct (Portuguese).
- [CHANGELOG.md](CHANGELOG.md) — change history (Keep a Changelog).

## License

Dual license: **MIT OR Apache-2.0** (files
[LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE)).
`SPDX-License-Identifier: MIT OR Apache-2.0`. Fonts included in fixtures use
OFL where applicable. All contributions are licensed under the same terms —
see [CONTRIBUTING.md](CONTRIBUTING.md).
