# engine-04-scala — Tier B (build real no nightly)

**Engine engine-04 da matriz RustyDroid (Apêndice G): Scala.**
Build REAL no `engines-nightly.yml` (ADR 0002): `scalac` 2.13.15 oficial
(jars do Maven Central) compila as fontes `.scala` commitadas; o `d8` dexa
as classes junto da `scala-library` — os strings `scala.runtime.*` ficam no
DEX de verdade.

- **Build:** `./build.sh --out dist` (delega a `tools/build-tier-b.py`;
  downloads pinados para a árvore de trabalho, nada commitado)
- **Pinos:** scala `2.13.15`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift)
- **minSdk 26 / targetSdk 36** · `dev.apktester.engine.engine04scala` · seed 20261022

## Verificação

`--verify-apk` confere o contrato: `classes.dex` presente e
`dex-strings:scala.runtime` nos dex.
