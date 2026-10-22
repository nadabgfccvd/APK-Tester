# Escada minSdk

A suíte `suites/sdk-ladder/` constrói **o mesmo app mínimo** (1 activity +
1 service + 1 receiver + 1 provider) em **12 valores de minSdk**:
9, 12, 14, 16, 19, 21, 23, 26, 29, 33, 35, 36.

## Tabela da escada (entregue em A2)

| minSdk | Flavor | applicationId | versionCode | Resultado esperado do RustyDroid |
|--------|--------|---------------|-------------|----------------------------------|
| 9  | `minsdk09` | `dev.apktester.ladder.minsdk09` | 9  | `BELOW_FLOOR(minSdk=9)` estruturado |
| 12 | `minsdk12` | `dev.apktester.ladder.minsdk12` | 12 | `BELOW_FLOOR(minSdk=12)` estruturado |
| 14 | `minsdk14` | `dev.apktester.ladder.minsdk14` | 14 | `BELOW_FLOOR(minSdk=14)` estruturado |
| 16 | `minsdk16` | `dev.apktester.ladder.minsdk16` | 16 | `BELOW_FLOOR(minSdk=16)` estruturado |
| 19 | `minsdk19` | `dev.apktester.ladder.minsdk19` | 19 | `BELOW_FLOOR(minSdk=19)` estruturado |
| 21 | `minsdk21` | `dev.apktester.ladder.minsdk21` | 21 | `BELOW_FLOOR(minSdk=21)` estruturado |
| 23 | `minsdk23` | `dev.apktester.ladder.minsdk23` | 23 | `BELOW_FLOOR(minSdk=23)` estruturado |
| 26 | `minsdk26` | `dev.apktester.ladder.minsdk26` | 26 | **execução** (piso do runtime) |
| 29 | `minsdk29` | `dev.apktester.ladder.minsdk29` | 29 | execução (switches por targetSdk) |
| 33 | `minsdk33` | `dev.apktester.ladder.minsdk33` | 33 | execução |
| 35 | `minsdk35` | `dev.apktester.ladder.minsdk35` | 35 | execução |
| 36 | `minsdk36` | `dev.apktester.ladder.minsdk36` | 36 | execução |

## Expectativa do RustyDroid

- **minSdk < 26** (piso do runtime): a resposta correta é o erro estruturado
  `BELOW_FLOOR(minSdk=X)` — isso É o teste (lei de erro, **nunca crash**). O
  degrau de minSdk 9 **existe** — é requisito duro da suíte (pilar 2).
- **minSdk >= 26**: o RustyDroid **executa** o APK; o comportamento por
  `targetSdk` (switches) é exercitado pelos próprios níveis da escada.

## Como é construído (zero drift por construção)

- Um único projeto Gradle em `suites/sdk-ladder/` com **12 product flavors**
  (dimensão `rung`) criados em tempo de configuração a partir de
  `rungs.properties` — arquivo **gerado** por `tools/gen-ladder.py` a partir
  da mesma tabela `RUNGS` que produz o answer key
  `contracts/sdk-ladder/answer-key.json`. Os flavors **não podem** divergir
  dos contratos.
- AGP 8.9.2 + compileSdk 36 handle minSdk 9 normalmente (o flagship já provou
  o par minSdk 9 / AGP 8 no CI). Não há mais necessidade de pin AGP 7.4.2;
  o caminho alternativo por `tools/fixture-pack.py --fixture minSdk9`
  permanece disponível como fallback empacotado.
- Código **framework-only** (sem androidx): `LadderActivity` (escreve
  `ladder-report.json` tudo-ou-nada e loga `LADDER/<degrau>`),
  `LadderService`, `LadderReceiver`, `LadderProvider` (stub determinístico
  sobre `MatrixCursor`). Disciplina de minSdk 9: sem lambdas, sem
  try-with-resources, sem `StandardCharsets`, sem `org.json`;
  `String.format` sempre com `Locale.US`.
- O app declara **zero permissões** — o CI afirma `E: uses-permission == 0`
  no binário de cada degrau (a variável em teste é apenas o minSdk).
- Ícone via `ShapeDrawable` (`res/drawable/ic_ladder.xml`) e tema
  `android:Theme` — ambos válidos desde a API 9.

## Build e validação

```bash
python3 tools/gen-ladder.py --out .        # regenera rungs.properties + contratos
cd suites/sdk-ladder && ./gradlew :app:assembleDebug   # 12 APKs
```

O job `sdk-ladder` do CI faz build dos 12 flavors, valida cada APK por
`aapt2 dump badging` (applicationId, versionCode = minSdk, minSdkVersion,
4 componentes, 0 permissões) e publica o artefato `sdk-ladder-apks`.

O gabarito executável por degrau vive em `contracts/suites.json`
(entries `sdk-ladder-09` … `sdk-ladder-36`) e o answer key humano em
`contracts/sdk-ladder/answer-key.json` + `ladder-audit.md`.
