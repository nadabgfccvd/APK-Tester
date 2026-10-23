# engine-20-unity-il2cpp — Unity IL2CPP (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com o layout IL2CPP: `lib/x86_64/libil2cpp.so` (stub ELF com `il2cpp_init`, `il2cpp_string_new` etc.), `assets/bin/Data/Managed/Metadata/global-metadata.dat` (magic `0xFAB11BAF`, versão 31) e `lib/x86_64/libunity.so`. NÃO há código IL2CPP nem metadata real.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-20-unity-il2cpp --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-20-unity-il2cpp --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-20-unity-il2cpp.apk \
    --engine engine-20-unity-il2cpp
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `lib/x86_64/libil2cpp.so` | arquivo no APK | payload do gen-engine-fixtures |
| `assets/bin/Data/Managed/Metadata/global-metadata.dat` | arquivo no APK | payload do gen-engine-fixtures |
| `lib/x86_64/libunity.so` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/bin/Data/Managed/Metadata/global-metadata.dat` | 2048 |
| `assets/fixture-marker.txt` | 308 |
| `lib/x86_64/libil2cpp.so` | 4096 |
| `lib/x86_64/libunity.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `unity-il2cpp` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
