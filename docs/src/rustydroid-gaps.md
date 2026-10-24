# GAPs do detector — drafts para o repo irmão (RustyDroid)

Os GAPs de detecção do RustyDroid contra fixtures REAIS do APK Tester estão
documentados no answer key (`contracts/engines/expected-engines.json`, notas
por entrada). O PAT de manutenção deste repo NÃO tem escrita no repo irmão
(`POST /repos/nadabgfccvd/RustyDroid/issues` → 403 "Resource not accessible
by personal access token", reverificado em 2026-10-24 com o PAT vigente — o
`permissions` do `GET /repos` reflete o usuário, não os escopos do token).
Enquanto o acesso não for doado, os drafts abaixo estão prontos para o dono
colar como issues — um `code block` por issue, título e corpo em inglês
(convenção das issues do irmão).

Evidência comum a todos: nightly `engines-nightly.yml` verde com
`resumo: OK=56 FAIL=0 SKIP=0 SEM_APK=0` (run 40105414707) contra o snapshot
pinado do `rd` (fonte `89bbe8f`, main do irmão em 2026-10-24) — os GAPs não
são falha do fixture: o fixture existe, builda REAL e a matriz fica verde;
o id fino do registro é que não dispara.

---

## Draft 1 — `tauri` nunca dispara em build real (cargo-ndk layout)

```text
Title: Detector: `tauri` id never fires on a real Tauri v2 mobile build (cargo-ndk layout)

Body:
## Context
APK Tester fixture `engine-16-tauri` is a REAL Tauri v2 mobile build
(WebView system + tauri/wry Rust libs via cargo-ndk), not a synthetic stub.

## Evidence (rd snapshot 89bbe8f, nightly run 40105414707)
- `rd engine detect` emits only structural family candidates:
  c-ndk, cpp-ndk, generated-java, go-mobile, haxe, java, jvm-dynamic,
  kotlin, kotlin-multiplatform, objective-c-ndk, rust-ndk, zig-llvm.
- Expected registry id `tauri` never fires.
- Answer key entry: APK-Tester `contracts/engines/expected-engines.json`,
  `engine-16-tauri` (notes field documents the same finding).

## Root cause hypothesis
The registry markers for `tauri` diverge from the real cargo-ndk APK
layout (marker file paths / .so names differ from what the registry
expects).

## Suggested fix
Re-derive the `tauri` markers from a real `tauri android build` output
(libapp .so + wry/tauri runtime .so names + WebView asset layout) and
pin them in the registry; APK-Tester keeps the fixture as-is and will
follow the registry change via its answerkey_drift bot check.
```

## Draft 2 — regra Defold espera `libdefold.so`, o build real produz `libdmengine.so`

```text
Title: Detector: Defold rule expects `libdefold.so` but real builds ship `libdmengine.so`

Body:
## Context
APK Tester fixture `engine-22-lua-defold` is a REAL Defold build
(dmengine release embedded from bob.jar 1.9.8 + game.arcd/arci content
pipeline; Android ABIs arm64-v8a).

## Evidence (rd snapshot 89bbe8f, nightly run 40105414707)
- `rd engine detect` emits only structural family candidates (same set
  as other native fixtures); registry id `lua-engines` never fires.
- Real Defold Android builds produce `libdmengine.so`, not
  `libdefold.so` as the registry rule expects.
- Answer key entry: APK-Tester `contracts/engines/expected-engines.json`,
  `engine-22-lua-defold`.

## Suggested fix
Accept `libdmengine.so` (and ideally versioned variants `libdmengine
release/debug.so` naming produced by bob.jar) in the Defold registry
rule. APK-Tester will follow the registry change via its
answerkey_drift bot check.
```

## Draft 3 — `twa-pwa` exige marcadores que o fixture mínimo não tem

```text
Title: Detector: `twa-pwa` requires asset_statements/metadata — define the minimal marker set

Body:
## Context
APK Tester fixture `engine-32-twa-pwa` is a minimal-but-honest TWA
detection fixture (digital asset links + androidx.browser trusted
markers + empty activity). It does NOT carry `asset_statements` /
WebView metadata.

## Evidence (rd snapshot 89bbe8f, nightly run 40105414707)
- `rd engine detect` emits only structural family candidates; registry
  id `twa-pwa` never fires for this fixture.
- Answer key entry: APK-Tester `contracts/engines/expected-engines.json`,
  `engine-32-twa-pwa`.

## Ask
Document the MINIMAL marker set the detector requires for `twa-pwa`
(`asset_statements` in the manifest? WebView provider metadata?
androidx.browser version marker?). If the minimal set is small,
APK-Tester will extend the fixture; if a real TWA always carries it,
the registry position ("requires asset_statements") is correct and
only needs to be written down in the Appendix G row.
```

## Draft 4 — scala/clojure/groovy/b4x sem registro (28 ids)

```text
Title: Registry: no entries for scala / clojure / groovy / b4x-appinventor (28-id registry)

Body:
## Context
APK Tester ships 4 REAL fixtures whose languages have NO registry entry
in the 28-language detector registry:
- `engine-04-scala` (real nightly build, scala.runtime embedded in DEX)
- `engine-05-clojure` (detection fixture, clojure.lang strings)
- `engine-06-groovy` (real Groovy runtime DEX)
- `engine-27-b4x-appinventor` (detection fixture,
  anywheresoftware.b4a / com.google.appinventor strings)

## Evidence (rd snapshot 89bbe8f, nightly run 40105414707)
- All four emit only structural family candidates (e.g. generated-java,
  java, kotlin, jvm-dynamic); fine identification is only possible via
  `detector_artifacts` (e.g. `dex-strings:scala.runtime`), which the
  answer key records per fixture.
- Answer key entries: `contracts/engines/expected-engines.json`,
  `engine-04-scala`, `engine-05-clojure`, `engine-06-groovy`,
  `engine-27-b4x-appinventor`.

## Ask
Either (a) add registry rows for scala, clojure, groovy and
b4x/appinventor (Appendix G grows 28 -> 32), or (b) document the
official position that they are covered by the JVM family + detector
artifacts only — so downstream answer keys stop treating the absence
as a GAP. APK-Tester follows either decision via its answerkey_drift
bot check.
```

---

## Como doar (dono)

1. Abrir `https://github.com/nadabgfccvd/RustyDroid/issues/new`.
2. Colar título e corpo de cada draft (os 4 são independentes).
3. Opcional: label `detection`/`registry` conforme as labels do irmão.
4. Depois de doadas, apagar/rascunhar esta página ou marcar os números das
   issues criadas — o `answerkey_drift` do APKBot vigia o registro e
   acusará o drift quando o irmão mudar (comportamento desenhado).
