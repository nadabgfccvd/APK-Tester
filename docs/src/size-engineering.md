# Engenharia de tamanho — o gate [850, 1000] MiB do flagship

Status: **entregue (A6)**. O flagship "Behemoth" (`dev.apktester.behemoth`)
compila um release `modern` dentro da faixa **[850 MiB, 1000 MiB]**, com o
`tools/size-budget.sh` emitindo o `contracts/flagship/size-report.csv`
(bytes descomprimidos por categoria) e o workflow **Size Gate** falhando fora
da faixa ou com drift de tamanho acima de **±2% por categoria**.

## Modelo de tamanho (A6)

| Fonte | Volume (descomprimido) | Categoria no CSV |
|---|---|---|
| gen-meshes (teapot, terreno 1024², crowd 50k) | ~120,6 MB | `meshes` |
| gen-audio (2 loops 5.1 reais) | ~17,3 MB | `audio` |
| gen-textures (48 KTX2 PBR 256²) | ~12,6 MB | `textures` |
| shader-library (239 programas + blobs SPIR-V style) | ~2,5 MB | `shaders` |
| **gen-bulk preset `full`** (carga determinística) | **805.306.756 B (768 MiB)** | textures/meshes/audio/other |
| dex (R8 full) + arsc + res + manifest | ~2 MB | `dex`/`arsc`/`resources` |
| **Total esperado do release modern** | **~960.779.683 B (≈916 MiB)** | — |

O gate mede o tamanho **descomprimido** das entradas do ZIP
(`file_size`), na unidade MiB (bytes / 1024²). A carga `full` é composta de
alta entropia (keystream SHA-3 shake_256), logo não comprime e o tamanho do
arquivo APK acompanha o tamanho descomprimido — o CSV é estável por
construção, não por coincidência.

## A carga determinística (`tools/gen-bulk.py`)

Gerador build-time (python3 stdlib-only, seed `20261022`) que produz
`assets/bulk/{textures,meshes,audio,data}/` + `assets/bulk/manifest.json`:

- **`textures/bulk_tex_NN.ktx2`** — 6 × ~32 MiB, cabeçalho KTX2 estrutural
  (magic `«KTX 20»\r\n\x1a\n`, vkFormat 65 = R5G6B5) + payload keystream.
- **`meshes/bulk_mesh_NN.ply`** — 4 × ~24 MiB, PLY binário little-endian
  válido (cabeçalho ASCII + vértices float32 de ruído determinístico).
- **`audio/bulk_stem_NN.wav`** — 8 × 16 MiB, WAV PCM16 mono 8 kHz válido
  (amostras de ruído determinístico — "stems" sintéticos).
- **`data/bulk_data_NN.bulk`** — 11 × 32 MiB, cabeçalho `APKT-BULK1` com JSON
  declarativo + payload keystream.

**Declaração de honestidade**: todo payload é keystream
`shake_256(seed:kind:ordinal)` — ruído determinístico, sem conteúdo capturado.
O `manifest.json` dentro do APK declara `synthetic: true` por arquivo, com
`sha256` e tamanho exatos; `--verify DIR` reconfere a árvore contra o
manifest e o `--selftest` prova determinismo byte a byte (9 provas).
Folga de cabeçalho por arquivo (KTX2/PLY/WAV) é documentada no manifest —
os totais reais são 805.306.756 B (`full`) e 15.728.846 B (`quick`).

### Presets e o modelo de dois modos

| Preset | Tamanho | Uso |
|---|---|---|
| `full` (default) | 768 MiB | release do Size Gate (assemble modern release) |
| `quick` | 15 MiB | builds de debug no CI (`-PbulkPreset=quick`) e scripts locais |

O CI de correção (`ci.yml`) compila os **debugs** com `quick` para não
custar ~2 GB de artefatos/empacotamento por push; o **Size Gate**
(`size-gate.yml`) é a autoridade de tamanho e compila o release com
`full`. O `tools/verify-deterministic.sh` também força `quick`
(mapa `turbo_args`). A diferença entre os dois presets afeta apenas
`assets/bulk/**` — nada de dex/arsc/res muda entre eles.

## Release "fully optimized"

- **R8 full mode** (`isMinifyEnabled` + `proguard-android-optimize.txt`) +
  regras próprias (`app/proguard-rules.pro`): `native <methods>` preservados
  por nome (JNI) e o bloco `sim3d.nativecompat` mantido (carregado por
  reflexão quando a biblioteca existe). Dex resultante: ~57 KB.
- **Resource shrinking ON** (`isShrinkResources`) com
  `res/raw/keep.xml` mantendo as famílias resolvidas só via
  `getIdentifier()` (`btn_label_%04d`, `ic_vector_%04d` — 1.800 recursos).
  O passo `aapt2 optimize` encurta os caminhos de `res/` (ex.:
  `res/drawable/ic_vector_0001.xml` → `res/Bw.xml`) sem remover conteúdo.
- **`vcsInfo.include = false`** — nenhum metadado de VCS dependente de
  ambiente dentro do APK.
- **Assinatura determinística**: keystore de fixture commitado como TEXTO
  base64 (`suites/flagship/keystore/behemoth-test.keystore.b64`,
  PKCS12 RSA-2048, senha `behemoth2026` documentada — não é segredo),
  decodificado pela tarefa `decodeKeystore`. Builds release são
  byte-reproduzíveis entre máquinas (a alternativa `~/.android/debug.keystore`
  varia por host e quebraria o `sha256_of_apk` do CSV).
- **Libs nativas descomprimidas** (`jniLibs.useLegacyPackaging = false`) —
  contrato do flagship com `:native`/`:rust` no modern (R2.2; ambos
  modern-only pelo piso do NDK 27 = API 21); zipalign é padrão do AGP no
  release.

## Gate e drift no CI

`tools/size-budget.sh --apk <apk> --baseline contracts/flagship/size-report.csv
--report dist/size-report.csv --min-mb 850 --max-mb 1000`:

1. Escreve o CSV fresco (artefato disponível mesmo em falha).
2. **Gate**: total descomprimido fora de [850, 1000] MiB → exit 1.
3. **Drift** por categoria (10 + total) vs o CSV commitado:
   `drift = (novo − antigo) / antigo`; FAIL se `> +2%` ou `< −2%`.
   Categorias com baseline 0 são SKIP (bootstrap do relatório A0);
   categoria que aparece/desaparece de um lado → FAIL. A coluna
   `sha256_of_apk` é ignorada no drift (assinatura/metadados de zip podem
   variar por ambiente).

O relatório medido é commitado como baseline logo após a primeira execução
verde do Size Gate; a partir daí qualquer crescimento ou encolhimento
acidental de tamanho acima de ±2% quebra o CI — mudanças intencionais de
tamanho exigem commit do CSV atualizado no mesmo PR.

## Sobre o piso de 850 MiB

APKs de 850 MiB+ ficam fora do Play (base ~200 MB) — este é um fixture de
teste de ferramentas (`rustydroid`/APKBot), distribuído por sideload. O piso
existe para forçar o exercício real de payloads grandes (análise de arsc,
dex, assets) que ferramentas de inspecção encontram no mundo real.
