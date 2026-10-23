# engine-13-flutter — Tier B (build real no nightly)

**Engine engine-13 da matriz RustyDroid (Apêndice G): Dart/Flutter.**
Build REAL no `engines-nightly.yml`: Flutter SDK **3.24.5 estável** (tarball
oficial `flutter_infra_release`), `flutter create --platforms android` +
`flutter build apk --release --target-platform android-x64`. O `lib/main.dart`
commitado substitui o gerado. A toolchain produz o APK final (gradle assina
com o debug keystore do runner).

- **Build:** `./build.sh --out dist` (baixa o SDK para a árvore de trabalho;
  use `FLUTTER_ROOT` para reaproveitar uma instalação local)
- **Pinos:** flutter `3.24.5`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine13flutter` · seed 20261022

## Artefatos de detecção

`lib/x86_64/libflutter.so` + `lib/x86_64/libapp.so` (AOT Dart) +
`assets/flutter_assets/` — verificados por `--verify-apk`.

## Custos honestos

Download ~1 GB do SDK + gradle/AGP na primeira build (~10–20 min no runner).
A build do flutter não é byte-determinística; o determinismo byte-a-byte do
repo continua sendo prova dos geradores seedados e do A8.
