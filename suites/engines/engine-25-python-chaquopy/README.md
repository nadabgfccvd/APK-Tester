# engine-25-python-chaquopy — Tier A (build real)

**Engine engine-25 da matriz RustyDroid (Apêndice G): Python/Chaquopy.**
Build REAL (payload executável): toolchains reais e pinadas, sem stub —
diferença honesta vs. Tier C (ADR 0003: "detecção não valida payload nem
autoriza execução"; aqui o payload É executável, então o detector deve
casar de verdade).

- **Build:** `./build.sh --out dist` (delega ao orquestrador
  `tools/build-tier-a.py`; sem toolchain no PATH, ele emite só o plano JSON)
- **Toolchain:** `source tools/setup-tier-a-toolchain.sh engine-25-python-chaquopy`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift
  contra `contracts/engines/expected-engines.json`)
- **minSdk 26 / targetSdk 36** · `applicationId` `dev.apktester.engine.engine25pythonchaquopy` · seed 20261022

## Estratégia de build (A4)

Gradle 8.10.2 + AGP 8.7.3 + Chaquopy 16.1.0: APK gradle real com libpython3*.so e assets/chaquopy (x86_64), assinado pelo apksigner do pack.

Pinos de versão: `gradle 8.10.2`, `chaquopy 16.1.0`, `agp 8.7.3`.

## Verificação

O CI (job `tier-a-engines`) executa: selftest → sync de contratos +
`git diff --exit-code` → build → `--verify-apk` (artefatos do contrato:
presença de caminho/glob, `dex-strings:*` nos dex, `elf-strings:*` nos
.so e magic ELF nos nativos). Os binários NÃO são commitados (lei do
repo); o sha256 de cada build vai para o artefato de CI (report JSON).
