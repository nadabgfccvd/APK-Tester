# Permissions Audit — flagship "Behemoth" (dev.apktester.behemoth)

STATUS: **preenchida em A1** — answer key das permissoes declaradas pelo
flagship, gerada por `tools/gen-flagship-manifest.py` a partir do registry
canonico `contracts/flagship/permissions-registry.json` (snapshot verbatim
do `frameworks/base/core/res/AndroidManifest.xml` do AOSP master,
sha256 `336cc3ed0c0182b9a6d9345f6003e042285b9bfbd67d74c5c5959d01186280fc`, capturado em 2026-10-22T15:51:19Z).

## Metodologia

1. **Verbatim, nao estimativa.** A lista de permissoes E o snapshot AOSP:
   1004 strings `android.permission.*` definidas no manifesto da
   plataforma — incluindo `@hide`/internas (as ~160 citadas no master
   prompt sao o subconjunto publicamente documentado; o manifesto real
   define mais. O APKBot (bot/checks/permission_drift.py) compara esta
   tabela contra o AOSP ao vivo: declarar menos geraria ruido permanente.
2. **protectionLevel verbatim** — a string completa do AOSP com flags
   (`signature|privileged|instant`, `dangerous|runtime`, ...). As
   contagens agregam pelo token base.
3. **Grupos de runtime** — o manifesto AOSP master nao declara
   `android:group` nas `<permission>` (grupos vivem no
   PermissionController); o grupo das `dangerous` vem do mapa curado
   `DANGEROUS_GROUPS` da ferramenta de snapshot (doc API 33-36).
4. **Flag @hide** — heuristica de comentario: `@hide` no bloco de
   comentario imediatamente anterior a declaracao.
5. **maxSdkVersion** — nao existe nas `<permission>` AOSP; o valor e da
   `<uses-permission>` do flagship (tabela curada de variantes
   deprecadas, ver secao abaixo).

## Contagens por protectionLevel (token base)

| protectionLevel (base) | contagem |
|------------------------|----------|
| dangerous | 42 |
| internal | 119 |
| module | 1 |
| normal | 95 |
| role | 1 |
| signature | 745 |
| system | 1 |
| **total** | **1004** |

Nota: `signatureOrSystem` (legacy) nao ocorre mais no manifesto master —
foi substituido por `signature|privileged`. Os niveis `internal`,
`role`, `system` e `module` sao niveis internos da plataforma e entram
no answer key tal como o RustyDroid os encontra.

## Contagens por grupo de runtime (somente dangerous)

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

`READ_CELL_BROADCASTS` e `dangerous` sem grupo de runtime no
PermissionController — excecao documentada no mapa curado.

## Flag @hide

677 de 1004 permissoes marcadas como `@hide`/internas
(67% do total). Permissoes signature/@hide sao
inobtiveis em device real: o flagship testa a **classificacao** do
permission engine do RustyDroid, nao instalabilidade (hard-truth do
master prompt).

## maxSdkVersion (uses-permission deprecadas)

| permissao | maxSdkVersion |
|-----------|---------------|
| android.permission.BLUETOOTH | 30 |
| android.permission.BLUETOOTH_ADMIN | 30 |
| android.permission.GET_TASKS | 21 |
| android.permission.PERSISTENT_ACTIVITY | 15 |
| android.permission.PROCESS_OUTGOING_CALLS | 28 |
| android.permission.READ_EXTERNAL_STORAGE | 32 |
| android.permission.USE_CREDENTIALS | 22 |
| android.permission.USE_FINGERPRINT | 28 |
| android.permission.WRITE_EXTERNAL_STORAGE | 32 |

## uses-permission-sdk-23 (declaradas so para API 23+)

- `android.permission.GET_ACCOUNTS`
- `android.permission.READ_PHONE_NUMBERS`

## Permissoes custom da suite

| name | protectionLevel | papel |
|------|-----------------|-------|
| dev.apktester.behemoth.permission.CUSTOM_NORMAL | normal | permissao custom normal — guarda a LEITURA do GuardedNormalProvider (exported; autoridade dev.apktester.behemoth.guarded.normal); referenciada de verdade desde a A9 (roadmap 3.6) |
| dev.apktester.behemoth.permission.CUSTOM_SIGNATURE | signature | permissao custom signature — guarda o GuardedProvider (leitura e escrita) |
| dev.apktester.behemoth.permission-group.BEHEMOTH | permission-group | agrupamento custom |
| dev.apktester.behemoth.permission-tree.DYNAMIC | permission-tree | arvore de permissoes dinamicas |

## Definicoes nao-plataforma no snapshot (12)

Definicoes `com.android.*` / `android.intent.category.*` presentes no
manifesto AOSP (nao entram na tabela canonica nem nas contagens de
plataforma; o flagship NAO as declara — sao registro de proveniencia):

| name | protectionLevel |
|------|-----------------|
| android.intent.category.MASTER_CLEAR.permission.C2D_MESSAGE | signature |
| com.android.alarm.permission.SET_ALARM | normal |
| com.android.browser.permission.READ_HISTORY_BOOKMARKS | normal |
| com.android.browser.permission.WRITE_HISTORY_BOOKMARKS | normal |
| com.android.launcher.permission.INSTALL_SHORTCUT | normal |
| com.android.launcher.permission.UNINSTALL_SHORTCUT | normal |
| com.android.permission.INSTALL_EXISTING_PACKAGES | signature\|privileged\|role |
| com.android.permission.USE_INSTALLER_V2 | signature\|privileged |
| com.android.permission.USE_SYSTEM_DATA_LOADERS | signature |
| com.android.voicemail.permission.ADD_VOICEMAIL | dangerous |
| com.android.voicemail.permission.READ_VOICEMAIL | signature\|privileged\|role |
| com.android.voicemail.permission.WRITE_VOICEMAIL | signature\|privileged\|role |

## Tabela canonica (ordem alfabetica)

Colunas: name | protectionLevel (verbatim) | group | maxSdkVersion | @hide.

| name | protectionLevel | group | maxSdkVersion | @hide |
|------|-----------------|-------|---------------|-------|
| android.permission.ACCEPT_HANDOVER | dangerous | PHONE |  | nao |
| android.permission.ACCESSIBILITY_MOTION_EVENT_OBSERVING | signature |  |  | sim |
| android.permission.ACCESS_AMBIENT_CONTEXT_EVENT | signature\|privileged\|role |  |  | sim |
| android.permission.ACCESS_AMBIENT_LIGHT_STATS | signature\|privileged\|development |  |  | sim |
| android.permission.ACCESS_BACKGROUND_LOCATION | dangerous\|instant | LOCATION |  | nao |
| android.permission.ACCESS_BLOBS_ACROSS_USERS | signature\|privileged\|development\|role |  |  | nao |
| android.permission.ACCESS_BROADCAST_RADIO | signature\|privileged |  |  | sim |
| android.permission.ACCESS_BROADCAST_RESPONSE_STATS | signature\|privileged\|development |  |  | sim |
| android.permission.ACCESS_CACHE_FILESYSTEM | signature\|privileged |  |  | sim |
| android.permission.ACCESS_CHECKIN_PROPERTIES | signature\|privileged |  |  | nao |
| android.permission.ACCESS_COARSE_LOCATION | dangerous\|instant | LOCATION |  | nao |
| android.permission.ACCESS_CONTENT_PROVIDERS_EXTERNALLY | signature |  |  | sim |
| android.permission.ACCESS_CONTEXTUAL_SEARCH | signature\|privileged |  |  | sim |
| android.permission.ACCESS_CONTEXT_HUB | signature\|privileged |  |  | sim |
| android.permission.ACCESS_DRM_CERTIFICATES | signature\|privileged |  |  | sim |
| android.permission.ACCESS_FINE_LOCATION | dangerous\|instant | LOCATION |  | nao |
| android.permission.ACCESS_FINE_POWER_MONITORS | signature\|privileged\|development |  |  | sim |
| android.permission.ACCESS_FM_RADIO | signature\|privileged |  |  | sim |
| android.permission.ACCESS_FPS_COUNTER | signature\|privileged |  |  | sim |
| android.permission.ACCESS_GPU_SERVICE | signature |  |  | sim |
| android.permission.ACCESS_HIDDEN_PROFILES | normal |  |  | nao |
| android.permission.ACCESS_HIDDEN_PROFILES_FULL | signature\|privileged |  |  | sim |
| android.permission.ACCESS_IMS_CALL_SERVICE | signature\|privileged |  |  | sim |
| android.permission.ACCESS_INPUT_FLINGER | signature |  |  | sim |
| android.permission.ACCESS_INSTANT_APPS | signature\|installer\|verifier\|role |  |  | sim |
| android.permission.ACCESS_KEYGUARD_SECURE_STORAGE | signature\|setup |  |  | sim |
| android.permission.ACCESS_LAST_KNOWN_CELL_ID | signature |  |  | sim |
| android.permission.ACCESS_LOCATION_EXTRA_COMMANDS | normal |  |  | nao |
| android.permission.ACCESS_LOCUS_ID_USAGE_STATS | signature\|role |  |  | sim |
| android.permission.ACCESS_LOWPAN_STATE | signature\|privileged |  |  | sim |
| android.permission.ACCESS_MEDIA_LOCATION | dangerous | STORAGE |  | nao |
| android.permission.ACCESS_MESSAGES_ON_ICC | signature |  |  | sim |
| android.permission.ACCESS_MOCK_LOCATION | signature |  |  | sim |
| android.permission.ACCESS_MTP | signature\|privileged |  |  | sim |
| android.permission.ACCESS_NETWORK_CONDITIONS | signature\|privileged |  |  | sim |
| android.permission.ACCESS_NETWORK_STATE | normal\|instant |  |  | nao |
| android.permission.ACCESS_NOTIFICATIONS | signature\|privileged\|appop |  |  | sim |
| android.permission.ACCESS_NOTIFICATION_POLICY | normal |  |  | nao |
| android.permission.ACCESS_PDB_STATE | signature\|role |  |  | sim |
| android.permission.ACCESS_RCS_USER_CAPABILITY_EXCHANGE | internal\|role |  |  | sim |
| android.permission.ACCESS_SHARED_LIBRARIES | signature\|installer |  |  | sim |
| android.permission.ACCESS_SHORTCUTS | signature\|role\|recents |  |  | sim |
| android.permission.ACCESS_SMARTSPACE | signature\|privileged\|development |  |  | sim |
| android.permission.ACCESS_SURFACE_FLINGER | signature |  |  | sim |
| android.permission.ACCESS_TEXT_CLASSIFIER_BY_TYPE | signature\|role |  |  | sim |
| android.permission.ACCESS_TUNED_INFO | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.ACCESS_TV_DESCRAMBLER | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.ACCESS_TV_SHARED_FILTER | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.ACCESS_TV_TUNER | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.ACCESS_UCE_OPTIONS_SERVICE | signature\|privileged |  |  | sim |
| android.permission.ACCESS_UCE_PRESENCE_SERVICE | signature\|privileged |  |  | sim |
| android.permission.ACCESS_ULTRASOUND | signature\|privileged |  |  | sim |
| android.permission.ACCESS_VIBRATOR_STATE | signature\|privileged |  |  | sim |
| android.permission.ACCESS_VOICE_INTERACTION_SERVICE | signature |  |  | sim |
| android.permission.ACCESS_VR_MANAGER | signature |  |  | sim |
| android.permission.ACCESS_VR_STATE | signature\|preinstalled |  |  | sim |
| android.permission.ACCESS_WIFI_STATE | normal |  |  | nao |
| android.permission.ACCOUNT_MANAGER | signature |  |  | nao |
| android.permission.ACTIVITY_EMBEDDING | signature\|privileged |  |  | sim |
| android.permission.ACTIVITY_RECOGNITION | dangerous\|instant | SENSORS |  | nao |
| android.permission.ACT_AS_PACKAGE_FOR_ACCESSIBILITY | signature |  |  | sim |
| android.permission.ADD_ALWAYS_UNLOCKED_DISPLAY | signature\|role |  |  | sim |
| android.permission.ADD_MIRROR_DISPLAY | internal\|role |  |  | sim |
| android.permission.ADD_TRUSTED_DISPLAY | signature\|role |  |  | sim |
| android.permission.ADJUST_RUNTIME_PERMISSIONS_POLICY | signature\|installer |  |  | sim |
| android.permission.ALLOCATE_AGGRESSIVE | signature\|privileged |  |  | sim |
| android.permission.ALLOW_ANY_CODEC_FOR_PLAYBACK | signature\|privileged |  |  | sim |
| android.permission.ALLOW_PLACE_IN_MULTI_PANE_SETTINGS | signature |  |  | sim |
| android.permission.ALLOW_SLIPPERY_TOUCHES | signature\|privileged\|recents\|role |  |  | sim |
| android.permission.ALWAYS_BOUND_TV_INPUT | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.ALWAYS_UPDATE_WALLPAPER | internal\|role |  |  | sim |
| android.permission.AMBIENT_WALLPAPER | signature\|preinstalled |  |  | sim |
| android.permission.ANSWER_PHONE_CALLS | dangerous\|runtime | PHONE |  | nao |
| android.permission.APPLY_PICTURE_PROFILE | normal |  |  | nao |
| android.permission.APPROVE_INCIDENT_REPORTS | signature\|incidentReportApprover |  |  | sim |
| android.permission.ASEC_ACCESS | signature |  |  | sim |
| android.permission.ASEC_CREATE | signature |  |  | sim |
| android.permission.ASEC_DESTROY | signature |  |  | sim |
| android.permission.ASEC_MOUNT_UNMOUNT | signature |  |  | sim |
| android.permission.ASEC_RENAME | signature |  |  | sim |
| android.permission.ASSOCIATE_COMPANION_DEVICES | internal\|role |  |  | sim |
| android.permission.ASSOCIATE_INPUT_DEVICE_TO_DISPLAY | signature |  |  | sim |
| android.permission.AUTHENTICATE_ACCOUNTS | normal |  |  | sim |
| android.permission.BACKGROUND_CAMERA | internal\|role |  |  | sim |
| android.permission.BACKUP | signature\|privileged |  |  | sim |
| android.permission.BACKUP_HEALTH_CONNECT_DATA_AND_SETTINGS | signature\|knownSigner |  |  | sim |
| android.permission.BATTERY_PREDICTION | signature\|privileged |  |  | sim |
| android.permission.BATTERY_STATS | signature\|privileged\|development |  |  | nao |
| android.permission.BIND_ACCESSIBILITY_SERVICE | signature |  |  | nao |
| android.permission.BIND_AMBIENT_CONTEXT_DETECTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_APPWIDGET | signature\|privileged |  |  | nao |
| android.permission.BIND_APP_FUNCTION_SERVICE | signature |  |  | nao |
| android.permission.BIND_ATTENTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_ATTESTATION_VERIFICATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_AUGMENTED_AUTOFILL_SERVICE | signature |  |  | sim |
| android.permission.BIND_AUTOFILL | signature |  |  | sim |
| android.permission.BIND_AUTOFILL_FIELD_CLASSIFICATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_AUTOFILL_SERVICE | signature |  |  | nao |
| android.permission.BIND_CACHE_QUOTA_SERVICE | signature |  |  | sim |
| android.permission.BIND_CALL_DIAGNOSTIC_SERVICE | signature |  |  | sim |
| android.permission.BIND_CALL_REDIRECTION_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_CALL_STREAMING_SERVICE | signature |  |  | sim |
| android.permission.BIND_CARRIER_MESSAGING_CLIENT_SERVICE | signature |  |  | nao |
| android.permission.BIND_CARRIER_MESSAGING_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_CARRIER_SERVICES | signature\|privileged |  |  | nao |
| android.permission.BIND_CELL_BROADCAST_SERVICE | signature |  |  | sim |
| android.permission.BIND_CHOOSER_TARGET_SERVICE | signature |  |  | nao |
| android.permission.BIND_COMPANION_DEVICE_MANAGER_SERVICE | signature |  |  | sim |
| android.permission.BIND_COMPANION_DEVICE_SERVICE | signature |  |  | nao |
| android.permission.BIND_CONDITION_PROVIDER_SERVICE | signature |  |  | nao |
| android.permission.BIND_CONNECTION_SERVICE | signature\|privileged |  |  | sim |
| android.permission.BIND_CONTENT_CAPTURE_SERVICE | signature |  |  | sim |
| android.permission.BIND_CONTENT_SUGGESTIONS_SERVICE | signature |  |  | sim |
| android.permission.BIND_CONTROLS | signature |  |  | nao |
| android.permission.BIND_CREDENTIAL_PROVIDER_SERVICE | signature |  |  | nao |
| android.permission.BIND_DEPENDENCY_INSTALLER | signature |  |  | sim |
| android.permission.BIND_DEVICE_ADMIN | signature\|role |  |  | nao |
| android.permission.BIND_DIRECTORY_SEARCH | signature\|privileged |  |  | sim |
| android.permission.BIND_DISPLAY_HASHING_SERVICE | signature |  |  | sim |
| android.permission.BIND_DOMAIN_SELECTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_DOMAIN_VERIFICATION_AGENT | signature |  |  | sim |
| android.permission.BIND_DREAM_SERVICE | signature |  |  | nao |
| android.permission.BIND_EUICC_SERVICE | signature |  |  | sim |
| android.permission.BIND_EXPLICIT_HEALTH_CHECK_SERVICE | signature\|privileged |  |  | sim |
| android.permission.BIND_EXTERNAL_STORAGE_SERVICE | signature |  |  | sim |
| android.permission.BIND_FIELD_CLASSIFICATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_GAME_SERVICE | signature |  |  | sim |
| android.permission.BIND_GBA_SERVICE | signature |  |  | sim |
| android.permission.BIND_HOTWORD_DETECTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_IMS_SERVICE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.BIND_INCALL_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_INLINE_SUGGESTION_RENDER_SERVICE | signature |  |  | sim |
| android.permission.BIND_INPUT_METHOD | signature |  |  | nao |
| android.permission.BIND_INTENT_FILTER_VERIFIER | signature |  |  | sim |
| android.permission.BIND_INTRUSION_DETECTION_EVENT_TRANSPORT_SERVICE | signature |  |  | sim |
| android.permission.BIND_JOB_SERVICE | signature |  |  | sim |
| android.permission.BIND_KEYGUARD_APPWIDGET | signature\|privileged |  |  | sim |
| android.permission.BIND_MIDI_DEVICE_SERVICE | signature |  |  | nao |
| android.permission.BIND_MUSIC_RECOGNITION_SERVICE | signature |  |  | sim |
| android.permission.BIND_NETWORK_RECOMMENDATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_NFC_SERVICE | signature\|module |  |  | nao |
| android.permission.BIND_NOTIFICATION_ASSISTANT_SERVICE | signature |  |  | sim |
| android.permission.BIND_NOTIFICATION_LISTENER_SERVICE | signature |  |  | nao |
| android.permission.BIND_ON_DEVICE_INTELLIGENCE_SERVICE | signature\|privileged |  |  | sim |
| android.permission.BIND_ON_DEVICE_SANDBOXED_INFERENCE_SERVICE | signature |  |  | sim |
| android.permission.BIND_PACKAGE_VERIFIER | signature |  |  | sim |
| android.permission.BIND_PHONE_ACCOUNT_SUGGESTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_POPULATION_DENSITY_PROVIDER_SERVICE | signature |  |  | sim |
| android.permission.BIND_PRINT_RECOMMENDATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_PRINT_SERVICE | signature |  |  | nao |
| android.permission.BIND_PRINT_SPOOLER_SERVICE | signature |  |  | sim |
| android.permission.BIND_QUICK_ACCESS_WALLET_SERVICE | signature |  |  | nao |
| android.permission.BIND_QUICK_SETTINGS_TILE | signature\|recents |  |  | nao |
| android.permission.BIND_REMOTEVIEWS | signature\|privileged |  |  | nao |
| android.permission.BIND_REMOTE_DISPLAY | signature |  |  | sim |
| android.permission.BIND_REMOTE_LOCKSCREEN_VALIDATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_RESOLVER_RANKER_SERVICE | signature |  |  | sim |
| android.permission.BIND_RESUME_ON_REBOOT_SERVICE | signature |  |  | sim |
| android.permission.BIND_RKP_SERVICE | signature |  |  | sim |
| android.permission.BIND_ROTATION_RESOLVER_SERVICE | signature |  |  | sim |
| android.permission.BIND_ROUTE_PROVIDER | signature |  |  | sim |
| android.permission.BIND_RUNTIME_PERMISSION_PRESENTER_SERVICE | signature |  |  | sim |
| android.permission.BIND_SATELLITE_GATEWAY_SERVICE | signature |  |  | sim |
| android.permission.BIND_SATELLITE_SERVICE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.BIND_SCREENING_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_SELECTION_TOOLBAR_RENDER_SERVICE | signature |  |  | sim |
| android.permission.BIND_SETTINGS_SUGGESTIONS_SERVICE | signature |  |  | sim |
| android.permission.BIND_SOUND_TRIGGER_DETECTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_TELECOM_CONNECTION_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_TELEPHONY_DATA_SERVICE | signature |  |  | sim |
| android.permission.BIND_TELEPHONY_NETWORK_SERVICE | signature |  |  | sim |
| android.permission.BIND_TEXTCLASSIFIER_SERVICE | signature |  |  | sim |
| android.permission.BIND_TEXT_SERVICE | signature |  |  | nao |
| android.permission.BIND_TIME_ZONE_PROVIDER_SERVICE | signature |  |  | sim |
| android.permission.BIND_TRACE_REPORT_SERVICE | signature |  |  | sim |
| android.permission.BIND_TRANSLATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_TRUST_AGENT | signature |  |  | sim |
| android.permission.BIND_TV_AD_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_TV_INPUT | signature\|privileged |  |  | nao |
| android.permission.BIND_TV_INTERACTIVE_APP | signature\|privileged |  |  | nao |
| android.permission.BIND_TV_REMOTE_SERVICE | signature\|privileged |  |  | sim |
| android.permission.BIND_VISUAL_QUERY_DETECTION_SERVICE | signature |  |  | sim |
| android.permission.BIND_VISUAL_VOICEMAIL_SERVICE | signature\|privileged |  |  | nao |
| android.permission.BIND_VOICE_INTERACTION | signature |  |  | nao |
| android.permission.BIND_VPN_SERVICE | signature |  |  | nao |
| android.permission.BIND_VR_LISTENER_SERVICE | signature |  |  | nao |
| android.permission.BIND_WALLPAPER | signature\|privileged |  |  | nao |
| android.permission.BIND_WALLPAPER_EFFECTS_GENERATION_SERVICE | signature |  |  | sim |
| android.permission.BIND_WEARABLE_SENSING_SERVICE | signature |  |  | sim |
| android.permission.BLUETOOTH | normal |  | 30 | nao |
| android.permission.BLUETOOTH_ADMIN | normal |  | 30 | nao |
| android.permission.BLUETOOTH_ADVERTISE | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.BLUETOOTH_CONNECT | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.BLUETOOTH_MAP | signature\|role |  |  | sim |
| android.permission.BLUETOOTH_PRIVILEGED | signature\|privileged |  |  | nao |
| android.permission.BLUETOOTH_SCAN | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.BLUETOOTH_STACK | signature\|role |  |  | sim |
| android.permission.BODY_SENSORS | dangerous | SENSORS |  | nao |
| android.permission.BODY_SENSORS_BACKGROUND | dangerous | SENSORS |  | nao |
| android.permission.BRICK | signature |  |  | sim |
| android.permission.BRIGHTNESS_SLIDER_USAGE | signature\|privileged\|development |  |  | sim |
| android.permission.BROADCAST_CLOSE_SYSTEM_DIALOGS | signature\|privileged\|recents |  |  | sim |
| android.permission.BROADCAST_NETWORK_PRIVILEGED | signature\|privileged |  |  | sim |
| android.permission.BROADCAST_OPTION_INTERACTIVE | signature\|privileged |  |  | sim |
| android.permission.BROADCAST_PACKAGE_REMOVED | signature |  |  | nao |
| android.permission.BROADCAST_SMS | signature |  |  | nao |
| android.permission.BROADCAST_STICKY | normal |  |  | nao |
| android.permission.BROADCAST_WAP_PUSH | signature |  |  | nao |
| android.permission.BYPASS_CONCURRENT_RECORD_AUDIO_RESTRICTION | signature\|privileged |  |  | sim |
| android.permission.BYPASS_ROLE_QUALIFICATION | internal\|role |  |  | sim |
| android.permission.CACHE_CONTENT | signature\|role |  |  | sim |
| android.permission.CALL_AUDIO_INTERCEPTION | signature\|privileged\|role |  |  | sim |
| android.permission.CALL_COMPANION_APP | normal |  |  | nao |
| android.permission.CALL_PHONE | dangerous | PHONE |  | nao |
| android.permission.CALL_PRIVILEGED | signature\|privileged |  |  | nao |
| android.permission.CAMERA | dangerous\|instant | CAMERA |  | nao |
| android.permission.CAMERA_DISABLE_TRANSMIT_LED | signature\|privileged |  |  | sim |
| android.permission.CAMERA_HEADLESS_SYSTEM_USER | signature |  |  | sim |
| android.permission.CAMERA_INJECT_EXTERNAL_CAMERA | signature |  |  | sim |
| android.permission.CAMERA_OPEN_CLOSE_LISTENER | signature |  |  | sim |
| android.permission.CAMERA_PRIVACY_ALLOWLIST | signature\|privileged |  |  | sim |
| android.permission.CAMERA_SEND_SYSTEM_EVENTS | signature\|privileged |  |  | sim |
| android.permission.CAPTURE_AUDIO_HOTWORD | signature\|privileged\|role |  |  | sim |
| android.permission.CAPTURE_AUDIO_OUTPUT | signature\|privileged\|role |  |  | nao |
| android.permission.CAPTURE_BLACKOUT_CONTENT | signature |  |  | sim |
| android.permission.CAPTURE_CONSENTLESS_BUGREPORT_DELEGATED_CONSENT | signature\|privileged |  |  | sim |
| android.permission.CAPTURE_CONSENTLESS_BUGREPORT_ON_USERDEBUG_BUILD | internal\|appop |  |  | sim |
| android.permission.CAPTURE_MEDIA_OUTPUT | signature\|privileged\|role |  |  | sim |
| android.permission.CAPTURE_SECURE_VIDEO_OUTPUT | signature\|role |  |  | sim |
| android.permission.CAPTURE_TUNER_AUDIO_INPUT | signature\|privileged |  |  | sim |
| android.permission.CAPTURE_TV_INPUT | signature\|privileged |  |  | sim |
| android.permission.CAPTURE_VIDEO_OUTPUT | signature |  |  | sim |
| android.permission.CAPTURE_VOICE_COMMUNICATION_OUTPUT | signature\|privileged\|role |  |  | sim |
| android.permission.CARRIER_FILTER_SMS | signature\|privileged |  |  | sim |
| android.permission.CHANGE_ACCESSIBILITY_VOLUME | signature |  |  | sim |
| android.permission.CHANGE_APP_IDLE_STATE | signature\|privileged |  |  | sim |
| android.permission.CHANGE_APP_LAUNCH_TIME_ESTIMATE | signature\|privileged |  |  | sim |
| android.permission.CHANGE_BACKGROUND_DATA_SETTING | signature |  |  | sim |
| android.permission.CHANGE_COMPONENT_ENABLED_STATE | signature\|privileged\|role |  |  | nao |
| android.permission.CHANGE_CONFIGURATION | signature\|privileged\|development\|role |  |  | nao |
| android.permission.CHANGE_DEVICE_IDLE_TEMP_WHITELIST | signature\|privileged |  |  | sim |
| android.permission.CHANGE_HDMI_CEC_ACTIVE_SOURCE | signature\|privileged |  |  | sim |
| android.permission.CHANGE_LOWPAN_STATE | signature\|privileged |  |  | sim |
| android.permission.CHANGE_NETWORK_STATE | normal |  |  | nao |
| android.permission.CHANGE_OVERLAY_PACKAGES | signature\|privileged |  |  | sim |
| android.permission.CHANGE_WIFI_MULTICAST_STATE | normal |  |  | nao |
| android.permission.CHANGE_WIFI_STATE | normal |  |  | nao |
| android.permission.CHECK_REMOTE_LOCKSCREEN | signature\|privileged |  |  | sim |
| android.permission.CLEAR_APP_CACHE | signature\|privileged |  |  | nao |
| android.permission.CLEAR_APP_GRANTED_URI_PERMISSIONS | signature |  |  | sim |
| android.permission.CLEAR_APP_USER_DATA | signature\|installer |  |  | sim |
| android.permission.CLEAR_FREEZE_PERIOD | signature |  |  | sim |
| android.permission.COMPANION_APPROVE_WIFI_CONNECTIONS | signature\|privileged |  |  | sim |
| android.permission.CONFIGURE_DISPLAY_BRIGHTNESS | signature\|privileged\|development |  |  | sim |
| android.permission.CONFIGURE_DISPLAY_COLOR_MODE | signature |  |  | sim |
| android.permission.CONFIGURE_FACTORY_RESET_PROTECTION | signature\|privileged |  |  | sim |
| android.permission.CONFIGURE_INTERACT_ACROSS_PROFILES | signature\|role |  |  | sim |
| android.permission.CONFIGURE_WIFI_DISPLAY | signature\|knownSigner |  |  | nao |
| android.permission.CONFIRM_FULL_BACKUP | signature |  |  | sim |
| android.permission.CONNECTIVITY_INTERNAL | signature\|privileged |  |  | sim |
| android.permission.CONNECTIVITY_USE_RESTRICTED_NETWORKS | signature\|privileged |  |  | sim |
| android.permission.CONTROL_ALWAYS_ON_VPN | signature |  |  | sim |
| android.permission.CONTROL_AUTOMOTIVE_GNSS | signature\|privileged |  |  | sim |
| android.permission.CONTROL_DEVICE_LIGHTS | signature\|privileged |  |  | sim |
| android.permission.CONTROL_DEVICE_STATE | signature |  |  | sim |
| android.permission.CONTROL_DISPLAY_BRIGHTNESS | signature |  |  | sim |
| android.permission.CONTROL_DISPLAY_COLOR_TRANSFORMS | signature\|privileged |  |  | sim |
| android.permission.CONTROL_DISPLAY_SATURATION | signature\|privileged |  |  | sim |
| android.permission.CONTROL_INCALL_EXPERIENCE | signature\|privileged\|role |  |  | sim |
| android.permission.CONTROL_KEYGUARD | signature |  |  | sim |
| android.permission.CONTROL_KEYGUARD_SECURE_NOTIFICATIONS | signature\|privileged |  |  | sim |
| android.permission.CONTROL_LOCATION_UPDATES | signature\|privileged |  |  | nao |
| android.permission.CONTROL_OEM_PAID_NETWORK_PREFERENCE | signature |  |  | sim |
| android.permission.CONTROL_REMOTE_APP_TRANSITION_ANIMATIONS | signature\|privileged\|recents |  |  | sim |
| android.permission.CONTROL_UI_TRACING | signature\|privileged\|development |  |  | sim |
| android.permission.CONTROL_VPN | signature\|privileged |  |  | sim |
| android.permission.CONTROL_WIFI_DISPLAY | signature |  |  | sim |
| android.permission.COPY_ACCOUNTS | signature\|role |  |  | sim |
| android.permission.COPY_PROTECTED_DATA | signature |  |  | sim |
| android.permission.CREATE_USERS | signature |  |  | sim |
| android.permission.CREATE_VIRTUAL_DEVICE | internal\|role |  |  | sim |
| android.permission.CREDENTIAL_MANAGER_QUERY_CANDIDATE_CREDENTIALS | normal |  |  | nao |
| android.permission.CREDENTIAL_MANAGER_SET_ALLOWED_PROVIDERS | normal |  |  | nao |
| android.permission.CREDENTIAL_MANAGER_SET_ORIGIN | normal |  |  | nao |
| android.permission.CRYPT_KEEPER | signature\|privileged\|role |  |  | sim |
| android.permission.DELETE_CACHE_FILES | signature\|privileged |  |  | nao |
| android.permission.DELETE_PACKAGES | signature\|privileged\|role |  |  | nao |
| android.permission.DELETE_STAGED_HEALTH_CONNECT_REMOTE_DATA | signature |  |  | sim |
| android.permission.DELIVER_COMPANION_MESSAGES | normal |  |  | nao |
| android.permission.DETECT_SCREEN_CAPTURE | normal |  |  | nao |
| android.permission.DETECT_SCREEN_RECORDING | normal |  |  | nao |
| android.permission.DEVICE_POWER | signature\|role |  |  | sim |
| android.permission.DIAGNOSTIC | signature |  |  | nao |
| android.permission.DISABLE_HIDDEN_API_CHECKS | signature |  |  | sim |
| android.permission.DISABLE_INPUT_DEVICE | signature |  |  | sim |
| android.permission.DISABLE_KEYGUARD | normal |  |  | nao |
| android.permission.DISABLE_SYSTEM_SOUND_EFFECTS | signature\|privileged |  |  | sim |
| android.permission.DISPATCH_NFC_MESSAGE | signature\|privileged |  |  | sim |
| android.permission.DISPATCH_PROVISIONING_MESSAGE | signature\|privileged |  |  | sim |
| android.permission.DOMAIN_VERIFICATION_AGENT | internal\|privileged |  |  | sim |
| android.permission.DUMP | signature\|privileged\|development |  |  | nao |
| android.permission.DVB_DEVICE | signature\|privileged |  |  | sim |
| android.permission.DYNAMIC_INSTRUMENTATION | signature |  |  | sim |
| android.permission.EMBED_ANY_APP_IN_UNTRUSTED_MODE | internal\|role |  |  | sim |
| android.permission.EMERGENCY_INSTALL_PACKAGES | signature\|privileged |  |  | sim |
| android.permission.ENABLE_TEST_HARNESS_MODE | signature |  |  | sim |
| android.permission.ENFORCE_UPDATE_OWNERSHIP | normal |  |  | nao |
| android.permission.ENTER_CAR_MODE_PRIORITIZED | signature\|privileged |  |  | sim |
| android.permission.ENTER_TRADE_IN_MODE | signature\|privileged |  |  | sim |
| android.permission.EXECUTE_APP_ACTION | internal\|role |  |  | nao |
| android.permission.EXECUTE_APP_FUNCTIONS | internal\|role |  |  | sim |
| android.permission.EXECUTE_APP_FUNCTIONS_TRUSTED | internal\|role |  |  | sim |
| android.permission.EXEMPT_FROM_AUDIO_RECORD_RESTRICTIONS | signature\|privileged\|role |  |  | sim |
| android.permission.EXPAND_STATUS_BAR | normal |  |  | nao |
| android.permission.FACTORY_TEST | signature |  |  | nao |
| android.permission.FILTER_EVENTS | signature |  |  | sim |
| android.permission.FLASHLIGHT | normal |  |  | sim |
| android.permission.FORCE_BACK | signature |  |  | sim |
| android.permission.FORCE_DEVICE_POLICY_MANAGER_LOGS | signature |  |  | sim |
| android.permission.FORCE_PERSISTABLE_URI_PERMISSIONS | signature |  |  | sim |
| android.permission.FORCE_STOP_PACKAGES | signature\|privileged |  |  | sim |
| android.permission.FOREGROUND_SERVICE | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_CAMERA | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_DATA_SYNC | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_FILE_MANAGEMENT | normal\|instant |  |  | sim |
| android.permission.FOREGROUND_SERVICE_HEALTH | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_LOCATION | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_MEDIA_PROCESSING | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_MICROPHONE | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_PHONE_CALL | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_REMOTE_MESSAGING | normal\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_SPECIAL_USE | normal\|appop\|instant |  |  | nao |
| android.permission.FOREGROUND_SERVICE_SYSTEM_EXEMPTED | normal\|instant |  |  | nao |
| android.permission.FRAME_STATS | signature |  |  | sim |
| android.permission.FREEZE_SCREEN | signature |  |  | sim |
| android.permission.GET_ACCOUNTS | dangerous | CONTACTS |  | nao |
| android.permission.GET_ACCOUNTS_PRIVILEGED | signature\|privileged |  |  | nao |
| android.permission.GET_ANY_PROVIDER_TYPE | signature |  |  | sim |
| android.permission.GET_APP_GRANTED_URI_PERMISSIONS | signature |  |  | sim |
| android.permission.GET_APP_METADATA | signature\|installer\|verifier |  |  | sim |
| android.permission.GET_APP_OPS_STATS | signature\|privileged\|development |  |  | sim |
| android.permission.GET_BACKGROUND_INSTALLED_PACKAGES | signature\|role |  |  | sim |
| android.permission.GET_BINDING_UID_IMPORTANCE | signature\|privileged |  |  | sim |
| android.permission.GET_DETAILED_TASKS | signature |  |  | sim |
| android.permission.GET_HISTORICAL_APP_OPS_STATS | internal\|role |  |  | sim |
| android.permission.GET_INTENT_SENDER_INTENT | signature |  |  | sim |
| android.permission.GET_PACKAGE_SIZE | normal |  |  | nao |
| android.permission.GET_PASSWORD | signature |  |  | sim |
| android.permission.GET_PEOPLE_TILE_PREVIEW | signature\|recents |  |  | sim |
| android.permission.GET_PROCESS_STATE_AND_OOM_SCORE | signature\|privileged\|development |  |  | sim |
| android.permission.GET_RUNTIME_PERMISSIONS | signature |  |  | sim |
| android.permission.GET_TASKS | normal |  | 21 | nao |
| android.permission.GET_TOP_ACTIVITY_INFO | signature\|recents |  |  | sim |
| android.permission.GLOBAL_SEARCH | signature\|privileged |  |  | nao |
| android.permission.GLOBAL_SEARCH_CONTROL | signature |  |  | sim |
| android.permission.GRANT_PROFILE_OWNER_DEVICE_IDS_ACCESS | signature |  |  | sim |
| android.permission.GRANT_RUNTIME_PERMISSIONS | signature\|installer\|verifier |  |  | sim |
| android.permission.GRANT_RUNTIME_PERMISSIONS_TO_TELEPHONY_DEFAULTS | signature |  |  | sim |
| android.permission.HANDLE_CAR_MODE_CHANGES | signature\|privileged |  |  | sim |
| android.permission.HANDLE_QUERY_PACKAGE_RESTART | signature |  |  | sim |
| android.permission.HARDWARE_TEST | signature |  |  | sim |
| android.permission.HDMI_CEC | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.HIDE_NON_SYSTEM_OVERLAY_WINDOWS | signature\|preinstalled |  |  | sim |
| android.permission.HIDE_OVERLAY_WINDOWS | normal |  |  | nao |
| android.permission.HIGH_SAMPLING_RATE_SENSORS | normal |  |  | nao |
| android.permission.INJECT_EVENTS | signature |  |  | sim |
| android.permission.INPUT_CONSUMER | signature |  |  | sim |
| android.permission.INSTALL_DEPENDENCY_SHARED_LIBRARIES | signature\|role |  |  | sim |
| android.permission.INSTALL_DPC_PACKAGES | signature\|role |  |  | sim |
| android.permission.INSTALL_DYNAMIC_SYSTEM | signature\|privileged |  |  | sim |
| android.permission.INSTALL_GRANT_RUNTIME_PERMISSIONS | signature\|installer\|verifier |  |  | sim |
| android.permission.INSTALL_LOCATION_PROVIDER | signature\|privileged |  |  | nao |
| android.permission.INSTALL_LOCATION_TIME_ZONE_PROVIDER_SERVICE | signature\|privileged |  |  | sim |
| android.permission.INSTALL_PACKAGES | signature\|privileged |  |  | nao |
| android.permission.INSTALL_PACKAGE_UPDATES | signature\|privileged |  |  | sim |
| android.permission.INSTALL_SELF_UPDATES | signature\|privileged |  |  | sim |
| android.permission.INSTALL_TEST_ONLY_PACKAGE | signature |  |  | sim |
| android.permission.INSTANT_APP_FOREGROUND_SERVICE | signature\|development\|instant\|appop |  |  | nao |
| android.permission.INTENT_FILTER_VERIFICATION_AGENT | signature\|privileged |  |  | sim |
| android.permission.INTERACT_ACROSS_PROFILES | signature\|appop |  |  | nao |
| android.permission.INTERACT_ACROSS_USERS | signature\|privileged\|development\|role |  |  | sim |
| android.permission.INTERACT_ACROSS_USERS_FULL | signature\|installer\|module\|role |  |  | sim |
| android.permission.INTERNAL_DELETE_CACHE_FILES | signature |  |  | sim |
| android.permission.INTERNAL_RECEIVE_PACKAGE_CHANGED_BROADCAST_ON_COMPONENT_STATE_CHANGED | internal |  |  | sim |
| android.permission.INTERNAL_SYSTEM_WINDOW | signature\|module\|recents |  |  | sim |
| android.permission.INTERNET | normal\|instant |  |  | nao |
| android.permission.INVOKE_CARRIER_SETUP | signature\|privileged |  |  | sim |
| android.permission.KEEP_UNINSTALLED_PACKAGES | signature |  |  | sim |
| android.permission.KEYPHRASE_ENROLLMENT_APPLICATION | signature\|privileged |  |  | sim |
| android.permission.KILL_ALL_BACKGROUND_PROCESSES | signature\|privileged |  |  | sim |
| android.permission.KILL_BACKGROUND_PROCESSES | normal |  |  | nao |
| android.permission.KILL_UID | signature\|installer\|role |  |  | sim |
| android.permission.LAUNCH_CAPTURE_CONTENT_ACTIVITY_FOR_NOTE | internal\|role |  |  | nao |
| android.permission.LAUNCH_CREDENTIAL_SELECTOR | signature |  |  | sim |
| android.permission.LAUNCH_DEVICE_MANAGER_SETUP | signature\|role |  |  | sim |
| android.permission.LAUNCH_MULTI_PANE_SETTINGS_DEEP_LINK | signature\|preinstalled |  |  | nao |
| android.permission.LAUNCH_PERMISSION_SETTINGS | signature\|privileged |  |  | sim |
| android.permission.LAUNCH_TRUST_AGENT_SETTINGS | signature\|privileged |  |  | sim |
| android.permission.LISTEN_ALWAYS_REPORTED_SIGNAL_STRENGTH | signature\|role |  |  | sim |
| android.permission.LIST_ENABLED_CREDENTIAL_PROVIDERS | signature\|privileged |  |  | sim |
| android.permission.LOADER_USAGE_STATS | signature\|privileged\|appop |  |  | nao |
| android.permission.LOCAL_MAC_ADDRESS | signature\|privileged |  |  | sim |
| android.permission.LOCATION_BYPASS | signature\|privileged |  |  | sim |
| android.permission.LOCATION_HARDWARE | signature\|privileged\|role |  |  | nao |
| android.permission.LOCK_DEVICE | signature\|privileged |  |  | sim |
| android.permission.LOG_COMPAT_CHANGE | signature\|privileged |  |  | sim |
| android.permission.LOG_FOREGROUND_RESOURCE_USE | signature\|module |  |  | sim |
| android.permission.LOOP_RADIO | signature\|privileged |  |  | sim |
| android.permission.MAKE_UID_VISIBLE | signature |  |  | sim |
| android.permission.MANAGE_ACCESSIBILITY | signature\|setup\|recents\|role |  |  | sim |
| android.permission.MANAGE_ACCOUNTS | normal |  |  | sim |
| android.permission.MANAGE_ACTIVITY_STACKS | signature |  |  | sim |
| android.permission.MANAGE_ACTIVITY_TASKS | signature\|recents |  |  | sim |
| android.permission.MANAGE_ADVANCED_PROTECTION_MODE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_APPOPS | signature |  |  | sim |
| android.permission.MANAGE_APP_HIBERNATION | signature\|installer |  |  | sim |
| android.permission.MANAGE_APP_OPS_MODES | signature\|installer\|verifier\|role |  |  | sim |
| android.permission.MANAGE_APP_OPS_RESTRICTIONS | signature\|installer |  |  | sim |
| android.permission.MANAGE_APP_PREDICTIONS | signature\|role |  |  | sim |
| android.permission.MANAGE_APP_TOKENS | signature |  |  | sim |
| android.permission.MANAGE_AUDIO_POLICY | signature |  |  | sim |
| android.permission.MANAGE_AUTO_FILL | signature |  |  | sim |
| android.permission.MANAGE_BIND_INSTANT_SERVICE | signature |  |  | sim |
| android.permission.MANAGE_BIOMETRIC | signature |  |  | sim |
| android.permission.MANAGE_BIOMETRIC_DIALOG | signature |  |  | sim |
| android.permission.MANAGE_BLUETOOTH_WHEN_WIRELESS_CONSENT_REQUIRED | signature |  |  | sim |
| android.permission.MANAGE_CAMERA | signature |  |  | sim |
| android.permission.MANAGE_CARRIER_OEM_UNLOCK_STATE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_CA_CERTIFICATES | signature\|privileged |  |  | sim |
| android.permission.MANAGE_CLIPBOARD_ACCESS_NOTIFICATION | signature\|installer |  |  | sim |
| android.permission.MANAGE_CLOUDSEARCH | signature\|privileged\|role |  |  | sim |
| android.permission.MANAGE_COMPANION_DEVICES | module\|signature\|role |  |  | sim |
| android.permission.MANAGE_CONTENT_CAPTURE | signature |  |  | sim |
| android.permission.MANAGE_CONTENT_SUGGESTIONS | signature\|role |  |  | sim |
| android.permission.MANAGE_CRATES | signature |  |  | sim |
| android.permission.MANAGE_CREDENTIAL_MANAGEMENT_APP | signature |  |  | sim |
| android.permission.MANAGE_DEBUGGING | signature\|privileged |  |  | sim |
| android.permission.MANAGE_DEFAULT_APPLICATIONS | signature\|role |  |  | sim |
| android.permission.MANAGE_DEVICE_ADMINS | signature\|role |  |  | sim |
| android.permission.MANAGE_DEVICE_LOCK_STATE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ACCESSIBILITY | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ACCOUNT_MANAGEMENT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ACROSS_USERS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ACROSS_USERS_FULL | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ACROSS_USERS_SECURITY_CRITICAL | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_AIRPLANE_MODE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_APPS_CONTROL | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_APP_EXEMPTIONS | internal\|role |  |  | sim |
| android.permission.MANAGE_DEVICE_POLICY_APP_FUNCTIONS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_APP_RESTRICTIONS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_APP_USER_DATA | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ASSIST_CONTENT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_AUDIO_OUTPUT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_AUDIT_LOGGING | internal\|role |  |  | sim |
| android.permission.MANAGE_DEVICE_POLICY_AUTOFILL | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_BACKUP_SERVICE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_BLOCK_UNINSTALL | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_BLUETOOTH | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_BUGREPORT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_CALLS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_CAMERA | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_CAMERA_TOGGLE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_CERTIFICATES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_COMMON_CRITERIA_MODE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_CONTENT_PROTECTION | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_DEBUGGING_FEATURES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_DEFAULT_SMS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_DEVICE_IDENTIFIERS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_DISPLAY | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_FACTORY_RESET | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_FUN | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_INPUT_METHODS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_INSTALL_UNKNOWN_SOURCES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_KEEP_UNINSTALLED_PACKAGES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_KEYGUARD | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_LOCALE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_LOCATION | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_LOCK | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_LOCK_CREDENTIALS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_LOCK_TASK | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MANAGED_SUBSCRIPTIONS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_METERED_DATA | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MICROPHONE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MICROPHONE_TOGGLE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MOBILE_NETWORK | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MODIFY_USERS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_MTE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_NEARBY_COMMUNICATION | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_NETWORK_LOGGING | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_ORGANIZATION_IDENTITY | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_OVERRIDE_APN | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PACKAGE_STATE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PHYSICAL_MEDIA | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PRINTING | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PRIVATE_DNS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PROFILES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PROFILE_INTERACTION | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_PROXY | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_QUERY_SYSTEM_UPDATES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_RESET_PASSWORD | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_RESTRICT_PRIVATE_DNS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_RUNTIME_PERMISSIONS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_RUN_IN_BACKGROUND | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SAFE_BOOT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SCREEN_CAPTURE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SCREEN_CONTENT | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SECURITY_LOGGING | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SETTINGS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SMS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_STATUS_BAR | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_STORAGE_LIMIT | internal |  |  | sim |
| android.permission.MANAGE_DEVICE_POLICY_SUPPORT_MESSAGE | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SUSPEND_PERSONAL_APPS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SYSTEM_APPS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SYSTEM_DIALOGS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_SYSTEM_UPDATES | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_THREAD_NETWORK | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_TIME | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_USB_DATA_SIGNALLING | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_USB_FILE_TRANSFER | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_USERS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_VPN | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_WALLPAPER | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_WIFI | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_WINDOWS | internal\|role |  |  | nao |
| android.permission.MANAGE_DEVICE_POLICY_WIPE_DATA | internal\|role |  |  | nao |
| android.permission.MANAGE_DISPLAYS | signature |  |  | sim |
| android.permission.MANAGE_DOCUMENTS | signature\|role |  |  | nao |
| android.permission.MANAGE_DYNAMIC_SYSTEM | signature |  |  | sim |
| android.permission.MANAGE_ENHANCED_CONFIRMATION_STATES | signature\|installer |  |  | sim |
| android.permission.MANAGE_ETHERNET_NETWORKS | signature |  |  | sim |
| android.permission.MANAGE_EXTERNAL_STORAGE | signature\|appop\|preinstalled |  |  | nao |
| android.permission.MANAGE_FACE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_FACTORY_RESET_PROTECTION | signature\|privileged |  |  | sim |
| android.permission.MANAGE_FINGERPRINT | signature\|privileged |  |  | sim |
| android.permission.MANAGE_GAME_ACTIVITY | signature\|privileged |  |  | sim |
| android.permission.MANAGE_GAME_MODE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_GLOBAL_PICTURE_QUALITY_SERVICE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.MANAGE_GLOBAL_SOUND_QUALITY_SERVICE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.MANAGE_HOTWORD_DETECTION | internal\|preinstalled |  |  | sim |
| android.permission.MANAGE_INTRUSION_DETECTION_STATE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_IPSEC_TUNNELS | signature\|appop |  |  | sim |
| android.permission.MANAGE_KEY_GESTURES | signature |  |  | sim |
| android.permission.MANAGE_LOWPAN_INTERFACES | signature\|privileged |  |  | sim |
| android.permission.MANAGE_LOW_POWER_STANDBY | signature\|privileged |  |  | sim |
| android.permission.MANAGE_MEDIA | signature\|appop\|preinstalled |  |  | nao |
| android.permission.MANAGE_MEDIA_PROJECTION | signature |  |  | sim |
| android.permission.MANAGE_MUSIC_RECOGNITION | signature\|privileged\|role |  |  | sim |
| android.permission.MANAGE_NETWORK_POLICY | signature |  |  | sim |
| android.permission.MANAGE_NOTIFICATIONS | signature |  |  | sim |
| android.permission.MANAGE_NOTIFICATION_LISTENERS | signature\|installer |  |  | sim |
| android.permission.MANAGE_ONE_TIME_PERMISSION_SESSIONS | signature\|installer |  |  | sim |
| android.permission.MANAGE_ONGOING_CALLS | signature\|appop |  |  | nao |
| android.permission.MANAGE_OWN_CALLS | normal |  |  | nao |
| android.permission.MANAGE_PROFILE_AND_DEVICE_OWNERS | signature\|role |  |  | sim |
| android.permission.MANAGE_REMOTE_AUTH | signature |  |  | sim |
| android.permission.MANAGE_ROLE_HOLDERS | signature\|installer\|module |  |  | sim |
| android.permission.MANAGE_ROLLBACKS | signature\|privileged |  |  | sim |
| android.permission.MANAGE_ROTATION_RESOLVER | signature |  |  | sim |
| android.permission.MANAGE_SAFETY_CENTER | internal\|installer\|role |  |  | sim |
| android.permission.MANAGE_SCOPED_ACCESS_DIRECTORY_PERMISSIONS | signature |  |  | sim |
| android.permission.MANAGE_SEARCH_UI | signature\|role |  |  | sim |
| android.permission.MANAGE_SECURE_LOCK_DEVICE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_SENSORS | signature |  |  | sim |
| android.permission.MANAGE_SENSOR_PRIVACY | internal\|role\|installer |  |  | sim |
| android.permission.MANAGE_SLICE_PERMISSIONS | signature |  |  | sim |
| android.permission.MANAGE_SMARTSPACE | signature |  |  | sim |
| android.permission.MANAGE_SOUND_TRIGGER | signature\|privileged\|role |  |  | sim |
| android.permission.MANAGE_SPEECH_RECOGNITION | signature |  |  | sim |
| android.permission.MANAGE_SUBSCRIPTION_PLANS | signature\|privileged |  |  | sim |
| android.permission.MANAGE_SUBSCRIPTION_USER_ASSOCIATION | signature |  |  | sim |
| android.permission.MANAGE_TEST_NETWORKS | signature |  |  | sim |
| android.permission.MANAGE_TIME_AND_ZONE_DETECTION | signature\|privileged |  |  | sim |
| android.permission.MANAGE_TOAST_RATE_LIMITING | signature |  |  | sim |
| android.permission.MANAGE_UI_TRANSLATION | signature\|privileged\|role |  |  | sim |
| android.permission.MANAGE_USB | signature\|privileged |  |  | sim |
| android.permission.MANAGE_USERS | signature\|privileged |  |  | sim |
| android.permission.MANAGE_USER_OEM_UNLOCK_STATE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_VOICE_KEYPHRASES | signature\|privileged |  |  | sim |
| android.permission.MANAGE_WALLPAPER_EFFECTS_GENERATION | signature\|privileged |  |  | sim |
| android.permission.MANAGE_WEAK_ESCROW_TOKEN | signature\|privileged |  |  | sim |
| android.permission.MANAGE_WEARABLE_SENSING_SERVICE | signature\|privileged |  |  | sim |
| android.permission.MANAGE_WIFI_COUNTRY_CODE | signature |  |  | sim |
| android.permission.MANAGE_WIFI_INTERFACES | signature\|privileged\|knownSigner |  |  | nao |
| android.permission.MANAGE_WIFI_NETWORK_SELECTION | signature\|privileged\|knownSigner |  |  | nao |
| android.permission.MARK_DEVICE_ORGANIZATION_OWNED | signature\|role |  |  | sim |
| android.permission.MASTER_CLEAR | signature\|privileged\|role |  |  | nao |
| android.permission.MEDIA_CONTENT_CONTROL | signature\|privileged |  |  | nao |
| android.permission.MEDIA_RESOURCE_OVERRIDE_PID | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.MEDIA_ROUTING_CONTROL | signature\|appop |  |  | nao |
| android.permission.MIGRATE_HEALTH_CONNECT_DATA | signature\|knownSigner |  |  | sim |
| android.permission.MODIFY_ACCESSIBILITY_DATA | signature |  |  | sim |
| android.permission.MODIFY_APPWIDGET_BIND_PERMISSIONS | signature\|privileged |  |  | sim |
| android.permission.MODIFY_AUDIO_ROUTING | signature\|privileged\|role |  |  | sim |
| android.permission.MODIFY_AUDIO_SETTINGS | normal |  |  | nao |
| android.permission.MODIFY_AUDIO_SETTINGS_PRIVILEGED | signature\|privileged |  |  | sim |
| android.permission.MODIFY_CELL_BROADCASTS | signature\|privileged |  |  | sim |
| android.permission.MODIFY_DAY_NIGHT_MODE | signature\|privileged\|role |  |  | sim |
| android.permission.MODIFY_DEFAULT_AUDIO_EFFECTS | signature\|privileged |  |  | sim |
| android.permission.MODIFY_HDR_CONVERSION_MODE | signature |  |  | sim |
| android.permission.MODIFY_NETWORK_ACCOUNTING | signature\|privileged |  |  | sim |
| android.permission.MODIFY_PARENTAL_CONTROLS | signature\|privileged |  |  | sim |
| android.permission.MODIFY_PHONE_STATE | signature\|privileged\|role |  |  | nao |
| android.permission.MODIFY_QUIET_MODE | signature\|privileged\|development\|role |  |  | sim |
| android.permission.MODIFY_REFRESH_RATE_SWITCHING_TYPE | signature |  |  | sim |
| android.permission.MODIFY_SETTINGS_OVERRIDEABLE_BY_RESTORE | signature\|setup |  |  | sim |
| android.permission.MODIFY_THEME_OVERLAY | signature |  |  | sim |
| android.permission.MODIFY_TOUCH_MODE_STATE | signature |  |  | sim |
| android.permission.MODIFY_USER_PREFERRED_DISPLAY_MODE | signature |  |  | sim |
| android.permission.MONITOR_DEFAULT_SMS_PACKAGE | signature\|privileged |  |  | sim |
| android.permission.MONITOR_DEVICE_CONFIG_ACCESS | signature |  |  | sim |
| android.permission.MONITOR_INPUT | signature\|recents |  |  | sim |
| android.permission.MONITOR_KEYBOARD_BACKLIGHT | signature |  |  | sim |
| android.permission.MONITOR_STICKY_MODIFIER_STATE | signature |  |  | sim |
| android.permission.MOUNT_FORMAT_FILESYSTEMS | signature\|privileged |  |  | nao |
| android.permission.MOUNT_UNMOUNT_FILESYSTEMS | signature\|privileged |  |  | nao |
| android.permission.MOVE_PACKAGE | signature\|privileged |  |  | sim |
| android.permission.NEARBY_WIFI_DEVICES | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.NETWORK_AIRPLANE_MODE | signature |  |  | sim |
| android.permission.NETWORK_BYPASS_PRIVATE_DNS | signature |  |  | sim |
| android.permission.NETWORK_CARRIER_PROVISIONING | signature\|privileged |  |  | sim |
| android.permission.NETWORK_FACTORY | signature\|role |  |  | sim |
| android.permission.NETWORK_MANAGED_PROVISIONING | signature\|role |  |  | sim |
| android.permission.NETWORK_SCAN | signature\|privileged |  |  | sim |
| android.permission.NETWORK_SETTINGS | signature |  |  | sim |
| android.permission.NETWORK_SETUP_WIZARD | signature\|setup |  |  | sim |
| android.permission.NETWORK_SIGNAL_STRENGTH_WAKEUP | signature\|privileged |  |  | sim |
| android.permission.NETWORK_STACK | signature |  |  | sim |
| android.permission.NETWORK_STATS_PROVIDER | signature |  |  | sim |
| android.permission.NET_ADMIN | signature\|role |  |  | sim |
| android.permission.NET_TUNNELING | signature\|role |  |  | sim |
| android.permission.NFC | normal |  |  | nao |
| android.permission.NFC_HANDOVER_STATUS | signature\|privileged |  |  | sim |
| android.permission.NFC_PREFERRED_PAYMENT_INFO | normal |  |  | nao |
| android.permission.NFC_SET_CONTROLLER_ALWAYS_ON | signature\|privileged |  |  | sim |
| android.permission.NFC_TRANSACTION_EVENT | normal |  |  | nao |
| android.permission.NOTIFICATION_DURING_SETUP | signature\|privileged |  |  | sim |
| android.permission.NOTIFY_PENDING_SYSTEM_UPDATE | signature\|privileged |  |  | sim |
| android.permission.NOTIFY_TV_INPUTS | signature\|privileged |  |  | sim |
| android.permission.OBSERVE_APP_USAGE | signature\|privileged\|role |  |  | sim |
| android.permission.OBSERVE_GRANT_REVOKE_PERMISSIONS | signature\|privileged |  |  | sim |
| android.permission.OBSERVE_NETWORK_POLICY | signature |  |  | sim |
| android.permission.OBSERVE_PICTURE_PROFILES | signature\|privileged |  |  | sim |
| android.permission.OBSERVE_ROLE_HOLDERS | signature\|installer\|module |  |  | sim |
| android.permission.OBSERVE_SENSOR_PRIVACY | internal\|role\|installer |  |  | sim |
| android.permission.OEM_UNLOCK_STATE | signature |  |  | sim |
| android.permission.OPEN_ACCESSIBILITY_DETAILS_SETTINGS | signature\|installer |  |  | sim |
| android.permission.OVERRIDE_COMPAT_CHANGE_CONFIG | signature\|privileged |  |  | sim |
| android.permission.OVERRIDE_COMPAT_CHANGE_CONFIG_ON_RELEASE_BUILD | signature\|privileged |  |  | sim |
| android.permission.OVERRIDE_DISPLAY_MODE_REQUESTS | signature |  |  | sim |
| android.permission.OVERRIDE_SYSTEM_KEY_BEHAVIOR_IN_FOCUSED_WINDOW | signature\|privileged |  |  | sim |
| android.permission.OVERRIDE_WIFI_CONFIG | signature\|privileged\|knownSigner |  |  | nao |
| android.permission.PACKAGE_ROLLBACK_AGENT | signature |  |  | sim |
| android.permission.PACKAGE_USAGE_STATS | signature\|privileged\|development\|appop\|retailDemo |  |  | nao |
| android.permission.PACKAGE_VERIFICATION_AGENT | signature\|privileged |  |  | sim |
| android.permission.PACKET_KEEPALIVE_OFFLOAD | signature\|privileged |  |  | sim |
| android.permission.PEEK_DROPBOX_DATA | signature |  |  | sim |
| android.permission.PEERS_MAC_ADDRESS | signature\|setup\|role |  |  | sim |
| android.permission.PERFORM_CDMA_PROVISIONING | signature\|privileged\|role |  |  | sim |
| android.permission.PERFORM_IMS_SINGLE_REGISTRATION | internal\|role |  |  | sim |
| android.permission.PERFORM_SIM_ACTIVATION | signature\|privileged |  |  | sim |
| android.permission.PERSISTENT_ACTIVITY | normal |  | 15 | nao |
| android.permission.POST_NOTIFICATIONS | dangerous\|instant | NOTIFICATIONS |  | nao |
| android.permission.POWER_SAVER | signature\|privileged |  |  | sim |
| android.permission.PREPARE_FACTORY_RESET | signature\|privileged |  |  | sim |
| android.permission.PROCESS_OUTGOING_CALLS | dangerous | PHONE | 28 | nao |
| android.permission.PROVIDE_DEFAULT_ENABLED_CREDENTIAL_SERVICE | signature\|privileged |  |  | sim |
| android.permission.PROVIDE_OWN_AUTOFILL_SUGGESTIONS | internal\|role |  |  | nao |
| android.permission.PROVIDE_REMOTE_CREDENTIALS | signature\|privileged\|role |  |  | nao |
| android.permission.PROVIDE_RESOLVER_RANKER_SERVICE | signature\|privileged |  |  | sim |
| android.permission.PROVIDE_TRUST_AGENT | signature\|privileged |  |  | sim |
| android.permission.PROVISION_DEMO_DEVICE | signature\|setup\|knownSigner |  |  | sim |
| android.permission.QUARANTINE_APPS | signature\|verifier |  |  | sim |
| android.permission.QUERY_ADMIN_POLICY | signature\|role |  |  | sim |
| android.permission.QUERY_ADVANCED_PROTECTION_MODE | normal |  |  | nao |
| android.permission.QUERY_ALL_PACKAGES | normal |  |  | nao |
| android.permission.QUERY_AUDIO_STATE | signature\|role |  |  | sim |
| android.permission.QUERY_CLONED_APPS | signature\|privileged |  |  | sim |
| android.permission.QUERY_DEVICE_STOLEN_STATE | internal\|role |  |  | sim |
| android.permission.QUERY_DO_NOT_ASK_CREDENTIALS_ON_BOOT | signature |  |  | sim |
| android.permission.QUERY_TIME_ZONE_RULES | signature\|privileged |  |  | sim |
| android.permission.QUERY_USERS | signature\|privileged\|role |  |  | sim |
| android.permission.RADIO_SCAN_WITHOUT_LOCATION | signature\|companion |  |  | sim |
| android.permission.RANGING | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.READ_ACTIVE_EMERGENCY_SESSION | signature |  |  | sim |
| android.permission.READ_APP_SPECIFIC_LOCALES | signature\|installer |  |  | sim |
| android.permission.READ_ASSISTANT_APP_SEARCH_DATA | internal\|role |  |  | nao |
| android.permission.READ_BASIC_PHONE_STATE | normal |  |  | nao |
| android.permission.READ_BLOCKED_NUMBERS | signature |  |  | sim |
| android.permission.READ_CALENDAR | dangerous | CALENDAR |  | nao |
| android.permission.READ_CALL_LOG | dangerous | PHONE |  | nao |
| android.permission.READ_CARRIER_APP_INFO | signature |  |  | sim |
| android.permission.READ_CELL_BROADCASTS | dangerous |  |  | sim |
| android.permission.READ_CLIPBOARD_IN_BACKGROUND | signature\|role |  |  | sim |
| android.permission.READ_COLOR_ZONES | normal |  |  | nao |
| android.permission.READ_COMPAT_CHANGE_CONFIG | signature\|privileged |  |  | sim |
| android.permission.READ_CONTACTS | dangerous | CONTACTS |  | sim |
| android.permission.READ_CONTENT_RATING_SYSTEMS | signature\|privileged |  |  | sim |
| android.permission.READ_DEVICE_CONFIG | signature\|preinstalled |  |  | sim |
| android.permission.READ_DREAM_STATE | signature\|privileged |  |  | sim |
| android.permission.READ_DREAM_SUPPRESSION | signature |  |  | sim |
| android.permission.READ_DROPBOX_DATA | signature\|privileged\|development |  |  | nao |
| android.permission.READ_EXTERNAL_STORAGE | dangerous | STORAGE | 32 | nao |
| android.permission.READ_FRAME_BUFFER | signature\|recents |  |  | sim |
| android.permission.READ_GLOBAL_APP_SEARCH_DATA | internal\|role |  |  | sim |
| android.permission.READ_HOME_APP_SEARCH_DATA | internal\|role |  |  | nao |
| android.permission.READ_INPUT_STATE | signature |  |  | nao |
| android.permission.READ_INSTALLED_SESSION_PATHS | signature\|installer |  |  | sim |
| android.permission.READ_INSTALL_SESSIONS | normal |  |  | sim |
| android.permission.READ_INTRUSION_DETECTION_STATE | signature\|privileged |  |  | sim |
| android.permission.READ_LOGS | signature\|privileged\|development |  |  | nao |
| android.permission.READ_LOWPAN_CREDENTIAL | signature\|privileged |  |  | sim |
| android.permission.READ_MEDIA_AUDIO | dangerous | STORAGE |  | nao |
| android.permission.READ_MEDIA_IMAGES | dangerous | STORAGE |  | nao |
| android.permission.READ_MEDIA_VIDEO | dangerous | STORAGE |  | nao |
| android.permission.READ_MEDIA_VISUAL_USER_SELECTED | dangerous | STORAGE |  | nao |
| android.permission.READ_NEARBY_STREAMING_POLICY | normal |  |  | nao |
| android.permission.READ_NETWORK_USAGE_HISTORY | signature\|privileged |  |  | sim |
| android.permission.READ_OEM_UNLOCK_STATE | signature\|privileged |  |  | sim |
| android.permission.READ_PEOPLE_DATA | signature\|recents\|role |  |  | sim |
| android.permission.READ_PHONE_NUMBERS | dangerous\|instant | PHONE |  | nao |
| android.permission.READ_PHONE_STATE | dangerous | PHONE |  | nao |
| android.permission.READ_PRECISE_PHONE_STATE | signature\|privileged |  |  | nao |
| android.permission.READ_PRINT_SERVICES | signature\|preinstalled |  |  | sim |
| android.permission.READ_PRINT_SERVICE_RECOMMENDATIONS | signature\|preinstalled |  |  | sim |
| android.permission.READ_PRIVILEGED_PHONE_STATE | signature\|privileged\|role |  |  | sim |
| android.permission.READ_PROFILE | normal |  |  | sim |
| android.permission.READ_PROJECTION_STATE | signature |  |  | sim |
| android.permission.READ_RESTRICTED_STATS | internal\|privileged |  |  | sim |
| android.permission.READ_RUNTIME_PROFILES | signature\|privileged |  |  | sim |
| android.permission.READ_SAFETY_CENTER_STATUS | signature\|privileged |  |  | sim |
| android.permission.READ_SEARCH_INDEXABLES | signature\|privileged |  |  | sim |
| android.permission.READ_SMS | dangerous | SMS |  | nao |
| android.permission.READ_SOCIAL_STREAM | normal |  |  | sim |
| android.permission.READ_SUBSCRIPTION_PLANS | signature\|privileged |  |  | sim |
| android.permission.READ_SYNC_SETTINGS | normal |  |  | nao |
| android.permission.READ_SYNC_STATS | normal |  |  | nao |
| android.permission.READ_SYSTEM_GRAMMATICAL_GENDER | signature\|privileged |  |  | sim |
| android.permission.READ_SYSTEM_PREFERENCES | signature\|privileged\|role |  |  | nao |
| android.permission.READ_SYSTEM_UPDATE_INFO | signature\|privileged |  |  | sim |
| android.permission.READ_USER_DICTIONARY | normal |  |  | sim |
| android.permission.READ_WALLPAPER_INTERNAL | signature\|privileged |  |  | sim |
| android.permission.READ_WIFI_CREDENTIAL | signature\|privileged |  |  | sim |
| android.permission.READ_WRITE_SYNC_DISABLED_MODE_CONFIG | signature\|verifier\|configurator |  |  | sim |
| android.permission.REAL_GET_TASKS | signature\|privileged |  |  | sim |
| android.permission.REBOOT | signature\|privileged |  |  | nao |
| android.permission.RECEIVE_BLUETOOTH_MAP | signature\|privileged |  |  | sim |
| android.permission.RECEIVE_BOOT_COMPLETED | normal |  |  | nao |
| android.permission.RECEIVE_DATA_ACTIVITY_CHANGE | signature\|privileged |  |  | sim |
| android.permission.RECEIVE_DEVICE_CUSTOMIZATION_READY | signature\|preinstalled |  |  | sim |
| android.permission.RECEIVE_EMERGENCY_BROADCAST | signature\|privileged |  |  | sim |
| android.permission.RECEIVE_MEDIA_RESOURCE_USAGE | signature\|privileged |  |  | sim |
| android.permission.RECEIVE_MMS | dangerous | SMS |  | nao |
| android.permission.RECEIVE_SANDBOX_TRIGGER_AUDIO | signature\|privileged\|appop |  |  | sim |
| android.permission.RECEIVE_SENSITIVE_NOTIFICATIONS | signature\|role |  |  | sim |
| android.permission.RECEIVE_SMS | dangerous | SMS |  | nao |
| android.permission.RECEIVE_STK_COMMANDS | signature\|privileged |  |  | sim |
| android.permission.RECEIVE_WAP_PUSH | dangerous | SMS |  | nao |
| android.permission.RECEIVE_WIFI_CREDENTIAL_CHANGE | signature\|privileged |  |  | sim |
| android.permission.RECORD_AUDIO | dangerous\|instant | MICROPHONE |  | nao |
| android.permission.RECORD_BACKGROUND_AUDIO | internal\|role |  |  | sim |
| android.permission.RECORD_SENSITIVE_CONTENT | signature |  |  | sim |
| android.permission.RECOVERY | signature\|privileged |  |  | sim |
| android.permission.RECOVER_KEYSTORE | signature\|privileged |  |  | sim |
| android.permission.REGISTER_CALL_PROVIDER | signature\|privileged |  |  | sim |
| android.permission.REGISTER_CONNECTION_MANAGER | signature\|privileged |  |  | sim |
| android.permission.REGISTER_MEDIA_RESOURCE_OBSERVER | signature\|privileged |  |  | sim |
| android.permission.REGISTER_NSD_OFFLOAD_ENGINE | signature |  |  | sim |
| android.permission.REGISTER_SIM_SUBSCRIPTION | signature\|privileged |  |  | sim |
| android.permission.REGISTER_STATS_PULL_ATOM | signature\|privileged |  |  | sim |
| android.permission.REGISTER_WINDOW_MANAGER_LISTENERS | signature |  |  | sim |
| android.permission.REMAP_MODIFIER_KEYS | signature |  |  | sim |
| android.permission.REMOTE_AUDIO_PLAYBACK | signature |  |  | sim |
| android.permission.REMOTE_DISPLAY_PROVIDER | signature\|privileged |  |  | sim |
| android.permission.REMOVE_ACCOUNTS | signature\|role |  |  | sim |
| android.permission.REMOVE_DRM_CERTIFICATES | signature\|privileged |  |  | sim |
| android.permission.REMOVE_TASKS | signature\|recents\|role |  |  | sim |
| android.permission.RENOUNCE_PERMISSIONS | signature\|privileged |  |  | sim |
| android.permission.REORDER_TASKS | normal |  |  | nao |
| android.permission.REPORT_USAGE_STATS | signature\|module |  |  | sim |
| android.permission.REQUEST_COMPANION_PROFILE_APP_STREAMING | signature\|privileged |  |  | nao |
| android.permission.REQUEST_COMPANION_PROFILE_AUTOMOTIVE_PROJECTION | internal\|role |  |  | nao |
| android.permission.REQUEST_COMPANION_PROFILE_COMPUTER | signature\|privileged |  |  | nao |
| android.permission.REQUEST_COMPANION_PROFILE_GLASSES | normal |  |  | nao |
| android.permission.REQUEST_COMPANION_PROFILE_NEARBY_DEVICE_STREAMING | signature\|privileged |  |  | nao |
| android.permission.REQUEST_COMPANION_PROFILE_WATCH | normal |  |  | nao |
| android.permission.REQUEST_COMPANION_RUN_IN_BACKGROUND | normal |  |  | nao |
| android.permission.REQUEST_COMPANION_SELF_MANAGED | signature\|privileged |  |  | nao |
| android.permission.REQUEST_COMPANION_START_FOREGROUND_SERVICES_FROM_BACKGROUND | normal |  |  | nao |
| android.permission.REQUEST_COMPANION_USE_DATA_IN_BACKGROUND | normal |  |  | nao |
| android.permission.REQUEST_DELETE_PACKAGES | normal |  |  | nao |
| android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS | normal |  |  | nao |
| android.permission.REQUEST_INCIDENT_REPORT_APPROVAL | signature\|privileged |  |  | sim |
| android.permission.REQUEST_INSTALL_PACKAGES | signature\|appop |  |  | nao |
| android.permission.REQUEST_NETWORK_SCORES | signature\|setup |  |  | sim |
| android.permission.REQUEST_NOTIFICATION_ASSISTANT_SERVICE | signature\|privileged\|role |  |  | sim |
| android.permission.REQUEST_OBSERVE_COMPANION_DEVICE_PRESENCE | normal |  |  | nao |
| android.permission.REQUEST_OBSERVE_DEVICE_UUID_PRESENCE | signature\|privileged |  |  | nao |
| android.permission.REQUEST_PASSWORD_COMPLEXITY | normal |  |  | nao |
| android.permission.REQUEST_UNIQUE_ID_ATTESTATION | signature |  |  | sim |
| android.permission.RESERVED_FOR_TESTING_SIGNATURE | signature |  |  | sim |
| android.permission.RESET_APP_ERRORS | signature |  |  | sim |
| android.permission.RESET_FINGERPRINT_LOCKOUT | signature |  |  | sim |
| android.permission.RESET_PASSWORD | signature\|privileged |  |  | sim |
| android.permission.RESET_SHORTCUT_MANAGER_THROTTLING | signature |  |  | sim |
| android.permission.RESTART_PACKAGES | normal |  |  | nao |
| android.permission.RESTART_WIFI_SUBSYSTEM | signature\|privileged |  |  | sim |
| android.permission.RESTORE_HEALTH_CONNECT_DATA_AND_SETTINGS | signature\|knownSigner |  |  | sim |
| android.permission.RESTORE_RUNTIME_PERMISSIONS | signature |  |  | sim |
| android.permission.RESTRICTED_VR_ACCESS | signature\|preinstalled |  |  | sim |
| android.permission.RESTRICT_DISPLAY_MODES | signature |  |  | sim |
| android.permission.RETRIEVE_WINDOW_CONTENT | signature\|privileged |  |  | sim |
| android.permission.RETRIEVE_WINDOW_TOKEN | signature |  |  | sim |
| android.permission.REVIEW_ACCESSIBILITY_SERVICES | signature |  |  | sim |
| android.permission.REVOKE_POST_NOTIFICATIONS_WITHOUT_KILL | signature |  |  | sim |
| android.permission.REVOKE_RUNTIME_PERMISSIONS | signature\|installer\|verifier |  |  | sim |
| android.permission.ROTATE_SURFACE_FLINGER | signature\|recents |  |  | sim |
| android.permission.RUN_IN_BACKGROUND | signature |  |  | sim |
| android.permission.RUN_USER_INITIATED_JOBS | normal |  |  | nao |
| android.permission.SATELLITE_COMMUNICATION | role\|signature\|privileged |  |  | sim |
| android.permission.SCHEDULE_EXACT_ALARM | signature\|privileged\|appop |  |  | nao |
| android.permission.SCHEDULE_PRIORITIZED_ALARM | signature\|privileged |  |  | sim |
| android.permission.SCORE_NETWORKS | signature\|privileged |  |  | sim |
| android.permission.SCREEN_TIMEOUT_OVERRIDE | signature |  |  | sim |
| android.permission.SECURE_ELEMENT_PRIVILEGED_OPERATION | signature\|privileged |  |  | sim |
| android.permission.SEND_CATEGORY_CAR_NOTIFICATIONS | signature\|privileged |  |  | sim |
| android.permission.SEND_DEVICE_CUSTOMIZATION_READY | signature\|privileged |  |  | sim |
| android.permission.SEND_EMBMS_INTENTS | signature\|privileged |  |  | sim |
| android.permission.SEND_RESPOND_VIA_MESSAGE | signature\|privileged |  |  | nao |
| android.permission.SEND_SAFETY_CENTER_UPDATE | internal\|privileged |  |  | sim |
| android.permission.SEND_SHOW_SUSPENDED_APP_DETAILS | signature |  |  | sim |
| android.permission.SEND_SMS | dangerous | SMS |  | nao |
| android.permission.SEND_SMS_NO_CONFIRMATION | signature\|privileged |  |  | sim |
| android.permission.SERIAL_PORT | signature\|privileged |  |  | sim |
| android.permission.SETUP_FSVERITY | signature\|privileged |  |  | sim |
| android.permission.SET_ACTIVITY_WATCHER | signature |  |  | sim |
| android.permission.SET_ALWAYS_FINISH | signature\|privileged\|development |  |  | nao |
| android.permission.SET_AND_VERIFY_LOCKSCREEN_CREDENTIALS | signature |  |  | sim |
| android.permission.SET_ANIMATION_SCALE | signature\|privileged\|development |  |  | nao |
| android.permission.SET_APP_SPECIFIC_LOCALECONFIG | signature |  |  | sim |
| android.permission.SET_BIOMETRIC_DIALOG_ADVANCED | signature\|privileged |  |  | nao |
| android.permission.SET_CLIP_SOURCE | signature\|recents |  |  | sim |
| android.permission.SET_DEBUG_APP | signature\|privileged\|development |  |  | nao |
| android.permission.SET_DEFAULT_ACCOUNT_FOR_CONTACTS | internal\|role |  |  | sim |
| android.permission.SET_DISPLAY_OFFSET | signature\|privileged |  |  | sim |
| android.permission.SET_GAME_SERVICE | signature |  |  | sim |
| android.permission.SET_HARMFUL_APP_WARNINGS | signature\|verifier |  |  | sim |
| android.permission.SET_INITIAL_LOCK | signature\|setup |  |  | sim |
| android.permission.SET_INPUT_CALIBRATION | signature |  |  | sim |
| android.permission.SET_KEYBOARD_LAYOUT | signature |  |  | sim |
| android.permission.SET_LOW_POWER_STANDBY_PORTS | signature\|privileged |  |  | sim |
| android.permission.SET_MEDIA_KEY_LISTENER | signature\|privileged\|development |  |  | sim |
| android.permission.SET_ORIENTATION | signature\|recents |  |  | sim |
| android.permission.SET_POINTER_SPEED | signature |  |  | sim |
| android.permission.SET_PREFERRED_APPLICATIONS | signature\|installer\|verifier |  |  | nao |
| android.permission.SET_PROCESS_LIMIT | signature\|privileged\|development |  |  | nao |
| android.permission.SET_SCREEN_COMPATIBILITY | signature |  |  | sim |
| android.permission.SET_SYSTEM_AUDIO_CAPTION | signature\|role |  |  | sim |
| android.permission.SET_THEME_OVERLAY_CONTROLLER_READY | signature\|setup |  |  | sim |
| android.permission.SET_TIME | signature\|privileged\|role |  |  | nao |
| android.permission.SET_TIME_ZONE | signature\|privileged\|role |  |  | nao |
| android.permission.SET_UNRESTRICTED_GESTURE_EXCLUSION | signature\|privileged\|recents |  |  | sim |
| android.permission.SET_UNRESTRICTED_KEEP_CLEAR_AREAS | signature\|privileged |  |  | sim |
| android.permission.SET_VOLUME_KEY_LONG_PRESS_LISTENER | signature\|privileged\|development |  |  | sim |
| android.permission.SET_WALLPAPER | normal |  |  | nao |
| android.permission.SET_WALLPAPER_COMPONENT | signature\|privileged |  |  | sim |
| android.permission.SET_WALLPAPER_DIM_AMOUNT | signature\|privileged |  |  | sim |
| android.permission.SET_WALLPAPER_HINTS | normal |  |  | nao |
| android.permission.SHOW_CUSTOMIZED_RESOLVER | signature\|privileged |  |  | sim |
| android.permission.SHOW_KEYGUARD_MESSAGE | signature\|privileged |  |  | sim |
| android.permission.SHUTDOWN | signature\|privileged\|role |  |  | sim |
| android.permission.SIGNAL_PERSISTENT_PROCESSES | signature\|privileged\|development |  |  | nao |
| android.permission.SIGNAL_REBOOT_READINESS | signature\|privileged |  |  | sim |
| android.permission.SINGLE_USER_TIS_ACCESS | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.SMS_FINANCIAL_TRANSACTIONS | signature\|appop |  |  | nao |
| android.permission.SOUNDTRIGGER_DELEGATE_IDENTITY | signature\|privileged |  |  | sim |
| android.permission.SOUND_TRIGGER_RUN_IN_BATTERY_SAVER | signature\|privileged |  |  | sim |
| android.permission.STAGE_HEALTH_CONNECT_REMOTE_DATA | signature\|knownSigner |  |  | sim |
| android.permission.START_ACTIVITIES_FROM_BACKGROUND | signature\|privileged\|vendorPrivileged\|oem\|verifier\|role |  |  | sim |
| android.permission.START_ACTIVITIES_FROM_SDK_SANDBOX | signature |  |  | sim |
| android.permission.START_ACTIVITY_AS_CALLER | signature |  |  | sim |
| android.permission.START_ANY_ACTIVITY | signature |  |  | sim |
| android.permission.START_CROSS_PROFILE_ACTIVITIES | signature\|role |  |  | sim |
| android.permission.START_FOREGROUND_SERVICES_FROM_BACKGROUND | signature\|privileged\|vendorPrivileged\|oem\|verifier\|role |  |  | nao |
| android.permission.START_REVIEW_PERMISSION_DECISIONS | signature\|installer |  |  | sim |
| android.permission.START_TASKS_FROM_RECENTS | signature\|privileged\|recents |  |  | sim |
| android.permission.START_VIBRATION_SESSIONS | signature\|privileged |  |  | sim |
| android.permission.START_VIEW_APP_FEATURES | signature\|installer |  |  | nao |
| android.permission.START_VIEW_PERMISSION_USAGE | signature\|installer\|module |  |  | nao |
| android.permission.STATSCOMPANION | signature |  |  | sim |
| android.permission.STATUS_BAR | signature\|privileged\|recents |  |  | nao |
| android.permission.STATUS_BAR_SERVICE | signature\|recents |  |  | sim |
| android.permission.STOP_APP_SWITCHES | signature\|privileged\|recents |  |  | sim |
| android.permission.STORAGE_INTERNAL | signature |  |  | sim |
| android.permission.SUBSCRIBED_FEEDS_READ | normal |  |  | sim |
| android.permission.SUBSCRIBED_FEEDS_WRITE | normal |  |  | sim |
| android.permission.SUBSCRIBE_TO_KEYGUARD_LOCKED_STATE | signature\|module\|role |  |  | nao |
| android.permission.SUBSTITUTE_NOTIFICATION_APP_NAME | signature\|privileged |  |  | sim |
| android.permission.SUBSTITUTE_SHARE_TARGET_APP_NAME_AND_ICON | signature\|privileged |  |  | sim |
| android.permission.SUGGEST_EXTERNAL_TIME | signature\|privileged |  |  | sim |
| android.permission.SUGGEST_MANUAL_TIME_AND_ZONE | signature |  |  | sim |
| android.permission.SUGGEST_TELEPHONY_TIME_AND_ZONE | signature |  |  | sim |
| android.permission.SUPPRESS_CLIPBOARD_ACCESS_NOTIFICATION | signature |  |  | sim |
| android.permission.SUSPEND_APPS | signature\|role\|verifier |  |  | sim |
| android.permission.SYNC_FLAGS | signature |  |  | sim |
| android.permission.SYSTEM_ALERT_WINDOW | signature\|setup\|appop\|installer\|pre23\|development |  |  | nao |
| android.permission.SYSTEM_APPLICATION_OVERLAY | signature\|recents\|role\|installer |  |  | sim |
| android.permission.SYSTEM_CAMERA | system\|signature\|role |  |  | sim |
| android.permission.TABLET_MODE | signature |  |  | sim |
| android.permission.TEMPORARY_ENABLE_ACCESSIBILITY | signature |  |  | sim |
| android.permission.TEST_BIOMETRIC | signature |  |  | sim |
| android.permission.TEST_BLACKLISTED_PASSWORD | signature |  |  | sim |
| android.permission.TEST_INPUT_METHOD | signature |  |  | sim |
| android.permission.TEST_MANAGE_ROLLBACKS | signature |  |  | sim |
| android.permission.TETHER_PRIVILEGED | signature\|privileged |  |  | sim |
| android.permission.THREAD_NETWORK_PRIVILEGED | signature\|privileged |  |  | sim |
| android.permission.THREAD_NETWORK_TESTING | signature |  |  | sim |
| android.permission.TIS_EXTENSION_INTERFACE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.TOGGLE_AUTOMOTIVE_PROJECTION | internal\|role |  |  | sim |
| android.permission.TRANSMIT_IR | normal |  |  | nao |
| android.permission.TRIGGER_LOST_MODE | signature\|role |  |  | sim |
| android.permission.TRIGGER_SHELL_BUGREPORT | signature |  |  | sim |
| android.permission.TRIGGER_SHELL_PROFCOLLECT_UPLOAD | signature |  |  | sim |
| android.permission.TRUST_LISTENER | signature |  |  | sim |
| android.permission.TUNER_RESOURCE_ACCESS | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.TURN_SCREEN_ON | signature\|privileged\|appop |  |  | nao |
| android.permission.TV_IMPLICIT_ENTER_PIP | normal |  |  | nao |
| android.permission.TV_INPUT_HARDWARE | signature\|privileged\|vendorPrivileged |  |  | sim |
| android.permission.TV_VIRTUAL_REMOTE_CONTROLLER | signature\|privileged |  |  | sim |
| android.permission.UNLIMITED_SHORTCUTS_API_CALLS | signature\|role |  |  | sim |
| android.permission.UNLIMITED_TOASTS | signature |  |  | sim |
| android.permission.UPDATE_APP_OPS_STATS | signature\|privileged\|installer\|role |  |  | sim |
| android.permission.UPDATE_CONFIG | signature\|privileged |  |  | sim |
| android.permission.UPDATE_DEVICE_MANAGEMENT_RESOURCES | signature\|role |  |  | sim |
| android.permission.UPDATE_DEVICE_STATS | signature\|privileged\|role |  |  | nao |
| android.permission.UPDATE_DOMAIN_VERIFICATION_USER_SELECTION | signature |  |  | sim |
| android.permission.UPDATE_FONTS | signature\|privileged |  |  | sim |
| android.permission.UPDATE_LOCK | signature\|privileged |  |  | sim |
| android.permission.UPDATE_LOCK_TASK_PACKAGES | signature\|setup |  |  | sim |
| android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION | normal |  |  | nao |
| android.permission.UPDATE_TIME_ZONE_RULES | signature\|privileged |  |  | sim |
| android.permission.UPGRADE_RUNTIME_PERMISSIONS | signature |  |  | sim |
| android.permission.USER_ACTIVITY | signature\|privileged |  |  | sim |
| android.permission.USE_ATTESTATION_VERIFICATION_SERVICE | signature |  |  | sim |
| android.permission.USE_BIOMETRIC | normal |  |  | nao |
| android.permission.USE_BIOMETRIC_INTERNAL | signature |  |  | sim |
| android.permission.USE_COLORIZED_NOTIFICATIONS | signature\|setup\|role |  |  | sim |
| android.permission.USE_COMPANION_TRANSPORTS | signature |  |  | sim |
| android.permission.USE_CREDENTIALS | normal |  | 22 | sim |
| android.permission.USE_DATA_IN_BACKGROUND | signature |  |  | sim |
| android.permission.USE_EXACT_ALARM | normal |  |  | nao |
| android.permission.USE_FINGERPRINT | normal |  | 28 | nao |
| android.permission.USE_FULL_SCREEN_INTENT | normal\|appop |  |  | nao |
| android.permission.USE_ICC_AUTH_WITH_DEVICE_IDENTIFIER | signature\|appop |  |  | nao |
| android.permission.USE_ON_DEVICE_INTELLIGENCE | signature\|privileged |  |  | sim |
| android.permission.USE_REMOTE_AUTH | signature |  |  | sim |
| android.permission.USE_RESERVED_DISK | signature\|privileged |  |  | sim |
| android.permission.USE_SIP | dangerous | PHONE |  | nao |
| android.permission.UWB_PRIVILEGED | signature\|privileged |  |  | sim |
| android.permission.UWB_RANGING | dangerous | NEARBY_DEVICES |  | nao |
| android.permission.VERIFY_ATTESTATION | signature |  |  | sim |
| android.permission.VIBRATE | normal\|instant |  |  | nao |
| android.permission.VIBRATE_ALWAYS_ON | signature |  |  | sim |
| android.permission.VIBRATE_SYSTEM_CONSTANTS | signature |  |  | sim |
| android.permission.VIBRATE_VENDOR_EFFECTS | signature\|privileged |  |  | sim |
| android.permission.VIEW_INSTANT_APPS | signature\|preinstalled |  |  | sim |
| android.permission.VIRTUAL_INPUT_DEVICE | signature |  |  | sim |
| android.permission.WAKEUP_SURFACE_FLINGER | signature\|recents |  |  | sim |
| android.permission.WAKE_LOCK | normal\|instant |  |  | nao |
| android.permission.WATCH_APPOPS | signature\|privileged |  |  | sim |
| android.permission.WHITELIST_AUTO_REVOKE_PERMISSIONS | signature\|installer |  |  | sim |
| android.permission.WHITELIST_RESTRICTED_PERMISSIONS | signature\|installer |  |  | sim |
| android.permission.WIFI_ACCESS_COEX_UNSAFE_CHANNELS | signature\|role |  |  | sim |
| android.permission.WIFI_SET_DEVICE_MOBILITY_STATE | signature\|privileged |  |  | sim |
| android.permission.WIFI_UPDATE_COEX_UNSAFE_CHANNELS | signature\|role |  |  | sim |
| android.permission.WIFI_UPDATE_USABILITY_STATS_SCORE | signature\|privileged |  |  | sim |
| android.permission.WRITE_ALLOWLISTED_DEVICE_CONFIG | signature\|verifier\|configurator |  |  | sim |
| android.permission.WRITE_APN_SETTINGS | signature\|privileged |  |  | nao |
| android.permission.WRITE_BLOCKED_NUMBERS | signature |  |  | sim |
| android.permission.WRITE_CALENDAR | dangerous | CALENDAR |  | nao |
| android.permission.WRITE_CALL_LOG | dangerous | PHONE |  | nao |
| android.permission.WRITE_CONTACTS | dangerous | CONTACTS |  | nao |
| android.permission.WRITE_DEVICE_CONFIG | signature\|verifier\|configurator |  |  | sim |
| android.permission.WRITE_DREAM_STATE | signature\|privileged |  |  | sim |
| android.permission.WRITE_EMBEDDED_SUBSCRIPTIONS | signature\|privileged\|development |  |  | sim |
| android.permission.WRITE_EXTERNAL_STORAGE | dangerous | STORAGE | 32 | nao |
| android.permission.WRITE_FLAGS | signature |  |  | sim |
| android.permission.WRITE_GSERVICES | signature\|privileged |  |  | nao |
| android.permission.WRITE_MEDIA_STORAGE | signature\|privileged |  |  | sim |
| android.permission.WRITE_OBB | signature\|privileged |  |  | sim |
| android.permission.WRITE_PROFILE | normal |  |  | sim |
| android.permission.WRITE_SECURE_SETTINGS | signature\|privileged\|development\|role\|installer |  |  | nao |
| android.permission.WRITE_SECURITY_LOG | signature\|privileged |  |  | sim |
| android.permission.WRITE_SETTINGS | signature\|preinstalled\|appop\|pre23\|role |  |  | nao |
| android.permission.WRITE_SETTINGS_HOMEPAGE_DATA | signature\|privileged |  |  | sim |
| android.permission.WRITE_SMS | normal |  |  | sim |
| android.permission.WRITE_SOCIAL_STREAM | normal |  |  | sim |
| android.permission.WRITE_SYNC_SETTINGS | normal |  |  | nao |
| android.permission.WRITE_SYSTEM_PREFERENCES | signature\|privileged\|appop |  |  | nao |
| android.permission.WRITE_USER_DICTIONARY | normal |  |  | sim |
| android.permission.WRITE_VERIFICATION_STATE_E2EE_CONTACT_KEYS | signature\|privileged |  |  | sim |

## Regras duras

1. Permissoes signature/`@hide` sao inobtiveis em device real — o
   flagship testa a classificacao, nao instalabilidade.
2. **Strings inventadas NUNCA entram aqui.** Permissoes inexistentes/fake
   vivem exclusivamente em `suites/parser-torture/unknown-perms/`.
3. O diff entre `rustydroid inspect --json` e esta tabela deve ser
   zero-drift (contagem por nivel, grupo por permissao, maxSdk e flag
   @hide).
4. AOSP master evolve todo dia: divergencias apontadas pelo APKBot
   (`permission_drift`) sao resolvidas re-executando
   `tools/snapshot-aosp-permissions.py` + este gerador.
