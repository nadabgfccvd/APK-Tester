# engine-32-twa-pwa — TWA/PWA (Tier C)

**fixture de detecção; payload não executável** — lei do RustyDroid (ADR 0003): *"detecção não valida payload nem autoriza execução"*.

## O que este APK é

Um APK com os marcadores de Trusted Web Activity: `meta-data asset_statements` no manifesto apontando para a string de digital asset links (`@string/asset_statements`) e classe marcador `androidx.browser.trusted.TrustedWebActivityIntentUtils` com as constantes `asset_statements` e `androidx.browser.trusted` no dex. Não há WebView wrapper real nem site verificado — a detecção é o teste.

## Como é construído (determinístico, seed 20261022)

```bash
# payloads (stubs + classes marcador):
python3 tools/gen-engine-fixtures.py --engine engine-32-twa-pwa --out WORK
# empacotamento (aapt2 + javac + d8 + zip + zipalign + apksigner):
python3 tools/fixture-pack.py --fixture engine-32-twa-pwa --out dist
# verificação contra o contrato:
python3 tools/gen-engine-fixtures.py --verify-apk dist/engine-32-twa-pwa.apk \
    --engine engine-32-twa-pwa
```

## Artefatos de detecção (contrato `expected-engines.json`)

| Artefato | Tipo | Origem |
|---|---|---|
| `dex-strings:asset_statements` | string no dex | classes marcador Java (javac + d8) |
| `dex-strings:androidx.browser.trusted` | string no dex | classes marcador Java (javac + d8) |
| `assets/fixture-marker.txt` | arquivo no APK | payload do gen-engine-fixtures |

## Payloads dentro do APK (sha256 em `contracts/engines/tier-c-payload-report.json`)

| Caminho no APK | Bytes |
|---|---|
| `assets/fixture-marker.txt` | 286 |

## Honestidade (leia antes de usar)

- Os stubs ELF/PE/metadata/pak têm a assinatura e o layout certos para a DETECÇÃO — não são runtimes reais, não executam nada, não contêm o payload da linguagem.
- O engine id esperado no `rd engine detect` é `twa` (chave de respostas canônica: `contracts/engines/expected-engines.json`).
- Toda alteração de payload passa pelo gerador determinístico; drift de sha256 contra o report commitado reprova o CI (`--verify-apk`).
