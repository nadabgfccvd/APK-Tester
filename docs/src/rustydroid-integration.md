# Integração RustyDroid

O APK Tester existe para ser consumido pelo RustyDroid. Abaixo, os comandos
exatos de integração e como o CI os consome.

## 1. Inspeção numerada — zero-drift vs answer key

```bash
# flagship (flavor modern, minSdk 26)
rd inspect --json suites/flagship/dist/behemoth.apk > /tmp/flagship-inspect.json
```

A saída JSON é diffada numericamente contra os contratos do flagship:

- `contracts/flagship/manifest-audit.md` — contagens de components
  (activities >= 30, aliases == 2, services >= 15, receivers >= 10,
  providers == 2, widgets == 2, as 16 BIND_*, queries, uses-feature,
  glEsVersion 0x00030002);
- `contracts/flagship/permissions-audit.md` — ~160 permissões com
  protectionLevel/grupo/maxSdk/@hide (classificação, não instalabilidade).

Qualquer divergência de contagem ou classificação é **drift** e vira issue
`fixture_gap`. Exemplo de checagem numérica:

```bash
python3 - <<'EOF'
import json
inspect = json.load(open("/tmp/flagship-inspect.json"))
# ajuste as chaves conforme a versão do RustyDroid; o princípio é:
# contagens e classificações do inspect == contagens dos audits (zero-drift)
print(json.dumps(inspect, indent=2)[:400])
EOF
```

## 2. Detector de engines — vs expected-engines.json

```bash
# por engine
rd engine detect suites/engines/engine-09-rust/dist/app.apk
# esperado: linha 'rust-ndk Candidate' (answer key = conjunto EMITIDO
# completo do detector; ver contracts/engines/expected-engines.json)

# híbrido TST-14: os quatro marcadores num único APK
rd engine detect suites/engines/engine-31-hybrid/dist/app.apk
# esperado: linhas 'react-native' + 'wasm' (candidates) — o híbrido não
# tem id próprio no registro do detector
```

O answer key canônico é `contracts/engines/expected-engines.json`
(`schema_version` 1, 32 entradas com `dir`, `tier`, `build`,
`rustydroid_engines` e `detector_artifacts`).

## 3. Suítes de cenário

```bash
rustydroid test contracts/suites.json
```

Executa cada suite declarada (engines, flagship, escada minSdk) e compara com
os `expects` de cada entrada (`rustydroid_engines`, `min_sdk`,
`below_floor_allowed`, resultado esperado `BELOW_FLOOR` vs execução).

## 4. Snapshot de compat gaps

```bash
rustydroid get_compat_gaps --json > docs/compat-gaps-snapshot.json
```

Snapshot dos gaps de compatibilidade conhecidos do runtime contra a suíte —
versionado para diff entre releases.

## 5. Matriz nightly

```bash
bash scripts/compat-nightly.sh
```

- Sem `rd` no PATH, o script faz bootstrap do snapshot pinado por sha256
  (ADR 0004); download/integridade falhando é FAIL, nunca SKIP silencioso;
- Com runtime: `rd inspect --json` + `rd engine detect` por fixture,
  diff contra o answer key, e agregação em `docs/compat-matrix.md`;
- Qualquer `FAIL` => exit 1 (o workflow nightly abre issue com label
  `fixture_gap` e publica a matriz no GH Pages).

## Como o CI consome

| Workflow | Consumo |
|----------|---------|
| `ci.yml` (`contracts-check`) | valida JSON de `contracts/**` e `schema_version == 1` de `suites.json` |
| `ci.yml` (`tier-a-skeleton`) | matriz Tier A; em A4 vira build real + detect |
| `size-gate.yml` | `tools/size-budget.sh` no flagship, gate [850 MB, 1000 MB], drift <= +2% |
| `engines-nightly.yml` (`compat-nightly`) | `scripts/compat-nightly.sh` -> `docs/compat-matrix.md` -> GH Pages + issues `fixture_gap` |
| `release.yml` | `tools/verify-deterministic.sh` (duas builds byte-idênticas exceto assinatura) + empacota `contracts/` + APKs |
