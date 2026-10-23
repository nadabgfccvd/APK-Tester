# engine-22-lua-defold — Tier B (build real no nightly)

**Engine engine-22 da matriz RustyDroid (Apêndice G): Lua/Defold.**
Build REAL no `engines-nightly.yml`: `bob.jar 1.9.8` (GitHub Releases
`defold/defold`) roda o pipeline de conteúdo Defold sobre o projeto
commitado (`defold/`) — `game.arcd`/`game.arci` reais em `build/default`;
o `libdmengine_release.so` (engine Android real, embutido no próprio
bob.jar) vira `lib/arm64-v8a/libdmengine.so`.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`;
  requer Java 21+ — bob.jar é class-file 65)
- **Pinos:** defold-bob `1.9.8` (sha1 67542769598a1b794877c96f740f3f527f63f491)
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine22lua...` · seed 20261022

## Notas honestas

- O `game.project` commitado usa `main_collection = /main/main.collectionc`
  (bob 1.9.8 resolve o recurso compilado; com `.collection` cru o
  `checkResource` do bob falha — descoberto e documentado no A7).
- A build do bob não é byte-determinística (dmanifest tem caminhos locais);
  o determinismo byte-a-byte segue sendo prova dos geradores seedados.
- bob.jar só embute o engine Android para `arm64-android`; o answer key
  foi refinado em A7 para `lib/arm64-v8a/libdmengine.so` (antes:
  `lib/x86_64/`).
