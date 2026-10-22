# Permissions Audit — flagship "Behemoth" (dev.apktester.behemoth)

STATUS: **esqueleto** — preencher em A1. Este documento é o answer key da
classificação de permissões feita pelo permission engine do RustyDroid
(permission engine as data) sobre o manifesto do flagship.

## Estrutura por permissão

Cada linha da tabela canônica carrega exatamente estas colunas:

| Coluna | Descrição |
|--------|-----------|
| name | string completa (ex.: `android.permission.CAMERA`) |
| protectionLevel | `normal` / `dangerous` / `signature` / `signatureOrSystem` |
| group | grupo de runtime (LOCATION, CAMERA, ...); vazio quando sem grupo |
| maxSdkVersion | teto para variantes deprecated; vazio quando não há |
| @hide | flag `sim`/`nao` para strings `@hide`/internas do AOSP |

## Contagens-alvo

Total alvo: **~160 permissões** (todas as strings de
`frameworks/base/core/res/AndroidManifest.xml` do AOSP), mais
`uses-permission-sdk-23`, `<permission>` custom (normal + signature),
`<permission-group>` e `<permission-tree>`.

| protectionLevel | alvo (~160 total) | contagem no manifest | status |
|-----------------|-------------------|----------------------|--------|
| normal | TBD (A1) | — | pendente A1 |
| dangerous | TBD (A1) | — | pendente A1 |
| signature | TBD (A1) | — | pendente A1 |
| signatureOrSystem | TBD (A1) | — | pendente A1 |
| **total** | **~160** | — | pendente A1 |

Grupos `dangerous` a cobrir: LOCATION, CAMERA, MICROPHONE, CONTACTS, PHONE,
SMS, STORAGE-MEDIA, SENSORS, CALENDAR, NEARBY_DEVICES, NOTIFICATIONS, HEALTH.

## Tabela canônica (preencher em A1 — ordem alfabética, ~160 linhas)

| name | protectionLevel | group | maxSdkVersion | @hide |
|------|-----------------|-------|---------------|-------|
| *(vazio até A1)* | | | | |

## Especiais a inventariar em A1

- Todas as `BIND_*` de serviços de sistema (16 — ver manifest-audit.md):
  WRITE_SECURE_SETTINGS, DUMP, READ_LOGS, REBOOT, DEVICE_POWER, BRICK,
  MANAGE_DOCUMENTS, INSTALL_LOCATION_PROVIDER, LOCATION_HARDWARE,
  CONTROL_LOCATION_UPDATES, READ_FRAME_BUFFER, CLEAR_APP_CACHE, GLOBAL_SEARCH,
  SET_DEBUG_APP, ACCESS_MOCK_LOCATION, FACTORY_TEST, ...;
- Special app access: SYSTEM_ALERT_WINDOW, WRITE_SETTINGS,
  MANAGE_EXTERNAL_STORAGE, REQUEST_INSTALL_PACKAGES, REQUEST_DELETE_PACKAGES,
  PACKAGE_USAGE_STATS, SCHEDULE_EXACT_ALARM / USE_EXACT_ALARM,
  USE_FULL_SCREEN_INTENT, ACCESS_NOTIFICATION_POLICY,
  START_FOREGROUND_SERVICES_FROM_BACKGROUND, IGNORE_BATTERY_OPTIMIZATIONS,
  QUERY_ALL_PACKAGES;
- FOREGROUND_SERVICE_* (todas as 15);
- Deprecated com maxSdkVersion: GET_TASKS (25), PROCESS_OUTGOING_CALLS (28),
  USE_CREDENTIALS (22), PERSISTENT_ACTIVITY (15), READ_EXTERNAL_STORAGE (32),
  USE_FINGERPRINT (27), BLUETOOTH (30), BLUETOOTH_ADMIN (30), ...;
- `@hide`/internas: ACCESS_CACHE_FILESYSTEM, CLEAR_APP_USER_DATA,
  FORCE_STOP_PACKAGES, MOVE_PACKAGE, UPDATE_DEVICE_STATS, SHUTDOWN, ... —
  **cada uma marcada com @hide=sim**.

## Regras duras

1. **Permissões signature/`@hide` são inobtíveis em device real** — o flagship
   testa a *classificação* do RustyDroid, não instalabilidade.
2. **Strings inventadas NUNCA entram aqui.** Permissões inexistentes/fake vivem
   exclusivamente em `suites/parser-torture/unknown-perms/` — jamais no
   flagship nem nesta auditoria.
3. O diff entre `rustydroid inspect --json` e esta tabela deve ser zero-drift
   (contagem por nível, grupo por permissão, maxSdk e flag @hide).
