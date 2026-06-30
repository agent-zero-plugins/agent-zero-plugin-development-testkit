#!/usr/bin/env bash
# BDD lifecycle runner (Cycle-3, DEC-063), run INSIDE the devcontainer.
#
#   a0-up (boot nested A0, with any .devkit.yml e2e_pod_env seam vars)
#     → playwright-bdd: the devkit's COMMON lifecycle+steps composed with the
#       plugin's tests/e2e/{features,steps} (install via the auto worker fixture,
#       behaviour scenarios, uninstall), one webm per scenario
#   a0-down
#
# Inputs (env):
#   PLUGIN_ZIP           plugin zip (the worker fixture installs from it)
#   PLUGIN_DISPLAY_NAME  the plugin's card title
#   WORKSPACE            the plugin repo root (default /workspace)
#   DEVKIT_PATH          the vendored devkit submodule path (default tests/_testkit)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"   # e2e/harness
export A0_NAME="${A0_NAME:-a0-lifecycle}"
export INSTANCE_ENV="${INSTANCE_ENV:-/tmp/a0-instance.env}"
: "${PLUGIN_ZIP:?set PLUGIN_ZIP}"
: "${PLUGIN_DISPLAY_NAME:?set PLUGIN_DISPLAY_NAME}"
PLUGIN_NAME="${PLUGIN_NAME:-$(unzip -p "$PLUGIN_ZIP" plugin.yaml 2>/dev/null | sed -nE 's/^name:[[:space:]]*"?([A-Za-z0-9_-]+)"?.*/\1/p' | head -1)}"
: "${PLUGIN_NAME:?could not determine PLUGIN_NAME}"
WORKSPACE="${WORKSPACE:-/workspace}"
DEVKIT_PATH="${DEVKIT_PATH:-tests/_testkit}"
export A0_POD_ENV="${A0_POD_ENV:-}"

cleanup(){ bash "$HERE/a0-down.sh" || true; }
trap cleanup EXIT

bash "$HERE/a0-up.sh"
set -a; . "$INSTANCE_ENV"; set +a   # A0_BASE_URL / A0_USERNAME / A0_PASSWORD / A0_CONTAINER

# Writable copy of the WHOLE plugin tree (the plugin steps import the devkit via
# the relative submodule path ../../_testkit/..., and bddgen writes .features-gen
# + test-results). Symlink node_modules so playwright-bdd / @playwright/test
# resolve (walk-up from any step file).
WORK="$(mktemp -d)"
cp -r "$WORKSPACE/." "$WORK/"
ln -sfn "$(npm root -g)" "$WORK/node_modules"
BDD="$WORK/$DEVKIT_PATH/e2e/bdd"
[ -f "$BDD/playwright.config.ts" ] || { echo "::error::no BDD config at $BDD — bump the devkit submodule to a Cycle-3 commit"; exit 1; }

export PLUGIN_ZIP PLUGIN_DISPLAY_NAME PLUGIN_NAME
export PLUGIN_BDD_DIR="$WORK/tests/e2e"
export BDD_FEATURES_ROOT="$WORK"
export A0_BASE="$A0_BASE_URL"
export A0_USERNAME="${A0_USERNAME:-admin}" A0_PASSWORD="${A0_PASSWORD:-admin}"

( cd "$BDD" && npx bddgen )

# Gate-3 seam-off red-proof (DEC-066): on the SAME instance, BEFORE installing the
# plugin, the behaviour scenarios must NOT pass — the seam endpoint 404s without the
# plugin, so honest scenarios go RED. Any pass here is fake-green. Cheap: one extra
# playwright pass, no second A0 boot.
RP_LOG="$(mktemp)"
( cd "$BDD" && BDD_SKIP_INSTALL=1 npx playwright test --config=playwright.config.ts ) > "$RP_LOG" 2>&1 || true
# NB: 0-passed is the SUCCESS case and prints no "N passed" line, so BOTH greps
# exit non-zero on empty input; with pipefail that propagates, so `|| true` must
# guard the WHOLE pipeline (not just the first grep) or set -e kills the script.
RP_PASSED=$(grep -oE '[0-9]+ passed' "$RP_LOG" | grep -oE '[0-9]+' | head -1 || true); RP_PASSED=${RP_PASSED:-0}
echo "[run-bdd] red-proof: $RP_PASSED scenario(s) passed with NO plugin installed (want 0)"
if [ "$RP_PASSED" -gt 0 ]; then
  echo "::error::seam-off red-proof FAILED — $RP_PASSED behaviour scenario(s) passed with no plugin installed (fake-green). See tests/_testkit/docs/BDD-GATES.md (Gate 3)."
  grep -aE '✓|passed|failed' "$RP_LOG" | tail -20
  exit 1
fi
echo "[run-bdd] red-proof OK — nothing passes without the plugin; the suite is real."

PW_RC=0
( cd "$BDD" && npx playwright test --config=playwright.config.ts ) || PW_RC=$?

# One webm per scenario → artifacts (named by the test-results subdir = scenario).
if [ -n "${ARTIFACT_DIR:-}" ]; then
  mkdir -p "$ARTIFACT_DIR"; n=0
  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")
    name=$(printf '%s' "$sub" | sed -E 's/-[0-9a-f]{5}-chromium$//; s/-chromium$//; s/[^A-Za-z0-9._-]/-/g')
    cp "$f" "$ARTIFACT_DIR/${PLUGIN_NAME}-${name}.webm" && n=$((n+1))
  done < <(find "$BDD/test-results" -name 'video.webm' 2>/dev/null)
  echo "[run-bdd] copied $n video(s) to ARTIFACT_DIR"
fi
exit $PW_RC
