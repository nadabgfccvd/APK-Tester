# engine-26-qt-qml — Tier B (build real no nightly)

**Engine engine-26 da matriz RustyDroid (Apêndice G): QML/Qt.**
Build REAL no `engines-nightly.yml`: kit Qt **6.6.3** `android_x86_64`
oficial via `aqtinstall 3.3.0` (download.qt.io) → `libQt6Core_x86_64.so` e
`libQt6Qml_x86_64.so` REAIS → `lib/x86_64/`; QML commitado → `assets/qml/`.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** qt `6.6.3`, aqtinstall `3.3.0`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine26qtqml` · seed 20261022

## Nota honesta

O repositório oficial do Qt só publica kits Android pré-construídos até a
6.6.3 no canal `qtsdkrepository` (6.7+ exige build); o pin reflete o que é
REALMENTE baixável. Esta é a estratégia "real enxuta": libs de runtime
oficiais + conteúdo QML próprio, sem qmake/gradle — documentada para o
detector (ADR 0003).
