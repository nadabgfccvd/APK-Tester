#!/usr/bin/env bash
# scripts/compat-nightly.sh
#
# Roda o RustyDroid (snapshot do CLI `rd` pinado por sha256 — ADR 0004)
# contra TODA a matriz e agrega o resultado em docs/compat-matrix.md.
# Answer key: contracts/engines/expected-engines.json.
#
# Escopo da matriz (R1.3, AUDIT_ROADMAP_V2):
#   1. os 32 engines da answer key — inspect + detect + match da answer key;
#   2. a escada minSdk 9..36 (12 degraus) — inspeção estrutural;
#   3. as fixtures de tortura de parser (11) — inspeção estrutural;
#   4. o flagship (variante classic no runner público) — inspeção estrutural.
#
# Contrato (R1.2):
#   - Bootstrap: sem `rd` no PATH, o script baixa o snapshot pinado do
#     release `rustydroid-cli-snapshot`, valida o sha256 PINADO aqui e
#     instala em $WORK_DIR/bin. Download ou integridade falhando = FAIL
#     explícito (nunca SKIP silencioso — o "se disponível" era mentira).
#   - Fixture sem APK construído: linha SEM_APK (não é FAIL).
#   - Qualquer FAIL (inspect, detect ou drift da answer key) => exit 1
#     (o CI abre issue fixture_gap).
#
# Diretórios de staging (R1.3; configuráveis por env para rodar local):
#   STAGING_LADDER    (padrão staging/compat/ladder)     — ladder-minsdk-NN.apk
#   STAGING_TORTURE   (padrão staging/compat/torture)    — torture-*.apk
#   STAGING_FLAGSHIP  (padrão staging/compat/flagship)   — flagship-*.apk
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_JSON="$REPO_ROOT/contracts/engines/expected-engines.json"
OUT_MD="$REPO_ROOT/docs/compat-matrix.md"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# Snapshot pinado do CLI RustyDroid (ADR 0004). Re-corte = re-dispatch do
# workflow rustydroid-snapshot.yml + novo sha256 aqui + nota no ADR.
RD_SNAPSHOT_URL="${RD_SNAPSHOT_URL:-https://github.com/nadabgfccvd/APK-Tester/releases/download/rustydroid-cli-snapshot/rd}"
RD_SHA256="${RD_SHA256:-5ff10a9e4b49183f0a54e3d9972997ff7b964e9a915b4194fe37f10501ef2bde}"

STAGING_LADDER="${STAGING_LADDER:-$REPO_ROOT/staging/compat/ladder}"
STAGING_TORTURE="${STAGING_TORTURE:-$REPO_ROOT/staging/compat/torture}"
STAGING_FLAGSHIP="${STAGING_FLAGSHIP:-$REPO_ROOT/staging/compat/flagship}"

if [ ! -f "$EXPECTED_JSON" ]; then
  echo "erro: answer key nao encontrada: $EXPECTED_JSON" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Bootstrap R1.2: garante `rd` no PATH (snapshot pinado, sha256 validado).
# Cache em $HOME/.cache/apk-tester para não re-baixar a cada repetição
# (o cheque flakiness do APKBot roda o script 3x por passe); a integridade
# é validada SEMPRE, inclusive no cache.
# ---------------------------------------------------------------------------
HAVE_RD=0
if command -v rd >/dev/null 2>&1; then
  HAVE_RD=1
  rd --help > /dev/null 2>&1 || true
fi

if [ "$HAVE_RD" -eq 0 ]; then
  CACHE_DIR="${RD_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/apk-tester}"
  mkdir -p "$CACHE_DIR" "$WORK_DIR/bin"
  DEST="$CACHE_DIR/rd"
  CACHED_OK=0
  if [ -f "$DEST" ]; then
    if echo "$RD_SHA256  $DEST" | sha256sum --check --status > /dev/null 2>&1; then
      CACHED_OK=1
    fi
  fi
  if [ "$CACHED_OK" -ne 1 ]; then
    echo "bootstrap: baixando snapshot do rustydroid (sha256 pinado)"
    if ! curl -fsSL --retry 3 --connect-timeout 20 \
         -o "$DEST.tmp" "$RD_SNAPSHOT_URL"; then
      echo "ERRO: download do snapshot rustydroid falhou" \
           "(R1.2: FAIL explícito, nunca SKIP)" >&2
      exit 1
    fi
    if ! echo "$RD_SHA256  $DEST.tmp" | sha256sum --check --status > /dev/null 2>&1; then
      echo "ERRO: sha256 do snapshot diverge do pin (integridade)" \
           "(esperado $RD_SHA256)" >&2
      rm -f "$DEST.tmp"
      exit 1
    fi
    mv "$DEST.tmp" "$DEST"
    chmod +x "$DEST"
    echo "bootstrap: install: OK (sha256 ${RD_SHA256:0:12}…)"
  else
    chmod +x "$DEST" 2> /dev/null || true
    echo "bootstrap: cache válido (sha256 ${RD_SHA256:0:12}…)"
  fi
  ln -sf "$DEST" "$WORK_DIR/bin/rd"
  PATH="$WORK_DIR/bin:$PATH"
  export PATH
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

# ---------------------------------------------------------------------------
# Seção 1: os 32 engines da answer key (inspect + detect + match).
# ---------------------------------------------------------------------------
while IFS=$'\t' read -r engine_id engine_dir engine_tier want_engines; do
  [ -n "$engine_id" ] || continue

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
    if rd inspect --json "$apk" > "$WORK_DIR/$engine_id.inspect.json" 2> "$log"; then
      if rd engine detect "$apk" > "$WORK_DIR/$engine_id.detect.txt" 2>> "$log"; then
        if WANT="$want_engines" DETECT_OUT="$WORK_DIR/$engine_id.detect.txt" python3 -c '
