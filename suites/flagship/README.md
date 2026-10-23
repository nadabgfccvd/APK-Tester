# suites/flagship — "Behemoth"

O APK *flagship*: um único aplicativo que declara a maior superfície possível
de plataforma Android, com conteúdo real de 3D/áudio/texturas e gate de
tamanho rígido. É o fixture que estressa TODAS as camadas do RustyDroid ao
mesmo tempo — parsers, VM Dalvik, permission engine, registro de componentes,
UI e switches por targetSdk.

## Identidade

| Campo | Valor |
|---|---|
| applicationId | `dev.apktester.behemoth` |
| versionName | `1.0.0` |
| versionCode | `900036` |
| minSdk | 9 |
| targetSdk | 36 |
| Flavors | `classic` (framework-only, minSdk 9) e `modern` (androidx/compose, minSdk 26) |
| Módulos | `:app`, `:compose` (só modern), `:native` (C++ JNI, 4 ABIs), `:rust` (cargo-ndk `.so` com stub fallback), `:sim3d` (3D por software headless) |
| Size gate (release) | **∈ [850 MB, 1000 MB]**, totalmente otimizado (R8 full, resource shrinking, zipalign, native libs uncompressed) |

No flavor `classic` todo código androidx fica isolado: guards com
`Build.VERSION` + lazy init seguro contra `NoClassDefFoundError`, de modo que
o código faltante nunca é tocado em APIs antigas.

## O que o Behemoth carrega

- **Permissões — literalmente todas (1004, snapshot verbatim do AOSP
  master):** todo o conjunto de
  `frameworks/base/core/res/AndroidManifest.xml` — `normal`, `dangerous`
  (todos os grupos), `signature`/`signatureOrSystem` (todos os `BIND_*`,
  `WRITE_SECURE_SETTINGS`, `DUMP`, `READ_LOGS`, …), special-app-access,
  todos os `FOREGROUND_SERVICE_*`, variantes deprecadas com `maxSdkVersion`,
  e strings `@hide`/internas (marcadas na auditoria; 677 de 1004). Também
  declara `<uses-permission-sdk-23>`, `<permission>` custom (normal +
  signature), `<permission-group>` e `<permission-tree>`.
  Gabarito: `contracts/flagship/permissions-audit.md`. Strings de permissão
  inventadas ficam APENAS em `suites/parser-torture/unknown-perms`.
- **Manifest de superfície máxima (stress CORE-12):** 30+ activities, 2
  aliases, 15+ services (foreground com todos os tipos + 16 services de
  sistema com seus `BIND_*`), 10+ receivers, 2 providers, 2 widgets,
  instrumentation, `<queries>`, `<uses-feature>`, glEsVersion, deep links
  com autoVerify, configs de tela, backup/network security (com conflito
  deliberado documentado), `sharedUserId` só no classic.
- **UI de automação:** PermissionsHub (um botão por permissão, 1004),
  ButtonGrid 1.200 botões (`btn_0001`…`btn_1200`), IconGrid 600 ImageViews,
  500+ vector drawables, adaptive/monochrome icons, zoo de widgets,
  RecyclerView 10k, hierarquia aninhada de 60 níveis, tela Compose
  (modern), variantes RTL/pseudolocale/night.
- **3D + shaders (`:sim3d` + `shader-library/`):** rasterizador por software
  determinístico (1M vértices, z-buffer), física 10k corpos rígidos,
  partículas 100k, marching-cubes, animação esquelética; 200+ programas
  GLSL ES 3.1; checksums golden por step em
  `contracts/flagship/sim3d-golden.json`. GLES probes retornam erros
  estruturados (`NOT_IMPLEMENTED`) — nunca crash.
- **Probe harness:** probes `{id, module_id, domain, api, result, error,
  duration_ms}` com tag `MAXPROBE/<MODULE_ID>` e saída `maxprobe-report.json`;
  registro em `contracts/flagship/api-probe-registry.json`.

## Contratos (gabaritos)

- `contracts/flagship/manifest-audit.md` — auditoria do manifest
- `contracts/flagship/permissions-audit.md` — as 1004 permissões com
  protectionLevel, grupo, maxSdk e flag `@hide`
- `contracts/flagship/api-probe-registry.json` — registro de probes
- `contracts/flagship/size-report.csv` — bytes por categoria (texturas /
  meshes / shaders / áudio / dex / arsc / so / locales), emitido por
  `tools/size-budget.sh`
- `contracts/flagship/sim3d-golden.json` — checksums golden do `:sim3d`

## Build

