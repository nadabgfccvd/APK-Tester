#!/usr/bin/env bash
# tools/build-variants.sh — orquestra os flavors do flagship e as builds de engines.
#
# Contrato:
#   - Flagship: se suites/flagship/gradlew existir -> ./gradlew :app:assemble<Flavor>Release;
#     senão degrada para o plano canônico via tools/fixture-pack.py --dry-run
#     (proxy modo minSdk9; a build gradle real do flagship chega no marco A1).
#   - Engines: dirs vindos de contracts/engines/expected-engines.json; com
#     build.sh/gradlew executáveis roda de verdade; sem script -> PLANEJADO
#     (fixtures Tier C são empacotadas por tools/fixture-pack.py nos marcos A3/A4).
#   - Sem toolchain o script NUNCA falha em modo --dry-run (roda limpo hoje).
#   - Códigos de saída: 0 ok/planejado; 1 falha de build real; 2 argumento ruim.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_PACK="$REPO_ROOT/tools/fixture-pack.py"
EXPECTED_JSON="$REPO_ROOT/contracts/engines/expected-engines.json"
PLAN_OUT_BASE="${TMPDIR:-/tmp}/apktester-build-variants"

FLAVOR="all"
ENGINE="all"
DRY_RUN=0
N_OK=0
N_PLAN=0
N_FAIL=0

erro() { echo "erro: $*" >&2; exit 2; }

[ "${1:-}" = "--help" ] && {
  echo "uso: tools/build-variants.sh [--flavor classic|modern|all] [--engine engine-NN-slug|all] [--dry-run]"
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --flavor) [ $# -ge 2 ] || erro "--flavor exige valor"; FLAVOR="$2"; shift 2 ;;
    --engine) [ $# -ge 2 ] || erro "--engine exige valor"; ENGINE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) erro "flag desconhecida: $1 (use --help)" ;;
  esac
done

case "$FLAVOR" in
  classic|modern|all) ;;
  *) erro "flavor inválida '$FLAVOR' (classic|modern|all)" ;;
esac

[ -f "$FIXTURE_PACK" ] || { echo "erro: $FIXTURE_PACK ausente" >&2; exit 1; }
[ -f "$EXPECTED_JSON" ] || { echo "erro: answer key ausente: $EXPECTED_JSON" >&2; exit 1; }

mapfile -t ALL_ENGINE_DIRS < <(python3 - "$EXPECTED_JSON" <<'PY'
import json, sys
for e in json.load(open(sys.argv[1], encoding="utf-8"))["engines"]:
    print(e["dir"])
PY
)
[ "${#ALL_ENGINE_DIRS[@]}" -gt 0 ] || { echo "erro: expected-engines.json sem engines" >&2; exit 1; }

build_flagship() {
  local flavors f cap
  case "$FLAVOR" in
    all) flavors="classic modern" ;;
    *) flavors="$FLAVOR" ;;
  esac
  for f in $flavors; do
    cap="${f^}"  # classic -> Classic
    if [ -x "$REPO_ROOT/suites/flagship/gradlew" ]; then
      echo "[build-variants] flagship flavor $f: ./gradlew :app:assemble${cap}Release"
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "[build-variants]   (dry-run) comando planejado, não executado"
        N_OK=$((N_OK + 1))
      elif (cd "$REPO_ROOT/suites/flagship" && ./gradlew ":app:assemble${cap}Release"); then
        N_OK=$((N_OK + 1))
      else
        echo "[build-variants]   FALHA na build gradle do flavor $f" >&2
        N_FAIL=$((N_FAIL + 1))
      fi
    else
      echo "[build-variants] flagship flavor $f: gradlew ausente — delegando plano" \
           "canônico ao fixture-pack.py (proxy modo minSdk9; build gradle real no marco A1)"
      mkdir -p "$PLAN_OUT_BASE/flagship-$f"
      if python3 "$FIXTURE_PACK" --fixture minSdk9 --dry-run \
          --out "$PLAN_OUT_BASE/flagship-$f" > "$PLAN_OUT_BASE/flagship-$f/plan.json"; then
        echo "[build-variants]   plano emitido: $PLAN_OUT_BASE/flagship-$f/plan.json"
        N_PLAN=$((N_PLAN + 1))
      else
        echo "[build-variants]   FALHA ao emitir plano do fixture-pack" >&2
        N_FAIL=$((N_FAIL + 1))
      fi
    fi
  done
}

build_engines() {
  local dirs=() d dp
  if [ "$ENGINE" != "all" ]; then
    printf '%s\n' "${ALL_ENGINE_DIRS[@]}" | grep -Fxq "$ENGINE" \
      || erro "engine desconhecida '$ENGINE' (veja contracts/engines/expected-engines.json)"
    dirs=("$ENGINE")
  else
    dirs=("${ALL_ENGINE_DIRS[@]}")
  fi
  for d in "${dirs[@]}"; do
    dp="$REPO_ROOT/suites/engines/$d"
    if [ -x "$dp/build.sh" ]; then
      echo "[build-variants] engine $d: ./build.sh"
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "[build-variants]   (dry-run) comando planejado, não executado"
        N_OK=$((N_OK + 1))
      elif (cd "$dp" && ./build.sh); then
        N_OK=$((N_OK + 1))
      else
        echo "[build-variants]   FALHA na build de $d" >&2
        N_FAIL=$((N_FAIL + 1))
      fi
    elif [ -x "$dp/gradlew" ]; then
      echo "[build-variants] engine $d: ./gradlew (dry-run=$DRY_RUN)"
      if [ "$DRY_RUN" -eq 1 ]; then
        N_OK=$((N_OK + 1))
      elif (cd "$dp" && ./gradlew assembleRelease); then
        N_OK=$((N_OK + 1))
      else
        echo "[build-variants]   FALHA na build de $d" >&2
        N_FAIL=$((N_FAIL + 1))
      fi
    else
      echo "[build-variants] engine $d: PLANEJADO (sem build script; fixture Tier C" \
           "empacotada por tools/fixture-pack.py nos marcos A3/A4)"
      N_PLAN=$((N_PLAN + 1))
    fi
  done
}

echo "[build-variants] inicio (flavor=$FLAVOR engine=$ENGINE dry-run=$DRY_RUN)"
build_flagship
build_engines
echo "[build-variants] resumo: OK=$N_OK PLANEJADO=$N_PLAN FALHA=$N_FAIL"

if [ "$N_FAIL" -gt 0 ]; then
  echo "build-variants: $N_FAIL build(s) com falha." >&2
  exit 1
fi
exit 0
