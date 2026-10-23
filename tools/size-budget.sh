#!/usr/bin/env bash
# tools/size-budget.sh — gate de tamanho do flagship + size-report.csv.
#
# Lista as entradas do APK (equivalente a unzip -l, via python3 zipfile inline)
# e classifica cada arquivo por extensão/magic em:
#   textures|meshes|shaders|audio|dex|arsc|so|locales|resources|other
# O total usa os tamanhos DESCOMPRIMIDOS das entradas (file_size do zip).
#
# Ordem de execução (A6-b):
#   1. escreve o CSV (category,bytes,files,sha256_of_apk) SEMPRE antes de
#      avaliar os gates — o CI pode coletar o artefato mesmo em falha;
#   2. gate 1 (total): falha (exit 1) se o total sair de [min,max] MB (MiB);
#      pulável com --no-gate (medição local de APKs pequenos de debug);
#   3. gate 2 (drift por categoria vs --baseline): falha (exit 1) se alguma
#      categoria (10 categorias + total) variar mais que ±2% vs o baseline.
#   Os dois gates são SEMPRE avaliados; qualquer falha => exit 1.
# APK ausente/corrompido ou erro de uso => exit 2.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK=""
MIN_MB=850
MAX_MB=1000
REPORT="$REPO_ROOT/contracts/flagship/size-report.csv"
BASELINE=""
NO_GATE=0

erro() { echo "erro: $*" >&2; exit 2; }

uso() {
  cat <<'USO'
uso: tools/size-budget.sh --apk PATH [--min-mb 850] [--max-mb 1000]
                          [--report CSV] [--baseline CSV] [--no-gate]

Gate de tamanho do APK flagship. Classifica cada entrada do zip por
extensão/magic em 10 categorias (textures|meshes|shaders|audio|dex|arsc|so|
locales|resources|other, tamanhos DESCOMPRIMIDOS), escreve o size-report.csv
e aplica dois gates. O relatório é escrito ANTES da avaliação — o CI pode
coletar o artefato (upload) mesmo quando um gate reprova.

Flags:
  --apk PATH      APK a medir (obrigatório).
  --min-mb N      limite inferior do gate do total, em MiB (padrão 850).
  --max-mb N      limite superior do gate do total, em MiB (padrão 1000).
  --report CSV    CSV de saída (category,bytes,files,sha256_of_apk); padrão:
                  contracts/flagship/size-report.csv.
  --baseline CSV  CSV anterior (mesmo formato) para checagem de drift POR
                  CATEGORIA (as 10 categorias + a linha total). Regra do ±2%:
                  drift = (novo - antigo) / antigo; reprova (exit 1) se
                  drift > +2% (crescimento) OU drift < -2% (encolhimento).
                    * categorias com bytes 0 no baseline são IGNORADAS (SKIP):
                      a primeira medição após o relatório zero do A0 não pode
                      reprovar (linha informativa é impressa);
                    * categoria presente em apenas um dos lados (só no
                      baseline ou só no relatório novo) reprova (FAIL);
                    * baseline informado mas inexistente no disco: drift
                      ignorado com aviso (bootstrap da primeira medição);
                    * a coluna sha256_of_apk é IGNORADA de propósito: a
                      assinatura e os metadados do zip variam entre
                      ambientes/empacotamentos — apenas bytes/files são
                      comparáveis entre relatórios.
  --no-gate       pula o gate [min,max] MiB (útil para medir APKs de debug
                  pequenos em diagnóstico local sem reprovar); o drift
                  continua ativo. --min-mb/--max-mb só valem com o gate ativo.

Exit codes: 0 = passou (gate e drift ok); 1 = falha de gate ou de drift
(mensagem "FALHA ..." no log); 2 = erro de uso ou APK ausente/corrompido.
USO
}

[ "${1:-}" = "--help" ] && { uso; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --apk) [ $# -ge 2 ] || erro "--apk exige caminho"; APK="$2"; shift 2 ;;
    --min-mb) [ $# -ge 2 ] || erro "--min-mb exige valor"; MIN_MB="$2"; shift 2 ;;
    --max-mb) [ $# -ge 2 ] || erro "--max-mb exige valor"; MAX_MB="$2"; shift 2 ;;
    --report) [ $# -ge 2 ] || erro "--report exige caminho"; REPORT="$2"; shift 2 ;;
    --baseline) [ $# -ge 2 ] || erro "--baseline exige caminho"; BASELINE="$2"; shift 2 ;;
    --no-gate) NO_GATE=1; shift ;;
    *) erro "flag desconhecida: $1 (use --help)" ;;
  esac
