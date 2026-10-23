#!/usr/bin/env bash
# build real do engine-31-hybrid (Tier A, A4) — delega para o orquestrador comum.
# Toolchains: tools/setup-tier-a-toolchain.sh engine-31-hybrid
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
exec python3 tools/build-tier-a.py --engine "engine-31-hybrid" "$@"
