# Fixtures Audit — pacote parser-torture (10 fixtures)

Gerado por `tools/gen-torture-contracts.py` (seed 20261022) lendo a tabela MODES
de `tools/fixture-pack.py` — zero drift entre esta auditoria, o
fragmento de suites e as ferramentas que empacotam os APKs.

Cada fixture ataca UMA suposição perigosa dos parsers do RustyDroid
(ZIP, assinaturas, AXML, ARSc, DEX, manifest) e é empacotada por
`tools/fixture-pack.py` (aapt2 + d8 + zip + apksigner, sem gradle).

| Modo | APK | minSdk | targetSdk | v1 | v2 | v3 | Patologia | Resultado esperado no RustyDroid |
|---|---|---|---|---|---|---|---|---|
| `sig-v1-only` | `sig-v1-only.apk` | 9 | 36 | sim | nao | nao | apenas assinatura v1 (JAR) presente | parser lê esquema v1 isolado |
| `sig-v2-only` | `sig-v2-only.apk` | 24 | 36 | nao | sim | nao | apenas assinatura v2 (APK Signing Block) | parser lê esquema v2 sem v1 |
| `sig-v3-only` | `sig-v3-only.apk` | 28 | 36 | nao | nao | sim | apenas assinatura v3 (rotação de chave) | parser lê esquema v3 sem v1/v2 |
| `unaligned` | `unaligned.apk` | 26 | 36 | sim | sim | nao | entradas sem zipalign | entradas desalinhadas parseadas |
| `zip64` | `zip64-65k.apk` | 26 | 36 | sim | nao | nao | >65.535 entradas (Zip64 EOCD) como data entries | offsets/contagens Zip64 corretos |
| `huge-arsc` | `huge-arsc.apk` | 26 | 36 | sim | sim | nao | resources.arsc sintético: 10k entradas x 40 locales + 7 densidades | ARSc 10k x 40 locales parseado sem OOM/timeout |
| `multidex-8` | `multidex-8.apk` | 21 | 36 | sim | sim | nao | 8 arquivos classesN.dex (multidex nativo, minSdk 21) | 8 classesN.dex carregados |
| `unknown-perms` | `unknown-perms.apk` | 26 | 36 | sim | sim | nao | strings de permissão inventadas dev.apktester.fake.* | permissões desconhecidas classificadas como unknown — nunca crash |
| `exported-audit` | `exported-audit.apk` | 26 | 36 | sim | sim | nao | 9 componentes-armadilha (exported/permissões mal declaradas) | 9 armadilhas reportadas na auditoria |
| `obfuscated` | `obfuscated-r8.apk` | 26 | 36 | sim | sim | nao | nomes minificados determinísticos + mapping.txt | nomes ofuscados resolvidos via mapping.txt |

## Notas do pacote

- POJOs sem imports `android.*`: o javac do pack roda sem android.jar;
  a verdade de componentes é o AndroidManifest.xml (CORE-12).
- Determinismo: seed canônica 20261022, stdlib-only; duas execuções
  dos geradores produzem bytes idênticos (`verify-deterministic.sh`).
- `unknown-perms` é o ÚNICO lugar do repo com strings de permissão
  inventadas — nunca no flagship.
- `exported-audit` é INTENCIONAL: as violações de exported/permissões
  estão documentadas em [exported-audit-traps.md](exported-audit-traps.md)
  e em `traps-report.json` (2 baselines de contraprova).
- `obfuscated-r8` é proxy honesto de ofuscação: nomes minificados
  determinísticos + `mapping.txt` DENTRO do APK em `assets/mapping.txt`
  (R8 real chega nos builds Tier A / release A6).
- `huge-arsc`: o resources.arsc sintético é gerado no pack e NÃO é
  commitado — o sha256 canônico em `arsc-report.json` (e a auditoria
  [h[huge-arsc-audit.md](huge-arsc-audit.md)) é a âncora.
- `multidex-8`: corpus do `gen-dex-stress` fatiado em 8 lotes
  contíguos -> classes.dex..classes8.dex na raiz do APK.
- `sig-v1-only` (minSdk 9), `sig-v2-only` (minSdk 24) e `multidex-8`
  (minSdk 21) ficam abaixo do piso 26 do RustyDroid: `below_floor_allowed`
  cobre o BELOW_FLOOR estruturado — nunca crash.
- Verificação de assinatura no CI limita o range de plataformas do
  `apksigner verify` (`--min-sdk-version`/`--max-sdk-version`): o
  apksigner simula INSTALAÇÃO (API 24+ exige v2 "ou posterior") e
  estas fixtures são alvos de PARSER, não de instalação — v1-only
  se verifica contra 9..23, v2-only contra 24+, v3-only contra 28+.

## Contratos deste diretório

| arquivo | conteúdo |
|---|---|
| `fixtures-audit.md` | esta visão geral |
| `exported-audit-traps.md` | tabela das 9 armadilhas (idem `gen-trap-manifest`) |
| `huge-arsc-audit.md` | contagens + validação do ARSc sintético |
| `suites-fragment.json` | as 10 entradas de `contracts/suites.json` |
| `manifest.json` | ledger com sha256 de cada arquivo gerado |
