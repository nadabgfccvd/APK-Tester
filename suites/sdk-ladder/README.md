# suites/sdk-ladder — escada de dois eixos: minSdk 9 → 36 + targetSdk 23 → 35

O **mesmo aplicativo mínimo** construído em **18 degraus de dois eixos**
(12 de minSdk + 6 de targetSdk, D2), para provar as leis de piso do
RustyDroid: o que está abaixo do floor 26 recebe erro estruturado; o que
está acima executa — e no eixo targetSdk os switches de comportamento
variam de verdade entre degraus.

## O app mínimo

Cada degrau da escada é a mesma aplicação com exatamente:

- 1 activity;
- 1 service;
- 1 receiver;
- 1 provider.

Nada mais — no eixo 1 a variável em teste é **apenas** o minSdk; no eixo 2
(D2) é o **targetSdk** (23/29/31/33/34/35, com minSdk no piso válido). O
código é framework-only, sem androidx, para que a API mínima real
corresponda ao minSdk declarado.

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
| Escada completa (9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36 + targetSdk 23, 29, 31, 33, 34, 35 — D2) | **entregue (A2 + D2)** — projeto Gradle com 18 product flavors lidos de `rungs.properties` |
| Contratos | `contracts/sdk-ladder/answer-key.json` + `ladder-audit.md` + ledger `manifest.json` (gerados por `tools/gen-ladder.py`, zero drift) |
| Build no CI | job `sdk-ladder` em `.github/workflows/ci.yml` (`:app:assembleDebug` → 18 APKs validados por aapt2 badging, por eixo) |

O app mínimo tem 1 activity, 1 service, 1 receiver e 1 provider
(`LadderActivity`, `LadderService`, `LadderReceiver`, `LadderProvider` —
package `dev.apktester.ladder`, applicationId `dev.apktester.ladder.minsdkNN`
ou `dev.apktester.ladder.targetsdkNN`, versionCode = minSdk no eixo 1 e =
targetSdk no eixo 2) e declara **zero permissões**. Contexto geral em
[README.md](../../README.md).
