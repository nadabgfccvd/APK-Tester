# ADR 0001 — Geradores Python stdlib-only e determinísticos

- Status: accepted
- Data: 2024-01-01 (A0)
- Decisores: nadabgfccvd, xisto-agent

## Contexto

A suíte precisa de milhares de assets determinísticos (texturas, meshes,
áudio, shaders, ícones, strings, DEX de stress) sem commitar binários no
repositório — binários incham o clone, quebram review e tornam o histórico
inverificável. Ferramentas com dependências (numpy, Pillow, build tools
não-reprodutíveis) introduziram variação entre máquinas e entre CI/local, o
que destrói a promessa central do projeto: **answer keys estáveis** e builds
byte-idênticas.

Alternativas consideradas:

- Commitar os assets gerados: rejeitado (histórico gigante, review cego,
  risco de drift entre artefato e gerador).
- Toolchains ricas com dependências externas: rejeitado (não-reprodutível
  entre runners; CI mais lento e mais frágil).
- Gerar assets no runtime do RustyDroid: rejeitado (o runtime deve consumir
  fixtures prontas; a geração é responsabilidade da suíte).

## Decisão

Todos os geradores em `tools/` são **Python 3 stdlib-only** (`python3
tools/gen-*.py`), **determinísticos** (seed explícita via `--seed`, ordenação
estável de arquivos, sem timestamps/nome de máquina na saída) e **nenhum
binário gerado é commitado** — os APKs e assets são sempre gerados do checkout
limpo. O contrato comum dos geradores é `--seed` / `--out`.

## Consequências

- Reprodutibilidade total: mesmo checkout + mesma seed => mesmos bytes
  (verificável por `tools/verify-deterministic.sh`: duas builds byte-idênticas
  exceto assinatura).
- CI simples: `python3 -m compileall tools scripts` é lint suficiente; nada a
  instalar.
- Geração pesada (4K PBR, áudio longo, malhas) é mais lenta que com libs
  binárias — aceito: roda offline e é paralelizável.
- Proibido commitar qualquer `dist/`, `build/` ou asset binário gerado.
