# engine-23-godot — Tier B (build real no nightly)

**Engine engine-23 da matriz RustyDroid (Apêndice G): GDScript/Godot.**
Build REAL no `engines-nightly.yml`: editor **Godot 4.3-stable** (GitHub
Releases `godotengine/godot`) headless + export templates Android oficiais
(`.tpz` ~1.1 GB). O export `--export-release "Android"` produz o APK do
template oficial (fonte dos `libgodot_android.so` reais, arm64-v8a +
x86_64) e o `--export-pack "Android"` produz o `game.pck` REAL (magic
`GDPC`, pipeline de export oficial) — os dois empacotados pelo caminho
comum do orquestrador (aapt2 → d8 → zipalign → apksigner v1+v2 com o
keystore do pack). Descobertas honestas do A7, documentadas no preset e
no projeto: (1) o export 4.3 sem gradle NÃO embute um `.pck` (assets
soltos), por isso o par export-release/export-pack; (2) a validação
silenciosa `should_import_etc2_astc()` exige
`rendering/textures/vram_compression/import_etc2_astc=true` no
`project.godot`; (3) o export-release assina com o keystore RELEASE do
preset (placeholders reescritos em build).

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
