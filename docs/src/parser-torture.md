# Pacote parser-torture

Fixtures criadas para atacar cada suposição perigosa dos parsers do
RustyDroid (ZIP, assinaturas, AXML, ARSc, DEX, manifest). Cada item do
pacote é um APK com **uma única patologia** — para que o gabarito isole a
causa. Todos são empacotados por `tools/fixture-pack.py` (aapt2 + d8 + zip +
zipalign + apksigner, python3 stdlib-only, determinístico por seed
20261022).

## As 10 fixtures (entregues em A2)

| Fixture | Patologia | Resultado esperado no RustyDroid |
|---|---|---|
| `sig-v1-only` | apenas assinatura v1 (JAR) | parser lê esquema v1 isolado |
| `sig-v2-only` | apenas assinatura v2 (APK Signing Block) | parser lê v2 sem v1 |
| `sig-v3-only` | apenas assinatura v3 (rotação de chave) | parser lê v3 sem v1/v2 |
| `unaligned` | entradas sem zipalign, de propósito | parser não assume alinhamento |
| `zip64-65k` | ZIP64 com 65.600+ entradas | offsets/contagens de 64 bits corretos |
| `huge-arsc` | `resources.arsc` sintético: 10.000 entradas × 40 locales + 7 densidades | ARSc grande e multi-locale sem OOM/timeout |
| `multidex-8` | exatamente 8 `classesN.dex` (corpus `gen-dex-stress`) | carregamento de multi-dex completo |
| `unknown-perms` | 4 strings de permissão inventadas (`dev.apktester.fake.*`) | classificação `unknown` estruturada — nunca crash |
| `exported-audit` | 9 componentes com armadilhas intencionais de `exported`/permissões | relato de auditoria aponta cada erro (manifest-as-truth) |
| `obfuscated-r8` | nomes minificados determinísticos + `mapping.txt` dentro do APK | resolução de nomes ofuscados via mapping |

## Honestidade das fixtures (leis do pacote)

- Permissões **inventadas** existem APENAS em `unknown-perms` — nunca no
  flagship (hard-truths do README).
- As armadilhas de `exported-audit` são **intencionais e documentadas** em
  `contracts/parser-torture/exported-audit-traps.md` (9 armadilhas: activity
  exportada sem permissão, alias oculto, service aberto, receiver aberto,
  provider mundialmente legível, grant amplo, foregroundServiceType sem a
  permissão exigida — mais 2 baselines limpos para contraste). Instalar este
  APK num dispositivo real NÃO é o objetivo; o alvo é o relato do RustyDroid.
- `obfuscated-r8` é um **proxy honesto**: os nomes minificados e o
  `assets/mapping.txt` são gerados por tabela determinística (R8 real chega
  nos builds Tier A/release, A4/A6).
- O binário `resources.arsc` do `huge-arsc` NÃO é commitado — o sha256 no
  `suites/parser-torture/huge-arsc/arsc-report.json` é a âncora; valide com
  `python3 tools/gen-arsc-stress.py --verify <arquivo>` (re-parser
  independente) e com `aapt2 dump resources` (segunda opinião no CI).

## Empacotar e validar localmente

```bash
python3 tools/fixture-pack.py --selftest                 # planos dos 11 modos
python3 tools/fixture-pack.py --fixture huge-arsc --out dist   # com toolchain
python3 tools/gen-torture-contracts.py --out .           # contratos (zero drift)
```

O job `parser-torture` do CI empacota as 10 fixtures com a toolchain real do
SDK e valida cada uma: esquemas de assinatura via `apksigner verify
--verbose`, reprovação esperada do `zipalign -c` na unaligned (com contraste
aprovando), contagem de entradas Zip64, os 8 dex, sha256 + re-parse do arsc,
as 4 permissões falsas, as armadilhas no manifesto binário e o
`mapping.txt` + classes `a.a.*` no dex. A auditoria completa de cada fixture
vive em `contracts/parser-torture/fixtures-audit.md`.
