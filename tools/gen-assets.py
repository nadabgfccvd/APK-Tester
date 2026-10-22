#!/usr/bin/env python3
"""Gerador dos assets miscelâneos determinísticos do APK Tester ("Behemoth").

Fase: A0/A1 — geradores core. Produz:
  - assets/probe/maxprobe-report.schema.json (JSON Schema do registro de probe)
  - assets/probe/apendice-c-domains.json (domínios de probe do Apêndice C)
  - assets/fixtures/net-record-replay/session_00{1,2,3}.json (gravação/replay)
  - assets/fonts/README.md (nota: fontes OFL entram em A1; zero binário)
  - assets/raw/blobs/<sha256>.bin — 5 blobs binários de 1 KB via cadeia
    hashlib (content-addressed: o nome É o sha256 do conteúdo)

Determinístico por --seed; apenas stdlib python3; manifest.json com sha256.

Uso:
    python3 tools/gen-assets.py --out /tmp/out [--seed 20261022]
    python3 tools/gen-assets.py --selftest
"""

import argparse
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

DEFAULT_SEED = 20261022
MODULE_IDS = ["CORE", "UI", "ST", "NET", "SYS", "MEDIA", "LANG"]
BLOB_COUNT = 5
BLOB_SIZE = 1024
SESSIONS = 3
ENTRIES_PER_SESSION = 8

SENSORS = [
    "accelerometer", "magnetic_field", "gyroscope", "light", "pressure",
    "proximity", "gravity", "linear_acceleration", "rotation_vector",
    "relative_humidity", "ambient_temperature", "object_temperature",
    "heart_rate", "heart_beat", "step_detector", "step_counter",
    "geomagnetic_rotation_vector", "significant_motion", "motion_detect",
    "stationary_detect", "low_latency_offbody_detect", "hinge_angle",
    "head_tracker", "accelerometer_uncalibrated", "gyroscope_uncalibrated",
    "magnetic_field_uncalibrated",
]

NOTIF_STYLES = [
    "basic", "big_text", "big_picture", "inbox", "messaging", "media",
    "progress", "custom_remoteviews", "heads_up", "group_summary", "bundled",
    "public_version", "secret",
]

