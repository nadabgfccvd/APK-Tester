# engine-07-c-ndk — Tier A (build real)

**Engine engine-07 da matriz RustyDroid (Apêndice G): C (NDK).**
Build REAL (payload executável): toolchains reais e pinadas, sem stub —
diferença honesta vs. Tier C (ADR 0003: "detecção não valida payload nem
autoriza execução"; aqui o payload É executável, então o detector deve
casar de verdade).

- **Build:** `./build.sh --out dist` (delega ao orquestrador
  `tools/build-tier-a.py`; sem toolchain no PATH, ele emite só o plano JSON)
- **Toolchain:** `source tools/setup-tier-a-toolchain.sh engine-07-c-ndk`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift
  contra `contracts/engines/expected-engines.json`)
- **minSdk 26 / targetSdk 36** · `applicationId` `dev.apktester.engine.engine07cndk` · seed 20261022

## Estratégia de build (A4)

clang do NDK r27: libnative-c.so para arm64-v8a e x86_64 com exports JNI Java_*.

Pinos de versão: `ndk r27 (ANDROID_NDK_LATEST_HOME do runner)`.

## Verificação

O CI (job `tier-a-engines`) executa: selftest → sync de contratos +
`git diff --exit-code` → build → `--verify-apk` (artefatos do contrato:
presença de caminho/glob, `dex-strings:*` nos dex, `elf-strings:*` nos
.so e magic ELF nos nativos). Os binários NÃO são commitados (lei do
repo); o sha256 de cada build vai para o artefato de CI (report JSON).
