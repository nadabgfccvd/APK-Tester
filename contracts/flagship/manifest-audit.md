# Manifest Audit — flagship "Behemoth" (dev.apktester.behemoth)

STATUS: **esqueleto** — preenchimento completo em A1. Este documento é o
answer key do `rustydroid inspect --json` para o manifesto do flagship
(CORE-12: manifest-as-truth). Toda contagem abaixo é valor-alvo FIXO: o diff
numérico entre o inspect e estas tabelas deve ser ZERO-DRIFT.

## Schema do documento

Cada seção abaixo vira uma tabela com uma linha por componente. As tabelas
estão vazias até A1; os valores-alvo desta página já são contratuais.

| Seção | Valor-alvo fixo |
|-------|-----------------|
| activities | >= 30 (uma por domínio, incl. telas 3D/Shaders/GLES) |
| activity-aliases | == 2 |
| services | >= 15 (AIDL + Messenger bound; foreground com TODOS os types declarados) |
| system services BIND_* | == 16 |
| receivers | >= 10 |
| providers | == 2 (CRUD próprio + FileProvider com readPermission) |
| widgets (appwidget-provider) | == 2 |
| instrumentation | == 1 |
| queries | 1 bloco (packages/intents/providers) |
| uses-feature required | == 3 (+ demais opcionais) |
| glEsVersion | 0x00030002 |
| deep links | https autoVerify + schemes custom (estilo maxprobe) + geo/tel/sms/mailto/market |
| sharedUserId | somente no flavor classic |

## Serviços de sistema (16) com BIND_*

| Serviço | Classe base | BIND_* |
|---------|-------------|--------|
| Accessibility | AccessibilityService | android.permission.BIND_ACCESSIBILITY_SERVICE |
| NotificationListener | NotificationListenerService | android.permission.BIND_NOTIFICATION_LISTENER_SERVICE |
| InputMethod (IME) | InputMethodService | android.permission.BIND_INPUT_METHOD |
| DeviceAdmin | DeviceAdminReceiver | android.permission.BIND_DEVICE_ADMIN |
| VoiceInteraction | VoiceInteractionService | android.permission.BIND_VOICE_INTERACTION |
| CallScreening | CallScreeningService | android.permission.BIND_SCREENING_SERVICE |
| Telecom (InCall) | InCallService | android.permission.BIND_INCALL_SERVICE |
| Print | PrintService | android.permission.BIND_PRINT_SERVICE |
| Autofill | AutofillService | android.permission.BIND_AUTOFILL_SERVICE |
| Tile | TileService | android.permission.BIND_QUICK_SETTINGS_TILE |
| HostApdu | HostApduService | android.permission.BIND_NFC_SERVICE |
| MediaBrowser | MediaBrowserService | android.permission.BIND_MEDIA_BROWSER_SERVICE |
| Wallpaper | WallpaperService | android.permission.BIND_WALLPAPER |
| Dream | DreamService | android.permission.BIND_DREAM_SERVICE |
| Vpn | VpnService | android.permission.BIND_VPN_SERVICE |
| Credential | CredentialProviderService | BIND_* exato confirmado em A1 |

## Tabelas a preencher em A1

### Activities (>= 30)

| name | exported | intent-filters | notes |
|------|----------|----------------|-------|
| *(vazio até A1)* | | | |

### Activity aliases (== 2)

| name | targetActivity | notes |
|------|----------------|-------|
| *(vazio até A1)* | | |

### Services (>= 15)

| name | exported | foregroundServiceType | bound | notes |
|------|----------|------------------------|-------|-------|
| *(vazio até A1)* | | | | |

### Receivers (>= 10)

| name | exported | intent-filters | notes |
|------|----------|----------------|-------|
| *(vazio até A1)* | | | |

### Providers (== 2)

| name | authorities | grantUriPermissions | readPermission | notes |
|------|-------------|---------------------|----------------|-------|
| *(vazio até A1)* | | | | |

### Widgets (== 2)

| receiver | appwidget-provider | notes |
|----------|--------------------|-------|
| *(vazio até A1)* | | |

### Instrumentation (== 1)

| name | targetPackage | notes |
|------|---------------|-------|
| *(vazio até A1)* | | |

### queries

| tipo | conteúdo | notes |
|------|----------|-------|
| *(vazio até A1)* | | |

### uses-feature / glEsVersion

| name | required | notes |
|------|----------|-------|
| *(3 required + opcionais, até A1)* | | |

glEsVersion fixa: `0x00030002`.

### Deep links

| scheme/host | autoVerify | notes |
|-------------|------------|-------|
| https (autoVerify) | true | asset links |
| schemes custom (estilo maxprobe) | false | edge cases de intent-filter |
| geo / tel / sms / mailto / market | false | |

### Config extras

- `dataExtractionRules` + `fullBackupContent` + `networkSecurityConfig`
  (com **conflito deliberado de cleartext** documentado para a auditoria);
- `extractNativeLibs`: ambas as variantes across flavors;
- `uses-configuration`, `supports-screens`/`compatible-screens`,
  `supports-gl-texture` (x3), `uses-native-library`, `localeConfig`;
- `sharedUserId`: **classic flavor only**.
