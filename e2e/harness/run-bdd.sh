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
# SPEED (DEC-070): the red-proof's cost is ENTIRELY in the fail path. With no
# plugin the seam 404s, so every scenario runs until something times out — and
# the binding clock is Playwright's TEST-level timeout (120s), not the action /
# expect timeouts: a step's explicit per-call `{ timeout: N }` (which plugin
# steps routinely pass) is NOT overridable from config, but IS capped by the
# test timeout. Measured: 12 scenarios x ~113s = 22m40s ~= 12 x the 120s cap.
# So cap the test timeout for the red-proof pass only. Semantics are untouched:
# every scenario still runs, and the assertion is still exactly 0 passes.
RED_PROOF_TIMEOUT_MS="${RED_PROOF_TIMEOUT_MS:-30000}"
RP_LOG="$(mktemp)"
rp_t0=$SECONDS
( cd "$BDD" && BDD_SKIP_INSTALL=1 npx playwright test --config=playwright.config.ts \
    --timeout="$RED_PROOF_TIMEOUT_MS" ) > "$RP_LOG" 2>&1 || true
rp_secs=$(( SECONDS - rp_t0 ))
# NB: 0-passed is the SUCCESS case and prints no "N passed" line, so BOTH greps
# exit non-zero on empty input; with pipefail that propagates, so `|| true` must
# guard the WHOLE pipeline (not just the first grep) or set -e kills the script.
RP_PASSED=$(grep -oE '[0-9]+ passed' "$RP_LOG" | grep -oE '[0-9]+' | head -1 || true); RP_PASSED=${RP_PASSED:-0}
RP_TOTAL=$(grep -oE 'Running [0-9]+ test' "$RP_LOG" | grep -oE '[0-9]+' | head -1 || true); RP_TOTAL=${RP_TOTAL:-0}
echo "[run-bdd] red-proof: $RP_PASSED scenario(s) passed with NO plugin installed (want 0) \
— $RP_TOTAL scenario(s) run in ${rp_secs}s (test-timeout cap ${RED_PROOF_TIMEOUT_MS}ms)"
if [ "$RP_PASSED" -gt 0 ]; then
  echo "::error::seam-off red-proof FAILED — $RP_PASSED behaviour scenario(s) passed with no plugin installed (fake-green). See tests/_testkit/docs/BDD-GATES.md (Gate 3)."
  grep -aE '✓|passed|failed' "$RP_LOG" | tail -20
  exit 1
fi
echo "[run-bdd] red-proof OK — nothing passes without the plugin; the suite is real."

PW_RC=0
PW_LOG="$(mktemp)"
( cd "$BDD" && npx playwright test --config=playwright.config.ts ) 2>&1 | tee "$PW_LOG" || true
PW_RC=${PIPESTATUS[0]}

# ── Anti-weakening guards on the speed-up (DEC-070) ───────────────────────────
# Capping the red-proof clock is only safe while a scenario that WOULD pass
# plugin-less still has room to pass. If the cap clipped such a scenario into a
# timeout-failure, the gate would report 0-passed and go green while a fake-green
# scenario sat undetected — a silently weakened gate. Two checks make that
# impossible to happen unnoticed.
PW_TOTAL=$(grep -oE 'Running [0-9]+ test' "$PW_LOG" | grep -oE '[0-9]+' | head -1 || true); PW_TOTAL=${PW_TOTAL:-0}

# Guard A — coverage parity: the red-proof must exercise the SAME scenario count
# as the real run. Catches any future change that narrows the red-proof pass
# (a filter, a project split, a grep) rather than merely speeding it up.
if [ "$RP_TOTAL" -ne "$PW_TOTAL" ]; then
  echo "::error::red-proof coverage MISMATCH — red-proof ran $RP_TOTAL scenario(s) but the real run ran $PW_TOTAL. The red-proof must cover every behaviour scenario (DEC-066/070)."
  exit 1
fi

# Guard B — cap adequacy: every scenario that genuinely PASSES in the real run
# must complete well inside the red-proof cap. If the slowest honest pass needs
# more time than the cap allows, the cap is capable of masking a fake-green, so
# fail loudly with the value to raise it to. 80% leaves headroom for the extra
# waiting a plugin-less run does before its own failure.
# Parse the per-scenario durations Playwright prints at end-of-line, e.g. "(18.5s)".
# POSIX sed + shell arithmetic ONLY — deliberately no gawk-style 3-arg match():
# the harness runs wherever the devkit image runs and mawk (Debian's default awk)
# rejects that GNU extension outright, which would make this guard a syntax error
# at runtime rather than a check. Verified against real CI log output.
SLOWEST_PASS_MS=0
while read -r v u; do
  case "$u" in
    ms) ms=${v%.*} ;;
    s)  ms=$(( ${v%%.*} * 1000 + 10#$(printf '%s' "${v#*.}0" | cut -c1-1) * 100 )) ;;
    m)  ms=$(( ${v%%.*} * 60000 )) ;;
    *)  ms=0 ;;
  esac
  [ "$ms" -gt "$SLOWEST_PASS_MS" ] && SLOWEST_PASS_MS=$ms
done <<EOF
$(grep -a '✓' "$PW_LOG" | sed -nE 's/.*\(([0-9.]+)(ms|s|m)\)[[:space:]]*$/\1 \2/p')
EOF
SLOWEST_PASS_MS=${SLOWEST_PASS_MS:-0}
BUDGET_MS=$(( RED_PROOF_TIMEOUT_MS * 80 / 100 ))
echo "[run-bdd] red-proof cap check: slowest PASSING scenario ${SLOWEST_PASS_MS}ms vs 80% of cap ${BUDGET_MS}ms"
if [ "$SLOWEST_PASS_MS" -gt "$BUDGET_MS" ]; then
  need=$(( SLOWEST_PASS_MS * 100 / 80 / 1000 * 1000 + 1000 ))
  echo "::error::red-proof timeout cap TOO TIGHT — a passing scenario takes ${SLOWEST_PASS_MS}ms but the red-proof cap is ${RED_PROOF_TIMEOUT_MS}ms. A scenario that passes plugin-less could be clipped into a false failure, masking a fake-green. Raise RED_PROOF_TIMEOUT_MS to >= ${need}."
  exit 1
fi

# One Playwright trace.zip per captured scenario → artifacts (network + DOM snapshots +
# console + video + timeline in one file; open with `npx playwright show-trace <file>` or
# trace.playwright.dev). Default: only failing scenarios (retain-on-failure); BDD_TRACE=on ⇒ all.
if [ -n "${ARTIFACT_DIR:-}" ]; then
  mkdir -p "$ARTIFACT_DIR"; n=0
  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")
    name=$(printf '%s' "$sub" | sed -E 's/-[0-9a-f]{5}-chromium$//; s/-chromium$//; s/[^A-Za-z0-9._-]/-/g')
    cp "$f" "$ARTIFACT_DIR/${PLUGIN_NAME}-${name}.trace.zip" && n=$((n+1))
  done < <(find "$BDD/test-results" -name 'trace.zip' 2>/dev/null)
  echo "[run-bdd] copied $n Playwright trace(s) to ARTIFACT_DIR (BDD_TRACE=${BDD_TRACE:-retain-on-failure}; open with: npx playwright show-trace <file>)"
fi
exit $PW_RC
