#!/usr/bin/env bash
# Phase-0 feasibility acceptance (SPEC DEC-031 / Appendix E.6).
#
# Runs INSIDE the devkit devcontainer. Proves the gating assumption behind the
# whole standard: that the Agent Zero container can be booted *nested* inside
# this container by *rootless* podman — no --privileged, no host docker.sock —
# and that the harness can reach + authenticate against it.
#
# Pass criteria (the Critical-4 gate):
#   1. rootless podman runs nested (a throwaway alpine container runs)
#   2. the real A0 image boots nested and /login becomes healthy
#   3. the harness logs in and gets an authenticated response
# The full install/verify/uninstall cycle runs on top of this via the existing
# Playwright harness (proven on livekit) — it is Phase-2, not this gate.
set -euo pipefail

# Fully-qualified: podman/stable enforces short-name resolution (no TTY to prompt in CI).
A0_IMAGE="${A0_IMAGE:-docker.io/agent0ai/agent-zero:latest}"   # DEC-019: parameterized
A0_HTTP_PORT="${A0_HTTP_PORT:-8080}"
A0_NAME="a0-spike"
AUTH_LOGIN="${AUTH_LOGIN:-admin}"
AUTH_PASSWORD="${AUTH_PASSWORD:-admin}"
# First boot in cold CI = image pull + initialize.sh (clone BRANCH + pip install),
# which comfortably exceeds 5 min on a fresh runner. CI run cd3db4e showed A0's
# services reaching RUNNING right as a 300s window expired — so give it room.
BOOT_TIMEOUT="${BOOT_TIMEOUT:-720}"
BASE="http://localhost:${A0_HTTP_PORT}"
COOKIES="$(mktemp)"

log(){ printf '\n\033[1;36m[spike]\033[0m %s\n' "$*"; }
fail(){ printf '\n\033[1;31m[spike FAIL]\033[0m %s\n' "$*"; exit 1; }

cleanup(){ podman rm -f "$A0_NAME" >/dev/null 2>&1 || true; rm -f "$COOKIES"; }
trap cleanup EXIT

# --- 0. environment sanity ----------------------------------------------------
log "podman: $(podman --version) | rootless: $(podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null || echo '?')"

# --- 1. nested rootless podman can run a container at all ---------------------
log "1/3 nested rootless container smoke test"
podman run --rm docker.io/library/alpine:3.20 echo NESTED_OK | grep -q NESTED_OK \
  || fail "rootless podman could not run a nested container"
log "    ✓ nested rootless container ran"

# --- 2. boot the real A0 image nested -----------------------------------------
log "2/3 booting A0 nested: $A0_IMAGE on :$A0_HTTP_PORT"
podman run -d --name "$A0_NAME" \
  -p "${A0_HTTP_PORT}:80" \
  -e AUTH_LOGIN="$AUTH_LOGIN" -e AUTH_PASSWORD="$AUTH_PASSWORD" \
  -e A0_SEEDED_SETTINGS_JSON='{}' \
  -e BRANCH=main \
  "$A0_IMAGE" \
  bash -c 'set -e; mkdir -p /a0/usr;
           printf "AUTH_LOGIN=%s\nAUTH_PASSWORD=%s\n" "$AUTH_LOGIN" "$AUTH_PASSWORD" > /a0/usr/.env;
           printf "%s\n" "$A0_SEEDED_SETTINGS_JSON" > /a0/usr/settings.json;
           # Rootless-nesting workaround: /usr/sbin/sshd exits 255 under rootless
           # podman (privsep needs caps a mapped-root lacks). A0s supervisor
           # event-listener kills the WHOLE instance on any process FATAL, so a
           # flapping sshd takes A0 down ~8s after boot. SSH is irrelevant to the
           # HTTP e2e, so replace sshd with a no-op that never exits → run_sshd
           # stays RUNNING, watchdog stays armed for genuinely-critical procs.
           printf "#!/bin/sh\nexec tail -f /dev/null\n" > /usr/sbin/sshd; chmod +x /usr/sbin/sshd;
           exec /exe/initialize.sh "$BRANCH"' >/dev/null

log "    waiting up to ${BOOT_TIMEOUT}s for /login ..."
deadline=$(( SECONDS + BOOT_TIMEOUT ))
until curl -sf "$BASE/login" >/dev/null 2>&1; do
  if [ $SECONDS -ge $deadline ]; then
    echo "--- curl -v (last attempt) ---"; curl -v "$BASE/login" 2>&1 | tail -15 || true
    echo "--- podman logs (tail) ---"; podman logs --tail 80 "$A0_NAME" || true
    fail "A0 did not become healthy in ${BOOT_TIMEOUT}s"
  fi
  sleep 3
done
log "    ✓ A0 booted nested; /login is healthy"

# --- 3. harness can authenticate ----------------------------------------------
log "3/3 logging in as $AUTH_LOGIN"
curl -sf -c "$COOKIES" -b "$COOKIES" \
  --data-urlencode "username=$AUTH_LOGIN" \
  --data-urlencode "password=$AUTH_PASSWORD" \
  -o /dev/null "$BASE/login" || fail "login POST failed"

# Authenticated fetch: unauthenticated requests to / redirect to /login; an
# authenticated session returns the app. -L follows; we assert we did NOT land
# back on the login form.
body="$(curl -s -L -b "$COOKIES" "$BASE/")"
echo "$body" | grep -qi 'name="password"' && fail "still seeing login form — auth did not stick"
log "    ✓ authenticated session established"

# Bonus (logged, not gating): try the plugins API with best-effort CSRF.
csrf="$(awk '/csrf_token/ {print $7}' "$COOKIES" | tail -1)"
if [ -n "${csrf:-}" ]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' -b "$COOKIES" \
      -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' \
      --data '{"filter":{"custom":true}}' "$BASE/api/plugins_list" || true)"
  log "    (bonus) POST /api/plugins_list → HTTP $code"
fi

log "PHASE-0 ACCEPTANCE PASSED — rootless nested A0 boot + auth confirmed."
