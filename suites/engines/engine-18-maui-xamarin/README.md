# engine-18-maui-xamarin — .NET MAUI / Xamarin (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com stubs de assemblies Mono (`assemblies/MyApp.dll`, `assemblies/Mono.Android.dll` — assinatura MZ/PE com metadata `BSJB` e marcadores `Mono.Android`, `Xamarin.Forms`, `Mono.Runtime`) e `lib/x86_64/libmonodroid.so`. NÃO é o runtime Mono nem contém IL executável real.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-18-maui-xamarin --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-18-maui-xamarin --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-18-maui-xamarin.apk \
    --engine engine-18-maui-xamarin
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `assemblies/*.dll` | arquivo no APK | payload do gen-engine-fixtures |
| `lib/x86_64/libmonodroid.so` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assemblies/Mono.Android.dll` | 4096 |
| `assemblies/MyApp.dll` | 4096 |
| `assets/fixture-marker.txt` | 308 |
| `lib/x86_64/libmonodroid.so` | 4096 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `maui-xamarin` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
