# ADR 0001 — Geradores Python stdlib-only e determinísticos

- Status: accepted
- Data: 2026-10-22 (decisão registrada no commit A0; data placeholder 2024-01-01 removida na A9)
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
- CI: lint real desde a A9 (ruff, seleção E4/E7/E9+F no `ruff.toml` —
  erros objetivos: imports mortos, nomes não definidos, variáveis não
  usadas) + `compileall` + shellcheck; a decisão de FORMATO (sem
  formatador automático) está documentada no `ruff.toml`.
- Geração pesada (4K PBR, áudio longo, malhas) é mais lenta que com libs
  binárias — aceito: roda offline e é paralelizável.
- **Escopo da garantia de determinismo (A9, roadmap 6.6 — decisão
  documentada):** a prova é POR-RUNNER (mesma máquina/python/stdlib — o
  CI do repo roda ubuntu-latest; `verify-deterministic.sh` compara duas
  execuções no MESMO ambiente, e a prova de release compara duas builds
  no MESMO run). Independência de libm/plataforma (2º runner em macOS)
  é trabalho futuro NÃO assumido: os geradores evitam float-no-output
  onde o conteúdo é contrato (inteiros/bytes), mas a prova formal
  cross-platform não existe — gap registrado, não silêncio.
- Proibido commitar qualquer `dist/`, `build/` ou asset binário gerado.
- **Exceção (A9, roadmap 5.1): `gradle/wrapper/gradle-wrapper.jar`.** As
  suítes Gradle (flagship e sdk-ladder) commitam o jar do wrapper — é a
  praxe padrão do ecossistema Gradle (o wrapper é o bootstrap confiável e
  auditável do build; sem ele o clone não reproduz o build sem instalar
  Gradle na mão). A exceção é delimitada e verificável: exatamente DOIS
  jars idênticos (sha256
  `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`),
  cada um com sidecar `gradle-wrapper.jar.sha256` pinado ao lado para
  `sha256sum -c`; a distribuição Gradle em si NÃO é commitada (o
  `gradle-wrapper.properties` pinado a `gradle-8.11.1-bin.zip` é baixado
  no build). Nenhum outro binário tem essa exceção.
