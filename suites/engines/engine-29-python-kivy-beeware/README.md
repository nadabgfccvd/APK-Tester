# engine-29-python-kivy-beeware — Python (Kivy/BeeWare) (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK no layout python-for-android/briefcase: `lib/x86_64/libpython3.11.so` (stub ELF com `Py_Initialize`, `PyRun_SimpleString`, `3.11.8`) e `assets/python/main.py` (entrypoint Python real, porém nunca executado pelo RustyDroid). NÃO é o intérprete CPython.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-29-python-kivy-beeware --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-29-python-kivy-beeware --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-29-python-kivy-beeware.apk \
    --engine engine-29-python-kivy-beeware
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `lib/x86_64/libpython3*.so` | arquivo no APK | payload do gen-engine-fixtures |
| `assets/python/main.py` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/fixture-marker.txt` | 326 |
| `assets/python/main.py` | 516 |
| `lib/x86_64/libpython3.11.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `python-kivy-beeware` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
