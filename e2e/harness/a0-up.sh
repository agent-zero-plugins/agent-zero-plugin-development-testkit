#!/usr/bin/env bash
# Boot an Agent Zero instance NESTED inside the devkit devcontainer, rootless.
#
# The proven Phase-0 recipe (SPEC DEC-040/041): inner A0 on --network=host so it
# binds port 80 on the devcontainer's netns (the devcontainer is run with
# --sysctl net.ipv4.ip_unprivileged_port_start=0), and /usr/sbin/sshd replaced
# with a no-op so A0's supervisor watchdog doesn't self-destruct.
#
# Writes an instance env file (A0_BASE_URL/creds/container) for the harness.
set -euo pipefail

A0_IMAGE="${A0_IMAGE:-docker.io/agent0ai/agent-zero:latest}"   # DEC-019 parameter
A0_NAME="${A0_NAME:-a0-lifecycle}"
A0_HTTP_PORT="${A0_HTTP_PORT:-80}"
AUTH_LOGIN="${AUTH_LOGIN:-admin}"
AUTH_PASSWORD="${AUTH_PASSWORD:-admin}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-720}"
INSTANCE_ENV="${INSTANCE_ENV:-/tmp/a0-instance.env}"

log(){ printf '\033[1;36m[a0-up]\033[0m %s\n' "$*"; }

podman rm -f "$A0_NAME" >/dev/null 2>&1 || true

log "booting $A0_IMAGE (nested, rootless, host-net) as '$A0_NAME'"
podman run -d --name "$A0_NAME" --network=host \
  -e AUTH_LOGIN="$AUTH_LOGIN" -e AUTH_PASSWORD="$AUTH_PASSWORD" \
  -e A0_SEEDED_SETTINGS_JSON='{}' -e BRANCH=main \
  "$A0_IMAGE" \
  bash -c 'set -e; mkdir -p /a0/usr;
    printf "AUTH_LOGIN=%s\nAUTH_PASSWORD=%s\n" "$AUTH_LOGIN" "$AUTH_PASSWORD" > /a0/usr/.env;
    printf "%s\n" "$A0_SEEDED_SETTINGS_JSON" > /a0/usr/settings.json;
    printf "#!/bin/sh\nexec tail -f /dev/null\n" > /usr/sbin/sshd; chmod +x /usr/sbin/sshd;
    exec /exe/initialize.sh "$BRANCH"' >/dev/null

log "waiting up to ${BOOT_TIMEOUT}s for /login ..."
deadline=$(( SECONDS + BOOT_TIMEOUT ))
until curl -sf "http://localhost:${A0_HTTP_PORT}/login" >/dev/null 2>&1; do
  if [ $SECONDS -ge $deadline ]; then
    podman logs --tail 60 "$A0_NAME" || true
    echo "[a0-up] A0 did not become healthy in ${BOOT_TIMEOUT}s" >&2; exit 1
  fi
  sleep 3
done

cat > "$INSTANCE_ENV" <<EOF
A0_BASE_URL=http://localhost:${A0_HTTP_PORT}
A0_USERNAME=${AUTH_LOGIN}
A0_PASSWORD=${AUTH_PASSWORD}
A0_CONTAINER=${A0_NAME}
EOF
log "healthy → http://localhost:${A0_HTTP_PORT}  (env → $INSTANCE_ENV)"
