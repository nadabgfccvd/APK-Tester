# engine-17-nativescript — Tier B (build real no nightly)

**Engine engine-17 da matriz RustyDroid (Apêndice G): JS/NativeScript.**
Build REAL no `engines-nightly.yml`: `libNativeScript.so` REAL extraído do
AAR `nativescript-regular.aar` do tarball npm `@nativescript/android@8.8.2`
(→ `lib/x86_64/`); o app JS commitado (`app.js`, `package.json`) vai para
`assets/app/` — a raiz que o runtime NativeScript carrega.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** nativescript-android `8.8.2`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine17nativescript` · seed 20261022

## Nota honesta

Nome REAL do runtime é `libNativeScript.so` (S maiúsculo); o answer key
canônico foi refinado em A7 para o nome real (antes: `libnativescript.so`).
