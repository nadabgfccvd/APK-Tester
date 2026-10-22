<!-- Descreva o PR no contexto das fases A0–A8. PRs fora do escopo da fase marcada serão redirecionados. -->

## Fase relacionada

- [ ] A0 — scaffold (governança, CI esqueleto, geradores)
- [ ] A1 — flagship skeleton (manifest completo, PermissionsHub, ButtonGrid/IconGrid)
- [ ] A2 — sdk-ladder (minSdk 9 primeiro) + parser-torture
- [ ] A3 — engines Tier C (fixtures sintéticas honestas)
- [ ] A4 — engines Tier A (builds reais)
- [ ] A5 — 3D/shaders (:sim3d + shader-library + texturas/meshes/áudio)
- [ ] A6 — engenharia de tamanho (gate [850, 1000] MB + size-report.csv)
- [ ] A7 — Tier B nightly + compat-nightly + docs site
- [ ] A8 — gate v1.0 (matriz verde + determinismo + release)

## O que mudou

<!-- Resumo objetivo. Referencie issues com "Closes #N". -->

## Como testar

```bash
# lints
python3 -m compileall tools scripts
shellcheck tools/*.sh scripts/*.sh
bash -n tools/*.sh scripts/*.sh

# contratos (answer keys) válidos
python3 -c "import json,glob; [json.load(open(f, encoding='utf-8')) for f in glob.glob('contracts/**/*.json', recursive=True)]"

# compat matrix local (sem rustydroid instalado: todas as linhas SKIP, exit 0)
bash scripts/compat-nightly.sh
```

## Checklist

- [ ] Lints verdes (shellcheck, compileall, bash -n)
- [ ] Contracts atualizados (suites.json / expected-engines.json / audits do flagship)
- [ ] Docs atualizados (mdBook — guide, matrizes, ADRs)
- [ ] Determinismo preservado (geradores stdlib-only com --seed, nenhum binário commitado)
