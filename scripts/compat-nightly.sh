#!/usr/bin/env bash
# scripts/compat-nightly.sh
#
# Roda o RustyDroid contra cada fixture de engine e agrega o resultado em
# docs/compat-matrix.md. Answer key: contracts/engines/expected-engines.json.
#
# Contrato:
#   - Sem `rustydroid` no PATH: TODAS as linhas viram SKIP e o script sai 0
#     (permite rodar limpo hoje, antes de A4/A7 instalarem o runtime no CI).
#   - Fixture sem APK construído: linha SEM_APK (não é FAIL).
#   - Qualquer FAIL (inspect ou detect) => exit 1 (o CI abre issue fixture_gap).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_JSON="$REPO_ROOT/contracts/engines/expected-engines.json"
OUT_MD="$REPO_ROOT/docs/compat-matrix.md"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

if [ ! -f "$EXPECTED_JSON" ]; then
  echo "erro: answer key nao encontrada: $EXPECTED_JSON" >&2
  exit 1
fi

HAVE_RUSTYDROID=0
if command -v rustydroid >/dev/null 2>&1; then
  HAVE_RUSTYDROID=1
fi

HAVE_RD=0
if command -v rd >/dev/null 2>&1; then
  HAVE_RD=1
fi

# Deserializa a answer key: id \t dir \t tier \t engines-esperados (csv)
EXPECTED_JSON="$EXPECTED_JSON" python3 -c '
import json, os
data = json.load(open(os.environ["EXPECTED_JSON"], encoding="utf-8"))
for e in data["engines"]:
    print("\t".join([
        e["id"],
        e["dir"],
        e.get("tier", "?"),
        ",".join(e.get("rustydroid_engines", [])),
    ]))
' > "$WORK_DIR/engines.tsv"

RESULTS="$WORK_DIR/results.tsv"
: > "$RESULTS"

n_ok=0
n_fail=0
n_skip=0
n_noapk=0

while IFS=$'\t' read -r engine_id engine_dir engine_tier want_engines; do
  [ -n "$engine_id" ] || continue

  status="SKIP"
  details="sem rustydroid no PATH (fixture nao exercitada)"

  if [ "$HAVE_RUSTYDROID" -eq 1 ]; then
    apk=""
    for cand in \
      "$REPO_ROOT/suites/engines/$engine_dir/dist/app.apk" \
      "$REPO_ROOT/suites/engines/$engine_dir/dist/$engine_dir.apk" \
      "$REPO_ROOT/suites/engines/$engine_dir/$engine_dir.apk" \
      "$REPO_ROOT/suites/engines/$engine_dir.apk"; do
      if [ -f "$cand" ]; then
        apk="$cand"
        break
      fi
    done

    if [ -z "$apk" ]; then
      status="SEM_APK"
      details="fixture ainda nao construida (A3/A4/A7)"
      n_noapk=$((n_noapk + 1))
    else
      log="$WORK_DIR/$engine_id.log"
      if rustydroid inspect --json "$apk" > "$WORK_DIR/$engine_id.inspect.json" 2> "$log"; then
        if [ "$HAVE_RD" -eq 0 ]; then
          status="SKIP"
          details="inspect ok; rd (engine detect) ausente no PATH"
          n_skip=$((n_skip + 1))
        elif rd engine detect "$apk" > "$WORK_DIR/$engine_id.detect.txt" 2>> "$log"; then
          if WANT="$want_engines" DETECT_OUT="$WORK_DIR/$engine_id.detect.txt" python3 -c '
import os, sys
want = [w.strip() for w in os.environ.get("WANT", "").split(",") if w.strip()]
out = open(os.environ["DETECT_OUT"], encoding="utf-8", errors="replace").read().lower()
missing = [w for w in want if w.lower() not in out]
if missing:
    print("detector nao casou: " + ", ".join(missing))
    sys.exit(1)
print("todos os engines esperados apareceram na saida do detector")
'; then
            status="OK"
            details="inspect ok + detect ok (answer key casada)"
            n_ok=$((n_ok + 1))
          else
            status="FAIL"
            details="drift do detector vs expected-engines.json (log: $engine_id.log)"
            n_fail=$((n_fail + 1))
          fi
        else
          status="FAIL"
          details="rd engine detect falhou (log: $engine_id.log)"
          n_fail=$((n_fail + 1))
        fi
      else
        status="FAIL"
        details="rustydroid inspect --json falhou (log: $engine_id.log)"
        n_fail=$((n_fail + 1))
      fi
    fi
  else
    n_skip=$((n_skip + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' "$engine_id" "$engine_dir" "$engine_tier" "$status" "$details" >> "$RESULTS"
done < "$WORK_DIR/engines.tsv"

mkdir -p "$(dirname "$OUT_MD")"
{
  echo '# Matriz de compatibilidade — APK Tester x RustyDroid'
  echo
  # aspas simples INTENCIONAIS: backticks literais no markdown gerado
  # shellcheck disable=SC2016
  echo 'Gerada por `scripts/compat-nightly.sh`; answer key: `contracts/engines/expected-engines.json`.'
  echo
  echo '| Engine | Diretório | Tier | Resultado | Detalhes |'
  echo '|---|---|---|---|---|'
  while IFS=$'\t' read -r engine_id engine_dir engine_tier status details; do
    echo "| $engine_id | $engine_dir | $engine_tier | $status | $details |"
  done < "$RESULTS"
  echo
  echo '## Resumo'
  echo
  echo "- OK: $n_ok"
  echo "- FAIL: $n_fail"
  echo "- SKIP (sem rustydroid/rd): $n_skip"
  echo "- SEM_APK (fixture não construída): $n_noapk"
  echo
  echo '> Regra (ADR 0003): detecção não valida payload nem autoriza execução. FAIL aqui é drift de DETECÇÃO vs answer key, não falha de payload.'
} > "$OUT_MD"

cat "$OUT_MD"
echo
echo "resumo: OK=$n_ok FAIL=$n_fail SKIP=$n_skip SEM_APK=$n_noapk"

if [ "$n_fail" -gt 0 ]; then
  echo "compat-nightly: $n_fail FAIL — o CI deve abrir issue fixture_gap." >&2
  exit 1
fi

exit 0
