#!/usr/bin/env bash
# Tear down the nested Agent Zero instance booted by a0-up.sh.
set -euo pipefail
A0_NAME="${A0_NAME:-a0-lifecycle}"
podman rm -f "$A0_NAME" >/dev/null 2>&1 || true
echo "[a0-down] removed '$A0_NAME'"
