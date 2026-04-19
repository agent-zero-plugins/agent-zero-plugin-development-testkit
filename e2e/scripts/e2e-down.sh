#!/usr/bin/env bash
# Tear down the hermetic A0 instance + wipe per-run state.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TESTKIT_E2E_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_BASE="$TESTKIT_E2E_DIR/compose-base.yml"

CONSUMER_ROOT="${CONSUMER_ROOT:?CONSUMER_ROOT is required}"
E2E_DIR="$CONSUMER_ROOT/tests/e2e/.e2e"

declare -a COMPOSE_FILES=(-f "$COMPOSE_BASE")
if [[ -n "${E2E_COMPOSE_OVERRIDES:-}" ]]; then
  for override in $E2E_COMPOSE_OVERRIDES; do
    [[ "$override" != /* ]] && override="$CONSUMER_ROOT/$override"
    COMPOSE_FILES+=(-f "$override")
  done
fi

docker compose "${COMPOSE_FILES[@]}" down -v --remove-orphans

rm -rf "$E2E_DIR"
echo "[e2e-down] stopped + cleaned"
