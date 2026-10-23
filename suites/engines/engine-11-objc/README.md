# engine-11-objc — Objective-C (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com o quarteto padrão de componentes e um stub ELF64 (`lib/x86_64/libobjc-fixture.so`) cuja `.rodata` carrega os marcadores `objc_msgSend`, `objc_getClass`, `sel_registerName` etc. O runtime Objective-C em Android é raríssimo; o stub existe para exercitar a DETECÇÃO, não a execução.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-11-objc --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-11-objc --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-11-objc.apk \
    --engine engine-11-objc
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `lib/x86_64/libobjc-fixture.so` | arquivo no APK | payload do gen-engine-fixtures |
| `assets/fixture-marker.txt` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/fixture-marker.txt` | 288 |
| `lib/x86_64/libobjc-fixture.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `objc` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
