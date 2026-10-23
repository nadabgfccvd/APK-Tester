# engine-24-haxe — Tier A (build real)

**Engine engine-24 da matriz RustyDroid (Apêndice G): Haxe.**
Build REAL (payload executável): toolchains reais e pinadas, sem stub —
diferença honesta vs. Tier C (ADR 0003: "detecção não valida payload nem
autoriza execução"; aqui o payload É executável, então o detector deve
casar de verdade).

- **Build:** `./build.sh --out dist` (delega ao orquestrador
  `tools/build-tier-a.py`; sem toolchain no PATH, ele emite só o plano JSON)
- **Toolchain:** `source tools/setup-tier-a-toolchain.sh engine-24-haxe`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift
  contra `contracts/engines/expected-engines.json`)
- **minSdk 26 / targetSdk 36** · `applicationId` `dev.apktester.engine.engine24haxe` · seed 20261022

## Estratégia de build (A4)

Haxe 4.3.6 -java (hxjava+ant): classes haxe.root compiladas por javac e dexadas.

Pinos de versão: `haxe 4.3.6`.

## Verificação

O CI (job `tier-a-engines`) executa: selftest → sync de contratos +
`git diff --exit-code` → build → `--verify-apk` (artefatos do contrato:
presença de caminho/glob, `dex-strings:*` nos dex, `elf-strings:*` nos
.so e magic ELF nos nativos). Os binários NÃO são commitados (lei do
repo); o sha256 de cada build vai para o artefato de CI (report JSON).
