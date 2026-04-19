#!/usr/bin/env bash
# Bring up a hermetic A0 instance for e2e tests — generic harness,
# called from consumer plugin repos via `make e2e-up` (which delegates
# to this script through tests/_testkit/e2e/Makefile.e2e).
#
# Consumer-facing env vars (all optional, sensible defaults):
#
#   CONSUMER_ROOT              absolute path of the plugin repo root
#                              (required; Makefile.e2e passes $(CURDIR))
#   E2E_COMPOSE_OVERRIDES      space-separated paths to extra compose files
#                              (e.g. docker/e2e.compose.override.yml)
#   E2E_PLUGIN_SETTINGS_JSON   path to a JSON file with plugin-specific
#                              settings to seed into /a0/usr/settings.json
#                              (e.g. {"plugin_livekit":{"livekit_rtc_tcp_port":50013}})
#   E2E_EXTRA_PORTS            space-separated "host:container" publishes
#                              to verify free + expose additionally
#                              (LiveKit plugin uses "50013:50013")
#   A0_IMAGE                   override the A0 docker image
#                              (default: agent0ai/agent-zero:latest)
#   A0_HTTP_PORT / A0_SSH_PORT override the base HTTP/SSH ports
#                              (default: 50011 / 50012)
#   AUTH_LOGIN / AUTH_PASSWORD override creds (default: admin / admin)
#   MCP_SERVER_TOKEN           override the per-run token
#                              (default: random 32 hex chars)
#
# The script:
#   1. Fail-fast if any required port is busy (base 50011+50012 plus any
#      hosts declared in E2E_EXTRA_PORTS).
#   2. Assemble the /a0/usr/settings.json JSON (base + plugin fragment).
#   3. Compose up with the base + any overrides.
#   4. Wait for the healthcheck.
#   5. Write <CONSUMER_ROOT>/tests/e2e/.e2e/instance.env so Playwright's
#      global-setup reads the base URL + creds.
#
# Idempotent: if the container is already running AND healthy, skip up
# and just re-write instance.env.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TESTKIT_E2E_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_BASE="$TESTKIT_E2E_DIR/compose-base.yml"

CONSUMER_ROOT="${CONSUMER_ROOT:?CONSUMER_ROOT (plugin repo root) is required}"
E2E_DIR="$CONSUMER_ROOT/tests/e2e/.e2e"
INSTANCE_ENV="$E2E_DIR/instance.env"

# ── Defaults ──────────────────────────────────────────────────────────────
A0_HTTP_PORT="${A0_HTTP_PORT:-50011}"
A0_SSH_PORT="${A0_SSH_PORT:-50012}"
A0_IMAGE="${A0_IMAGE:-agent0ai/agent-zero:latest}"
A0_CONTAINER_NAME="${A0_CONTAINER_NAME:-a0-e2e}"
AUTH_LOGIN="${AUTH_LOGIN:-admin}"
AUTH_PASSWORD="${AUTH_PASSWORD:-admin}"
MCP_SERVER_TOKEN="${MCP_SERVER_TOKEN:-$(openssl rand -hex 16)}"
PIP_CACHE_HOST_DIR="${PIP_CACHE_HOST_DIR:-$CONSUMER_ROOT/.e2e-cache/pip}"
mkdir -p "$PIP_CACHE_HOST_DIR"

