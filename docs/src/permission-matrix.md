# Matriz de Permissões

## Estrutura da auditoria

O flagship **Behemoth** (`dev.apktester.behemoth`) declara **literalmente
toda permissão da plataforma** enumerada em
`frameworks/base/core/res/AndroidManifest.xml` do AOSP master: **1004
declarações `android.permission.*`** (snapshot verbatim — 1004 nomes
únicos, pois o próprio manifesto do AOSP declara 2 permissões duas vezes
com `protectionLevel` distinto). A auditoria canônica é
`contracts/flagship/permissions-audit.md` (answer key **preenchida e
entregue em A1**) e cada entrada carrega:

- `name` — string completa da permissão (ex.: `android.permission.CAMERA`);
- `protectionLevel` — string verbatim do AOSP com flags
  (`normal` / `dangerous` / `signature` / `internal` / `signature|privileged`,
  ...); as contagens agregam pelo token base;
- `group` — grupo de runtime (LOCATION, CAMERA, ...);
- `maxSdkVersion` — para variantes deprecated com teto (9 no flagship);
- `@hide` — flag marcando strings `@hide`/internas (677 de 1004).

O snapshot de onde tudo deriva é `contracts/flagship/permissions-registry.json`
— o bloco `provenance` guarda a URL da fonte, o `sha256` do manifesto AOSP
capturado e a data UTC da captura.

## Protection levels

| protectionLevel | Significado | Expectativa no RustyDroid |
|-----------------|-------------|----------------------------|
| `normal` | Concedida automaticamente na instalação | classificada como normal |
| `dangerous` | Permissão de runtime por grupo | classificada com o grupo correto |
| `signature` | Só se assinada pelo mesmo certificado | classificada; inobtível em device real |
| `signatureOrSystem` | Assinatura ou partição system (legacy) | classificada; inobtível em device real |

Permissões `signature`/`signatureOrSystem`/`@hide` são **inobtíveis em
dispositivo real**: o flagship testa a *classificação* feita pelo permission
engine do RustyDroid (permission engine as data), não instalabilidade.

## Grupos de permissões perigosas (dangerous)

LOCATION, CAMERA, MICROPHONE, CONTACTS, PHONE, SMS, STORAGE-MEDIA, SENSORS,
CALENDAR, NEARBY_DEVICES, NOTIFICATIONS, HEALTH.

Além disso, a auditoria cobre: todas as `BIND_*` de serviços de sistema
(16 serviços no manifesto do flagship), permissões especiais de app-access
(SYSTEM_ALERT_WINDOW, WRITE_SETTINGS, MANAGE_EXTERNAL_STORAGE,
REQUEST_INSTALL/DELETE_PACKAGES, PACKAGE_USAGE_STATS,
SCHEDULE_EXACT_ALARM/USE_EXACT_ALARM, USE_FULL_SCREEN_INTENT,
ACCESS_NOTIFICATION_POLICY, IGNORE_BATTERY_OPTIMIZATIONS, QUERY_ALL_PACKAGES,
...), todas as FOREGROUND_SERVICE_* (15), variantes deprecated com
`maxSdkVersion` (GET_TASKS 21, PROCESS_OUTGOING_CALLS 28, USE_CREDENTIALS 22,
PERSISTENT_ACTIVITY 15, READ_EXTERNAL_STORAGE 32, USE_FINGERPRINT 28,
BLUETOOTH/BLUETOOTH_ADMIN 30, ... — níveis de deprecação documentados,
auditados valor a valor pelo check `permission_drift` do APKBot), `uses-permission-sdk-23`, e declarações
custom `<permission>` (normal + signature), `<permission-group>` e
`<permission-tree>`.

### Contagens por grupo de runtime (somente dangerous, A1)

| grupo | contagem |
|-------|----------|
| CALENDAR | 2 |
| CAMERA | 1 |
| CONTACTS | 3 |
| LOCATION | 3 |
| MICROPHONE | 1 |
| NEARBY_DEVICES | 6 |
| NOTIFICATIONS | 1 |
| PHONE | 9 |
| SENSORS | 3 |
| SMS | 5 |
| STORAGE | 7 |
| (sem grupo) | 1 |
| **total** | **42** |

