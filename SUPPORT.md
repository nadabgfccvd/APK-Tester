# Suporte — APK Tester

## Onde perguntar

Use as **Issues** deste repositório com os templates disponíveis:

| Template | Quando usar |
|---|---|
| `bug` | fixture ou gerador com comportamento incorreto (contrato divergente do APK) |
| `fixture_gap` | cobertura faltando: engine, minSdk ou superfície de parser não coberta |
| `size_regression` | drift de tamanho do flagship fora da tolerância do size gate |

Antes de abrir, procure em:

1. [README.md](README.md) — contexto, matriz de engines, hard-truths;
2. [`docs/`](docs/) — guias, matriz de permissões, escada minSdk, integração
   com RustyDroid;
3. Issues fechadas — o gap pode já estar registrado ou planejado em uma fase
   A0–A8 (ver [GOVERNANCE.md](GOVERNANCE.md)).

## O que incluir no relato

Para reproduzir rapidamente, inclua:

- **Versão do rustydroid** (`rustydroid --version`) ou o commit do runtime;
- **ID do fixture** exatamente como no repositório (ex.: `engine-09-rust`,
  `sdk-ladder/minSdk-9`, `parser-torture/zip64-65k`, `flagship/behemoth`);
- **Comando executado** (linha completa, ex.:
  `rustydroid inspect --json <apk>`);
- **Saída completa** (não resumida) do comando;
- **Esperado vs obtido** — a linha do contrato relevante
  (`contracts/flagship/*`, `contracts/engines/expected-engines.json`,
  `contracts/suites.json`) e o resultado que você obteve;
- Versão do fixture/release em que o problema apareceu.

Sem esses dados, o triage fica mais lento ou o relato é encerrado como
`incomplete`.

## Expectativas de resposta

- Suporte é **best-effort** dado por mantenedores/contribuidores, sem SLA
  formal (o SLA de segurança é separado: [SECURITY.md](SECURITY.md)).
- O projeto está em construção ativa (fases A0–A8): partes da suíte ainda não
  existem e issues de `fixture_gap` podem ser convertidas em milestone de
  fase futura em vez de correção imediata.
- Triagem típica em dias úteis; issues sem informações mínimas podem aguardar
  até serem completadas.

## O que NÃO é suportado

- Instalação dos APKs em dispositivos pessoais/produção ou distribuição em
  lojas — os fixtures são para ambientes de teste (ver README e SECURITY.md);
- Uso da suíte como ferramenta ofensiva ou para enganar ferramentas de
  terceiros;
- Dúvidas sobre o runtime em si — use os canais do
  [RustyDroid](https://github.com/nadabgfccvd/RustyDroid). Os marcos
  M10–M12 do irmão (dispositivos virtuais, engines em golden flow,
  ecossistema GH/docs/releases) vivem no ROADMAP do
  [RustyDroid](https://github.com/nadabgfccvd/RustyDroid/blob/main/docs/ROADMAP.md);
  o APK-Tester consome o CLI `rd` via snapshot pinado (ADR 0004) e os
  GAPs de detecção conhecidos estão documentados no answer key
  (`contracts/engines/expected-engines.json`, coluna notes).