import os, re, sys
want = [w.strip() for w in os.environ.get("WANT", "").split(",") if w.strip()]
out = open(os.environ["DETECT_OUT"], encoding="utf-8",
           errors="replace").read()
# Answer key (R1.3): casa ids de registro em LINHAS do detector (row-start
# "id Signature/Candidate"), nunca substring solta no texto — o nome do
# pacote do fixture (engineNNnome) vaza na saida e mascarava drift.
present = set(re.findall(
    r"^([a-z][a-z0-9-]+)\s+(?:Signature|Candidate)\b", out, re.M))
missing = [w for w in want if w.lower() not in present]
if missing:
    print("detector nao casou: " + ", ".join(missing))
    sys.exit(1)
print("todos os engines esperados apareceram como linhas do detector")
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
      details="rd inspect --json falhou (log: $engine_id.log)"
      n_fail=$((n_fail + 1))
    fi
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$engine_id" "$engine_dir" "$engine_tier" "$status" "$details" >> "$RESULTS"
done < "$WORK_DIR/engines.tsv"

# ---------------------------------------------------------------------------
# Seções 2-4: escada + tortura + flagship (inspeção estrutural — sem
# answer key de engine; qualquer APK que o rd não abrir é FAIL).
# Dir de staging ausente = SEM_APK (o CI cria os dirs; checkout local não
# constrói as suites — honestidade sobre o estado, nunca SKIP).
# ---------------------------------------------------------------------------
inspect_section() {
  local section="$1" staging="$2" glob_label="$3"
  local apk status details
  if [ -d "$staging" ] && ls "$staging"/*.apk > /dev/null 2>&1; then
    for apk in "$staging"/*.apk; do
      local name
      name="$(basename "$apk" .apk)"
      if rd inspect --json "$apk" > "$WORK_DIR/x.inspect.json" 2> "$WORK_DIR/x.log"; then
        status="OK"
        details="inspect ok (estrutura parseada pelo rd)"
        n_ok=$((n_ok + 1))
      else
        status="FAIL"
        details="rd inspect --json falhou (log: x.log)"
        n_fail=$((n_fail + 1))
      fi
      printf '%s\t%s\textra\t%s\t%s\n' \
        "$name" "$section" "$status" "$details" >> "$RESULTS"
    done
  else
    status="SEM_APK"
    details="suite não construída neste checkout (R1.3: staging ausente)"
    n_noapk=$((n_noapk + 1))
    printf '%s\t%s\textra\t%s\t%s\n' \
      "$glob_label" "$section" "$status" "$details" >> "$RESULTS"
  fi
}

inspect_section "sdk-ladder" "$STAGING_LADDER" "sdk-ladder (12 degraus minSdk 9-36)"
inspect_section "parser-torture" "$STAGING_TORTURE" "parser-torture (11 fixtures)"
inspect_section "flagship" "$STAGING_FLAGSHIP" "flagship (variante classic)"

mkdir -p "$(dirname "$OUT_MD")"
{
  echo '# Matriz de compatibilidade — APK Tester x RustyDroid'
  echo
  # aspas simples INTENCIONAIS: backticks literais no markdown gerado
  # shellcheck disable=SC2016
  echo 'Gerada por `scripts/compat-nightly.sh` com o snapshot pinado do CLI `rd`'
  echo '(ADR 0004); answer key: `contracts/engines/expected-engines.json`.'
  echo
  echo '## Engines (answer key: inspect + detect + match)'
  echo
  echo '| Engine | Diretório | Tier | Resultado | Detalhes |'
  echo '|---|---|---|---|---|'
  while IFS=$'\t' read -r engine_id engine_dir engine_tier status details; do
    echo "| $engine_id | $engine_dir | $engine_tier | $status | $details |"
  done < "$RESULTS"
  echo
  echo '## Escada, tortura e flagship (inspeção estrutural)'
  echo
  echo '| APK | Seção | Resultado | Detalhes |'
  echo '|---|---|---|---|'
  while IFS=$'\t' read -r engine_id engine_dir engine_tier status details; do
    if [ "$engine_tier" = "extra" ]; then
      echo "| $engine_id | $engine_dir | $status | $details |"
    fi
  done < "$RESULTS"
  echo
  echo '## Resumo'
  echo
  echo "- OK: $n_ok"
  echo "- FAIL: $n_fail"
  echo "- SKIP: $n_skip (estruturalmente 0 desde R1.2: o bootstrap instala o"
  echo "  snapshot pinado; download/integridade falhando é FAIL, não SKIP)"
  echo "- SEM_APK (não construída): $n_noapk"
  echo
  echo '> Regra (ADR 0003): detecção não valida payload nem autoriza execução. FAIL aqui é drift de DETECÇÃO vs answer key ou APK que o parser não abriu, não falha de payload.'
} > "$OUT_MD"

cat "$OUT_MD"
echo
echo "resumo: OK=$n_ok FAIL=$n_fail SKIP=$n_skip SEM_APK=$n_noapk"

if [ "$n_fail" -gt 0 ]; then
  echo "compat-nightly: $n_fail FAIL — o CI deve abrir issue fixture_gap." >&2
  exit 1
fi

exit 0
