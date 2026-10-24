# APKBot

APKBot é o bot anti-regressão nativo do APK Tester — um Dependabot, só que
para regressão de fixture/parser em vez de dependências. Ele roda no próprio
repositório, guarda a memória de estado commitada
(`bot/state/bot-state.json`), é agendado via GitHub Actions e gerencia issues
de forma autônoma: abre, atualiza e fecha sozinho, com deduplicação por
fingerprint. Implementação 100% python3 stdlib — nenhum `pip install`.

## Por que existe (o que o CI não cobre)

O CI clássico é sem estado: responde apenas ao commit presente. O APKBot
complementa com seis capacidades:

1. **Memória entre execuções** — baselines, confirmações, issues abertos e
   histórico de reincidências vivem commitados no repo; a execução de hoje é
   comparada com a de ontem.
2. **Detecção de drift temporal** — mudanças lentas e silenciosas (tamanho,
   gabaritos, matriz de engines) que nunca falham um gate pontual.
3. **Cruzamento multi-repositório** — compara gabaritos locais com as fontes
   da verdade externas: RustyDroid (README/Apêndice G e docs) e o AOSP
   (`AndroidManifest.xml` de `frameworks/base`).
4. **Estatística de flakiness** — variância entre execuções (coeficiente de
   variação) e contagem de reincidências (`flap_history`).
5. **Auditoria de identidade dos commits** — autores dos commits recentes
   contra `allowed_authors` (o agente de commits não pode virar autor
   anônimo).
6. **Previsão de breach de gate** — projeta a curva de tamanho por categoria
   contra o gate [850 MB, 1000 MB] antes de estourar.

## Como funciona (visão geral)

1. Carrega `bot/bot-config.json` e `bot/state/bot-state.json`.
2. Garante as labels do bot no repositório (tolerante a falha).
3. Executa os checks selecionados — cada um isolado; exceção vira nota,
   nunca derruba a execução.
4. Protocolo de aprendizado: `learn` novo só vira baseline após N confirmações
   (`learn_mode` padrão `"merge"`) ou imediatamente quando o check declara
   `learn_mode: "immediate"` (fatos por-execução e séries temporais).
5. Sincroniza issues (criar/comentar/fechar) — pulado em `--local`/`--dry-run`.
6. Registra o resumo da execução em `state.runs` e persiste o estado se mudou.
7. Commita e envia o estado com `[skip ci]` (exceto `--local`/`--dry-run`).
8. Imprime o relatório markdown no stdout.

## Catálogo de checks

| Check | O que vigia (uma linha) |
|---|---|
| `determinism` | perda de determinismo dos geradores (mesma seed, saída diferente) |
| `flakiness` | instabilidade estatística entre execuções (CV acima do limite) |
| `staleness` | links mortos em docs, marcadores de dívida e deriva de agendamento do bot |
| `engine_matrix` | consistência da matriz de engines entre `contracts/` e docs |
| `answerkey_drift` | drift entre gabaritos locais e as fontes do RustyDroid |
| `permission_drift` | permissões do AOSP `main` vs `contracts/flagship/permissions-audit.md` |
| `size_drift` | tamanho por categoria vs gate [850, 1000] MB e projeção de breach |
| `governance` | identidade dos commits (`allowed_authors`) e presença do kit de governança |
| `locale_sync` | drift de tradução PT/EN nos READMEs (tabela de engines: conjunto, fase de entrega, status "planned") |

## Contrato de um check

Cada módulo `bot/checks/<id>.py` expõe `CHECK_ID` e `run(ctx)`:

```python
from bot.lib.base import BotContext, CheckResult, Finding

CHECK_ID = "meu_check"

def run(ctx: BotContext) -> CheckResult:
    # ctx.repo_path, ctx.state, ctx.now, ctx.gh, ctx.cfg, ctx.dry_run
    return CheckResult(check=CHECK_ID, findings=[...], learn={...}, ran=True)
```

Severidades válidas: `regression`, `drift`, `new`, `flaky`, `info`.
Fingerprint estável do finding: `f"{check}:{target}:{kind}"`.

