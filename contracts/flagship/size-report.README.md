# size-report.csv — nota de uso

Este CSV é o answer key de tamanho do flagship Behemoth
(`dev.apktester.behemoth`), emitido por `tools/size-budget.sh`.

- **Hoje (A0)**: arquivo contém apenas o header + as 10 categorias com zeros —
  valores preenchidos a partir de A1 e fechados no gate de A6.
- **Gate (A6)**: tamanho de release do flagship dentro de **[850 MB, 1000 MB]**;
  o workflow Size Gate falha fora da faixa e se o drift vs último relatório
  passar de **+2%**.
- Categorias: textures, meshes, shaders, audio, dex, arsc, so, locales,
  resources, other (bytes descomprimidos por categoria + contagem de arquivos;
  `sha256_of_apk` é o checksum do APK de origem da medição).
- **Nota**: CSV não suporta linhas de comentário — por isso esta nota vive
  neste README e o CSV se mantém puro (parseável por
  `python3 -c "import csv; ..."` e pelo workflow).