done

[ -n "$APK" ] || erro "--apk é obrigatório (use --help)"
[ -f "$APK" ] || erro "APK não encontrado: $APK"
case "$MIN_MB" in ''|*[!0-9]*) erro "--min-mb deve ser inteiro: $MIN_MB" ;; esac
case "$MAX_MB" in ''|*[!0-9]*) erro "--max-mb deve ser inteiro: $MAX_MB" ;; esac
[ "$MIN_MB" -le "$MAX_MB" ] || erro "--min-mb ($MIN_MB) maior que --max-mb ($MAX_MB)"

mkdir -p "$(dirname "$REPORT")"

# O python devolve: 0 = passou, 1 = falha de gate/drift, 2 = APK corrompido.
# O rc é capturado com "|| rc=$?" (e não com "if !") para o exit 2 do APK
# corrompido não virar 1 e a negação não corromper o "$?".
rc=0
APK_PATH="$APK" REPORT_PATH="$REPORT" MIN_MB="$MIN_MB" MAX_MB="$MAX_MB" \
    BASELINE_PATH="$BASELINE" NO_GATE="$NO_GATE" \
    python3 - <<'PY' || rc=$?
import csv
import hashlib
import os
import re
import sys
import zipfile

min_mb, max_mb = int(os.environ["MIN_MB"]), int(os.environ["MAX_MB"])
apk, report = os.environ["APK_PATH"], os.environ["REPORT_PATH"]
baseline = os.environ.get("BASELINE_PATH", "")
no_gate = os.environ.get("NO_GATE", "0") == "1"

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


def load_report(path: str) -> dict:
    """Le um size-report.csv (category,bytes,files,sha256_of_apk) via
    csv.DictReader e devolve {categoria: (bytes, arquivos)}.

    A coluna sha256_of_apk e IGNORADA de proposito: assinatura e metadados
    do zip variam entre ambientes/empacotamentos, portanto apenas
    bytes/files sao comparaveis entre relatorios.
    """
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        if not {"category", "bytes"} <= fields:
            raise ValueError("cabecalho invalido (esperado "
                             "category,bytes,files,sha256_of_apk)")
        for row in reader:
            cat = (row.get("category") or "").strip()
            if not cat:
                continue
            out[cat] = (int(row["bytes"]), int(row["files"] or 0))
    return out


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