# (id, label, module_id, probes) — espelho do Apêndice C do master prompt.
DOMAIN_DATA = [
    ("lifecycle", "Activity/Service/Fragment lifecycle", "CORE",
     ["onCreate", "onStart", "onResume", "onPause", "onStop", "onDestroy",
      "onSaveInstanceState", "onRestoreInstanceState", "onConfigurationChanged",
      "onTrimMemory"]),
    ("pm", "PackageManager introspection", "CORE",
     ["getPackageInfo", "queryIntentActivities", "getInstalledPackages",
      "checkPermission", "getLaunchIntentForPackage", "getProviderInfo"]),
    ("widgets", "Widget zoo (all android.widget classes)", "UI",
     ["TextView", "EditText", "Button", "CheckBox", "RadioButton",
      "ToggleButton", "Switch", "SeekBar", "RatingBar", "ProgressBar",
      "Spinner", "ListView", "GridView", "ScrollView", "HorizontalScrollView",
      "AutoCompleteTextView", "ExpandableListView", "TabHost", "VideoView",
      "TextClock", "AnalogClock", "Chronometer", "DatePicker", "TimePicker",
      "CalendarView", "SearchView", "TextureView", "SurfaceView",
      "ViewFlipper", "NumberPicker", "StackView", "ZoomControls"]),
    ("graphics/canvas", "Canvas/Paint drawing", "UI",
     ["Canvas.drawPath", "Paint.setShader", "PathMeasure", "Bitmap.compress",
      "PorterDuffXfermode", "ColorMatrixColorFilter", "Picture", "Region"]),
    ("text", "Text layout, spans and RTL", "UI",
     ["SpannableString", "TextPaint", "StaticLayout", "DynamicLayout",
      "Editable", "InputFilter", "Typeface", "Layout.Directions",
      "BreakIterator"]),
    ("os/handler", "Looper/Handler/Messenger", "SYS",
     ["Handler.postDelayed", "Looper.getMainLooper", "MessageQueue.idle",
      "Messenger.send", "HandlerThread", "AsyncTask"]),
    ("sqlite", "SQLite database", "ST",
     ["SQLiteDatabase.insert", "query", "update", "delete",
      "beginTransaction", "SQLiteOpenHelper", "Cursor.moveToFirst"]),
    ("room", "Room persistence (androidx)", "ST",
     ["@Entity", "@Dao", "@Database", "InvalidationTracker", "TypeConverter"]),
    ("providers", "ContentProviders CRUD", "CORE",
     ["ContentResolver.query", "insert", "update", "delete", "call",
      "openFileDescriptor", "getStreamTypes"]),
    ("net", "Network record/replay fixtures", "NET",
     ["HttpURLConnection", "SSLSocket", "Socket", "InetAddress.getAllByName",
      "record-session", "replay-session"]),
    ("media", "Media playback/capture", "MEDIA",
     ["MediaPlayer", "AudioTrack", "SoundPool", "MediaCodec", "AudioRecord",
      "MediaExtractor", "MediaMuxer"]),
    ("camera2", "Camera2 API", "MEDIA",
     ["CameraManager.getCameraIdList", "CameraDevice.openCamera",
      "CameraCaptureSession", "CaptureRequest.Builder", "ImageReader"]),
    ("sensors", "Sensor suite (all hardware types)", "SYS", SENSORS),
    ("location", "Location services", "SYS",
     ["getLastKnownLocation", "requestLocationUpdates", "requestSingleUpdate",
      "Geocoder.getFromLocation", "addProximityAlert",
      "registerGnssMeasurementsCallback"]),
    ("telephony", "Telephony and SMS", "SYS",
     ["getNetworkOperator", "getServiceState", "SmsManager.sendTextMessage",
      "listen(CallStateListener)", "getCellLocation", "getDataState"]),
    ("bluetooth_le", "Bluetooth LE scan/GATT", "NET",
     ["BluetoothLeScanner.startScan", "ScanFilter", "ScanSettings",
      "BluetoothGatt.connect", "discoverServices", "writeCharacteristic"]),
    ("nfc", "NFC reader/Card emulation", "NET",
     ["NfcAdapter.enableReaderMode", "Tag.getTechList", "IsoDep.transceive",
      "NdefMessage", "HostApduService.processCommandApdu"]),
    ("keystore", "AndroidKeyStore crypto", "SYS",
     ["KeyStore.getInstance(AndroidKeyStore)", "KeyGenerator AES",
      "KeyPairGenerator RSA", "Cipher.doFinal", "Mac", "Signature"]),
    ("biometric", "Fingerprint/Biometric auth", "SYS",
     ["FingerprintManager.authenticate", "BiometricPrompt (framework)",
      "CryptoObject"]),
    ("accounts", "AccountManager", "SYS",
     ["AccountManager.get", "getAccountsByType", "addAccount", "setAuthToken",
      "AbstractAccountAuthenticator"]),
    ("tts", "Text-to-speech", "MEDIA",
     ["TextToSpeech.speak", "synthesizeToFile", "UtteranceProgressListener",
      "getAvailableLanguages"]),
    ("print", "Printing framework", "SYS",
     ["PrintManager.print", "PrintDocumentAdapter.onLayout",
      "PrintJob.getInfo"]),
    ("job", "Jobs/alarms/background work", "SYS",
     ["JobScheduler.schedule", "JobInfo.Builder", "JobParameters",
      "AlarmManager.setExactAndAllowWhileIdle", "AlarmManager.setAndAllowWhileIdle"]),
    ("notifications", "Notification styles (all)", "SYS", NOTIF_STYLES),
    ("clipboard", "Clipboard access", "UI",
     ["ClipboardManager.getPrimaryClip", "setPrimaryClip",
      "addPrimaryClipChangedListener", "ClipDescription"]),
    ("localemanager", "Per-app locales", "LANG",
     ["LocaleManager.setApplicationLocales", "getApplicationLocales",
      "LocaleList.getDefault", "getSystemLocales"]),
    ("webview", "WebView + JS bridge", "UI",
     ["WebView.loadUrl", "WebViewClient.shouldOverrideUrlLoading",
      "WebChromeClient", "addJavascriptInterface", "evaluateJavascript",
      "postMessage"]),
    ("gles", "GLES 3.1 shader probes", "MEDIA",
     ["GLES31.glCreateShader", "glShaderSource", "glCompileShader",
      "glCreateProgram", "glLinkProgram", "glGetError",
      "EGL14.eglCreateContext"]),
    ("jni", "JNI matrix", "SYS",
     ["GetStringUTFChars", "ReleaseStringUTFChars",
      "GetObjectArrayElement", "SetIntArrayRegion", "NewDirectByteBuffer",
      "ThrowNew", "AttachCurrentThread", "GetJavaVM"]),
]