## Configuração (bot/bot-config.json)

| Chave | Padrão | Significado |
|---|---|---|
| `schema_version` | 1 | versão do esquema de configuração |
| `determinism_runs` | 2 | execuções do gerador para comparar saídas |
| `confirmations_for_new` | 2 | observações idênticas do mesmo payload antes de virar baseline |
| `size_drift_pct` | 2.0 | variação percentual por categoria que caracteriza drift de tamanho |
| `size_forecast_min_samples` | 5 | amostras mínimas de histórico para projetar breach do gate |
| `size_gate_mb` | min 850 / max 1000 | faixa oficial do flagship "Behemoth" |
| `flake_runs` | 3 | execuções recentes consideradas na estatística de flakiness |
| `flake_cv_threshold` | 0.6 | coeficiente de variação acima do qual algo é flaky |
| `commit_audit_count` | 60 | quantidade de commits auditados por execução |
| `allowed_authors` | lista | autores de confiança na auditoria de commits |
| `rustydroid` | objeto | owner/repo/branch e `candidate_paths` das fontes RustyDroid |
| `aosp_manifest_url` | URL | fonte (base64 via `?format=TEXT`) do AndroidManifest.xml do AOSP |
| `labels` | mapa | nome -> cor das labels criadas/mantidas pelo bot |
| `state_path` | bot/state/bot-state.json | caminho do estado relativo à raiz |
| `http_timeout_s` | 15 | timeout (segundos) das chamadas HTTP |

## Estado (bot/state/bot-state.json)

| Chave | Significado |
|---|---|
| `schema_version` | versão do esquema do estado (1) |
| `bot` | identidade do bot (`apkbot`) |
| `updated` | data ISO UTC da última gravação |
| `runs` | últimas 30 execuções: `{date, findings_count, checks_ran}` |
| `baselines` | por check, o gabarito aprendido e confirmado |
| `confirmations` | pendências de aprendizado: `{check, runs_seen, payload, first_seen}` |
| `open_issues` | fingerprint -> `{number, title, url, check, target, severity, first_seen}` |
| `flap_history` | fingerprint -> `{count, last_seen, title}` (reincidências) |

O carregamento é tolerante: arquivo ausente ou corrompido inicia um esquema
novo e vira nota no relatório (nunca derruba a execução).

## Protocolo de aprendizado (anti-flake)

- Cada check pode devolver um `learn` (dict) no `CheckResult`, com uma
  política em `learn_mode`:
  - `"merge"` (padrão): confirmação múltipla anti-flake (abaixo);
  - `"immediate"`: o payload é aplicado na MESMA execução, sem confirmação —
    usado quando o payload é fato por-execução (durações de `flakiness`),
    série temporal carregada para frente pelo próprio check (`samples` de
    `size_drift`) ou quando precisa persistir de imediato (âncora
    `bot_since_sha` do `governance`). Pendências antigas do check são
    removidas.
- Modo `"merge"`, passo a passo:
- Chave da pendência: `f"{check}:{sha256_canônico(learn)}"` (hash estável do
  payload com `sort_keys`).
- Se o payload for igual ao baseline atual do check: nada a fazer.
- Senão, vira pendência em `confirmations` com `runs_seen` incrementado;
  pendências ANTERIORES do mesmo check são removidas (superadas — só a
  observação mais recente é candidata, o que impede lixo eterno no estado).
- Quando `runs_seen >= confirmations_for_new`, o payload é mesclado
  (`deep_merge`) em `baselines[check]`, a pendência é removida e um finding
  `[INFO]` "Baseline atualizada" entra no relatório.
- Finding de severidade `regression` **nunca** é auto-aprendido: execução com
  regressão não atualiza memória.
- Efeito prático: uma flutuação de uma única execução nunca vira verdade no
  estado; só padrão repetido vira baseline.

## Ciclo de vida dos issues

- Severidades `regression`, `drift` e `flaky` geram/atualizam issues;
  `new` e `info` ficam apenas no relatório.
