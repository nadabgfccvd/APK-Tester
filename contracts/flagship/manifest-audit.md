# Manifest Audit — flagship "Behemoth" (dev.apktester.behemoth)

STATUS: **A1 — esqueleto completo, todo componente declarado tem classe
real**. Este documento e o answer key do `rustydroid inspect --json` para
o manifesto do flagship (CORE-12: manifest-as-truth). Gerado por
`tools/gen-flagship-manifest.py` — manifesto e auditoria saem da mesma
tabela de componentes (zero drift por construcao). A superficie final
(30+ activities por dominio, aliases r3..r8, AIDL, mais widgets) chega
nos marcos A5/A6 — os valores-alvo fixos de cada secao continuam
contratuais na coluna `alvo`.

## Identidade

| campo | valor |
|-------|-------|
| applicationId | `dev.apktester.behemoth` |
| versionName | `1.0.0` |
| versionCode | `900036` |
| minSdk | 9 (classic) / 26 (modern) |
| targetSdk | 36 |
| sharedUserId | `dev.apktester.behemoth` — **somente** flavor classic |
| extractNativeLibs | atributo removido do manifesto (regra AGP 8); `useLegacyPackaging` por flavor entra com as libs nativas no marco A4 |

## Permissoes

| item | contagem |
|------|----------|
| uses-permission (plataforma, snapshot verbatim) | 1004 |
| uses-permission com maxSdkVersion | 9 |
| uses-permission-sdk-23 | 3 |
| permission custom | 2 (normal + signature) |
| permission-group custom | 1 |
| permission-tree custom | 1 |

Answer key detalhado: contracts/flagship/permissions-audit.md.

## Activities

| classe | label | exported | intent-filters | status |
|--------|-------|----------|----------------|--------|
| .MainActivity | @string/app_name | true | 2 filter(s) (https autoVerify): android.intent.action.MAIN; android.intent.action.VIEW | A1 |
| .PermissionsHubActivity | @string/permission_hub_title | true | 0 filter(s): — | A1 |
| .ButtonGridActivity | @string/button_grid_title | true | 0 filter(s): — | A1 |
| .IconGridActivity | @string/icon_grid_title | true | 0 filter(s): — | A1 |
| .ProbeReportActivity | @string/probe_report_title | true | 6 filter(s): android.intent.action.VIEW; android.intent.action.VIEW; android.intent.action.VIEW; android.intent.action.VIEW; android.intent.action.VIEW; android.intent.action.VIEW | A1 |
**atual: 5 — alvo: >= 30 (uma por dominio, incl. telas 3D/Shaders/GLES em A5/A6)**

### Activity-aliases (2)

| classe | target | icone | enabled | launcher | nota |
|--------|--------|-------|---------|----------|------|
| .MainActivityLauncherAlias1 | .MainActivity | @drawable/ic_launcher_r1 | true | sim | alias ativo com icone proprio (launcher icon multiplo) |
| .MainActivityLauncherAlias2 | .MainActivity | @drawable/ic_launcher_r2 | false | nao | alias DESATIVADO (android:enabled=false) — caso de borda auditado |
Alvo final: 8 aliases (r1..r8 com icones do gen-icons).

## Services

| classe | guard (permission) | intent-filter | exported | status |
|--------|--------------------|---------------|----------|--------|
| .services.AccessibilityStubService | android.permission.BIND_ACCESSIBILITY_SERVICE | android.accessibilityservice.AccessibilityService | true | A1 |
| .services.NotificationListenerStub | android.permission.BIND_NOTIFICATION_LISTENER_SERVICE | android.service.notification.NotificationListenerService | true | A1 |
| .services.InputMethodStub | android.permission.BIND_INPUT_METHOD | android.view.InputMethod | true | A1 |
| .services.VoiceInteractionStub | android.permission.BIND_VOICE_INTERACTION | android.service.voice.VoiceInteractionService | true | A1 |
| .services.CallScreeningStub | android.permission.BIND_SCREENING_SERVICE | android.telecom.CallScreeningService | true | A1 |
| .services.InCallStub | android.permission.BIND_INCALL_SERVICE | android.telecom.InCallService | true | A1 |
| .services.PrintStub | android.permission.BIND_PRINT_SERVICE | android.printservice.PrintService | true | A1 |
| .services.AutofillStub | android.permission.BIND_AUTOFILL_SERVICE | android.service.autofill.AutofillService | true | A1 |
| .services.TileStub | android.permission.BIND_QUICK_SETTINGS_TILE | android.service.quicksettings.action.QS_TILE | true | A1 |
| .services.HostApduStub | android.permission.BIND_NFC_SERVICE | — | true | A1 |
| .services.MediaBrowserStub | android.permission.BIND_MEDIA_BROWSER_SERVICE | android.media.browse.MediaBrowserService | true | A1 |
| .services.WallpaperStub | android.permission.BIND_WALLPAPER | android.service.wallpaper.WallpaperService | true | A1 |
| .services.DreamStub | android.permission.BIND_DREAM_SERVICE | android.service.dreams.DreamService | true | A1 |
| .services.VpnStub | android.permission.BIND_VPN_SERVICE | — | true | A1 |
| .services.CredentialStub | android.permission.BIND_CREDENTIALS_SERVICE | android.service.credentials.CredentialProviderService | true | A1 |
| .services.MessengerService | — | — | false | A1 |
| .services.ForegroundStub | — | — | false | A1 |
**atual: 17 — alvo: >= 15 (AIDL + Messenger bound; foreground com TODOS os types declarados)**

### Servicos de sistema (15 <service> + DeviceAdminReceiver = 16)

