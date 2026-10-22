# Huge ARSc — auditoria da fixture huge-arsc

Gerado por `tools/gen-arsc-stress.py` (seed 20261022, stdlib-only,
determinístico). Este documento acompanha o pacote parser-torture e
é a answer key do resources.arsc sintético.

## O que a fixture prova

- ARSc grande e multi-locale (10000 entradas de tipo string x 40 configs de locale = 400000 valores de string ÚNICOS no pool global) parseado sem OOM/timeout.
- Tipo integer com 12 entradas x 7 configs de densidade (120, 160, 213, 240, 320, 480, 640 dpi) = 84 valores INT_DEC.
- Chunk chain ResTable íntegro: table -> pool global -> package (0x7f "torture") -> 2 pools internas -> 2 TypeSpec + chunks de config dense.

## Contagens canônicas

| campo | valor |
|---|---|
| package | torture |
| entries | 10000 |
| locales_count | 40 |
| string_entries_total | 400000 |
| integer_entries | 12 |
| integer_entries_total | 84 |
| file_bytes | 40930960 |
| sha256 | 506d1c0a10be3e899c41d8f8f2faae7eda34dcf812d1f8bf759d36790cafbf77 |

## Decisão de configs (documentada)

- Tipo `string`: 40 configs de locale, **SEM config default** — recurso sem default é válido e é exatamente o que se quer torturar aqui (o `aapt2 dump resources` mostra 40 configs por chave).
- Tipo `integer`: 7 configs de densidade, **sem default**.
- A lista canônica de locales do plano tinha 39 entradas; `ca` completa o conjunto para fechar as 40 configs prometidas (10.000 x 40 = 400000 valores) — desvio documentado.

## Como validar

1. Re-parse local (gold standard): `python3 tools/gen-arsc-stress.py --verify <resources.arsc>` — sai 0 se a cadeia de chunks fecha e as contagens batem.
2. Segunda opinião no CI: `aapt2 dump resources <apk>` deve listar 40 configs por chave de string e 7 por chave integer.
3. O sha256 acima deve bater com `arsc-report.json` (contracts/parser-torture/) — âncora do binário.

## Binário não commitado

O resources.arsc é gerado no pack (o fixture-pack remove o arsc do aapt2 e anexa este no lugar). O binário NÃO vai para o git — o sha256 canônico em `arsc-report.json` é a âncora de integridade.
