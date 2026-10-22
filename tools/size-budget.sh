#!/usr/bin/env bash
# tools/size-budget.sh — gate de tamanho do flagship + size-report.csv.
#
# Lista as entradas do APK (equivalente a unzip -l, via python3 zipfile inline)
# e classifica cada arquivo por extensão/magic em:
#   textures|meshes|shaders|audio|dex|arsc|so|locales|resources|other
# O total usa os tamanhos DESCOMPRIMIDOS das entradas (file_size do zip).
# Escreve o CSV (category,bytes,files,sha256_of_apk) e falha (exit 1) se o
# total sair de [min,max] MB. APK ausente/corrompido => exit 2.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK=""
MIN_MB=850
MAX_MB=1000
REPORT="$REPO_ROOT/contracts/flagship/size-report.csv"

erro() { echo "erro: $*" >&2; exit 2; }

[ "${1:-}" = "--help" ] && {
  echo "uso: tools/size-budget.sh --apk PATH [--min-mb 850] [--max-mb 1000] [--report CSV]"
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apk) [ $# -ge 2 ] || erro "--apk exige caminho"; APK="$2"; shift 2 ;;
    --min-mb) [ $# -ge 2 ] || erro "--min-mb exige valor"; MIN_MB="$2"; shift 2 ;;
    --max-mb) [ $# -ge 2 ] || erro "--max-mb exige valor"; MAX_MB="$2"; shift 2 ;;
    --report) [ $# -ge 2 ] || erro "--report exige caminho"; REPORT="$2"; shift 2 ;;
    *) erro "flag desconhecida: $1 (use --help)" ;;
  esac
done

[ -n "$APK" ] || erro "--apk é obrigatório (use --help)"
[ -f "$APK" ] || erro "APK não encontrado: $APK"
[ "$MIN_MB" -le "$MAX_MB" ] || erro "--min-mb ($MIN_MB) maior que --max-mb ($MAX_MB)"

mkdir -p "$(dirname "$REPORT")"

if ! APK_PATH="$APK" REPORT_PATH="$REPORT" MIN_MB="$MIN_MB" MAX_MB="$MAX_MB" \
    python3 - <<'PY'
import hashlib
import os
import re
import sys
import zipfile

min_mb, max_mb = int(os.environ["MIN_MB"]), int(os.environ["MAX_MB"])
apk, report = os.environ["APK_PATH"], os.environ["REPORT_PATH"]

CATS = ["textures", "meshes", "shaders", "audio", "dex", "arsc", "so",
        "locales", "resources", "other"]
EXT_CAT = {
    "ktx2": "textures", "ktx": "textures", "pkm": "textures",
    "astc": "textures", "etc1": "textures", "basis": "textures",
    "exr": "textures", "hdr": "textures",
    "gltf": "meshes", "glb": "meshes", "obj": "meshes", "ply": "meshes",
    "spv": "shaders", "glsl": "shaders", "vert": "shaders",
    "frag": "shaders", "comp": "shaders", "tesc": "shaders",
    "tese": "shaders", "geom": "shaders",
    "wav": "audio", "ogg": "audio", "oga": "audio", "flac": "audio",
    "mp3": "audio", "opus": "audio", "m4a": "audio", "aac": "audio",
}
KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"


def classify(name: str, head: bytes) -> str:
    """Extensão primeiro, magic como desempate; locales por caminho."""
    n = name.replace("\\", "/").lower()
    base = n.rsplit("/", 1)[-1]
    if base == "resources.arsc":
        return "arsc"
    if base.endswith(".dex") or head[:4] == b"dex\n":
        return "dex"
    if base.endswith(".so") or head[:4] == b"\x7fELF":
        return "so"
    ext = base.rsplit(".", 1)[1] if "." in base else ""
    if ext in EXT_CAT:
        return EXT_CAT[ext]
    if head[:12] == KTX2_MAGIC:
        return "textures"
    if head[:4] == b"glTF":
        return "meshes"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio"
    # values-<locale>/ (o values/ default conta como resources) e bundles
    if re.match(r"res/values-[a-z0-9_~]+/", n) or n.startswith("assets/locales/"):
        return "locales"
    if n.startswith("res/") or base == "androidmanifest.xml":
        return "resources"
    return "other"


try:
    sha = hashlib.sha256()
    with open(apk, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    apk_sha = sha.hexdigest()

    stats = {c: [0, 0] for c in CATS}  # categoria -> [bytes, arquivos]
    with zipfile.ZipFile(apk) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            with zf.open(info) as fh:
                head = fh.read(16)
            cat = classify(info.filename, head)
            stats[cat][0] += info.file_size
            stats[cat][1] += 1
except (zipfile.BadZipFile, OSError) as exc:
    print(f"[size-budget] erro: APK invalido ou ilegivel ({apk}): {exc}",
          file=sys.stderr)
    sys.exit(2)

total_bytes = sum(v[0] for v in stats.values())
total_files = sum(v[1] for v in stats.values())

with open(report, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("category,bytes,files,sha256_of_apk\n")
    for cat in CATS:
        fh.write(f"{cat},{stats[cat][0]},{stats[cat][1]},{apk_sha}\n")
    fh.write(f"total,{total_bytes},{total_files},{apk_sha}\n")

print(f"[size-budget] APK: {apk}")
print(f"[size-budget] sha256: {apk_sha}")
print(f"[size-budget] total: {total_bytes} bytes "
      f"({total_bytes / (1024 * 1024):.2f} MB) em {total_files} entradas "
      "(tamanhos descomprimidos)")
for cat in CATS:
    if stats[cat][1]:
        print(f"[size-budget]   {cat:<10} {stats[cat][0]:>15} bytes "
              f"{stats[cat][1]:>6} arquivos")
print(f"[size-budget] relatorio: {report}")

lo, hi = min_mb * 1024 * 1024, max_mb * 1024 * 1024
if not lo <= total_bytes <= hi:
    print(f"[size-budget] FALHA no gate: {total_bytes / (1024 * 1024):.2f} MB "
          f"fora de [{min_mb}, {max_mb}] MB (conteudo real do flagship entra "
          "no marco A6)", file=sys.stderr)
    sys.exit(1)
print(f"[size-budget] PASS: dentro do gate [{min_mb}, {max_mb}] MB")
PY
then
  exit 1
fi

exit 0
