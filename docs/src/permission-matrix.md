# Matriz de Permissões

## Estrutura da auditoria

O flagship **Behemoth** (`dev.apktester.behemoth`) declara **literalmente toda
permissão da plataforma** enumerada em
`frameworks/base/core/res/AndroidManifest.xml` do AOSP: **~160 strings no
total**. A auditoria canônica é
`contracts/flagship/permissions-audit.md` (answer key preenchida em A1) e cada
entrada carrega:

- `name` — string completa da permissão (ex.: `android.permission.CAMERA`);
- `protectionLevel` — `normal` / `dangerous` / `signature` / `signatureOrSystem`;
- `group` — grupo de runtime (LOCATION, CAMERA, ...);
- `maxSdkVersion` — para variantes deprecated com teto;
- `@hide` — flag marcando strings `@hide`/internas (apenas flagship).

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
`maxSdkVersion` (GET_TASKS 25, PROCESS_OUTGOING_CALLS 28, USE_CREDENTIALS 22,
PERSISTENT_ACTIVITY 15, READ_EXTERNAL_STORAGE 32, USE_FINGERPRINT 27,
BLUETOOTH/BLUETOOTH_ADMIN 30, ...), `uses-permission-sdk-23`, e declarações
custom `<permission>` (normal + signature), `<permission-group>` e
`<permission-tree>`.

## Política @hide

Strings `@hide`/internas do AOSP (ACCESS_CACHE_FILESYSTEM,
CLEAR_APP_USER_DATA, FORCE_STOP_PACKAGES, MOVE_PACKAGE, UPDATE_DEVICE_STATS,
SHUTDOWN, ...) entram **somente no flagship**, e cada uma vem marcada com a
flag `@hide` na auditoria para não poluir a contagem das permissões públicas.

## Permissões inventadas — NUNCA no flagship

Strings inventadas/inexistentes (permission strings que não existem no AOSP)
vivem **exclusivamente** em `suites/parser-torture/unknown-perms/`. Elas testam
como o RustyDroid classifica permissões desconhecidas — e jamais entram no
flagship nem nesta matriz.

## Tabela esqueleto (preencher em A1)

A tabela canônica por permissão (order alfabético, ~160 linhas):

| name | protectionLevel | group | maxSdkVersion | @hide |
|------|-----------------|-------|---------------|-------|
| *(vazio até A1)* | | | | |

Contagens por nível (answer key `permissions-audit.md` deve bater com o
manifest, zero-drift):

| protectionLevel | alvo (~160 total) | contagem no manifest | status |
|-----------------|-------------------|----------------------|--------|
| normal | TBD (A1) | — | pendente A1 |
| dangerous | TBD (A1) | — | pendente A1 |
| signature | TBD (A1) | — | pendente A1 |
| signatureOrSystem | TBD (A1) | — | pendente A1 |
| **total** | **~160** | — | pendente A1 |