# ── Port probe ────────────────────────────────────────────────────────────
port_free() {
  python3 - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", port))
    sys.exit(0)
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

probe_or_die() {
  local port="$1" label="$2"
  if ! port_free "$port"; then
    echo >&2 "[e2e-up] PORT $port ($label) is busy."
    echo >&2 "[e2e-up]   -> $(lsof -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2 | head -1 || echo 'run: lsof -i :'"$port")"
    exit 2
  fi
}

# Collect the host ports to publish and probe. Start with the base
# A0 HTTP + SSH. Add any plugin extras declared via E2E_EXTRA_PORTS.
declare -a EXTRA_PORT_ARGS=()
if [[ -n "${E2E_EXTRA_PORTS:-}" ]]; then
  for mapping in $E2E_EXTRA_PORTS; do
    # Expect "host:container" or just "n" (same both sides).
    host_port="${mapping%%:*}"
    EXTRA_PORT_ARGS+=(-p "$mapping")
    # Defer the probe until after the early-out check below.
  done
fi

# ── Early-out: already running + healthy? ─────────────────────────────────
# Build the full compose -f chain up front so every invocation uses the
# same overlay set.
declare -a COMPOSE_FILES=(-f "$COMPOSE_BASE")
if [[ -n "${E2E_COMPOSE_OVERRIDES:-}" ]]; then
  for override in $E2E_COMPOSE_OVERRIDES; do
    # Resolve relative paths relative to the consumer root.
    if [[ "$override" != /* ]]; then
      override="$CONSUMER_ROOT/$override"
    fi
    COMPOSE_FILES+=(-f "$override")
  done
fi

compose_id() { docker compose "${COMPOSE_FILES[@]}" ps -q agent-zero 2>/dev/null | head -1; }

CID="$(compose_id || true)"
if [[ -n "${CID:-}" ]]; then
  STATUS="$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo unknown)"
  if [[ "$STATUS" == "healthy" ]]; then
    echo "[e2e-up] already running + healthy (container $CID); skipping up"
    SKIP_UP=1
  fi
fi

if [[ -z "${SKIP_UP:-}" ]]; then
  probe_or_die "$A0_HTTP_PORT" "A0 HTTP"
  probe_or_die "$A0_SSH_PORT" "A0 SSH"
  if [[ -n "${E2E_EXTRA_PORTS:-}" ]]; then
    for mapping in $E2E_EXTRA_PORTS; do
      host_port="${mapping%%:*}"
      probe_or_die "$host_port" "plugin extra ($mapping)"
    done
  fi

  # ── Build the /a0/usr/settings.json seed host-side ─────────────────────
  # Base = mcp_server_token; consumer plugins can merge in their own
  # top-level keys (typically a "plugin_<name>": {...} block) via a JSON
  # file at E2E_PLUGIN_SETTINGS_JSON.
  BASE_SETTINGS=$(printf '{"mcp_server_token":"%s"}' "$MCP_SERVER_TOKEN")
  if [[ -n "${E2E_PLUGIN_SETTINGS_JSON:-}" && -f "$E2E_PLUGIN_SETTINGS_JSON" ]]; then
    A0_SEEDED_SETTINGS_JSON=$(
      python3 - "$MCP_SERVER_TOKEN" "$E2E_PLUGIN_SETTINGS_JSON" <<'PY'
import json, sys
token, plugin_file = sys.argv[1], sys.argv[2]
base = {"mcp_server_token": token}
with open(plugin_file) as fh:
    plugin = json.load(fh)
base.update(plugin)
print(json.dumps(base))
PY
    )
  else
    A0_SEEDED_SETTINGS_JSON="$BASE_SETTINGS"
  fi

  echo "[e2e-up] base ports $A0_HTTP_PORT/$A0_SSH_PORT + extras [${E2E_EXTRA_PORTS:-none}] free"
  echo "[e2e-up] AUTH_LOGIN=$AUTH_LOGIN  mcp_token=${MCP_SERVER_TOKEN:0:8}..."

  export A0_HTTP_PORT A0_SSH_PORT A0_IMAGE A0_CONTAINER_NAME
  export AUTH_LOGIN AUTH_PASSWORD MCP_SERVER_TOKEN
  export A0_SEEDED_SETTINGS_JSON
  export PIP_CACHE_HOST_DIR

  # Bring the stack up. Extra ports are passed via a throwaway override
  # yaml because `docker compose up` doesn't accept -p port mappings.
  if [[ ${#EXTRA_PORT_ARGS[@]} -gt 0 ]]; then
    TMP_PORTS_OVERRIDE=$(mktemp --suffix=.yml)
    {
      printf 'services:\n  agent-zero:\n    ports:\n'
      for mapping in $E2E_EXTRA_PORTS; do printf '      - "%s"\n' "$mapping"; done
    } > "$TMP_PORTS_OVERRIDE"
    trap 'rm -f "$TMP_PORTS_OVERRIDE"' EXIT
    COMPOSE_FILES+=(-f "$TMP_PORTS_OVERRIDE")
  fi

  docker compose "${COMPOSE_FILES[@]}" up -d
fi

# ── Wait for healthcheck ──────────────────────────────────────────────────
echo "[e2e-up] waiting for healthcheck..."
CID="$(compose_id)"
[[ -n "$CID" ]] || { echo >&2 "[e2e-up] container not found after compose up"; exit 3; }

for _ in $(seq 1 80); do
  STATUS="$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo unknown)"
  [[ "$STATUS" == "healthy" ]] && { echo "[e2e-up] healthy"; break; }
  [[ "$STATUS" == "unhealthy" ]] && {
    echo >&2 "[e2e-up] container unhealthy — recent logs:"
    docker logs --tail 40 "$CID" >&2 || true
    exit 4
  }
  sleep 3
done

if [[ "$STATUS" != "healthy" ]]; then
  echo >&2 "[e2e-up] timed out; status=$STATUS"
  docker logs --tail 40 "$CID" >&2 || true
  exit 5
fi

# ── Write instance.env for Playwright globalSetup ────────────────────────
mkdir -p "$E2E_DIR"
{
  echo "# Generated by testkit e2e-up.sh — do not edit."
  echo "# Consumed by tests/e2e/global-setup.ts on every playwright run."
  echo "A0_BASE_URL=http://localhost:$A0_HTTP_PORT"
  echo "A0_USERNAME=$AUTH_LOGIN"
  echo "A0_PASSWORD=$AUTH_PASSWORD"
  echo "A0_MCP_SERVER_TOKEN=$MCP_SERVER_TOKEN"
  # Consumer plugins can export additional key=value lines via
  # E2E_INSTANCE_ENV_EXTRA (multiline). Appended verbatim so specs
  # read plugin-specific values (e.g. A0_LK_RTC_TCP_PORT=50013).
  if [[ -n "${E2E_INSTANCE_ENV_EXTRA:-}" ]]; then
    printf '%s\n' "$E2E_INSTANCE_ENV_EXTRA"
  fi
} > "$INSTANCE_ENV"

echo "[e2e-up] wrote $INSTANCE_ENV"
echo "[e2e-up] A0 ready at http://localhost:$A0_HTTP_PORT  (user: $AUTH_LOGIN)"
