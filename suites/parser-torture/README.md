# suites/parser-torture — pacote de tortura de parser

Fixtures criados para atacar cada suposição perigosa dos parsers do
RustyDroid (ZIP, assinaturas, AXML, ARSc, DEX, manifest). Cada item do
pacote é um APK com uma única patologia — para que o gabarito isole a causa.
Todos são gerados por `tools/fixture-pack.py` (python3, stdlib-only,
determinístico) e acompanhados de auditoria esperada.

## O pacote

| Fixture | Patologia | O que provar |
|---|---|---|
| `sig-v1-only` | apenas assinatura v1 (JAR) presente | parser lê esquema v1 isolado |
| `sig-v2-only` | apenas assinatura v2 (APK Signing Block) | parser lê v2 sem v1 |
| `sig-v3-only` | apenas assinatura v3 (key rotation) | parser lê v3 sem v1/v2 |
| `unaligned` | entradas sem zipalign | parser não assume alinhamento |
| `zip64-65k` | ZIP64 com mais de 65.535 entradas | offsets/contagens de 64 bits corretos |
| `huge-arsc` | `resources.arsc` com 10k entradas, 40 locales e todas as densidades | ARSc grande e multi-locale sem OOM/timeout |
| `multidex-8` | 8 arquivos `classesN.dex` | carregamento de multi-dex completo |
| `unknown-perms` | strings de permissão inventadas/inexistentes | classificação `unknown` estruturada — **único fixture com permissões falsas** |
| `exported-audit` | conjunto de armadilhas: `exported`/permissões mal declaradas de propósito | auditoria documenta cada erro intencional (teste do manifest-as-truth) |
| `obfuscated-r8` | R8 full com ofuscação + `mapping.txt` | resolução de nomes ofuscados via mapping |

## Regras do pacote

- Permissões **inventadas** existem APENAS aqui (`unknown-perms`) — nunca no
  flagship (ver hard-truths no [README.md](../../README.md)).
- As armadilhas de `exported-audit` são **intencionais e documentadas** no
  gabarito; o CI compara o relato do RustyDroid com a lista de erros
  esperados.
- Todos os fixtures são determinísticos: duas execuções do gerador produzem
  bytes idênticos (`tools/verify-deterministic.sh`).

## Status

| Item | Status |
|---|---|
| Pacote completo (10 fixtures + gabaritos) | **entregue (A2)** — 11 modos em `tools/fixture-pack.py` (os 10 + `minSdk9` da escada), toolchain real aapt2+d8+zip+zipalign+apksigner |
| Contratos | `contracts/parser-torture/` (fixtures-audit, huge-arsc-audit, exported-audit-traps, suites-fragment, ledger `manifest.json`) — gerados por `tools/gen-torture-contracts.py`, zero drift |
| ARSc sintético | `tools/gen-arsc-stress.py` (10.000 entradas × 40 locales + 7 densidades; binário NÃO commitado — sha256 no `arsc-report.json` é a âncora) |
| Build no CI | job `parser-torture` em `.github/workflows/ci.yml` (empacota as 10 + valida cada uma: esquemas de assinatura, zip64, multidex, arsc, armadilhas, mapping) |
