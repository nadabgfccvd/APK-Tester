# ADR 0003 — Detecção não valida payload nem autoriza execução

- Status: accepted
- Data: 2026-10-22 (decisão registrada no commit A0; data placeholder 2024-01-01 removida na A9)
- Decisores: nadabgfccvd, xisto-agent

## Contexto

As fixtures Tier C (ver ADR 0002) carregam stubs com marcadores de detector
(DEX strings, ELF headers, assets com layout correto) mas sem payload
executável real. Havia dois riscos: (1) alguém tratar o sucesso da detecção
como prova de que o APK "funciona"; (2) alguém considerar os stubs uma
burla — tentando executá-los e tratando a falha como bug da suíte.

A lei do RustyDroid é explícita: **"detecção não valida payload nem autoriza
execução"**. A detecção é uma leitura de marcadores; execução é outro
subsistema, com seus próprios contratos (probes, suites, golden checksums).

## Decisão

1. Fixtures Tier C testam **DETECÇÃO apenas**. O critério de sucesso é
   `rd engine detect` casar `contracts/engines/expected-engines.json`
   (`rustydroid_engines` + `detector_artifacts`) — nada mais.
2. Nenhum teste, script ou doc da suíte pode inferir "payload válido" ou
   "autorização de execução" a partir de detecção bem-sucedida.
3. Executabilidade é provada por caminhos separados e explícitos:
   - Tier A/B: builds reais + `rustydroid test contracts/suites.json`;
   - flagship: probe harness com resultados `OK` ou `NOT_IMPLEMENTED`
     **estruturados** (a suíte prova a lei: erro estruturado, nunca crash);
   - sim3d: golden frame checksums reprodutíveis nas rotas CPU.
4. Toda fixture Tier C declara em seu README: "detection fixture, payload not
   executable".

## Consequências

- `scripts/compat-nightly.sh` reporta drift de DETECÇÃO (label `fixture_gap`),
  e não falhas de payload; stubs Tier C nunca entram em cenários de execução.
- GLES/câmera/sensores/mídia probes do flagship esperam `NOT_IMPLEMENTED`
  estruturado sob o RustyDroid — isso É o golden (prova da lei de erro).
- Se um stub Tier C um dia for executável, ele foi gerado errado (violação
  desta ADR); se uma build real não for detectada, é drift do detector, não
  problema do stub.
