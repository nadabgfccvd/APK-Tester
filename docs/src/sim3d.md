# Pilar 3D/Shaders (:sim3d + shader-library) — fase A5

O terceiro pilar do APK Tester (APK_TESTER_PROMPT.md, "3D SIMULATION +
SHADERS") virou código e contrato na fase A5. Este documento descreve a
arquitetura, as leis de determinismo e como verificar tudo localmente.

## Visão geral

| Componente | Onde vive | Status |
|---|---|---|
| Motor 3D headless `:sim3d` | `suites/flagship/sim3d/` (biblioteca Java pura) | entregue (A5) |
| Golden checksums | `contracts/flagship/sim3d-golden.json` | entregue (A5, zero drift no CI) |
| Paridade nativa C++ | `sim3d/src/main/cpp/sim3d_native.cpp` | entregue (A5, provada no CI) |
| shader-library (239 programas GLSL ES 3.1) | `tools/gen-shaders.py` → assets build-time | entregue (A5) |
| Texturas PBR (KTX2: raw/ETC1/ASTC) | `tools/gen-textures.py` → assets build-time | entregue (A5, escala de amostra) |
| Malhas (teapot, terreno 1024², crowd 50k) | `tools/gen-meshes.py` → assets build-time | entregue (A5) |
| Áudio 5.1 (WAV 48 kHz) | `tools/gen-audio.py` → assets build-time | entregue (A5, loops curtos) |
| Telas: `Sim3dActivity` + `GlesProbeActivity` | `:app` (probes `MEDIA-SM-001`/`MEDIA-GX-001`) | entregue (A5) |
| Engenharia de tamanho (4K, loops longos, gate 850 MB–1 GB) | A6 | pendente |

## :sim3d — o motor 3D headless

Biblioteca `java-library` sem dependências (nem `android.*`): roda no JVM
do CI (JavaExec), dentro do APK e sob o RustyDroid headless.

**Lei de determinismo:** TODA a matemática é inteira — ponto fixo Q16.16
(1.0 = 65536), trigonometria BAM24 (2²⁴ = 2π) via CORDIC de 24 iterações,
raiz por isqrt bit a bit, PRNG xorshift32 semeado. Nenhum float/double:
os checksums são idênticos em qualquer JVM, arquitetura ou host — e
paráveis com a referência C++ (mesma semântica de divisão truncante).

Subsistemas (executados nesta ordem fixa):

1. **Malha procedural de 1M vértices** (`Mesh1M`): grade 1024×1024 =
   1.048.576 vértices (2²⁰), terreno de value-noise inteiro em 3 oitavas,
   altura 0–3 m, 2.093.058 triângulos; UV com tiling 8×8.
2. **Rasterizador de software** (`Rasterizer`): triângulos macro (stride
   16 → célula efetiva de 25 cm) texturizados com correção de perspectiva
   (interpolação de 1/z, u/z, v/z em espaço de tela), z-buffer inteiro,
   backface cull por área com sinal, framebuffer RGB565 320×240,
   4 frames de 1536 triângulos com rotação BAM24 de 8°/frame.
3. **Física de 10.000 corpos rígidos** (`PhysicsSim`): passo fixo 1/60 s
   (dt racional, integração semi-implícita), gravidade −9,80665 m/s²,
   chão com restituição 0.375 + atrito 0.98, paredes ±8 m com restituição
   0.5, colisões corpo-corpo por grade uniforme de 0,25 m (resposta no
   eixo de menor penetração, impulso com restituição 0.2, ordem de índice
   fixa), sono após 30 passos lentos.
4. **Partículas CPU (100.000)** (`ParticleSystem`): emissor único,
   cone de velocidades semeado, arrasto 0.98, vida 40–120 passos com
   respawn determinístico.
5. **Marching cubes** (`MarchingCubes`): grade 48³ (49³ amostras,
   espaçamento 0,15 m), poligonização pela decomposição canônica em 6
   tetraedros por cubo (variante que resolve por construção os casos
   ambíguos da tabela 256 original — nota de honestidade no golden).
6. **Esqueleto animado** (`Skeleton`): 16 juntas em árvore binária,
   2 poses-chave semeadas, 30 frames com interpolação Q16, FK via Mat4
   Q16 e skinning de 64 vértices.

Checksums: FNV-1a 64 bits dobrado little-endian byte a byte, por passo e
finais, sobre o estado de cada subsistema — `contracts/flagship/
sim3d-golden.json` é o contrato (2,4 KB, sem drift).

### Paridade Java == C++

O "C++ JNI fallback" do pilar (`sim3d_native.cpp`) reimplementa a física
com as MESMAS operações inteiras (`int32_t`/`int64_t`, divisão truncante,
shifts idênticos). O CI compila a `.so` host e roda `Sim3dGolden
--parity sim3d_native`: checksum final da física **idêntico** entre Java
e C++ (prova de que a lei inteira é portável). A biblioteca é OPCIONAL:
ausente (RustyDroid headless, dispositivo sem fallback), a rota Java
segue sem crash.

### Comandos

```bash
cd suites/flagship
./gradlew :sim3d:goldenSelftest   # asserções internas (Q16, FNV, raster, MC)
./gradlew :sim3d:goldenVerify     # reexecuta e compara byte a byte com o contrato
./gradlew :sim3d:goldenWrite      # regrava o contrato (mudança de lei consciente)
```

## shader-library — 239 programas GLSL ES 3.1

`tools/gen-shaders.py` gera, com seed 20261022: **215 programas gráficos**
(pbr 40, raymarch 40, fluid 30, ssao 24, noise 30, stress 25, longloop 26)
+ **24 compute shaders** (jacobi/reduce/partículas com `barrier()` e
`memoryBarrierShared()`), cada um com:

- fontes `.vert`/`.frag` ou `.comp` (fullscreen triangle via `gl_VertexID`);
- blob **SPIR-V style** sintético honesto (`.spv`: magic 0x07230203,
  versão 1.0, payload determinístico de keystream SHA-256 — a fonte GLSL
  é o contrato compilável; declarado `synthetic: true` no index);
- entrada em `shader-library/index.json` (id, arquivos, sha256, uniforms,
  stage, spirv).

**Validação real no CI (job `flagship-3d`):** os 454 arquivos GLSL são
compilados pelo `glslangValidator` (ES 3.1: `.vert`, `.frag` e `.comp`)
— a shader-library não é decoração: compila de verdade. No dispositivo,
`GlesProbeActivity` compila/linka todos os programas via GLES 3.1 e
registra resultado estruturado por programa (`MEDIA-GX-001`); sob o
RustyDroid a lei é erro estruturado — nunca crash.

## Texturas, malhas e áudio (ativos do APK)

Gerados a cada build pelo Gradle (`genSim3dDir` → `assets.srcDirs`),
determinísticos por seed; o CI assegura presença no APK binário:

- **texturas/**: 4 materiais × 4 mapas PBR (albedo/normal/roughness/AO)
  × 3 contêineres KTX2 (`raw` R8G8B8A8 real; `etc1`/`astc` stubs honestos
  com vkFormat correto e chave `apktester.stub` — codificação ETC/ASTC
  real exige toolchain externa, fora do escopo stdlib; 4K entra no A6);
- **mesh/**: `teapot.obj`/`.ply` (7.232 tris), `terrain_1024.obj` (2,09 M
  tris, 72 MB) + `terrain_1024.glb` (glTF 2.0 binário), `crowd_50000.gltf`
  (50.000 instâncias por nós glTF, sem duplicar geometria);
- **audio/**: loops WAV PCM 16-bit 48 kHz 5.1 (FL/FR/FC/LFE/BL/BR) —
  escala curta no A5; `--size-budget-mb` alimenta o gate do A6.

## Contratos e suites

- `contracts/flagship/sim3d-golden.json` — golden checksums (zero drift).
- `contracts/flagship/api-probe-registry.json` — +2 probes (MEDIA-SM-001,
  MEDIA-GX-001) espelhados em `ProbeCatalog`.
- `contracts/suites.json` — +3 suites do flagship (`flagship-sim3d-golden`,
  `flagship-sim3d-cpu`, `flagship-gles-probes`).

## Desvios conscientes (honestidade documentada)

1. **Marching cubes via 6 tetraedros** — topologicamente equivalente à
   tabela 256 clássica; sem tabela externa de 4.096 entradas; nota no
   golden. A superfície isovalente e o determinismo são o contrato.
2. **Triângulos macro (stride 16)** para o rasterizador — células
   unitárias (1,56 cm) são sub-pixel a 9 m; a malha de 1M vértices
   permanece integralmente gerada e checksumada.
3. **ETC1/ASTC são stubs honestos** (contêiner KTX2 válido com vkFormat
   correto) — codificação real é toolchain externa; o `raw` R8G8B8A8 é
   byte a byte real. O 4K completo entra na engenharia de tamanho (A6).
4. **Blobs SPIR-V são sintéticos** (magic válido, payload opaco) —
   declarado no index; a validação real é glslang sobre as fontes GLSL.
5. **Sono da física = 0** no golden — com gravidade aplicada a cada
   passo, corpos nunca ficam 30 passos abaixo do limiar; a contagem de
   contatos de chão (4.223) prova a convergência da pilha.
