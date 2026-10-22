# suites/sdk-ladder — escada minSdk 9 → 36

O **mesmo aplicativo mínimo** construído em doze níveis de minSdk, para
provar as leis de piso do RustyDroid: o que está abaixo do floor 26 recebe
erro estruturado; o que está acima executa.

## O app mínimo

Cada degrau da escada é a mesma aplicação com exatamente:

- 1 activity;
- 1 service;
- 1 receiver;
- 1 provider.

Nada mais — a variável em teste é **apenas** o minSdk. O código é
framework-only (o flavor `classic`), sem androidx, para que a API mínima
real corresponda ao minSdk declarado.

## Degrada da escada

| minSdk | Resultado esperado no RustyDroid |
|---|---|
| 9 | `BELOW_FLOOR(minSdk=9)` estruturado |
| 12 | `BELOW_FLOOR(minSdk=12)` estruturado |
| 14 | `BELOW_FLOOR(minSdk=14)` estruturado |
| 16 | `BELOW_FLOOR(minSdk=16)` estruturado |
| 19 | `BELOW_FLOOR(minSdk=19)` estruturado |
| 21 | `BELOW_FLOOR(minSdk=21)` estruturado |
| 23 | `BELOW_FLOOR(minSdk=23)` estruturado |
| 26 | executa (no piso) |
| 29 | executa |
| 33 | executa |
| 35 | executa |
| 36 | executa |

**minSdk 9 é o teste:** está abaixo do piso do RustyDroid (26) e o resultado
esperado é o erro estruturado `BELOW_FLOOR(minSdk=…)` — lei de erro, nunca
crash. Nenhum degrau pode derrubar o runtime.

## Como é construído

- Build preferencial com AGP padrão; se o AGP recusar minSdk < 19, o degrau
  é construído com AGP pinado em 7.4.2 para aquele módulo, **ou** empacotado
  por `tools/fixture-pack.py` (aapt2 + d8 + zip diretamente).
- O degrau minSdk 9 **precisa existir de qualquer forma** — é requisito
  duro da suíte (pilar 2).

## Status

| Item | Status |
|---|---|
| Escada completa (9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36) | **construída em A2** (minSdk 9 primeiro) |
| Contratos (gabaritos de `inspect` por degrau) | `contracts/suites.json` na fase A2 |

Diretório ainda vazio nesta fase (A0). Contexto geral em
[README.md](../../README.md).
