# size-report.csv — nota de uso

Este CSV é a answer key de tamanho do flagship Behemoth
(`dev.apktester.behemoth`), emitido por `tools/size-budget.sh` sobre o
release `modern` (`:app:assembleModernRelease`).

- **Estado A6**: gate REAL ativo. O workflow Size Gate (`size-gate.yml`)
  compila o release com a carga determinística completa
  (`tools/gen-bulk.py --preset full`, ~768 MiB sob `assets/bulk/`), mede o
  APK e aplica **duas checagens**:
  1. **Gate**: total descomprimido dentro de **[850 MiB, 1000 MiB]**
     (bytes / 1024², como imprime o script);
  2. **Drift**: por categoria (10 categorias + `total`) contra ESTE arquivo
     commitado — falha se qualquer categoria variar mais de **±2%**.
     Categorias com baseline `0` são SKIP (bootstrap do relatório A0);
     categoria que só existe de um lado → FAIL.
- **Bootstrap A6**: este baseline foi MEDIDO no CI (run
  `39990968533` do Size Gate, commit `306a05f`): total
  **960.783.552 bytes = 916,27 MiB em 1.435 entradas**, gate [850, 1000]
  MiB PASS. A primeira execução falhou apenas no drift contra o
  placeholder não-zero do A0 (a regra de SKIP cobre baselines zerados;
  o placeholder A0 tinha valores mínimos não-zero) — resolvido pelo
  commit deste CSV medido.
- **`sha256_of_apk`**: informativo (checksum do APK de origem da medição).
  É deliberadamente IGNORADO no drift: metadados de assinatura/zip podem
  variar entre ambientes; apenas `bytes` e `files` são contratuais.
- **Categorias** (bytes descomprimidos por categoria + contagem de
  arquivos; regras por extensão/magic — ver `tools/size-budget.sh`):
  - `textures` — `.ktx2/.ktx/.pkm/.astc/...` (gen-textures + `assets/bulk/textures/`)
  - `meshes` — `.obj/.glb/.gltf/.ply` (gen-meshes + `assets/bulk/meshes/`)
  - `shaders` — `.glsl/.vert/.frag/.comp/.spv` (shader-library)
  - `audio` — `.wav/.ogg/...` (gen-audio + `assets/bulk/audio/`)
  - `dex` — `classes*.dex`; `arsc` — `resources.arsc`; `so` — `lib/**/*.so`
  - `locales` — `res/values-*` e `assets/locales/`
  - `resources` — `res/**` e `AndroidManifest.xml`
  - `other` — o restante (inclui `assets/bulk/data/*.bulk` e manifestos JSON)
- **Presets**: os debugs do `ci.yml` usam `-PbulkPreset=quick` (~15 MiB de
  carga, para custo de CI); o Size Gate usa o `full` (~768 MiB). A
  diferença entre presets afeta APENAS `assets/bulk/**` — as demais
  categorias são idênticas. O CSV contratual é sempre medido no release
  com preset `full`.
- **Mudança intencional de tamanho**: atualize este CSV no MESMO PR que
  altera geradores/carga; o drift check tolera ±2% por categoria — acima
  disso o Size Gate falha.
- **Nota**: CSV não suporta linhas de comentário — por isso esta nota vive
  neste README e o CSV se mantém puro (parseável por
  `python3 -c "import csv; ..."` e pelo workflow).
