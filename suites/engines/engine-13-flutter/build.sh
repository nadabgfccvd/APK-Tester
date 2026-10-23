#!/usr/bin/env bash
# build real do engine-13-flutter (Tier B, A7) — delega para o orquestrador comum.
# A toolchain pesada e pinada é baixada da fonte oficial pelo próprio
# tools/build-tier-b.py; builds reais rodam no engines-nightly.yml (ADR 0002).
# Sem rede/toolchain, use --plan-only (emite o plano JSON, exit 0).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
exec python3 tools/build-tier-b.py --engine "engine-13-flutter" "$@"
