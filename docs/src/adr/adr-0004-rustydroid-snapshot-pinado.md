# ADR 0004 — Snapshot pinado do CLI RustyDroid para o compat-nightly

- Status: accepted
- Data: 2026-10-24
- Decisores: xisto

## Contexto

O cheque de compatibilidade noturno (`scripts/compat-nightly.sh`) existia
desde a A7 mas nunca exerceu o runtime irmão: sem `rustydroid`/`rd` no
runner, TODAS as linhas da matriz viravam `SKIP` desde sempre (SKIP=32 em
todo nightly — a matriz era aspiracional). O AUDIT_ROADMAP_V2 (R1.1/R1.2)
exige compat REAL: binário publicado e pinado por sha256, bootstrap no
script, falha de download/integridade como FAIL explícito.

Forças em jogo:

1. O repo irmão `nadabgfccvd/RustyDroid` existe e está ativo, mas o PAT de
   manutenção do APK-Tester NÃO tem acesso de escrita a ele (403 verificado
   em 2026-10-24) — não há como publicar um release com asset lá.
2. O CI do RustyDroid em `main` @ `89bbe8f274f8d57b279f604406540ab12b8473c3`
   está vermelho APENAS num alvo clippy de TESTE (`rd-vm` test
   `parcel_binder`, clippy `-D warnings`); o `cargo check --workspace`
   (job MSRV) passa — o CLI `rd` compila limpo naquele commit.
3. A lei do repositório proíbe binário commitado (ADR 0002, nota do
   nightly: "nada de binário commitado").
4. Builds de cargo não são byte-reprodutíveis entre ambientes — pin por
   sha256 exige UM binário fixo publicado, não build por runner.

## Decisão

**Publicar o snapshot do CLI `rd` como asset fixo do release
`rustydroid-cli-snapshot` NO PRÓPRIO APK-Tester, buildado pela fonte
pinada via CI, e pinar o sha256 em `scripts/compat-nightly.sh`.**

Detalhes:

- O workflow `.github/workflows/rustydroid-snapshot.yml` (manual,
  `workflow_dispatch`) clona `nadabgfccvd/RustyDroid` no commit pinado
  (`RD_COMMIT` no topo do workflow), roda `cargo build --release
  -p rd-cli --locked`, faz smoke (`rd --help`, `rd engine list`) e publica
  `rd` + `rustydroid-cli-sha256.txt` + `rustydroid-cli-provenance.txt`
  (commit fonte, toolchain, data UTC do corte) como assets do release
  `rustydroid-cli-snapshot` (idempotente: `--clobber` se já existe).
- A tag do release NÃO casa com `v*` — o workflow Release não dispara.
- `scripts/compat-nightly.sh` (R1.2) baixa o asset, valida o sha256 PINADO
  no próprio script, instala em `$WORK_DIR/bin` e antecipa ao `PATH`.
  Download ou integridade falhando = **FAIL explícito** (nunca SKIP).
- Re-corte de snapshot = novo `RD_COMMIT` no workflow + re-dispatch +
  novo sha256 pinado no script + nota de corte aqui.

### Proveniência do corte atual

| Campo | Valor |
|-------|-------|
| Fonte | `https://github.com/nadabgfccvd/RustyDroid.git` |
| Commit | `89bbe8f274f8d57b279f604406540ab12b8473c3` (main, 2026-10-24) |
| Build | `cargo build --release -p rd-cli --locked`, runner ubuntu-latest |
| Asset | `rustydroid-cli-snapshot/rd` (sha256 no arquivo de pin do script) |

## Consequências

- **Fica fácil:** o compat-nightly exercita o runtime irmão de verdade
  (R1.3 estende para ladder + torture + flagship); a matriz publicada
  reflete resultados reais (R1.4); SKIP some como status estrutural.
- **Fica difícil:** o snapshot ENVELHECE — o pin é uma data de corte, não
  um follow de main. Drift entre o snapshot e o repo irmão é esperado e
  documentado (re-corte quando houver mudança relevante no detector).
- **Passa a ser proibido:** subir o sha256 do pin sem passar pelo workflow
  de snapshot (o sha256 tem que vir de um asset publicado com proveniência
  registrada); commitar o binário na árvore.
- **Verificável:** o log do nightly traz `install: OK (sha256 …)`; o
  `sha256sum` do asset publicado casa com o pin do script; a proveniência
  do corte fica nos assets do release e neste ADR.
