# engine-30-wasm-in-app — Tier A (build real)

**Engine engine-30 da matriz RustyDroid (Apêndice G): Rust/WASM (host embutido).**
Build REAL (payload executável): toolchains reais e pinadas, sem stub —
diferença honesta vs. Tier C (ADR 0003: "detecção não valida payload nem
autoriza execução"; aqui o payload É executável, então o detector deve
casar de verdade).

- **Build:** `./build.sh --out dist` (delega ao orquestrador
  `tools/build-tier-a.py`; sem toolchain no PATH, ele emite só o plano JSON)
- **Toolchain:** `source tools/setup-tier-a-toolchain.sh engine-30-wasm-in-app`
- **Contrato:** `expected-engines.json` (cópia por diretório, zero drift
  contra `contracts/engines/expected-engines.json`)
- **minSdk 26 / targetSdk 36** · `applicationId` `dev.apktester.engine.engine30wasminapp` · seed 20261022

## Estratégia de build (A4)

module.wasm compilado pelo wat2wasm (wabt 1.0.36) + host libwasmer.so (crate wasmer 7, singlepass) via cargo-ndk.

Pinos de versão: `wabt 1.0.36`, `rust 1.83.0`, `cargo-ndk 3.5.0`, `wasmer 7`.

## Verificação

O CI (job `tier-a-engines`) executa: selftest → sync de contratos +
`git diff --exit-code` → build → `--verify-apk` (artefatos do contrato:
presença de caminho/glob, `dex-strings:*` nos dex, `elf-strings:*` nos
.so e magic ELF nos nativos). Os binários NÃO são commitados (lei do
repo); o sha256 de cada build vai para o artefato de CI (report JSON).

## Verificação do módulo WASM (A9)

O `--verify-apk` do orquestrador vai além da presença de artefatos para o
kind `wasm`: o `assets/module.wasm` extraído do APK é (1) validado
estruturalmente por um parser de seções WASM em stdlib (magic `\0asm`,
versão 1, tamanhos de seção coerentes, export section decodificada com
LEB128 — exports `apktester_add`/`apktester_checksum`/`apktester_mem` — e
data segment com o marcador `apktester-wasm/engine-30`) e (2) INSTANCIADO
de verdade no WebAssembly do node (preinstalado nos runners do CI):
`apktester_add(2,3)==5`, `apktester_checksum()==20261022` e
`memória[0:24]=="apktester-wasm/engine-30"`. O runtime wasmer do APK deixa
de ser apenas linkado — a promessa de "validável em runtime" agora é uma
prova executável (auditoria A9/roadmap 3.4).
