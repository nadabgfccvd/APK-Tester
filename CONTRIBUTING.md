# Contribuindo para o APK Tester

Obrigado pelo interesse em contribuir. A suíte é construída em fases
(A0–A8) — leia o [README.md](README.md) para o contexto e o
[GOVERNANCE.md](GOVERNANCE.md) para o ciclo de vida dos marcos e o processo
de decisão. Este documento cobre ambiente por tier, geradores, como adicionar
fixtures, convenções de commit e o checklist de PR.

## Configuração de ambiente por tier

### Comum a todos os tiers

- `python3` >= 3.10 — todos os geradores são **stdlib-only** (nenhuma
  dependência de pip);
- `git` e `shellcheck` (para os scripts `.sh` em `tools/` e `scripts/`);
- `mdbook` (opcional) — apenas para renderizar o site de docs localmente.

### Tier A — builds reais (exigidos no CI)

| Ferramenta | Versão / pacote | Usada em |
|---|---|---|
| JDK | 17 (Temurin ou equivalente) | builds AGP, `d8` |
| Android SDK | `cmdline-tools` + `platform-tools` + build-tools com `aapt2`, `d8`, `apksigner` | empacotamento e assinatura de todos os fixtures |
| Rust | stable + `cargo-ndk` | flagship `:rust`, `engine-09-rust` |
| Go | stable + `gomobile` | `engine-10-go` |
| Zig | 0.13+ (`zig cc` para `.so`) | `engine-12-zig` |

Os demais toolchains Tier A (Haxe, Tauri v2, Chaquopy, host WASM) entram na
fase A4 com versões pinadas documentadas no README de cada diretório de
engine.

### Tier B — toolchains pesados (gated para nightly)

Flutter, React Native/Hermes, Cordova, NativeScript, Godot, Qt/QML,
.NET/Avalonia, Scala e Lua/Defold exigem downloads grandes e SDKs próprios.
Esses builds rodam **somente** no workflow `engines-nightly.yml`; não é
necessário instalar nada disso para contribuições comuns.

### Tier C — nenhum toolchain necessário

Fixtures sintéticos de detecção, gerados por `tools/fixture-pack.py` (com
`aapt2`+`d8`+`zip` quando disponíveis, ou layout sintético honesto com
marcadores corretos). Nada proprietário é necessário — basta python3.

## Geradores

Todos os geradores vivem em `tools/`, são python3 **stdlib-only**, seeded e
determinísticos: mesmos inputs produzem os mesmos bytes. Binários nunca são
commitados; APKs são artefatos de release gerados localmente ou pelo CI.

```bash
python3 tools/gen-icons.py --help
python3 tools/gen-dex-stress.py --help
python3 tools/fixture-pack.py --help
```

Após alterar qualquer gerador, rode `tools/verify-deterministic.sh` e confirme
que duas execuções produzem saída byte-idêntica.

## Como adicionar um fixture

1. Abra uma issue com o template `fixture_gap` descrevendo o gap (qual engine,
   minSdk ou superfície de parser não está coberta).
2. Defina o tier (A/B/C) conforme a matriz do README — mudar o tier de um
   fixture exige ADR (ver GOVERNANCE.md).
3. Crie o diretório `suites/engines/engine-NN-<slug>/` (ou o diretório da
   suíte correspondente) com: script de build ou chamada ao
   `tools/fixture-pack.py`, `expected-engines.json` (engine ids que o
   RustyDroid DEVE detectar) e `README.md`.
4. Gere o APK localmente. **Nunca commite o APK** — ele é artefato de release
   (o CI o produz e anexa à release).
5. Atualize os contratos: `contracts/engines/expected-engines.json` e/ou
   `contracts/suites.json` (e as auditorias do flagship quando aplicável).
6. Escreva o README do fixture com honestidade: fixtures Tier C devem dizer
   explicitamente "fixture de detecção; payload não executável".
