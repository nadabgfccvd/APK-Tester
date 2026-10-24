#!/usr/bin/env bash
# scripts/pack-tier-c.sh — empacota e verifica as 9 fixtures Tier C (A3).
#
# Laço compartilhado pelos workflows ci.yml, engines-nightly.yml e
# release.yml (A9/roadmap 5.5: o mesmo pipeline de empacotamento estava
# duplicado nos três arquivos — qualquer mudança precisava ser editada em
# triplicata). Para cada engine Tier C:
#   1. tools/fixture-pack.py --fixture E --out OUT_DIR (aapt2+d8+apksigner
#      do toolchain real do SDK);
#   2. tools/gen-engine-fixtures.py --verify-apk OUT_DIR/E.apk --engine E
#      (contratos de detecção + âncora sha256 do payload).
#
# Uso: scripts/pack-tier-c.sh OUT_DIR [BT_DIR]
#   OUT_DIR  destino dos .apk (criado se não existir; ex.: dist)
#   BT_DIR   diretório de build-tools com aapt2/d8/apksigner/zipalign
#            (default: ${ANDROID_HOME}/build-tools/35.0.0)
# Exit != 0 na primeira falha de empacotamento OU verificação.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TIER_C_ENGINES=(
  engine-05-clojure
  engine-11-objc
  engine-18-maui-xamarin
  engine-19-unity-mono
  engine-20-unity-il2cpp
  engine-21-unreal
  engine-27-b4x-appinventor
  engine-29-python-kivy-beeware
  engine-32-twa-pwa
)

OUT_DIR="${1:?uso: pack-tier-c.sh OUT_DIR [BT_DIR]}"
BT_DIR="${2:-${ANDROID_HOME}/build-tools/35.0.0}"

for tool in aapt2 d8 apksigner zipalign; do
  test -x "${BT_DIR}/${tool}" || {
    echo "erro: ${BT_DIR}/${tool} não existe/executável" >&2
    exit 2
  }
done

mkdir -p "${OUT_DIR}"

for e in "${TIER_C_ENGINES[@]}"; do
  echo "[pack-tier-c] empacotando ${e}..."
  python3 "${REPO_ROOT}/tools/fixture-pack.py" --fixture "${e}" \
    --out "${OUT_DIR}" \
    --aapt2 "${BT_DIR}/aapt2" --d8 "${BT_DIR}/d8" \
    --apksigner "${BT_DIR}/apksigner" --zipalign "${BT_DIR}/zipalign"
  echo "[pack-tier-c] verificando ${e} contra o contrato..."
  python3 "${REPO_ROOT}/tools/gen-engine-fixtures.py" \
    --verify-apk "${OUT_DIR}/${e}.apk" --engine "${e}"
done

echo "[pack-tier-c] OK: ${#TIER_C_ENGINES[@]} fixtures Tier C empacotadas " \
     "e verificadas em ${OUT_DIR}"
