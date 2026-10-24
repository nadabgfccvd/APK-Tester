# ADRs — Índice e Template

Architecture Decision Records do APK Tester. Todo ADR aceito é imutável; para
mudar uma decisão, crie um novo ADR com status `superseded by ADR-MMMM`.

| ADR | Título | Status |
|-----|--------|--------|
| [ADR 0001](adr-0001-geradores-python-stdlib.md) | Geradores Python stdlib-only e determinísticos | accepted |
| [ADR 0002](adr-0002-tiers-de-build.md) | Tiers de build A/B/C | accepted |
| [ADR 0003](adr-0003-deteccao-nao-valida-payload.md) | Detecção não valida payload nem autoriza execução | accepted |
| [ADR 0004](adr-0004-rustydroid-snapshot-pinado.md) | Snapshot pinado do CLI RustyDroid para o compat-nightly | accepted |

## Template de ADR

Copie o esqueleto abaixo para `adr/adr-NNNN-slug.md`, numere sequencialmente
e abra PR com a label `governance`.

````markdown
# ADR NNNN — <título curto>

- Status: proposed | accepted | superseded por ADR-MMMM
- Data: AAAA-MM-DD
- Decisores: <handles>

## Contexto

Qual problema força uma decisão? Restrições, forças em jogo, alternativas
consideradas (com prós/contras).

## Decisão

A decisão tomada, em uma frase clara e imperativa, seguida dos detalhes
necessários para implementar sem ambiguidade.

## Consequências

O que fica mais fácil, o que fica mais difícil, o que passa a ser proibido,
e como a decisão é verificável no repositório (CI, contratos, docs).
````

Convenções:

- ADRs vivem em `docs/src/adr/` e entram no SUMÁRIO do mdBook;
- Título do arquivo: `adr-NNNN-slug-curto.md` (kebab-case, sem acentos);
- O CI não valida ADRs, mas o checklist do PR exige docs atualizados.