FONTS_README = """# assets/fonts — placeholders (fase A0)

NOTA IMPORTANTE (A1): as fontes OFL (Noto Sans, DejaVu Sans etc.) entram na
fase A1 do suite. NENHUM binário de fonte é commitado neste repositório: os
arquivos .ttf/.otf são obtidos/copiados no build (tools/fixture-pack.py) a
partir das fontes OFL baixadas no CI, e o audit de licenças (contracts/)
lista os hashes esperados de cada arquivo.

- Licenças aceitas: SIL OFL 1.1 apenas (ver contracts/ na fase A1).
- Binários commitados: nenhum (política do repo — só texto determinístico).
- Consumidores: :app classic (fontes do sistema como fallback) e :compose
  modern (FontFamily fornecido em A1).
"""


def build_schema() -> dict:
    """JSON Schema draft-07 do registro de probe (contrato Apêndice C)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://apktester.dev/schemas/maxprobe-report.schema.json",
        "title": "MaxProbeReport",
        "description": "Registro de probe do APK Tester consumido por "
                       "RustyDroid (AG-09/AG-12) e pelo CI de compatibilidade.",
        "type": "object",
        "required": ["probes"],
        "properties": {
            "session": {"type": "string"},
            "seed": {"type": "integer"},
            "probes": {
                "type": "array",
                "items": {"$ref": "#/definitions/probe"},
            },
        },
        "definitions": {
            "probe": {
                "type": "object",
                "required": ["id", "module_id", "domain", "api", "result",
                             "duration_ms"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z0-9_.-]+$"},
                    "module_id": {"enum": MODULE_IDS},
                    "domain": {"type": "string"},
                    "api": {"type": "string"},
                    "result": {"enum": ["OK", "ERROR"]},
                    "error": {"type": ["string", "null"],
                              "description": "Obrigatório quando result=ERROR"},
                    "duration_ms": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
        },
    }


def build_domains(seed: int) -> dict:
    """Catálogo dos domínios de probe do Apêndice C (master prompt)."""
    domains = []
    for domain_id, label, module_id, probes in DOMAIN_DATA:
        domains.append({
            "id": domain_id,
            "label": label,
            "module_id": module_id,
            "probe_count": len(probes),
            "probes": list(probes),
        })
    return {
        "tool": "gen-assets.py",
        "seed": seed,
        "source": "APK_TESTER_PROMPT.md — Apêndice C (domínios de probe)",
        "domain_count": len(domains),
        "probe_example": {
            "id": "lifecycle.activity.oncreate.001",
            "module_id": "CORE",
            "domain": "lifecycle",
            "api": "Activity.onCreate",
            "result": "OK",
            "error": None,
            "duration_ms": 12,
        },
        "domains": domains,
    }


def build_session(seed: int, index: int) -> dict:
    """Sessão net record/replay determinística (sem relógio de parede)."""
    rng = random.Random(seed * 1000 + index)
    methods = ["GET", "GET", "POST", "PUT", "HEAD"]
    statuses = [200, 200, 200, 201, 204, 404, 500]
    entries = []
    for seq in range(1, ENTRIES_PER_SESSION + 1):
        status = rng.choice(statuses)
        body = json.dumps({
            "ok": status < 400,
            "seq": seq,
            "fixture": f"net-{index:03d}",
            "payload": rng.choice(["ping", "echo", "chunk", "status"]),
        }, sort_keys=True)
        entries.append({
            "seq": seq,
            "method": rng.choice(methods),
            "url": f"https://fixture.apktester.dev/v1/{rng.choice(['ping', 'echo', 'data'])}/{seq:02d}",
            "status": status,
            "request_headers": {
                "Accept": "application/json",
                "X-Probe": "apk-tester",
            },
            "response_headers": {
                "Content-Type": "application/json",
                "X-Fixture": f"net-{index:03d}/{seq:02d}",
            },
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "body": body,
            "latency_ms": rng.randrange(5, 120),
        })
    return {
        "session_id": f"net-{index:03d}",
        "tool": "gen-assets.py",
        "seed": seed,
        "replay": {"mode": "strict", "base_delay_ms": 20},
        "entries": entries,
    }


def build_blob(seed: int, index: int) -> bytes:
    """Cadeia sha256 determinística até 1024 bytes (content-addressed)."""
    chain = hashlib.sha256(f"{seed}:raw-blob:{index}".encode("utf-8")).digest()
    chunks = bytearray()
    while len(chunks) < BLOB_SIZE:
        chain = hashlib.sha256(chain).digest()
        chunks.extend(chain)
    return bytes(chunks[:BLOB_SIZE])


def generate(out_dir: Path, seed: int) -> list:
    """Gera todos os assets; devolve a lista de caminhos relativos."""
    artifacts = []

    def write(rel: str, text: str) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        artifacts.append(rel)

    def write_json(rel: str, payload) -> None:
        write(rel, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    write_json("assets/probe/maxprobe-report.schema.json", build_schema())
    write_json("assets/probe/apendice-c-domains.json", build_domains(seed))
    for i in range(1, SESSIONS + 1):
        write_json(f"assets/fixtures/net-record-replay/session_{i:03d}.json",
                   build_session(seed, i))
    write("assets/fonts/README.md", FONTS_README)

    for i in range(BLOB_COUNT):
        data = build_blob(seed, i)
        name = hashlib.sha256(data).hexdigest()
        rel = f"assets/raw/blobs/{name}.bin"
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        artifacts.append(rel)

    write_manifest(out_dir, "gen-assets.py", seed, artifacts)
    return artifacts


def write_manifest(out_dir: Path, tool: str, seed: int, rel_paths: list) -> None:
    entries = []
    for rel in sorted(rel_paths):
        data = (out_dir / rel).read_bytes()
        entries.append({
            "path": rel,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    payload = {"tool": tool, "seed": seed, "artifacts": entries}
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_selftest() -> int:
    """Valida JSONs, schema, sessões e estabilidade dos blobs entre dirs."""
    try:
        with tempfile.TemporaryDirectory(prefix="apktester-gen-assets-") as tmp:
            root = Path(tmp)
            generate(root, DEFAULT_SEED)
            schema = json.loads(
                (root / "assets/probe/maxprobe-report.schema.json")
                .read_text("utf-8"))
            assert schema["definitions"]["probe"]["required"] == [
                "id", "module_id", "domain", "api", "result", "duration_ms"]
            modules = set(schema["definitions"]["probe"]["properties"]
                          ["module_id"]["enum"])
            assert modules == set(MODULE_IDS)

            domains = json.loads(
                (root / "assets/probe/apendice-c-domains.json").read_text("utf-8"))
            assert domains["domain_count"] >= 25, "domínios Apêndice C faltando"
            by_id = {d["id"]: d for d in domains["domains"]}
            assert "jni" in by_id and "gles" in by_id and "webview" in by_id
            assert len(by_id["sensors"]["probes"]) >= 20, "sensores incompletos"
            assert len(by_id["notifications"]["probes"]) >= 10
            for domain in domains["domains"]:
                assert domain["module_id"] in MODULE_IDS

            for i in range(1, SESSIONS + 1):
                session = json.loads(
                    (root / f"assets/fixtures/net-record-replay/"
                            f"session_{i:03d}.json").read_text("utf-8"))
                assert len(session["entries"]) == ENTRIES_PER_SESSION
                for entry in session["entries"]:
                    digest = hashlib.sha256(entry["body"].encode("utf-8"))
                    assert digest.hexdigest() == entry["body_sha256"]

            blobs = sorted((root / "assets/raw/blobs").glob("*.bin"))
            assert len(blobs) == BLOB_COUNT, f"blobs={len(blobs)}"
            for blob in blobs:
                assert blob.stat().st_size == BLOB_SIZE
                assert blob.stem == hashlib.sha256(blob.read_bytes()).hexdigest()

            second = root / "second-run"
            generate(second, DEFAULT_SEED)
            first_names = {p.name for p in blobs}
            second_names = {p.name
                            for p in (second / "assets/raw/blobs").glob("*.bin")}
            assert first_names == second_names, "blobs instáveis entre dirs"
            a = (root / "assets/probe/apendice-c-domains.json").read_bytes()
            b = (second / "assets/probe/apendice-c-domains.json").read_bytes()
            assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    except AssertionError as exc:
        print(f"gen-assets selftest: FAIL ({exc})")
        return 1
    print("gen-assets selftest: OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera schemas, domínios de probe, fixtures net, blobs.")
    parser.add_argument("--out", help="diretório de saída (obrigatório)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--selftest", action="store_true",
                        help="roda asserções internas e sai com 0/1")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.out:
        parser.error("--out é obrigatório (ou use --selftest)")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate(out_dir, args.seed)
    print(f"gen-assets: {len(artifacts)} artefatos gravados em {out_dir} "
          f"(seed={args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
