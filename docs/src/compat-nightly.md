# Compatibilidade nightly (RustyDroid x fixtures)

O workflow [`engines-nightly.yml`](https://github.com/nadabgfccvd/APK-Tester/blob/main/.github/workflows/engines-nightly.yml)
é o coração do pilar 5 (governança de grade profissional): todo dia às 03:00
UTC (ou sob demanda via `workflow_dispatch`) ele:

1. **Constrói os 9 engines Tier B de verdade** (Scala, Flutter, React Native,
   Cordova, NativeScript, Lua/Defold, Godot, Qt/QML, Avalonia/.NET) com as
   toolchains pesadas pinadas — uma matriz de jobs com `fail-fast: false`;
   a build de PR nunca espera por elas (ADR 0002);
2. **Empacota as 9 fixtures Tier C** (detection fixtures honestas, ADR 0003)
   pela `tools/fixture-pack.py`;
3. **Roda o `scripts/compat-nightly.sh`**: para cada engine dos 32 do answer
   key (`contracts/engines/expected-engines.json`) ele executa
   `rustydroid inspect --json` e `rd engine detect` contra o APK e compara a
   saída com os `rustydroid_engines` esperados;
4. **Publica `docs/compat-matrix.md` no GH Pages** junto com o site mdBook
   (job `docs-pages`);
5. **Abre uma issue `fixture_gap`** automaticamente se qualquer linha vier
   FAIL (drift de detecção vs answer key).

## Lei do nightly

- **Sem `rustydroid` no PATH**, todas as linhas viram `SKIP` e o script sai 0
  — a matriz existe e é publicada mesmo antes do runtime estar disponível no
  runner. Quando o binário do RustyDroid for publicado, o mesmo script passa
  a exercitá-lo sem mudança de workflow (basta colocá-lo no PATH).
- **Fixture sem APK** vira linha `SEM_APK` (não é FAIL): honestidade sobre o
  estado da cobertura.
- **Qualquer FAIL sai 1** e o workflow abre `fixture_gap` com o run e os
  próximos passos. FAIL aqui é **drift de DETECÇÃO** — não falha de payload
  (ADR 0003: "detecção não valida payload nem autoriza execução").

## Como rodar localmente

```bash
bash scripts/compat-nightly.sh            # matriz com SKIP (sem rustydroid)
# com um rustydroid local no PATH:
rustydroid --version && bash scripts/compat-nightly.sh
```

O script procura cada APK em
`suites/engines/<engine>/dist/<engine>.apk`,
`suites/engines/<engine>/dist/app.apk`,
`suites/engines/<engine>/<engine>.apk` e escreve
`docs/compat-matrix.md` com a tabela completa + resumo (OK/FAIL/SKIP/
SEM_APK).

## Estratégia de build Tier B (fase A7)

Cada engine tem um `build.sh` que delega ao orquestrador
`tools/build-tier-b.py`: a toolchain pesada é **baixada da fonte oficial para
a árvore de trabalho** (Maven Central, npm registry, NuGet, GitHub Releases,
aqt/Qt, Flutter SDK) com versões pinadas — nada de binário commitado. O
empacotamento segue o MESMO caminho do Tier A/fixture-pack
(aapt2 → d8 → zipalign → apksigner v1+v2); para Flutter e Godot, a própria
toolchain produz o APK final. Detalhes por engine na [Matriz de Engines](engine-matrix.md)
e no README de cada diretório em `suites/engines/`.

Nomes de artefatos que divergiram da previsão A3 foram **refinados contra os
artefatos REAIS** em A7 (honestidade do answer key > conveniência):

| Engine | A3 (previsão) | A7 (real, pinado) |
|---|---|---|
| engine-17-nativescript | `lib/x86_64/libnativescript.so` | `lib/x86_64/libNativeScript.so` |
| engine-22-lua-defold | `lib/x86_64/libdmengine.so` | `lib/arm64-v8a/libdmengine.so` |
| engine-28-avalonia-dotnet | `libmonodroid.so` + `libskiasharp.so` | `libmono-android.release.so` + `libSkiaSharp.so` |