# O relatorio fresco e escrito ANTES de qualquer gate: o CI pode coletar o
# artefato (upload) mesmo quando o gate ou o drift reprovam.
with open(report, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("category,bytes,files,sha256_of_apk\n")
    for cat in CATS:
        fh.write(f"{cat},{stats[cat][0]},{stats[cat][1]},{apk_sha}\n")
    fh.write(f"total,{total_bytes},{total_files},{apk_sha}\n")

print(f"[size-budget] APK: {apk}")
# sha256 informativo (muda com assinatura/metadados do zip entre ambientes);
# o drift NAO o compara — ver comentario em load_report().
print(f"[size-budget] sha256: {apk_sha}")
print(f"[size-budget] total: {total_bytes} bytes "
      f"({total_bytes / (1024 * 1024):.2f} MB) em {total_files} entradas "
      "(tamanhos descomprimidos)")
for cat in CATS:
    if stats[cat][1]:
        print(f"[size-budget]   {cat:<10} {stats[cat][0]:>15} bytes "
              f"{stats[cat][1]:>6} arquivos")
print(f"[size-budget] relatorio: {report}")

# ------------------------------------------------------------- gate 1: total
gate_fail = False
if no_gate:
    print("[size-budget] gate de tamanho IGNORADO (--no-gate)")
else:
    lo, hi = min_mb * 1024 * 1024, max_mb * 1024 * 1024
    if not lo <= total_bytes <= hi:
        print(f"[size-budget] FALHA no gate: {total_bytes / (1024 * 1024):.2f} MB "
              f"fora de [{min_mb}, {max_mb}] MB (conteudo real do flagship entra "
              "no marco A6)", file=sys.stderr)
        gate_fail = True
    else:
        print(f"[size-budget] PASS: dentro do gate [{min_mb}, {max_mb}] MB")

# --------------------------------------------- gate 2: drift por categoria
# Regra ±2%: drift = (novo - antigo) / antigo; reprova se drift > +2%
# (crescimento) ou drift < -2% (encolhimento). Baseline zero => SKIP
# (a primeira medicao apos o relatorio zero do A0 nao pode reprovar).
# Categoria em apenas um dos lados => FAIL (renome/queda silenciosa de
# categoria viola o contrato de 10 categorias + total).
drift_fail = False
if baseline:
    if not os.path.exists(baseline):
        print(f"[size-budget] baseline ausente ({baseline}): drift ignorado "
              "(primeira medicao antes do baseline existir?)")
    else:
        try:
            old = load_report(baseline)
            new = load_report(report)  # re-le o relatorio recem-escrito
        except (OSError, ValueError) as exc:
            print(f"[size-budget] erro: CSV de baseline/report invalido: {exc}",
                  file=sys.stderr)
            sys.exit(2)

        # Ordem contratual primeiro (10 categorias + total); qualquer linha
        # fora do contrato (se algum dia existir) vai ao fim, sem renomear.
        order = CATS + ["total"]
        seen = []
        for cat in order + list(old) + list(new):
            if cat not in seen:
                seen.append(cat)

        rows = []      # (categoria, antigo, novo, drift, status) p/ tabela
        skipped = []   # categorias com baseline zero (primeira medicao)
        n_ok = n_skip = n_fail = 0
        for cat in seen:
            o, n = old.get(cat), new.get(cat)
            if o is None:
                rows.append((cat, "-", str(n[0]), "n/a", "FAIL"))
                print(f"[size-budget] FALHA drift: categoria '{cat}' presente "
                      f"no novo relatorio ({n[0]} bytes) mas ausente no "
                      "baseline", file=sys.stderr)
                n_fail += 1
                drift_fail = True
            elif n is None:
                rows.append((cat, str(o[0]), "-", "n/a", "FAIL"))
                print(f"[size-budget] FALHA drift: categoria '{cat}' presente "
                      f"no baseline ({o[0]} bytes) mas ausente no novo "
                      "relatorio", file=sys.stderr)
                n_fail += 1
                drift_fail = True
            elif o[0] == 0:
                rows.append((cat, "0", str(n[0]), "n/a", "SKIP"))
                skipped.append(cat)
                n_skip += 1
            else:
                drift = (n[0] - o[0]) / o[0]
                status = "OK"
                if drift > 0.02 or drift < -0.02:
                    status = "FAIL"
                    print(f"[size-budget] FALHA drift: categoria '{cat}' foi "
                          f"de {o[0]} para {n[0]} bytes (drift {drift:+.2%}, "
                          "limite ±2.00%)", file=sys.stderr)
                    n_fail += 1
                    drift_fail = True
                else:
                    n_ok += 1
                rows.append((cat, str(o[0]), str(n[0]), f"{drift:+.2%}", status))

        print(f"[size-budget] drift por categoria vs baseline: {baseline} "
              "(limite ±2.00%; coluna sha256_of_apk ignorada)")
        print(f"[size-budget]   {'categoria':<12}{'antigo':>14}{'novo':>14}"
              f"{'drift':>10}  status")
        for cat, o_s, n_s, d_s, st in rows:
            print(f"[size-budget]   {cat:<12}{o_s:>14}{n_s:>14}{d_s:>10}  {st}")
        if skipped:
            print(f"[size-budget] SKIP (baseline com bytes 0, primeira "
                  f"medicao): {', '.join(skipped)}")
        print(f"[size-budget] resumo drift: {n_ok} OK, {n_skip} SKIP, "
              f"{n_fail} FAIL")

# Os dois gates rodam sempre; a falha mais grave define o exit (qualquer
# falha => 1), mas o log mostra todos os problemas de uma vez.
if gate_fail or drift_fail:
    sys.exit(1)
print("[size-budget] PASS: gate e drift OK")
PY

exit "$rc"
