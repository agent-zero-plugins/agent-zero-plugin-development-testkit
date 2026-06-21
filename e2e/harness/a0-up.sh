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

A0_IMAGE="${A0_IMAGE:-ghcr.io/nuevanext/agent-zero:latest-nonroot}"   # DEC-055 fork-first default
A0_NAME="${A0_NAME:-a0-lifecycle}"
A0_HTTP_PORT="${A0_HTTP_PORT:-80}"
AUTH_LOGIN="${AUTH_LOGIN:-admin}"
AUTH_PASSWORD="${AUTH_PASSWORD:-admin}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-1080}"
INSTANCE_ENV="${INSTANCE_ENV:-/tmp/a0-instance.env}"

log(){ printf '\033[1;36m[a0-up]\033[0m %s\n' "$*"; }

# Plugin-declared extra env to forward INTO the nested A0 pod (DEC-057). A plugin
# whose behaviour sits behind an env-gated test seam (e.g. a deterministic probe
# gated by FOO_TEST_PROBE=1, kept off in prod) declares it in .devkit.yml
# `e2e_pod_env:`; the reusable workflow flattens that to A0_POD_ENV, a
# whitespace/newline-separated list of KEY=VAL entries. We turn each into a
# `-e KEY=VAL` flag so the seam is enabled for e2e ONLY.
POD_ENV_ARGS=()
if [ -n "${A0_POD_ENV:-}" ]; then
  while IFS= read -r kv; do
    [ -z "$kv" ] && continue
    case "$kv" in
      *=*) POD_ENV_ARGS+=( -e "$kv" ); log "pod-env: ${kv%%=*} (forwarded to nested A0)";;
      *) echo "[a0-up] ignoring malformed A0_POD_ENV entry (no '='): $kv" >&2;;
    esac
  done < <(printf '%s\n' $A0_POD_ENV)
fi

podman rm -f "$A0_NAME" >/dev/null 2>&1 || true

# Private-registry pull auth (DEC-055/Q-030): if ghcr creds are provided, log in
# so a private fork image (ghcr.io/nuevanext/agent-zero) can be pulled. No creds
# ⇒ skipped (public images need none).
if [ -n "${GHCR_TOKEN:-}" ]; then
  log "podman login ghcr.io (private fork-image pull)"
  printf '%s' "$GHCR_TOKEN" | podman login ghcr.io -u "${GHCR_USER:-x}" --password-stdin >/dev/null 2>&1 \
    || { echo "[a0-up] ghcr login failed (check GHCR_PULL_TOKEN: read:packages on NuevaNext)" >&2; exit 1; }
fi

log "booting $A0_IMAGE (nested, rootless, host-net) as '$A0_NAME'"
podman run -d --name "$A0_NAME" --network=host \
  -e AUTH_LOGIN="$AUTH_LOGIN" -e AUTH_PASSWORD="$AUTH_PASSWORD" \
  -e A0_SEEDED_SETTINGS_JSON='{}' -e BRANCH=main \
  ${POD_ENV_ARGS[@]+"${POD_ENV_ARGS[@]}"} \
  "$A0_IMAGE" \
  bash -c 'set -e; mkdir -p /a0/usr;
    printf "AUTH_LOGIN=%s\nAUTH_PASSWORD=%s\n" "$AUTH_LOGIN" "$AUTH_PASSWORD" > /a0/usr/.env;
    printf "%s\n" "$A0_SEEDED_SETTINGS_JSON" > /a0/usr/settings.json;
    # Neutralize sshd so A0s supervisor watchdog does not self-destruct on its
    # rootless 255 exit (DEC-040). Best-effort: the root image lets us overwrite
    # the binary; the non-root fork image rejects it (Permission denied) but
    # already handles sshd via its non-root init, so we proceed either way.
    if printf "#!/bin/sh\nexec tail -f /dev/null\n" > /usr/sbin/sshd 2>/dev/null; then
      chmod +x /usr/sbin/sshd 2>/dev/null || true; echo "[a0] sshd neutralized";
    else echo "[a0] /usr/sbin/sshd not writable (non-root image) — relying on image init"; fi;
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
