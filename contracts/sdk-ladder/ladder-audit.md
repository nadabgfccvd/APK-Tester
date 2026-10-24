# SDK Ladder Audit — dois eixos: minSdk 9 → 36 e targetSdk 23 → 35 (dev.apktester.ladder.*)

STATUS: **preenchida em A2, estendida em D2** — answer key dos 18
degraus da escada (12 de minSdk + 6 de targetSdk), gerada por
`tools/gen-ladder.py` a partir das constantes `MIN_SDK_RUNGS` e
`TARGET_SDK_RUNGS` (fonte única). O projeto Gradle consome
`suites/sdk-ladder/rungs.properties` em tempo de configuração, o app
consome o asset `ladder/rungs.json` em tempo de execução e este
documento consolida o gabarito: todos saem das mesmas listas — zero
drift por construção.

## A lei do piso

O RustyDroid tem piso de execução em **minSdk 26**. Para um APK com
`minSdk < 26` a resposta esperada é o erro estruturado
`BELOW_FLOOR(minSdk=…)` — lei de erro, **nunca crash**. Para
`minSdk >= 26` o app executa e os switches de comportamento passam a
ser governados pelo targetSdk — e no eixo 2 da escada o targetSdk
VARIA de verdade (23/29/31/33/34/35), exercitando os switches que o
eixo 1 (targetSdk 36 constante) jamais exercitaria.

**minSdk 9 é o teste:** o degrau mais baixo existe exatamente para
provar a lei do piso — nenhuma suíte pode omiti-lo.

## Os doze degraus do eixo minSdk (targetSdk 36)

| Degrau | Flavor | minSdk | versionCode | applicationId | Resultado esperado |
|--------|--------|--------|-------------|---------------|--------------------|
| sdk-ladder-09 | minsdk09 | 9 | 9 | dev.apktester.ladder.minsdk09 | BELOW_FLOOR(minSdk=9) estruturado — nunca crash |
| sdk-ladder-12 | minsdk12 | 12 | 12 | dev.apktester.ladder.minsdk12 | BELOW_FLOOR(minSdk=12) estruturado — nunca crash |
| sdk-ladder-14 | minsdk14 | 14 | 14 | dev.apktester.ladder.minsdk14 | BELOW_FLOOR(minSdk=14) estruturado — nunca crash |
| sdk-ladder-16 | minsdk16 | 16 | 16 | dev.apktester.ladder.minsdk16 | BELOW_FLOOR(minSdk=16) estruturado — nunca crash |
| sdk-ladder-19 | minsdk19 | 19 | 19 | dev.apktester.ladder.minsdk19 | BELOW_FLOOR(minSdk=19) estruturado — nunca crash |
| sdk-ladder-21 | minsdk21 | 21 | 21 | dev.apktester.ladder.minsdk21 | BELOW_FLOOR(minSdk=21) estruturado — nunca crash |
| sdk-ladder-23 | minsdk23 | 23 | 23 | dev.apktester.ladder.minsdk23 | BELOW_FLOOR(minSdk=23) estruturado — nunca crash |
| sdk-ladder-26 | minsdk26 | 26 | 26 | dev.apktester.ladder.minsdk26 | execução (switches de comportamento por targetSdk=36) |
| sdk-ladder-29 | minsdk29 | 29 | 29 | dev.apktester.ladder.minsdk29 | execução (switches de comportamento por targetSdk=36) |
| sdk-ladder-33 | minsdk33 | 33 | 33 | dev.apktester.ladder.minsdk33 | execução (switches de comportamento por targetSdk=36) |
| sdk-ladder-35 | minsdk35 | 35 | 35 | dev.apktester.ladder.minsdk35 | execução (switches de comportamento por targetSdk=36) |
| sdk-ladder-36 | minsdk36 | 36 | 36 | dev.apktester.ladder.minsdk36 | execução (switches de comportamento por targetSdk=36) |

## Os seis degraus do eixo targetSdk (D2)

