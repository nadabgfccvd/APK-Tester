# Exported Audit — armadilhas de manifesto (fixture exported-audit)

Gerado por `tools/gen-trap-manifest.py` (seed 20261022) a partir da MESMA
tabela TRAPS que emite o manifesto e os POJOs — zero drift.

> **AVISO:** as violações abaixo são **INTENCIONAIS**. A fixture
> existe para o relato de auditoria do RustyDroid
> (manifest-as-truth, CORE-12). Instalar em dispositivo real NÃO é
> o objetivo — e as permissões ausentes são parte do gabarito.

Pacote `dev.apktester.fixture.exportedaudit` · minSdk 26 · targetSdk 36 · versionCode 900036 · uses-permission: apenas `android.permission.INTERNET`.

| ID | Componente | O que está errado | O que o relato do RustyDroid DEVE apontar |
|---|---|---|---|
| T1 | activity `.TrapExportedNoPermActivity` | activity exportada sem android:permission | componente exportado sem permissão de invocação — qualquer app pode iniciá-la |
| T2 | activity `.TrapLauncherActivity` | (baseline) nenhum — baseline de launcher | launcher padrão; o relato NÃO deve apontá-la como achado |
| T3 | activity-alias `.TrapAlias` | alias oculto (exported=false) apontando para activity exportada | divergência alias x alvo: o alias não deve herdar a exposição do targetActivity |
| T4 | service `.TrapExportedService` | service exportado sem android:permission | serviço exportado sem permissão — qualquer app pode bind/start |
| T5 | service `.TrapBoundService` | (baseline) nenhum — baseline de serviço privado | serviço privado; o relato NÃO deve apontá-lo como achado |
| T6 | receiver `.TrapOpenReceiver` | receiver aberto por intent-filter (action custom) sem android:permission | receiver implicitamente exportado sem permissão de broadcast |
| T7 | provider `.TrapOpenProvider` | provider exportado SEM readPermission/writePermission (mundialmente legível e gravável) | provider exportado sem guarda de leitura/escrita — armadilha forte |
| T8 | provider `.TrapGrantProvider` | grantUriPermissions=true com pathPattern amplo /.* | concessão de URI ampla: acesso delegável a qualquer caminho do provider |
| T9 | service `.TrapForegroundTypeService` | foregroundServiceType=location sem ACCESS_FINE_LOCATION nem FOREGROUND_SERVICE declaradas | tipo em foreground sem a permissão exigida (regra de targetSdk 34+) |

São 9 componentes: 7 armadilhas + 2 baselines (T2, T5) de contraprova.

## Zero drift

Manifesto, POJOs, `traps-report.json` e esta auditoria saem da MESMA tabela TRAPS em `tools/gen-trap-manifest.py`. O CI compara o relato do RustyDroid com `traps-report.json` (9 entradas, sendo 2 baselines que NÃO devem virar achados). Regenerar: `python3 tools/gen-trap-manifest.py --out <dir>`.
