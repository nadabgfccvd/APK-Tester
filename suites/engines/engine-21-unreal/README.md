# engine-21-unreal — Unreal (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com `lib/x86_64/libUE4.so` (stub ELF com marcadores UE4/UnrealEngine/FRunnable) e `assets/main.pak` (magic `0x5A6F12E1`, versão 8 — placeholder de pacote de assets). NÃO é o engine Unreal.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-21-unreal --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-21-unreal --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-21-unreal.apk \
    --engine engine-21-unreal
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `lib/x86_64/libUE4.so` | arquivo no APK | payload do gen-engine-fixtures |
| `assets/*.pak` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/fixture-marker.txt` | 291 |
| `assets/main.pak` | 1536 |
| `lib/x86_64/libUE4.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `unreal` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
