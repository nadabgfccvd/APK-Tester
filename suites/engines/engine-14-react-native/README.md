# engine-14-react-native — Tier B (build real no nightly)

**Engine engine-14 da matriz RustyDroid (Apêndice G): JS/React Native.**
Build REAL no `engines-nightly.yml` com as peças oficiais do RN 0.76.9:

- `hermesc` (binário ELF estático do tarball npm `react-native@0.76.9`)
  compila `assets-src/index.js` → `assets/index.android.bundle` (bytecode
  Hermes real, magic `0x1F1903C6`);
- `libhermes.so` real do AAR `com.facebook.react:hermes-android:0.76.9`
  (Maven Central) → `lib/x86_64/`;
- `classes.jar` do AAR `com.facebook.react:react-android:0.76.9` → d8 →
  `classes.dex` com strings `com.facebook.react`.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** react-native `0.76.9`, hermes-android `0.76.9`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine14reactnative` · seed 20261022

## Nota honesta

Esta é a estratégia "real enxuta" (artefatos oficiais do RN + payload
compilado pela toolchain oficial), sem a build gradle completa do template
RN — documentada para o detector; a detecção não valida payload (ADR 0003).
