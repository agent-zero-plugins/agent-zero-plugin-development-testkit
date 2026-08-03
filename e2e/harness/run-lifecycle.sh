#!/usr/bin/env bash
# Generic plugin lifecycle runner (SPEC §5.4/§5.5), run INSIDE the devcontainer.
#
#   a0-up (boot nested A0)
#     → snapshot baseline (/a0/usr/plugins listing)
#     → playwright lifecycle spec: install → verify-installed (UI) →
#       uninstall → verify-uninstalled (UI)
#     → verify-uninstalled common check: plugins dir == baseline (no residue)
#   a0-down
#
# Inputs (env):
#   PLUGIN_ZIP           path to the plugin zip to install
#   PLUGIN_DISPLAY_NAME  the plugin's title as shown on its card
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"   # e2e/harness
E2E_DIR="$(cd "$HERE/.." && pwd)"       # e2e
LIFECYCLE_DIR="$E2E_DIR/lifecycle"
export A0_NAME="${A0_NAME:-a0-lifecycle}"
export INSTANCE_ENV="${INSTANCE_ENV:-/tmp/a0-instance.env}"
: "${PLUGIN_ZIP:?set PLUGIN_ZIP}"
: "${PLUGIN_DISPLAY_NAME:?set PLUGIN_DISPLAY_NAME}"
# Internal plugin dir name (the `name:` in plugin.yaml). Derive from the zip if
# not supplied — it's what /a0/usr/plugins/<name> is created/removed as.
PLUGIN_NAME="${PLUGIN_NAME:-$(unzip -p "$PLUGIN_ZIP" plugin.yaml 2>/dev/null | sed -nE 's/^name:[[:space:]]*"?([A-Za-z0-9_-]+)"?.*/\1/p' | head -1)}"
: "${PLUGIN_NAME:?could not determine PLUGIN_NAME (set it, or ensure plugin.yaml has name:)}"

cleanup(){ bash "$HERE/a0-down.sh" || true; }
trap cleanup EXIT

bash "$HERE/a0-up.sh"
set -a; . "$INSTANCE_ENV"; set +a   # export A0_BASE_URL/USERNAME/PASSWORD/CONTAINER

# The repo is bind-mounted and owned by the host uid; the container user can't
# write into it (needed for the node_modules symlink). Run from a
# container-writable copy of e2e/ (preserves all the ../ relative imports), and
# symlink node_modules there so the testkit pages/fixtures resolve
# "@playwright/test" (resolution walks up from e2e/**).
WORK="$(mktemp -d)"
cp -r "$E2E_DIR/." "$WORK/"
ln -sfn "$(npm root -g)" "$WORK/node_modules"

# The spec (running in Node inside the devcontainer) now drives the common
# checks + per-plugin hooks via podman exec / child_process, so it needs the
# plugin name, the live container name, and where the plugin's hooks live.
export PLUGIN_ZIP PLUGIN_DISPLAY_NAME PLUGIN_NAME A0_CONTAINER CASE_NAME
export HOOK_DIR="${HOOK_DIR:-}"
export BEHAVIOUR_FILE="${BEHAVIOUR_FILE:-}"     # legacy single-seam (DEC-053)
export BEHAVIOUR_SPECS="${BEHAVIOUR_SPECS:-}"   # ≤10 grouped specs (DEC-056), JSON [{name,path}]
export A0_POD_ENV="${A0_POD_ENV:-}"             # plugin-declared nested-A0 env (DEC-057), KEY=VAL list

PW_RC=0
( cd "$WORK/lifecycle" && npx playwright test --config=playwright.config.ts ) || PW_RC=$?

# Collect e2e traces (the rich single-file artifact: network + DOM snapshots + console +
# video + timeline) to the writable artifact mount, even on failure. One trace.zip per
# captured spec, named by its test-results subdir. Traces are always captured (DEC-073).
#
# Playwright also writes .png and .webm NEXT TO each trace.zip. This collector used to
# copy only trace.zip (plus the behaviour-*.png the spec itself renders), so screenshots
# and the recorded video were dropped on the floor — the same defect fixed in run-bdd.sh.
# The GIF step downstream globs artifacts/*.webm and silently produced nothing.
if [ -n "${ARTIFACT_DIR:-}" ]; then
  mkdir -p "$ARTIFACT_DIR"
  n=0; shots=0; vids=0
  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")        # e.g. lifecycle-lifecycle-behaviour-<group>-<hash>-chromium
    name=$(printf '%s' "$sub" | sed -E 's/^lifecycle-lifecycle-//; s/-[0-9a-f]{5}-chromium$//; s/-chromium$//')
    cp "$f" "$ARTIFACT_DIR/${PLUGIN_NAME}-${name}.trace.zip" && n=$((n+1))
  done < <(find "$WORK/lifecycle/test-results" -name 'trace.zip' 2>/dev/null)
  # Keep the spec dir in the name so shots/videos stay attributable, and preserve
  # Playwright's -1/-2 suffixes rather than overwriting repeats.
  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")
    name=$(printf '%s' "$sub" | sed -E 's/^lifecycle-lifecycle-//; s/-[0-9a-f]{5}-chromium$//; s/-chromium$//')
    base=$(basename "$f")
    case "$base" in
      *.png)  cp "$f" "$ARTIFACT_DIR/${PLUGIN_NAME}-${name}--${base}" && shots=$((shots+1)) ;;
      *.webm) cp "$f" "$ARTIFACT_DIR/${PLUGIN_NAME}-${name}--${base}" && vids=$((vids+1)) ;;
    esac
  done < <(find "$WORK/lifecycle/test-results" \( -name '*.png' -o -name '*.webm' \) 2>/dev/null)
  # Spec-rendered behaviour screenshots (DEC-051 media), written outside test-results.
  for f in "${A0_REPORT_DIR:-/tmp}"/behaviour-*.png; do
    [ -e "$f" ] && cp "$f" "$ARTIFACT_DIR/" && shots=$((shots+1))
  done
  echo "[run-lifecycle] copied $n trace(s), $shots screenshot(s), $vids video(s) to ARTIFACT_DIR (open a trace: npx playwright show-trace <file>)"
fi
exit $PW_RC

# verify-uninstalled (fs layer, DEC-029): assert the PLUGIN'S OWN dir is gone —
# NOT that /a0/usr/plugins is byte-identical to a baseline. A0 lazily
# materializes builtin plugin dirs (_office, _whisper_stt, ...) mid-session;
# those are ambient drift, not this plugin's residue. (pip/settings/API → 1c.)
if podman exec "$A0_NAME" test -d "/a0/usr/plugins/$PLUGIN_NAME"; then
  echo "::error::verify-uninstalled — /a0/usr/plugins/$PLUGIN_NAME persists after uninstall (defect)"
  podman exec "$A0_NAME" sh -c "ls -laR /a0/usr/plugins/$PLUGIN_NAME" || true
  exit 1
fi
echo "✅ LIFECYCLE OK — install → verify-installed → uninstall → verify-uninstalled ($PLUGIN_NAME dir removed)"