| Degrau | Flavor | minSdk | targetSdk | versionCode | applicationId | Resultado esperado |
|--------|--------|--------|-----------|-------------|---------------|--------------------|
| sdk-ladder-ts23 | targetsdk23 | 23 | 23 | 23 | dev.apktester.ladder.targetsdk23 | BELOW_FLOOR(minSdk=23) estruturado — nunca crash |
| sdk-ladder-ts29 | targetsdk29 | 26 | 29 | 29 | dev.apktester.ladder.targetsdk29 | execução (switches de comportamento por targetSdk=29) |
| sdk-ladder-ts31 | targetsdk31 | 26 | 31 | 31 | dev.apktester.ladder.targetsdk31 | execução (switches de comportamento por targetSdk=31) |
| sdk-ladder-ts33 | targetsdk33 | 26 | 33 | 33 | dev.apktester.ladder.targetsdk33 | execução (switches de comportamento por targetSdk=33) |
| sdk-ladder-ts34 | targetsdk34 | 26 | 34 | 34 | dev.apktester.ladder.targetsdk34 | execução (switches de comportamento por targetSdk=34) |
| sdk-ladder-ts35 | targetsdk35 | 26 | 35 | 35 | dev.apktester.ladder.targetsdk35 | execução (switches de comportamento por targetSdk=35) |

Nota honesta do degrau `targetsdk23`: targetSdk 23 exige minSdk 23
(contrato da toolchain: targetSdk >= minSdk), então o degrau fica
ABAIXO do piso 26 do RustyDroid — a resposta esperada é o
BELOW_FLOOR(minSdk=23) estruturado. O degrau prova que o targetSdk
baixo não engana a lei do piso; os switches de comportamento por
targetSdk são exercitados de verdade pelos cinco degraus 29..35
(minSdk 26, execução real, targetSdk diferente em cada um).

## Como é construído

- **AGP 8.9.2 + compileSdk 36 + Gradle 8.11.1** (a mesma ferramenta
  comprovada em CI pelo flagship, que já constrói minSdk 9 no flavor
  classic; AGP 8 não recusa minSdk baixo — ele recusa apenas
  atributos de manifesto antigos, que a escada não usa).
- **18 product flavors** na dimensão `rung`, lidos de
  `rungs.properties` no configure-time do Gradle: `minSdk`,
  `targetSdk` (eixo 2), `applicationId`, `versionCode`,
  `versionName` e o `resValue` `rung_label` de cada degrau vêm do
  arquivo gerado.
- **Zero drift por construção:** flavors, asset de runtime e answer
  key saem das mesmas constantes do gerador — os flavors NUNCA
  podem divergir do gabarito; qualquer divergência é regressão do
  gerador (corrige-se a ferramenta, nunca o arquivo gerado).
- Um flavor por APK: `:app:assemble<Flavor>Debug` produz o degrau
  correspondente; o par flavor/diretório contratado é
  `minsdkNN`/`minsdk-NN` (eixo 1) e `targetsdkNN`/`targetsdk-NN`
  (eixo 2) — 18 APKs, ids em `contracts/sdk-ladder/answer-key.json`.

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
- Eixo 1: `targetSdk 36` em todos os degraus minsdkNN (a variável em
  teste é **apenas** o minSdk; os switches de comportamento NÃO são
  exercitados neste eixo — promessa em contrário era falsa e foi
  corrigida em D2 com o eixo 2).
- Eixo 2: `minSdk` fixo (23 no degrau ts23; 26 nos demais) e
  `targetSdk` 23/29/31/33/34/35 — a variável em teste é o targetSdk.

## Regras duras

1. O degrau minSdk 9 precisa existir de qualquer forma (requisito duro
   da suíte; se um futuro AGP recusar minSdk < 19, o degrau é
   construído com AGP pinado em 7.4.2 ou empacotado por
   `tools/fixture-pack.py` — aapt2 + d8 + zip direto).
2. Nenhum degrau pode derrubar o runtime: `BELOW_FLOOR` é erro
   estruturado, nunca crash.
3. O diff entre `rustydroid inspect --json` e `answer-key.json` deve
   ser zero-drift (18 degraus, 4 componentes por degrau, 0 permissões,
   targetSdk por degrau conforme o eixo).
4. Entradas espelhadas em `contracts/suites.json` (`sdk-ladder-09` até
   `sdk-ladder-36` e `sdk-ladder-ts23` até `sdk-ladder-ts35`, caminhos
   `suites/sdk-ladder/minsdk-NN` e `suites/sdk-ladder/targetsdk-NN`):
   o APKBot e o CI consomem os dois gabaritos, que saem da mesma
   fonte.
