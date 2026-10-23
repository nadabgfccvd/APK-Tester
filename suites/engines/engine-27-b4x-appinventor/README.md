# engine-27-b4x-appinventor — B4X / App Inventor (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com classes marcador nos pacotes `anywheresoftware.b4a` e `com.google.appinventor.components.runtime` — strings que o detector casa no dex. NÃO é o runtime B4A/Rapid Debugger.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-27-b4x-appinventor --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-27-b4x-appinventor --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-27-b4x-appinventor.apk \
    --engine engine-27-b4x-appinventor
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `classes.dex` | arquivo no APK | pipeline padrão do fixture-pack |
| `dex-strings:anywheresoftware.b4a` | string no dex | classes marcador Java (javac + d8) |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/fixture-marker.txt` | 315 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `b4x-appinventor` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
