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

- **Permissões — literalmente todas (~160):** todo o conjunto de
  `frameworks/base/core/res/AndroidManifest.xml` — `normal`, `dangerous`
  (todos os grupos), `signature`/`signatureOrSystem` (todos os `BIND_*`,
  `WRITE_SECURE_SETTINGS`, `DUMP`, `READ_LOGS`, …), special-app-access,
  todos os `FOREGROUND_SERVICE_*`, variantes deprecadas com `maxSdkVersion`,
  e strings `@hide`/internas (marcadas na auditoria). Também declara
  `<uses-permission-sdk-23>`, `<permission>` custom (normal + signature),
  `<permission-group>` e `<permission-tree>`.
  Gabarito: `contracts/flagship/permissions-audit.md`. Strings de permissão
  inventadas ficam APENAS em `suites/parser-torture/unknown-perms`.
- **Manifest de superfície máxima (stress CORE-12):** 30+ activities, 2
  aliases, 15+ services (foreground com todos os tipos + 16 services de
  sistema com seus `BIND_*`), 10+ receivers, 2 providers, 2 widgets,
  instrumentation, `<queries>`, `<uses-feature>`, glEsVersion, deep links
  com autoVerify, configs de tela, backup/network security (com conflito
  deliberado documentado), `sharedUserId` só no classic.
- **UI de automação:** PermissionsHub (um botão por permissão, ~160),
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
- `contracts/flagship/permissions-audit.md` — as ~160 permissões com
  protectionLevel, grupo, maxSdk e flag `@hide`
- `contracts/flagship/api-probe-registry.json` — registro de probes
- `contracts/flagship/size-report.csv` — bytes por categoria (texturas /
  meshes / shaders / áudio / dex / arsc / so / locales), emitido por
  `tools/size-budget.sh`
- `contracts/flagship/sim3d-golden.json` — checksums golden do `:sim3d`

## Status

| Item | Status |
|---|---|
| Esqueleto do flagship (probe harness + manifest completo + PermissionsHub + ButtonGrid + IconGrid, ~30 MB) | **chega em A1** |
| Pilar 3D/shaders (`:sim3d` golden + shader-library) | planejado (A5) |
| Size gate completo ∈ [850 MB, 1000 MB] + `size-report.csv` | planejado (A6) |

Nota: APKs de 850 MB+ são escala de sideload apenas (limite do Play ~200 MB
de base). Este fixture não se destina a lojas de aplicativos — ver hard-truths
no [README.md](../../README.md) raiz.