- Abertura: título `[apkbot] {título}`, corpo padrão (evidência + execução +
  instruções de triagem), labels `apkbot` e `apkbot:{severidade}`.
- Fingerprint já aberto: um comentário com evidência fresca (máximo 1
  comentário por fingerprint por execução) e `flap_history` incrementado.
- Fingerprint aberto que desapareceu: comentário "Resolvido na execução
  {data}", fechamento do issue e remoção de `open_issues`. Se o fingerprint
  voltar, é aberto acompanhamento novo (o histórico fica no issue fechado).
- Toda operação de issue é tolerante a falha: vira nota no relatório, nunca
  derruba a execução.

## Como rodar localmente

```bash
cd /caminho/para/apk-tester
python3 bot/apkbot.py --local --dry-run                      # só relatório, nada é tocado
python3 bot/apkbot.py --local --dry-run --check size_drift   # um check específico
python3 bot/apkbot.py --strict                               # execução completa; exit 1 se regressão
```

| Flag | Efeito |
|---|---|
| `--check all\|id[,id...]` | seleciona checks (padrão: todos os 8) |
| `--local` | sem GitHub API (`gh=None`), sem issues e sem push |
| `--dry-run` | nunca grava estado, nunca faz push, nunca toca em issues |
| `--strict` | exit 1 se houver qualquer finding `regression` |
| `--repo owner/name` | repositório alvo (padrão: env `GITHUB_REPOSITORY`) |
| `--summary-only` | apenas o relatório no stdout (notas vão para stderr) |

Códigos de saída: `0` normal; `1` com `--strict` e ao menos um finding
`regression`; `2` uso inválido ou configuração ilegível.

## Segurança de loop no CI

- O commit do estado tem a mensagem `apkbot: atualiza estado [skip ci]`, o
  que impede que os workflows do repositório rodem em cima do próprio bot.
- Além disso, o push é feito com `GITHUB_TOKEN`: por regra do GitHub, pushes
  autenticados com `GITHUB_TOKEN` não disparam novas execuções de workflows —
  dupla proteção contra loop infinito (o `[skip ci]` cobre o caso de um PAT).
- O agendamento (workflow dedicado com `schedule`) acopla o dispatcher ao CI;
  em `--local`/`--dry-run` nada é escrito em lugar algum.
- Autor do commit configurável via `BOT_AUTHOR_NAME`/`BOT_AUTHOR_EMAIL`
  (padrão `apkbot[bot]` / `apkbot@users.noreply.github.com`).

## Escalada de severidades

| Severidade | Significado | Efeito |
|---|---|---|
| `info` | observação do bot (ex.: baseline atualizada) | só relatório |
| `new` | observação nova ainda não confirmada | só relatório; vira baseline após confirmações |
| `flaky` | instabilidade estatística entre execuções | issue + comentários; `flap_history` acumula |
| `drift` | mudança lenta monitorada (tamanho, gabaritos) | issue; acompanha tendência |
| `regression` | quebra confirmada contra baseline | issue; nunca auto-aprendida; `--strict` exit 1 |

Escalada típica: `new` repetido confirma e vira baseline (sai da conversa);
`drift` que cruza um limite (ex.: `size_drift_pct` ou o gate de tamanho) passa
a ser reportado pelo check como `regression`; reincidência de `flaky`
acumula `flap_history` para o humano decidir.

## Arquivos

- `bot/apkbot.py` — dispatcher (CLI, orquestração, aprendizado, issues, push).
- `bot/lib/base.py` — contrato congelado (`Finding`, `CheckResult`, `BotContext`).
- `bot/lib/github_api.py` — cliente REST mínimo (urllib, timeout curto, 1 retry).
- `bot/lib/state.py` — carga/gravação tolerante, merge recursivo, hash estável.
- `bot/lib/report.py` — relatório markdown e corpos de issue/comentário.
- `bot/checks/` — um módulo por check (ver catálogo acima).
- `bot/bot-config.json` — configuração do bot.
- `bot/state/bot-state.json` — memória commitada entre execuções.
