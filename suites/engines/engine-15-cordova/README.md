# engine-15-cordova — Tier B (build real no nightly)

**Engine engine-15 da matriz RustyDroid (Apêndice G): JS/Cordova.**
Build REAL no `engines-nightly.yml`: `cordova.js` REAL vem do template do
tarball npm `cordova-android@14.0.1`
(`package/templates/project/assets/www/cordova.js`); o `www` do fixture
(index.html/js/css commitados) e o `cordova_plugins.js` no formato canônico
do `cordova prepare` (lista vazia — projeto sem plugins) completam
`assets/www/`.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`)
- **Pinos:** cordova-android `14.0.1`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine15cordova` · seed 20261022

## Verificação

`--verify-apk` confere `assets/www/index.html`, `assets/www/cordova.js` e
`assets/www/cordova_plugins.js`.
