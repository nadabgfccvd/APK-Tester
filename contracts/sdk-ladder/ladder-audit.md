# SDK Ladder Audit — escada minSdk 9 → 36 (dev.apktester.ladder.*)

STATUS: **preenchida em A2** — answer key dos 12 degraus da escada,
gerada por `tools/gen-ladder.py` a partir da constante `RUNGS` (fonte
única). O projeto Gradle consome `suites/sdk-ladder/rungs.properties`
em tempo de configuração, o app consome o asset `ladder/rungs.json` em
tempo de execução e este documento consolida o gabarito: todos saem da
mesma lista — zero drift por construção.

## A lei do piso

O RustyDroid tem piso de execução em **minSdk 26**. Para um APK com
`minSdk < 26` a resposta esperada é o erro estruturado
`BELOW_FLOOR(minSdk=…)` — lei de erro, **nunca crash**. Para
`minSdk >= 26` o app executa e os switches de comportamento passam a
ser governados pelo targetSdk (36 em todos os degraus).

**minSdk 9 é o teste:** o degrau mais baixo existe exatamente para
provar a lei do piso — nenhuma suíte pode omiti-lo.

## Os doze degraus

| Degrau | Flavor | minSdk | versionCode | applicationId | Resultado esperado |
|--------|--------|--------|-------------|---------------|--------------------|
| sdk-ladder-09 | minsdk09 | 9 | 9 | dev.apktester.ladder.minsdk09 | BELOW_FLOOR(minSdk=9) estruturado — nunca crash |
| sdk-ladder-12 | minsdk12 | 12 | 12 | dev.apktester.ladder.minsdk12 | BELOW_FLOOR(minSdk=12) estruturado — nunca crash |
| sdk-ladder-14 | minsdk14 | 14 | 14 | dev.apktester.ladder.minsdk14 | BELOW_FLOOR(minSdk=14) estruturado — nunca crash |
| sdk-ladder-16 | minsdk16 | 16 | 16 | dev.apktester.ladder.minsdk16 | BELOW_FLOOR(minSdk=16) estruturado — nunca crash |
| sdk-ladder-19 | minsdk19 | 19 | 19 | dev.apktester.ladder.minsdk19 | BELOW_FLOOR(minSdk=19) estruturado — nunca crash |
| sdk-ladder-21 | minsdk21 | 21 | 21 | dev.apktester.ladder.minsdk21 | BELOW_FLOOR(minSdk=21) estruturado — nunca crash |
| sdk-ladder-23 | minsdk23 | 23 | 23 | dev.apktester.ladder.minsdk23 | BELOW_FLOOR(minSdk=23) estruturado — nunca crash |
| sdk-ladder-26 | minsdk26 | 26 | 26 | dev.apktester.ladder.minsdk26 | execução (piso/switches por targetSdk) |
| sdk-ladder-29 | minsdk29 | 29 | 29 | dev.apktester.ladder.minsdk29 | execução (piso/switches por targetSdk) |
| sdk-ladder-33 | minsdk33 | 33 | 33 | dev.apktester.ladder.minsdk33 | execução (piso/switches por targetSdk) |
| sdk-ladder-35 | minsdk35 | 35 | 35 | dev.apktester.ladder.minsdk35 | execução (piso/switches por targetSdk) |
| sdk-ladder-36 | minsdk36 | 36 | 36 | dev.apktester.ladder.minsdk36 | execução (piso/switches por targetSdk) |

## Como é construído

- **AGP 8.9.2 + compileSdk 36 + Gradle 8.11.1** (a mesma ferramenta
  comprovada em CI pelo flagship, que já constrói minSdk 9 no flavor
  classic; AGP 8 não recusa minSdk baixo — ele recusa apenas
  atributos de manifesto antigos, que a escada não usa).
- **12 product flavors** na dimensão `rung`, lidos de
  `rungs.properties` no configure-time do Gradle: `minSdk`,
  `applicationId`, `versionCode`, `versionName` e o `resValue`
  `rung_label` de cada degrau vêm do arquivo gerado.
- **Zero drift por construção:** flavors, asset de runtime e answer
  key saem da mesma constante `RUNGS` do gerador — os flavors NUNCA
  podem divergir do gabarito; qualquer divergência é regressão do
  gerador (corrige-se a ferramenta, nunca o arquivo gerado).
- Um flavor por APK: `:app:assemble<Flavor>Debug` produz o degrau
  correspondente; o par flavor/diretório contratado é
  `minsdkNN`/`minsdk-NN` (12 APKs, ids em
  `contracts/sdk-ladder/answer-key.json`).

## O app mínimo

Cada degrau é a MESMA aplicação com exatamente:

- 1 activity (`LadderActivity`, exported, filtro MAIN/LAUNCHER);
- 1 service (`LadderService`, não-exportado, binder local);
- 1 receiver (`LadderReceiver`, exported, action de probe);
- 1 provider (`LadderProvider`, não-exportado, stub determinístico
  sobre MatrixCursor).

- **0 permissões declaradas** (nenhum `uses-permission`; afirmado em
  CI: `grep 'E: uses-permission' == 0` no binário).
- Framework-only, sem androidx — a API mínima real do código é o
  próprio minSdk declarado; guardas `Build.VERSION.SDK_INT` no estilo
  do flagship classic (java.io puro com charset por nome, sem
  try-with-resources, sem `org.json`, `String.format` sempre com
  `Locale.US`).
- `targetSdk 36` em todos os degraus: a variável em teste é **apenas**
  o minSdk.

## Regras duras

1. O degrau minSdk 9 precisa existir de qualquer forma (requisito duro
   da suíte; se um futuro AGP recusar minSdk < 19, o degrau é
   construído com AGP pinado em 7.4.2 ou empacotado por
   `tools/fixture-pack.py` — aapt2 + d8 + zip direto).
2. Nenhum degrau pode derrubar o runtime: `BELOW_FLOOR` é erro
   estruturado, nunca crash.
3. O diff entre `rustydroid inspect --json` e `answer-key.json` deve
   ser zero-drift (12 degraus, 4 componentes por degrau, 0 permissões).
4. Entradas espelhadas em `contracts/suites.json` (`sdk-ladder-09` até
   `sdk-ladder-36`, caminhos `suites/sdk-ladder/minsdk-NN`): o APKBot
   e o CI consomem os dois gabaritos, que saem da mesma fonte.
