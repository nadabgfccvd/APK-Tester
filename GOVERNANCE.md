# Governança — APK Tester

Este documento define papéis, processo de decisão, ciclo de vida dos marcos,
política de versionamento e licenciamento do APK Tester — a suíte de
*golden fixtures* do [RustyDroid](https://github.com/nadabgfccvd/RustyDroid).
O objetivo é manter um nível de governança igual ao do próprio RustyDroid.

## Papéis e responsáveis

| Papel | Quem | Responsabilidades |
|---|---|---|
| Owner / mantenedor principal | `nadabgfccvd` | decisões finais, merges para `main`, criação de releases e tags, aceitação/rejeição de ADRs, moderação (ver CODE_OF_CONDUCT.md) |
| Agente de commits | `xisto-agent` | agente automatizado que executa tarefas técnicas delegadas (scaffolds, geradores, docs, commits e PRs) sob instruções registradas; **não** decide arquitetura nem faz merge — toda contribuição passa por revisão do owner |
| Contribuidores | comunidade | issues, PRs, fixtures novos, docs; seguem CONTRIBUTING.md |
| Revisores | nomeados pelo owner | revisam PRs específicos (ex.: toolchains Tier B) |

Regras do agente de commits: commits assinados/atribuídos ao agente nunca são
mesclados por ele mesmo; mudanças em contratos (`contracts/`) e em ADRs exigem
aprovação humana explícita.

## APKBot (automação anti-regressão)

O **APKBot** é o bot autônomo anti-regressão do repositório: implementado em
`bot/apkbot.py` e agendado pelo workflow
[.github/workflows/apkbot.yml](.github/workflows/apkbot.yml), executa 8
verificações (determinismo entre execuções, flakiness, staleness, consistência
da matriz de engines, drift do registro do RustyDroid, drift do AOSP, previsão
de breach do gate de tamanho e auditoria de governança), mantém memória
persistente em `bot/state/` e registra achados em issues deduplicadas por
fingerprint. Detalhes de operação em `bot/README.md`.

**Identidade:** commits de automação são atribuídos a
`apkbot[bot] <apkbot@users.noreply.github.com>`. O `xisto-agent` permanece o
agente de commits de desenvolvimento e o owner permanece `nadabgfccvd` — o
APKBot não altera essa hierarquia e não tem autoridade de merge.

O APKBot PODE fazer autonomamente:

- commitar apenas o estado do bot em `bot/state/` (inclusive
  `bot-state.json`), sempre com `[skip ci]` na mensagem;
- abrir, comentar e fechar issues criadas por ele próprio, sempre com as
  labels `apkbot:*` (`apkbot`, `apkbot:regression`, `apkbot:drift`,
  `apkbot:flaky`);
- criar as labels próprias `apkbot:*` caso ainda não existam no repositório.

O APKBot NUNCA pode:

- mexer em código, fixtures ou contratos (`contracts/`) sem PR revisado por
  humano — o aprendizado de baseline (*baseline learning*) fica restrito a
  `bot/state/` e jamais altera gabaritos;
- fechar ou editar issues abertas por humanos;
- alterar workflows (`.github/workflows/`), permissões ou o próprio
  agendamento.

**Cadência:** a cada 6 horas (`cron "0 */6 * * *"`, distinto do Engines
Nightly às 03:00) e sob demanda via `workflow_dispatch`. Execuções são
serializadas pelo grupo de concurrency `apkbot` (sem cancelamento em
andamento).

**Como desativar:** remover (ou desabilitar) o workflow
`.github/workflows/apkbot.yml` — não há nenhum outro gatilho do bot; as issues
que ele abriu permanecem como histórico auditável.

## Processo de decisão — ADR-first

Decisões de arquitetura e de escopo são registradas em **ADRs**
(Architecture Decision Records) em `docs/src/adr/`, no site mdBook:

- Nome do arquivo: `NNNN-titulo-curto.md` (numeração sequencial a partir de
  `0001`).
- Formato mínimo: **Contexto**, **Decisão**, **Consequências** (e
  **Alternativas** quando útil).
- Status de ciclo de vida: `proposto` → `aceito` | `rejeitado`; ADRs
  substituídos são marcados `superseded por NNNN` e mantidos no histórico.

Exigem ADR (lista não exaustiva):

- mudar o tier (A/B/C) de um fixture da matriz de engines;
- alterar contratos consumidos pelo RustyDroid (`expected-engines.json`,
  auditorias, `suites.json`) de forma incompatível;
- mudar gates (faixa de tamanho do flagship, piso minSdk da escada);
- introduzir toolchain novo ou dependência fora da política
  (python3 stdlib-only nos geradores);
- alterar fases A0–A8 ou critérios de saída.

Decisões de rotina (bugfixes, docs, ajustes de gerador) seguem o fluxo normal
de PR + revisão descrito em CONTRIBUTING.md.

## Marcos — ciclo de vida A0–A8

Cada fase é um milestone do GitHub e termina compilando verde. Nenhuma fase
começa sem a anterior concluída (critério de saída verificado).

| Fase | Escopo | Critério de saída |
|---|---|---|
| A0 | Scaffold do repositório + governança + esqueletos de CI + geradores `tools/` | layout completo, workflows em modo esqueleto, `python3 tools/gen-*.py --help` funcional |
| A1 | Esqueleto do flagship "Behemoth" | build verde (~30 MB); probe harness; manifest completo com TODAS as permissões (~160); PermissionsHub + ButtonGrid (1.200 botões) + IconGrid (600 ícones) |
| A2 | `sdk-ladder` + `parser-torture` | fixture minSdk 9 existe; escada 9→36 completa; pacote de tortura com gabaritos |
| A3 | Fixtures Tier C + `expected-engines.json` | todos os fixtures Tier C gerados; contratos de detecção consistentes |
| A4 | Builds reais Tier A | todos os builds Tier A verdes no `ci.yml` |
| A5 | Pilar 3D/shaders | `:sim3d` com checksums golden reproduzíveis; GLES probes retornam apenas erros estruturados (`NOT_IMPLEMENTED`), nunca crash |
| A6 | Engenharia de tamanho | release do flagship ∈ [850 MB, 1000 MB], R8 full + resource shrinking; `size-report.csv` reconciliado por categoria |
| A7 | Tier B nightly + compat + docs | `engines-nightly.yml` verde; `scripts/compat-nightly.sh` roda rustydroid contra todos os fixtures; `docs/compat-matrix.md` publicada |
| A8 | Gate v1.0 | Definition of Done completo; duas builds de release consecutivas byte-idênticas; release v1.0.0 |

## Versionamento — política 0.x → 1.0

- Durante **0.x** (fases A0–A8): mudanças que quebram contratos podem ocorrer
  entre versões *minor* (0.1 → 0.2 → …), sempre documentadas no CHANGELOG e,
  quando arquiteturais, acompanhadas de ADR.
- **1.0.0** é publicada somente quando, simultaneamente:
  1. a matriz completa de engines está verde (Tier A no CI, Tier B no nightly,
     Tier C consistente com `expected-engines.json`);
  2. o **size gate** está verde (flagship release ∈ [850 MB, 1000 MB]);
  3. o job nightly de compatibilidade (`compat-nightly`) está verde.
- **Status: 1.0.0 publicada (A8)** — as três condições acima mais a prova de
  determinismo (duas builds de release consecutivas byte-identicas) são
  avaliadas sistematicamente pelo gate
  [`tools/v1-gate.py`](tools/v1-gate.py) (contrato
  [`contracts/v1-gate.json`](contracts/v1-gate.json), zero drift no CI;
  evidências dinâmicas dentro do workflow Release antes de publicar
  qualquer artefato). Detalhes: [docs/src/v1-gate.md](docs/src/v1-gate.md).
- Após 1.0: SemVer estrito — **MAJOR** quebra contratos, **MINOR** adiciona
  fixtures/contratos compatíveis, **PATCH** corrige sem mudar contratos.
- Tags: `vMAJOR.MINOR.PATCH` (ex.: `v0.1.0`), criadas apenas pelo owner, com
  changelog atualizado.

## Changelog

O projeto segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/):
toda mudança visível entra na seção `[Unreleased]` do
[CHANGELOG.md](CHANGELOG.md) e é movida para a entrada da versão na release.

## Licenciamento

Dupla licença **MIT OR Apache-2.0** ([LICENSE-MIT](LICENSE-MIT) /
[LICENSE-APACHE](LICENSE-APACHE)); fontes inclusas usam OFL quando aplicável.
Toda contribuição é licenciada sob os mesmos termos (ver CONTRIBUTING.md).

## Documentos relacionados

- [CONTRIBUTING.md](CONTRIBUTING.md) — ambiente, geradores, commits, PRs.
- [SECURITY.md](SECURITY.md) — reporte privado de vulnerabilidades e SLA.
- [SUPPORT.md](SUPPORT.md) — canais de suporte.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — conduta da comunidade.