`READ_CELL_BROADCASTS` é `dangerous` sem grupo de runtime no
PermissionController — exceção documentada no mapa curado.

## Metodologia (A1)

1. **Verbatim, não estimativa.** A lista de permissões É o snapshot AOSP:
   `tools/snapshot-aosp-permissions.py` captura o manifesto da plataforma
   (`frameworks/base/core/res/AndroidManifest.xml`, branch master) e extrai
   as 1004 strings — incluindo `@hide`/internas. As ~160 citadas na
   literatura são o subconjunto publicamente documentado; o manifesto real
   define mais. Declarar menos geraria ruído permanente no
   `bot/checks/permission_drift.py`, que compara a tabela contra o AOSP vivo.
2. **protectionLevel verbatim** — a string completa do AOSP com flags;
   contagens agregadas pelo token base.
3. **Grupos de runtime** — o manifesto AOSP master não declara
   `android:group` nas `<permission>` (grupos vivem no PermissionController);
   o grupo das `dangerous` vem do mapa curado da ferramenta de snapshot
   (doc API 33–36).
4. **Flag @hide** — heurística de comentário: `@hide` presente no bloco de
   comentário imediatamente anterior à declaração.
5. **maxSdkVersion** — não existe nas `<permission>` do AOSP; o valor vem da
   `<uses-permission>` do flagship (tabela curada de variantes deprecated).

## Política @hide

Strings `@hide`/internas do AOSP (ACCESS_CACHE_FILESYSTEM,
CLEAR_APP_USER_DATA, FORCE_STOP_PACKAGES, MOVE_PACKAGE, UPDATE_DEVICE_STATS,
SHUTDOWN, ...) entram **somente no flagship**, e cada uma vem marcada com a
flag `@hide` na auditoria para não poluir a contagem das permissões
públicas. Em A1 são **677 de 1004** (67% do total) — número que cresce a
cada snapshot do AOSP.

## Permissões inventadas — NUNCA no flagship

Strings inventadas/inexistentes (permission strings que não existem no AOSP)
vivem **exclusivamente** em `suites/parser-torture/unknown-perms/`. Elas testam
como o RustyDroid classifica permissões desconhecidas — e jamais entram no
flagship nem nesta matriz.

## Contagens por protectionLevel (A1, answer key entregue)

A tabela canônica por permissão (ordem alfabética, 1004 linhas: name,
protectionLevel verbatim, group, maxSdkVersion, @hide) vive em
`contracts/flagship/permissions-audit.md` — fonte única, regenerada por
`tools/gen-flagship-manifest.py` (zero drift por construção).

Contagens por nível base (o `permissions-audit.md` e o manifest batem,
zero-drift):

| protectionLevel (base) | contagem no manifest |
|------------------------|----------------------|
| normal | 95 |
| dangerous | 42 |
| signature | 745 |
| internal | 119 |
| role | 1 |
| system | 1 |
| module | 1 |
| **total** | **1004** |

Notas de A1: `signatureOrSystem` (legacy) não ocorre mais no manifesto
master — foi substituído por `signature|privileged`; os níveis `internal`,
`role`, `system` e `module` são níveis internos da plataforma e entram no
answer key tal como o RustyDroid os encontra. Superfície completa do
manifesto: 1004 `uses-permission` (9 com `maxSdkVersion`), 3
`uses-permission-sdk-23`, 2 `<permission>` custom (normal + signature),
1 `<permission-group>`, 1 `<permission-tree>`; 12 definições
não-plataforma do snapshot registradas como proveniência (o flagship não
as declara).

## Referências (A1)

- `contracts/flagship/permissions-audit.md` — answer key canônica por
  permissão (name, protectionLevel, group, maxSdkVersion, @hide) +
  contagens por nível e grupo;
- `contracts/flagship/permissions-registry.json` — snapshot verbatim do
  AOSP master (bloco `provenance` com sha256 e data da captura);
- `contracts/flagship/manifest-audit.md` — answer key do manifesto
  (componentes, queries, features, deep links);
- `contracts/flagship/manifest.json` — ledger de integridade dos
  artefatos gerados.
