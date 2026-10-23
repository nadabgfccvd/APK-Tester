# engine-16-tauri — Tier A (build real)

**Engine engine-16 da matriz RustyDroid (Apêndice G): Rust/Tauri v2.**
Build REAL (payload executável): toolchains reais e pinadas, sem stub —
diferença honesta vs. Tier C (ADR 0003: "detecção não valida payload nem
autoriza execução"; aqui o payload É executável, então o detector deve
casar de verdade).

- **Build:** `./build.sh --out dist` (delega ao orquestrador
  `tools/build-tier-a.py`; sem toolchain no PATH, ele emite só o plano JSON)
- **Toolchain:** `source tools/setup-tier-a-toolchain.sh engine-16-tauri`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift
  contra `contracts/engines/expected-engines.json`)
- **minSdk 26 / targetSdk 36** · `applicationId` `dev.apktester.engine.engine16tauri` · seed 20261022

## Estratégia de build (A4)

Dois cdylibs reais da stack Tauri: tauri-android (crate tauri 2.12) e wry (crate wry 0.57), cargo-ndk para x86_64.

Pinos de versão: `rust 1.83.0`, `cargo-ndk 3.5.0`, `tauri 2.12`, `wry 0.57`.

## Verificação

O CI (job `tier-a-engines`) executa: selftest → sync de contratos +
`git diff --exit-code` → build → `--verify-apk` (artefatos do contrato:
presença de caminho/glob, `dex-strings:*` nos dex, `elf-strings:*` nos
.so e magic ELF nos nativos). Os binários NÃO são commitados (lei do
repo); o sha256 de cada build vai para o artefato de CI (report JSON).
