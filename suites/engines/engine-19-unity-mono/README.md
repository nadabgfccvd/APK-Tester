# engine-19-unity-mono — Unity Mono (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com o layout de um jogo Unity Mono: `assets/bin/Data/Managed/Assembly-CSharp.dll` (stub MZ/PE + `BSJB` + marcadores UnityEngine/MonoBehaviour), `lib/x86_64/libunity.so` e `lib/x86_64/libmonobdwgc-2.0.so` (stubs ELF com marcadores). NÃO é o player Unity.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-19-unity-mono --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-19-unity-mono --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-19-unity-mono.apk \
    --engine engine-19-unity-mono
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `assets/bin/Data/Managed/Assembly-CSharp.dll` | arquivo no APK | payload do gen-engine-fixtures |
| `lib/x86_64/libunity.so` | arquivo no APK | payload do gen-engine-fixtures |
| `lib/x86_64/libmonobdwgc-2.0.so` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/bin/Data/Managed/Assembly-CSharp.dll` | 4096 |
| `assets/fixture-marker.txt` | 302 |
| `lib/x86_64/libmonobdwgc-2.0.so` | 4096 |
| `lib/x86_64/libunity.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `unity-mono` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
