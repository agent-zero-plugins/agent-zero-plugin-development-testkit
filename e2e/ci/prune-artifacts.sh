#!/usr/bin/env bash
#
# Count-based artifact retention (DEC-074) — keep the newest $KEEP artifacts
# named $ART_NAME and delete the rest.
#
# WHY THIS IS A SCRIPT AND NOT INLINE YAML
#   It is called from two workflows (the reusable plugin-e2e.yml and the devkit's
#   own sample-plugin-e2e.yml self-test). Inlining it twice is exactly the
#   copy-paste that let the artifact-collector bug survive its first fix.
#
# WHY IT EXISTS AT ALL
#   GitHub has NO native "keep last N artifacts" setting. `retention-days` is the
#   only built-in control and it is purely time-based, so under a variable CI
#   cadence it cannot express "the last N executions". Uploads therefore set a
#   long retention-days as a pure backstop and let this script decide what
#   actually disappears.
#
# Env:
#   GH_TOKEN            token with actions:write (capped by the CALLER's grant
#                       for a reusable workflow — see the caller template)
#   GITHUB_REPOSITORY   owner/repo
#   ART_NAME            artifact name to prune
#   KEEP                how many of the newest to keep (default 5)
#   IS_FORK             "true" when running for a fork PR (token is read-only)
#
# Never fails the run: callers invoke it with continue-on-error, and retention
# housekeeping must not turn a green e2e red.
set -euo pipefail

KEEP="${KEEP:-5}"
: "${ART_NAME:?set ART_NAME}"
: "${GITHUB_REPOSITORY:?set GITHUB_REPOSITORY}"

if [ "${IS_FORK:-false}" = "true" ]; then
  echo "fork PR — token is read-only, skipping prune"
  exit 0
fi

# Newest-first list of this artifact name, excluding already-expired ones.
# Sorting here (rather than trusting API order) is what makes "newest N" correct.
mapfile -t ids < <(
  gh api --paginate \
    "repos/${GITHUB_REPOSITORY}/actions/artifacts?per_page=100" \
    -q ".artifacts[] | select(.name == \"${ART_NAME}\") | select(.expired == false) | \"\(.created_at) \(.id)\"" \
  | sort -r | awk '{print $2}'
)

total=${#ids[@]}
echo "found $total live artifact(s) named ${ART_NAME}; keeping newest ${KEEP}"
if [ "$total" -le "$KEEP" ]; then
  echo "nothing to prune"
  exit 0
fi

deleted=0
for id in "${ids[@]:$KEEP}"; do
  if gh api -X DELETE "repos/${GITHUB_REPOSITORY}/actions/artifacts/${id}" >/dev/null 2>&1; then
    deleted=$((deleted + 1))
  else
    echo "::warning::could not delete artifact ${id} (insufficient permission?)"
  fi
done
echo "pruned ${deleted} artifact(s), kept ${KEEP}"