```bash
cd suites/flagship
./gradlew :app:assembleClassicDebug :app:assembleModernDebug
```

Requisitos: JDK 17, Android SDK com `platforms;android-36` e
`build-tools;35.0.0`, AGP 8.9.2 e Gradle 8.11.1 (wrapper `./gradlew`).
No CI, o job `flagship-skeleton` do `.github/workflows/ci.yml` roda este
build, regenera o manifesto/auditorias com `tools/gen-flagship-manifest.py`
(provando zero drift com `git diff --exit-code`) e valida a superfície de
permissões no APK binário com `aapt2`.

## Estrutura do módulo `:app`

| caminho | conteúdo |
|---|---|
| `app/src/main/java/.../probe/` | probe harness (`MAXPROBE/<MODULE_ID>` + `maxprobe-report.json`), `BehemothInstrumentation` e telas de hub |
| `app/src/main/java/.../services/` | 17 services: 15 de sistema com `BIND_*` (Accessibility, NotificationListener, IME, VoiceInteraction, CallScreening, InCall, Print, Autofill, Tile, HostApdu, MediaBrowser, Wallpaper, Dream, Vpn, Credential) + Messenger + Foreground (todos os foregroundServiceType; DeviceAdmin é receiver — no total são 16 serviços de sistema) |
| `app/src/main/java/.../receivers/` | 10 receivers (BOOT/LOCALE/TIME/TIMEZONE/PACKAGE_REPLACED/MY_PACKAGE_REPLACED/USER_PRESENT/POWER/SCREEN + DeviceAdminReceiver) |
| `app/src/main/java/.../providers/` | 2 providers: `BehemothProvider` (SQLite CRUD) e `GuardedProvider` (read/writePermission por permissão custom signature) |
| `app/src/main/java/.../widgets/` | 2 app widgets (`BehemothAppWidget`, `SecondAppWidget`) |
| `app/src/main/res/` | res "de mão" commitado (XML de appwidget, regras de backup/rede, locales) |
| `app/src/classic/` + `app/src/modern/` | overlays de manifesto por flavor (minSdk 9 vs 26; `sharedUserId` só no classic; `extractNativeLibs`/`useLegacyPackaging` fica no build a partir de A4) |
| `app/build/generated/` + `app/src/main/assets/` | res e assets gerados em tempo de build pelos Exec tasks (`gen-strings` / `gen-icons` / `gen-assets` e, no A5, `gen-shaders` / `gen-textures` / `gen-meshes` / `gen-audio` — shader-library, texturas KTX2, malhas e áudio 5.1 sob `build/gen/sim3d`, seed 20261022) e pelo gerador de manifesto (assets `permissions/registry.json` + `permissions.tsv`) |

## Status

| Item | Status |
|---|---|
| Esqueleto do flagship (probe harness + manifest completo + PermissionsHub + ButtonGrid + IconGrid, ~30 MB) | **entregue (A1)** — módulo `:app` Gradle (AGP 8.9.2, Gradle 8.11.1, JDK 17) com flavors classic/modern; 5 activities, 2 activity-aliases, 17 services (16 de sistema contando o DeviceAdmin receiver), 10 receivers, 2 providers, 2 widgets, 1 instrumentation; 1004 `uses-permission`, 2 `<permission>` + 1 `<permission-group>` + 1 `<permission-tree>`; build real e zero-drift no CI |
| Pilar 3D/shaders (`:sim3d` golden + shader-library) | **entregue (A5)** — módulo `:sim3d` (biblioteca Java pura Q16 inteiro: malha 1M vértices, rasterizador perspectiva-correto com z-buffer, física 10k corpos, 100k partículas, marching cubes 48³, esqueleto 16 juntas) com golden byte a byte (`contracts/flagship/sim3d-golden.json`, zero drift no CI) e paridade nativa Java==C++ provada; shader-library de 239 programas GLSL ES 3.1 (215 gráficos + 24 compute) validados por glslang no CI; texturas PBR KTX2 + malhas (teapot/terreno 1024²/crowd 50k) + áudio 5.1 gerados build-time e empacotados no APK; telas `Sim3dActivity` (MEDIA-SM-001) e `GlesProbeActivity` (MEDIA-GX-001, erro estruturado — nunca crash) |
| Size gate completo ∈ [850 MB, 1000 MB] + `size-report.csv` | planejado (A6) |

Nota: APKs de 850 MB+ são escala de sideload apenas (limite do Play ~200 MB
de base). Este fixture não se destina a lojas de aplicativos — ver hard-truths
no [README.md](../../README.md) raiz.