| servico | classe base | BIND_* |
|---------|-------------|--------|
| Accessibility | AccessibilityService | android.permission.BIND_ACCESSIBILITY_SERVICE |
| NotificationListener | NotificationListenerService | android.permission.BIND_NOTIFICATION_LISTENER_SERVICE |
| InputMethod (IME) | InputMethodService | android.permission.BIND_INPUT_METHOD |
| DeviceAdmin (receiver) | DeviceAdminReceiver | android.permission.BIND_DEVICE_ADMIN |
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
| Credential | CredentialProviderService | android.permission.BIND_CREDENTIALS_SERVICE |

ForegroundStub declara TODOS os foregroundServiceType (dataSync,
mediaPlayback, location, camera, microphone, phoneCall, connectedDevice,
mediaProjection, remoteMessaging, shortService, specialUse, health,
systemExperiments) + property `android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE`.

## Receivers (10)

| classe | actions | exported | status |
|--------|---------|----------|--------|
| .receivers.BootReceiver | android.intent.action.BOOT_COMPLETED | true | A1 |
| .receivers.LocaleReceiver | android.intent.action.LOCALE_CHANGED | true | A1 |
| .receivers.TimeReceiver | android.intent.action.TIME_SET | true | A1 |
| .receivers.TimezoneReceiver | android.intent.action.TIMEZONE_CHANGED | true | A1 |
| .receivers.PackageReplacedReceiver | android.intent.action.PACKAGE_REPLACED | true | A1 |
| .receivers.MyPackageReplacedReceiver | android.intent.action.MY_PACKAGE_REPLACED | true | A1 |
| .receivers.UserPresentReceiver | android.intent.action.USER_PRESENT | true | A1 |
| .receivers.PowerReceiver | android.intent.action.ACTION_POWER_CONNECTED; android.intent.action.ACTION_POWER_DISCONNECTED | true | A1 |
| .receivers.ScreenReceiver | android.intent.action.SCREEN_ON; android.intent.action.SCREEN_OFF | true | A1 |
| .receivers.DeviceAdminReceiverStub | android.app.action.DEVICE_ADMIN_ENABLED | true | A1 |

## Providers (2)

| classe | authorities | exported | readPermission | writePermission | nota |
|--------|-------------|----------|----------------|-----------------|------|
| .providers.BehemothProvider | dev.apktester.behemoth.provider | true | — | — | CRUD proprio sobre SQLite (probe CORE-PV-001) |
| .providers.GuardedProvider | dev.apktester.behemoth.guarded | true | dev.apktester.behemoth.permission.CUSTOM_SIGNATURE | dev.apktester.behemoth.permission.CUSTOM_SIGNATURE | provider com readPermission/writePermission guardados por permissao custom signature |

Nota do master prompt menciona FileProvider (androidx): entra no flavor
modern junto do resto do androidx (A5/A6). Em A1 os 2 providers sao
framework-only para o classic compilar limpo.

## Widgets (2)

| classe | meta-data | label | status |
|--------|-----------|-------|--------|
| .widgets.BehemothAppWidget | @xml/appwidget_provider | @string/app_name | A1 |
| .widgets.SecondAppWidget | @xml/appwidget_provider_second | @string/behemoth_widget_second_label | A1 |

## Instrumentation (1)

- `.probe.BehemothInstrumentation` targetPackage `dev.apktester.behemoth` functionalTest=true handleProfiling=false

## Queries / features / telas

| item | valor |
|------|-------|
| queries | 1 bloco: 2 packages + 7 intents |
| uses-feature required | 3 (camera, microphone, sensor.compass) |
| glEsVersion | 0x00030002 (required) |
| uses-feature opcionais | 12 (gps, network location, BLE, NFC, telephony, wifi, gyroscope, type.pc, leanback, app_widgets, device_admin, vulkan.version 0x401000) |
| uses-configuration | 2 (touchscreen finger; fiveWayNav + qwerty) |
| supports-screens | any/large/normal/small/xlarge + resizeable |
| compatible-screens | 4 (small/ldpi, normal/hdpi, large/xhdpi, xlarge/xxhdpi) |
| supports-gl-texture | 3 |
| uses-native-library | 3 dentro de <application> (libEGL.so, libOpenSLES.so opcionais; libc.so required) |

### Deep links

| scheme | host/path | autoVerify | classe |
|--------|-----------|------------|--------|
| https | maxprobe.dev/apktester | sim | .MainActivity |
| maxprobe | — | nao | .ProbeReportActivity |
| geo / tel / sms / mailto / market | — | nao | .ProbeReportActivity |

## Configs de backup/rede/locales (conflito deliberado)

- `android:networkSecurityConfig` -> @xml/network_security_config (permite
  cleartext APENAS para 10.0.0.1)
- `android:usesCleartextTraffic="false"` no <application> — **conflito
  deliberado** com a NSC acima: o RustyDroid deve reportar a divergencia
  (erro estruturado), nunca crashar.
- `android:dataExtractionRules` (API 31+) + `android:fullBackupContent`
  (legacy) -> @xml/data_extraction_rules / @xml/backup_rules
- `android:localeConfig` (API 33) -> @xml/locales_config (12 locales do
  gen-strings)
- `android:extractNativeLibs`: NAO declarado — o AGP 8 proibe o atributo no
  manifesto-fonte; o empacotamento de libs nativas (useLegacyPackaging)
  sera definido por flavor no build.gradle quando :native/:rust
  existirem (A4)

## RustyDroid — diff esperado

`rustydroid inspect --json` sobre o flagship deve reproduzir: contagens
deste documento, a tabela canonica de permissions-audit.md (zero drift),
os 2 aliases, os 16 servicos de sistema com seus BIND_*, o conflito de
cleartext documentado e sharedUserId SO no flavor classic.
