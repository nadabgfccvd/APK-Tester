# APK Tester — Master Prompt v1.0 (paste into your code-gen agent)

> Sibling repo to RustyDroid. 30+ APKs: one per engine in RustyDroid's registry
> (Apêndice G, 28+), a minSdk-9→36 ladder, parser-torture pack, and a 850 MB–1 GB
> flagship with 3D/shader stress, every platform permission, and thousands of
> icons/buttons. Professional GitHub governance on par with the RustyDroid repo itself.

````markdown
# ROLE
You are a principal Android engineer + release manager. Create a complete, professional,
separate GitHub repository named **APK Tester** (`github.com/nadabgfccvd/apk-tester`) —
the official golden-fixture suite for **RustyDroid** (https://github.com/nadabgfccvd/RustyDroid),
a Rust runtime that parses and executes real APKs on Linux x86_64 (no VM, headless,
agent-first, floor minSdk 26 with structured `BELOW_FLOOR` for older, engine registry
of 28 languages in its Apêndice G, permission engine as data, manifest-as-truth CORE-12).

APK Tester produces APKs that are NOT for Google Play. They exist to stress-test every
layer of RustyDroid: ZIP/AXML/ARSc/DEX/ELF parsers, Dalvik VM, permission engine,
component registry, engine detector, UI rendering, and behavior switches per targetSdk.
Every APK is deterministic (seeded generators, no runtime network, no proprietary SDKs),
openly licensed (MIT OR Apache-2.0, OFL fonts), and comes with a machine-checkable
ANSWER KEY so `rustydroid inspect --json` can be diffed numerically.

# THE 5 PILLARS (hard requirements)
1. **One APK per language engine — all 28+ of RustyDroid's registry** (see ENGINE MATRIX).
2. **minSdk 9** must exist in the suite (SDK ladder 9→36), not just minSdk 26.
3. **Literally every platform permission** declared somewhere in the suite (flagship
   declares the full set, including @hide/internal strings), plus appops/roles coverage.
4. **Heavy 3D simulation + shaders** and a **fully optimized flagship of 850 MB minimum,
   1 GB maximum** (size is content: procedural textures/meshes/audio/shader libraries —
   never padding garbage).
5. **A separate, professional GitHub repo** with the same governance grade as RustyDroid
   (CI matrix, size gate, nightly compat job, docs site, ADRs, templates, releases).

# REPOSITORY LAYOUT (create exactly this)
```
apk-tester/
├── suites/
│   ├── flagship/              # "Behemoth" — the 850MB–1GB, everything APK
│   ├── engines/               # 28+ dirs, ONE APK PER ENGINE (engine-01…engine-30)
│   │   ├── engine-01-java/    # … each: real build OR detection fixture (tiered)
│   │   └── …
│   ├── sdk-ladder/            # same minimal app built at minSdk 9,12,14,16,19,21,23,26,29,33,35,36
│   └── parser-torture/        # ZIP64, v1/v2/v3-only sigs, unknown-perms, huge-arsc, 65k-entry, obfuscated
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
└── xtask-like: scripts/compat-nightly.sh   # runs rustydroid against every fixture
```

# FLAGSHIP APK — "BEHEMOTH" (suites/flagship)
- applicationId `dev.apktester.behemoth` · versionName `1.0.0` · versionCode `900036`
- **minSdk 9, targetSdk 36** (two flavors: `classic` minSdk 9 framework-only code;
  `modern` minSdk 26 with full androidx/compose — all androidx code isolated so the
  classic flavor never touches missing classes; guards = Build.VERSION checks +
  NoClassDefFoundError-safe lazy init)
- **Size gate: release APK ∈ [850 MB, 1000 MB], fully optimized** (R8 full, resource
  shrinking ON, zipalign, uncompressed native libs). `tools/size-budget.sh` FAILS CI
  outside the range and emits `contracts/flagship/size-report.csv` (bytes per category:
  textures / meshes / shaders / audio / dex / arsc / so / locales).
- Modules: `:app`, `:compose` (modern only), `:native` (C++ JNI, 4 ABIs), `:rust`
  (cargo-ndk .so, stub fallback), `:sim3d` (headless software 3D — see PILLAR 3D).

## Permissions — LITERALLY EVERYTHING
- Declare **every permission in AOSP `frameworks/base/core/res/AndroidManifest.xml`**:
  the agent MUST enumerate the complete set (≈160): all `normal`, all `dangerous`
  (every group: LOCATION/CAMERA/MICROPHONE/CONTACTS/PHONE/SMS/STORAGE-MEDIA/SENSORS/
  CALENDAR/NEARBY_DEVICES/NOTIFICATIONS/HEALTH), all `signature`+`signatureOrSystem`
  (every BIND_* service permission, WRITE_SECURE_SETTINGS, DUMP, READ_LOGS, REBOOT,
  DEVICE_POWER, BRICK, MANAGE_DOCUMENTS, INSTALL_LOCATION_PROVIDER, LOCATION_HARDWARE,
  CONTROL_LOCATION_UPDATES, READ_FRAME_BUFFER, CLEAR_APP_CACHE, GLOBAL_SEARCH,
  SET_DEBUG_APP, ACCESS_MOCK_LOCATION, FACTORY_TEST, …), all special-app-access
  (SYSTEM_ALERT_WINDOW, WRITE_SETTINGS, MANAGE_EXTERNAL_STORAGE, REQUEST_INSTALL/DELETE_
  PACKAGES, PACKAGE_USAGE_STATS, SCHEDULE_EXACT_ALARM/USE_EXACT_ALARM, USE_FULL_SCREEN_
  INTENT, ACCESS_NOTIFICATION_POLICY, START_FOREGROUND_SERVICES_FROM_BACKGROUND,
  IGNORE_BATTERY_OPTIMIZATIONS, QUERY_ALL_PACKAGES), all FOREGROUND_SERVICE_* type
  permissions (15), all deprecated-with-maxSdkVersion variants (GET_TASKS 25,
  PROCESS_OUTGOING_CALLS 28, USE_CREDENTIALS 22, PERSISTENT_ACTIVITY 15,
  READ_EXTERNAL_STORAGE 32, USE_FINGERPRINT 27, BLUETOOTH/ADMIN 30 …),
  `@hide`/internal strings (ACCESS_CACHE_FILESYSTEM, CLEAR_APP_USER_DATA,
  FORCE_STOP_PACKAGES, MOVE_PACKAGE, UPDATE_DEVICE_STATS, SHUTDOWN, …) — audit marks
  each `@hide`. Include `<uses-permission-sdk-23>`, custom `<permission>` (normal +
  signature), `<permission-group>`, `<permission-tree>`.
- `contracts/flagship/permissions-audit.md` = answer key: name, protectionLevel, group,
  maxSdk, hide-flag, count per level. If a permission string is invented/nonexistent it
  goes ONLY in `parser-torture/unknown-perms` — never in the flagship.
- **PermissionsHub screen: one BUTTON PER PERMISSION (~160 buttons)**, grouped by
  protection level; tapping requests/inspects it and logs a probe. Roles requested where
  possible (DIALER/EMERGENCY/HOME/BROWSER/MUSIC/GALLERY/ASSISTANT/NOTES) + appops toggles.

## Manifest — maximum surface (CORE-12 stress)
30+ activities (one per domain incl. 3D/Shaders/GLES screens), 2 activity-aliases,
15+ services (AIDL+Messenger bound, foreground with ALL types declared, 16 system
services: Accessibility/NotificationListener/IME/DeviceAdmin/VoiceInteraction/
CallScreening/Telecom/Print/Autofill/Tile/HostApdu/MediaBrowser/Wallpaper/Dream/Vpn/
Credential — each with its BIND_* permission), 10+ receivers, 2 providers (CRUD +
FileProvider + readPermission-guarded), 2 widgets, instrumentation, `<queries>` block,
all `<uses-feature>` (3 required), glEsVersion 0x00030002, uses-configuration,
supports/compatible-screens, supports-gl-texture ×3, uses-native-library, localeConfig,
dataExtractionRules + fullBackupContent + networkSecurityConfig + deliberate
cleartext-conflict for the audit, extractNativeLibs both variants across flavors,
deep links (https autoVerify + maxprobe-style custom schemes + geo/tel/sms/mailto/market),
intent-filter edge cases, sharedUserId in classic flavor only.

## 3D SIMULATION + SHADERS (its own pillar — make it heavy)
- `:sim3d` — **headless, deterministic, executes under RustyDroid** (pure Kotlin/Java +
  C++ JNI fallback): software rasterizer (perspective-correct textured triangles, z-buffer,
  1M-vertex procedural mesh), physics sim (10k rigid bodies, fixed-step, seeded),
  particle system (100k particles CPU), marching-cubes terrain, skeleton animation.
  Golden frame checksums per step (`contracts/flagship/sim3d-golden.json`).
- `shader-library/` (generated by `tools/gen-shaders.py`): 200+ GLSL ES 3.1 programs
  (PBR, raymarching, fluid, SSAO, noise libs, compute shaders, 512-uniform stress,
  long-loop fragment shaders) + SPIR-V style binary blobs as opaque assets.
- `gen-textures.py`: procedural PBR sets (albedo/normal/roughness/AO) 4K, ETC1/ASTC/KTX2
  containers, all density buckets; `gen-meshes.py`: glTF/PLY/OBJ (teapot, terrain 1024²,
  instanced crowd 50k); `gen-audio.py`: 5.1 WAV set, long-form ambient loops (size budget
  contributors). GLES3.1 probes compile/link every shader programmatically and log
  structured results; on RustyDroid these return `NOT_IMPLEMENTED` structured errors —
  the golden must PROVE the law (no crash), while `:sim3d` CPU paths MUST actually run.

## UI — many icons, many buttons (automation stress for AG-01/AG-02)
- **ButtonGrid: 1,200 buttons** (ids `btn_0001`…`btn_1200`, stable content-desc,
  deterministic labels from strings-gen) + **IconGrid: 600 ImageViews** +
  widget zoo (every android.widget class instantiated) + RecyclerView 10k with DiffUtil +
  60-level nested hierarchy + all layouts + Fragments/Navigation/BottomNav +
  Compose Material3 screen (modern flavor) + RTL/pseudolocale/night/fontScale variants.
- `tools/gen-icons.py`: **500+ vector drawables**, adaptive icons (fg/bg/monochrome
  API 33), legacy+round icons at all 6 densities, TV banner, 8 launcher aliases with
  distinct icons, shortcut/notification/action-bar icon sets. Every icon has a checksum
  entry in the audit.

## Probe harness (feeds AG-09/AG-12/compat-matrix)
Every probe = `{id, module_id(CORE/UI/ST/NET/SYS/MEDIA/LANG), domain, api,
result: OK|ERROR, error, duration_ms}`; Logcat tag `MAXPROBE/<MODULE_ID>` + append to
`maxprobe-report.json`. Cover Apêndice C domains end-to-end: lifecycle, pm, all widgets,
graphics/canvas, text, os/handler, sqlite+Room, providers, net (record/replay fixtures),
media, camera2, sensors (ALL types), location, telephony, bluetooth LE, NFC, keystore+
biometric, accounts, TTS, widgets, print, job/work/alarms, notifications (all styles),
clipboard, LocaleManager, WebView+JS bridge, GLES probes, JNI matrix (strings/arrays/
direct ByteBuffer/exceptions/AttachCurrentThread).

# ENGINE MATRIX — ONE APK PER LANGUAGE (suites/engines/, 28+)
Mirror RustyDroid Apêndice G exactly. Each dir = `engine-NN-<lang>/` with build script +
`expected-engines.json` (engine ids + artifacts the detector MUST match) + README.
**Tier A — real CI builds:** 01 Java (DEX, multi-dex, invoke-custom), 02 Kotlin,
03 KMP/Compose-MP shared DEX, 07 C NDK, 08 C++ NDK+STL, 09 Rust (cargo-ndk jni crate),
10 Go (gomobile bind), 12 Zig (zig cc .so), 24 Haxe, 30 WASM-in-app (wasmtime-compiled
module in assets + JS/JNI host), 25 Python-Chaquopy, 16 Tauri v2, 06 Groovy.
**Tier B — heavy toolchains, gated nightly jobs:** 13 Flutter (libapp.so+flutter_assets),
14 React Native (Hermes bundle), 15 Cordova (assets/www), 17 NativeScript, 23 Godot
(headless export .pck+libgodot), 26 Qt/QML, 28 Avalonia (.NET), 04 Scala, 22 Lua-Defold.
**Tier C — detection fixtures (synthetic, honest):** 05 Clojure, 11 ObjC, 18 MAUI/Xamarin
(assemblies/*.dll stubs), 19 Unity Mono (Assembly-CSharp.dll stub), 20 Unity IL2CPP
(libil2cpp.so+global-metadata.dat stubs), 21 Unreal (libUE4.so stub+pak), 27 B4X/App
Inventor, 29 Python-Kivy/BeeWare, TWA/PWA (assetlinks+manifest markers). Fixtures built by
`tools/fixture-pack.py` with correct artifact layout/ELF markers; README states plainly:
"detection fixture, payload not executable". CI matrix marks tier per job. Total ≥ 30 APKs
(hybrid #31: Kotlin+Rust+Hermes+wasm in ONE apk — unified coverage test, TST-14).

# SDK LADDER + PARSER TORTURE (suites/)
- **sdk-ladder**: same 1-activity+1-service+1-receiver+1-provider app built at
  minSdk 9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36 (classic uses framework-only code;
  if AGP refuses minSdk<19 pin AGP 7.4.2 for that module or use `tools/fixture-pack.py`
  with aapt2+d8 directly — the minSdk 9 fixture MUST exist either way). RustyDroid must
  answer `BELOW_FLOOR(minSdk=…)` for <26 and execute ≥26.
- **parser-torture**: v1-only/v2-only/v3-only signatures, unaligned, ZIP64 >65k entries,
  10k-entry resources.arsc with 40 locales + all densities, 8-way multi-dex,
  `unknown-perms` (fake permission strings), exported-audit trap set (intentional
  exported/permission mistakes the audit documents), obfuscated R8 + mapping.

# PROFESSIONAL GITHUB (pillar 5 — same grade as RustyDroid)
- **Governance**: README PT+EN with logo/badges, CONTRIBUTING (per-tier toolchain setup),
  CODE_OF_CONDUCT, SECURITY.md, SUPPORT.md, GOVERNANCE.md, ADRs in docs/adr/, issue
  templates (bug / fixture_gap / size_regression), PR template, labels.json, milestones
  A0–A8, semver 0.x→1.0 (1.0 = full matrix green + size gate + nightly compat), Keep a
  Changelog, dual license MIT OR Apache-2.0.
- **CI (GitHub Actions)**: `ci.yml` (fmt/shellcheck/python-lint + Tier A builds + unit),
  `size-gate.yml` (flagship ∈ [850,1000] MB + size-report diff, fail >+2% drift),
  `engines-nightly.yml` (Tier B matrix + runs `scripts/compat-nightly.sh` → rustydroid
  inspect/detect/test on ALL fixtures → publishes `docs/compat-matrix.md` to GH Pages,
  auto-opens `fixture_gap` issues on regressions), `release.yml` (attaches all APKs +
  contracts to GitHub Releases, reproducible-build check via `verify-deterministic.sh`:
  two builds byte-identical except signature).
- **Docs site**: mdBook — guide, engine matrix table (tier/status/size), permission
  matrix, minSdk ladder table, RustyDroid integration guide (exact CLI commands:
  `rustydroid inspect --json` diff vs audit, `rd engine detect` vs expected-engines.json,
  `rustydroid test contracts/suites.json`, `get_compat_gaps` snapshot).
- **Docs language**: repo docs in PT-BR (matching RustyDroid) + README.en.md.

# DELIVERY PHASES (build in this order; each phase compiles green)
- **A0** repo scaffold + governance files + CI skeletons + tools/ generators
- **A1** flagship skeleton (probe harness, manifest-complete with EVERY permission,
  PermissionsHub + ButtonGrid + IconGrid) — small assets, size ~30 MB
- **A2** sdk-ladder (minSdk 9 first!) + parser-torture pack
- **A3** engine Tier C fixtures (fast) + expected-engines.json
- **A4** engine Tier A real builds (Java→Kotlin→C/C++→Rust→Go→Zig→Wasm…)
- **A5** 3D/shader pillar (`:sim3d` golden sim + shader-library + textures/meshes/audio)
- **A6** size engineering to the [850,1000] MB gate + size-report.csv
- **A7** Tier B nightly jobs + compat-nightly + docs site
- **A8** v1.0 gate: full matrix green, deterministic build proven, release v1.0.0

# DEFINITION OF DONE
[ ] ≥30 APKs buildable from clean checkout with documented toolchains (Tier C needs none)
[ ] Flagship release ∈ [850 MB, 1000 MB], R8-optimized, size-report.csv reconciles bytes
[ ] permissions-audit.md: ~160 permissions, counts per protectionLevel match the manifest
[ ] minSdk 9 APK exists and is accepted by the build path (or packed fixture) 
[ ] `:sim3d` golden checksums reproducible; GLES probes → structured errors only
[ ] ButtonGrid 1200 + IconGrid 600 + 500+ vector drawables + adaptive/monochrome icons
[ ] `rustydroid inspect` on every APK diffs numerically against its audit (zero drift)
[ ] `expected-engines.json` matches `rd engine detect` for all 31 engine APKs
[ ] Two consecutive release builds byte-identical (determinism proof)
[ ] Repo has full governance kit, mdBook docs, 5 workflows, milestones A0–A8, v1.0.0 release
````

---

## Suggested PARTE 0 selection when testing with RustyDroid
`PRESET: COMPLETO` (this suite exists to exercise everything — including the
experimental engines), plus `PRF-05` for the multi-app/IPC tests and `PRF-07` for the
minSdk/targetSdk behavior switches.

## Hard-truth notes (documented in the repo, keep them)
- minSdk 9 is **below RustyDroid's floor**: expected result is structured
  `BELOW_FLOOR(minSdk=9)` — that IS the test (error law, never crash).
- Tier C fixtures are honest synthetic detection targets (RustyDroid's own law:
  "detecção não valida payload nem autoriza execução" — ADR 003).
- Signature/`@hide` permissions are unobtainable on real devices; the flagship tests
  RustyDroid's *classification*, not device installability.
- 850 MB+ APKs: sideload scale only (Play limit ~200 MB base) — fine, this is a fixture.
