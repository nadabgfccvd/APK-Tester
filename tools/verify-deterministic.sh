#!/usr/bin/env bash
# tools/verify-deterministic.sh — prova de determinismo do APK Tester.
#
# Modo generators: roda cada tools/gen-*.py DUAS vezes (mesmo --seed) em dois
# mktemp dirs e compara a lista ordenada de sha256sum de TODOS os arquivos
# (manifest.json + artefatos). PASS/FAIL em PT-BR por ferramenta; exit 1 se
# qualquer FAIL.
#
# Modo apk: compara dois APKs entrada a entrada (python3 zipfile inline),
# IGNORANDO META-INF/* (assinatura/mtimes não afetam o conteúdo). PASS/FAIL.
#
# Nota: alguns geradores têm workload pesado por padrão (ex.: gen-textures
# 4096x4096); o modo generators usa args de redução de carga que NÃO alteram
# a semântica do seed — apenas encolhem o workload para rodar rápido no CI.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEED=20261022
MODE=""
APK1=""
APK2=""

erro() { echo "erro: $*" >&2; exit 2; }

usage() {
  echo "uso: tools/verify-deterministic.sh --mode generators [--seed N]"
  echo "     tools/verify-deterministic.sh --mode apk --apk1 PATH --apk2 PATH"
}

[ $# -eq 0 ] && { usage >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --mode) [ $# -ge 2 ] || erro "--mode exige valor"; MODE="$2"; shift 2 ;;
    --seed) [ $# -ge 2 ] || erro "--seed exige valor"; SEED="$2"; shift 2 ;;
    --apk1) [ $# -ge 2 ] || erro "--apk1 exige caminho"; APK1="$2"; shift 2 ;;
    --apk2) [ $# -ge 2 ] || erro "--apk2 exige caminho"; APK2="$2"; shift 2 ;;
    --help) usage; exit 0 ;;
    *) erro "flag desconhecida: $1 (use --help)" ;;
  esac
done

turbo_args() {
  # Redução de carga por ferramenta (não altera determinismo do seed).
  case "$1" in
    gen-textures.py) printf '%s\n' "--size" "64" ;;
    gen-meshes.py) printf '%s\n' "--terrain-res" "32" "--crowd" "200" \
                           "--profile-samples" "3" "--radial" "8" ;;
    gen-buttons.py) printf '%s\n' "--buttons" "32" "--icons" "16" ;;
    gen-strings.py) printf '%s\n' "--buttons" "32" ;;
    *) : ;;
  esac
}

# Lista estável "caminho sha256" de todos os arquivos de um diretório.
sha_list() {
  (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum)
}

case "$MODE" in
  generators)
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    shopt -s nullglob
    TOOLS=("$REPO_ROOT"/tools/gen-*.py)
    shopt -u nullglob
    [ "${#TOOLS[@]}" -gt 0 ] || { echo "erro: nenhum tools/gen-*.py" >&2; exit 1; }
    N_PASS=0
    N_FAIL=0
    for t in "${TOOLS[@]}"; do
      name="$(basename "$t")"
      dir_a="$TMP/${name%.py}-a"
      dir_b="$TMP/${name%.py}-b"
      mapfile -t EXTRA < <(turbo_args "$name")
      ok=1
      for side in a b; do
        dir="$dir_a"
        [ "$side" = "b" ] && dir="$dir_b"
        if ! python3 "$t" --out "$dir" --seed "$SEED" \
             ${EXTRA[@]+"${EXTRA[@]}"} > "$TMP/$name.$side.log" 2>&1; then
          echo "[verify-deterministic] FAIL $name: geracao $side falhou" \
               "(ultimas linhas do log:)"
          tail -n 3 "$TMP/$name.$side.log" | sed 's/^/    /' >&2
          ok=0
        fi
      done
      if [ "$ok" -eq 1 ]; then
        sha_list "$dir_a" > "$TMP/$name.a.sha"
        sha_list "$dir_b" > "$TMP/$name.b.sha"
        if diff -u "$TMP/$name.a.sha" "$TMP/$name.b.sha" \
            > "$TMP/$name.diff" 2>&1; then
          n_files="$(wc -l < "$TMP/$name.a.sha" | tr -d ' ')"
          echo "[verify-deterministic] PASS $name ($n_files arquivos " \
               "identicos nas duas execucoes, seed=$SEED)"
          N_PASS=$((N_PASS + 1))
        else
          echo "[verify-deterministic] FAIL $name: listas de sha256 divergem" \
               "(primeiras linhas do diff:)"
          head -n 6 "$TMP/$name.diff" | sed 's/^/    /' >&2
          N_FAIL=$((N_FAIL + 1))
        fi
      else
        N_FAIL=$((N_FAIL + 1))
      fi
    done
    echo "[verify-deterministic] resumo: PASS=$N_PASS FAIL=$N_FAIL"
    if [ "$N_FAIL" -gt 0 ]; then
      echo "verify-deterministic: determinismo QUEBRADO em $N_FAIL gerador(es)." >&2
      exit 1
    fi
    exit 0
    ;;
  apk)
    [ -n "$APK1" ] || erro "--mode apk exige --apk1"
    [ -n "$APK2" ] || erro "--mode apk exige --apk2"
    [ -f "$APK1" ] || erro "APK nao encontrado: $APK1"
    [ -f "$APK2" ] || erro "APK nao encontrado: $APK2"
    if ! python3 - "$APK1" "$APK2" <<'PY'
import hashlib
import sys
import zipfile


def entry_hashes(path: str) -> dict:
    out = {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("META-INF/"):
                continue
            h = hashlib.sha256()
            with zf.open(info) as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            out[info.filename] = h.hexdigest()
    return out


a, b = entry_hashes(sys.argv[1]), entry_hashes(sys.argv[2])
only_a = sorted(set(a) - set(b))
only_b = sorted(set(b) - set(a))
changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
print(f"[verify-deterministic] entradas comparadas (META-INF/* ignorado): "
      f"A={len(a)} B={len(b)}")
if not only_a and not only_b and not changed:
    print("[verify-deterministic] PASS: conteudo identico entrada a entrada")
    sys.exit(0)
for k in only_a[:10]:
    print(f"    so-em-apk1: {k}")
for k in only_b[:10]:
    print(f"    so-em-apk2: {k}")
for k in changed[:10]:
    print(f"    divergente: {k}")
print(f"[verify-deterministic] FAIL: {len(only_a)} novas, {len(only_b)} "
      f"ausentes, {len(changed)} divergentes", file=sys.stderr)
sys.exit(1)
PY
    then
      exit 1
    fi
    exit 0
    ;;
  *)
    usage >&2
    erro "modo inválido '$MODE' (generators|apk)"
    ;;
esac
