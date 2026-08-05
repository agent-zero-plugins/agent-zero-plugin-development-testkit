#!/usr/bin/env bash
#
# Resolve the current manifest digest of an image on Docker Hub, anonymously.
#
# WHY THIS EXISTS — it is the whole cost argument for the nightly.
#   A calendar-driven nightly re-runs 4 × ~14min e2e every night whether or not
#   upstream changed. docker.io/agent0ai/agent-zero:latest does NOT change
#   nightly. Gating the expensive fan-out on "did the digest actually move"
#   turns ~1,700 runner-min/month into roughly the number of upstream releases
#   × 56 min, plus a ~20s probe every night. Same detection latency, ~10% of the
#   spend, and — unlike a calendar trigger — every expensive run corresponds to a
#   real upstream change, so a red result is never ambiguous.
#
# Uses the anonymous pull token, so no Docker credentials are needed and this
# works on a fork PR. Prints the digest on stdout; writes GH outputs if
# GITHUB_OUTPUT is set.
#
# Env/args:
#   IMAGE   default docker.io/agent0ai/agent-zero:latest
set -euo pipefail

IMAGE="${1:-${IMAGE:-docker.io/agent0ai/agent-zero:latest}}"

ref="${IMAGE#docker.io/}"
repo="${ref%:*}"
tag="${ref##*:}"
[ "$tag" = "$repo" ] && tag=latest
case "$repo" in */*) ;; *) repo="library/$repo" ;; esac

token=$(curl -fsS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${repo}:pull" \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

digest=$(curl -fsSI -H "Authorization: Bearer ${token}" \
  -H 'Accept: application/vnd.oci.image.index.v1+json' \
  -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json' \
  -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
  "https://registry-1.docker.io/v2/${repo}/manifests/${tag}" \
  | tr -d '\r' | awk 'tolower($1)=="docker-content-digest:"{print $2}')

if [ -z "${digest:-}" ]; then
  echo "::error::could not resolve digest for ${IMAGE}" >&2
  exit 1
fi

echo "$digest"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "digest=${digest}"
    echo "digest_short=${digest#sha256:}"
    echo "image=${IMAGE}"
  } >> "$GITHUB_OUTPUT"
fi
