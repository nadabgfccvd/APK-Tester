# engine-23-godot — Tier B (build real no nightly)

**Engine engine-23 da matriz RustyDroid (Apêndice G): GDScript/Godot.**
Build REAL no `engines-nightly.yml`: editor **Godot 4.3-stable** (GitHub
Releases `godotengine/godot`) headless + export templates Android oficiais
(`.tpz` ~1.1 GB) → `--headless --export-release "Android"` com o preset
commitado (`export_presets.cfg`, placeholders de keystore reescritos em
build) — APK real assinado com o keystore do pack, `assets/*.pck` incluído.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** godot `4.3-stable`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · preset `package/unique_name`
  `dev.apktester.engine.engine23godot` · seed 20261022

## Custos honestos

Download ~1.1 GB dos templates por build (nightly, `fail-fast: false`).
Se o template oficial não incluir `lib/x86_64/libgodot_android.so`, o
nightly abre `fixture_gap` e o answer key é refinado contra o artefato
REAL (mesma lei dos refinamentos de A7).
