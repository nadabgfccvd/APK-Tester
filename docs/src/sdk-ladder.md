# Escada minSdk

A suíte `suites/sdk-ladder/` constrói **o mesmo app mínimo** (1 activity +
1 service + 1 receiver + 1 provider) em **12 valores de minSdk**:
9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36.

## Tabela da escada

| minSdk | Caminho de build | Resultado esperado do RustyDroid |
|--------|------------------|----------------------------------|
| 9  | AGP pin 7.4.2 **ou** `tools/fixture-pack.py` (aapt2+d8) | `BELOW_FLOOR(minSdk=9)` estruturado |
| 12 | AGP pin 7.4.2 **ou** `tools/fixture-pack.py` | `BELOW_FLOOR(minSdk=12)` estruturado |
| 14 | AGP pin 7.4.2 **ou** `tools/fixture-pack.py` | `BELOW_FLOOR(minSdk=14)` estruturado |
| 16 | AGP pin 7.4.2 **ou** `tools/fixture-pack.py` | `BELOW_FLOOR(minSdk=16)` estruturado |
| 19 | AGP normal | `BELOW_FLOOR(minSdk=19)` estruturado |
| 21 | AGP normal | `BELOW_FLOOR(minSdk=21)` estruturado |
| 23 | AGP normal | `BELOW_FLOOR(minSdk=23)` estruturado |
| 26 | AGP normal | **execução** (piso do runtime) |
| 29 | AGP normal | execução (switches de comportamento por targetSdk) |
| 33 | AGP normal | execução |
| 35 | AGP normal | execução |
| 36 | AGP normal | execução |

## Expectativa do RustyDroid

- **minSdk < 26** (piso do runtime): a resposta correta é o erro estruturado
  `BELOW_FLOOR(minSdk=X)` — isso É o teste (lei de erro, **nunca crash**). A
  fixture de minSdk 9 DEVE existir de qualquer forma.
- **minSdk >= 26**: o RustyDroid **executa** o APK; o comportamento por
  `targetSdk` (switches) é exercitado pelos próprios níveis da escada.

## Notas de build

- Se o AGP recusar minSdk < 19, faça pin de **AGP 7.4.2** apenas no módulo da
  escada clássica, **ou** use `tools/fixture-pack.py` (aapt2+d8+zip direto) —
  o APK de minSdk 9 tem que existir por um dos dois caminhos.
- O flavor clássico usa código framework-only (nenhum androidx); guardas de
  versão (`Build.VERSION` + lazy init seguro para `NoClassDefFoundError`)
  isolam qualquer código moderno.

## Contratos

As entradas `sdk-ladder-*` de `contracts/suites.json` declaram, por nível:
`min_sdk`, `below_floor_allowed` (true para < 26) e o resultado esperado
(`BELOW_FLOOR` estruturado vs execução). O CI consome via
`rustydroid test contracts/suites.json` (ver [Integração RustyDroid](rustydroid-integration.md)).