7. Abra o PR seguindo o checklist abaixo.

## Convenções de commit (Conventional Commits)

Formato: `<tipo>(<escopo>): <resumo curto, minúsculas, sem ponto final>`

| Tipo | Uso |
|---|---|
| `feat` | novo fixture, gerador, contrato ou recurso |
| `fix` | correção de bug |
| `docs` | documentação |
| `chore` | manutenção geral |
| `refactor` | mudança interna sem alterar contratos |
| `test` | suítes e cenários de teste |
| `build` | toolchains, gradle, empacotamento |
| `ci` | workflows do GitHub Actions |
| `perf` | otimizações (ex.: tamanho do flagship) |

Escopos sugeridos: `flagship`, `engines`, `sdk-ladder`, `parser-torture`,
`tools`, `contracts`, `docs`, `governance`.

Exemplos:

```text
feat(engines): adiciona fixture engine-05-clojure (tier c)
docs(readme): atualiza tabela da matriz de engines
ci(size-gate): ajusta faixa do gate para 850-1000 mb
```

Regras: uma mudança lógica por commit; sem emojis; referencie issues quando
aplicável (`(#42)`).

## Checklist de PR

- [ ] Build local verde (ou gerador verificado com
      `tools/verify-deterministic.sh` — duas execuções byte-idênticas);
- [ ] Contratos atualizados (`expected-engines.json`, auditorias,
      `suites.json`) quando o fixture ou o flagship mudam;
- [ ] README do fixture/diretório atualizado e honesto quanto ao tier;
- [ ] Nenhum binário commitado (apenas geradores e contratos) — **exceção
      documentada**: `gradle/wrapper/gradle-wrapper.jar` das suítes Gradle
      (flagship e sdk-ladder), com sha256 pinado no sidecar
      `gradle-wrapper.jar.sha256` ao lado de cada jar (verificação:
      `cd suites/flagship/gradle/wrapper && sha256sum -c
      gradle-wrapper.jar.sha256`); é a praxe padrão do ecossistema Gradle
      (o wrapper é o bootstrap confiável do build) e a exceção está
      registrada no ADR 0001;
- [ ] Commits seguem Conventional Commits;
- [ ] Descrição referencia issue e milestone (fase A0–A8);
- [ ] Mudanças que alteram decisões de arquitetura acompanham um ADR em
      `docs/src/adr/`.

## Marcos de fase (milestones A0–A8)

| Fase | Escopo | Critério de saída |
|---|---|---|
| A0 | Scaffold + governança + esqueletos de CI + geradores `tools/` | repositório parseável, workflows em modo esqueleto, `--help` dos geradores funcional |
| A1 | Esqueleto do flagship | build verde (~30 MB), probe harness, manifest com TODAS as permissões, PermissionsHub + ButtonGrid + IconGrid |
| A2 | `sdk-ladder` + `parser-torture` | minSdk 9 existe; pacote de tortura completo com gabaritos |
| A3 | Fixtures Tier C + `expected-engines.json` | todos os fixtures Tier C gerados e detectáveis |
| A4 | Builds reais Tier A | todos os builds Tier A verdes no CI |
| A5 | Pilar 3D/shaders | `:sim3d` com checksums golden; GLES probes retornam erros estruturados |
| A6 | Engenharia de tamanho | release do flagship ∈ [850 MB, 1000 MB]; `size-report.csv` reconciliado |
| A7 | Tier B nightly + compat + docs | `engines-nightly.yml` verde; `docs/compat-matrix.md` publicada |
| A8 | Gate v1.0 | DoD completo: determinismo provado, release v1.0.0 |

## Licença das contribuições

Salvo declaração em contrário, toda contribuição é licenciada sob a dupla
licença **MIT OR Apache-2.0** (ver [LICENSE-MIT](LICENSE-MIT) e
[LICENSE-APACHE](LICENSE-APACHE)). Ao abrir um PR, você concorda com esses
termos.
