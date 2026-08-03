# shellcheck shell=bash
#
# Shared Playwright artifact collector, sourced by run-bdd.sh and run-lifecycle.sh.
#
# WHY THIS FILE EXISTS
#   The two harnesses each carried their own near-identical copy of this logic.
#   The copies drifted (only one sanitised non-alphanumerics in scenario names),
#   and when the "green runs upload an empty artifact" bug was fixed in one copy
#   the other silently kept the defect — a green e2e still shipped 0 screenshots
#   and 0 videos, and the downstream "video → GIF" step produced nothing at all.
#   One definition, two callers: a fix lands everywhere or nowhere.
#
# WHAT PLAYWRIGHT WRITES
#   Per scenario, under <test-results>/<scenario-dir>/:
#     trace.zip          (network + DOM snapshots + console + video + timeline)
#     *.png              screenshots        — `screenshot: "on"`
#     *.webm             recorded video     — `video: { mode: "on" }`
#   All three are always captured (DEC-073). Collecting only trace.zip was the bug.

# collect_playwright_artifacts <test-results-dir> <artifact-dir> <plugin-name> [name-prefix-strip]
#
# Copies traces, screenshots and videos out of a Playwright test-results tree
# into the (writable, usually bind-mounted) artifact dir, naming every file after
# the scenario it came from so it stays attributable once flattened.
#
# The optional 4th arg is an extra sed expression applied to the scenario dir
# name — run-lifecycle passes 's/^lifecycle-lifecycle-//' to strip the doubled
# prefix Playwright generates there. Everything else is identical by construction.
#
# Sets: COLLECTED_TRACES / COLLECTED_SHOTS / COLLECTED_VIDEOS.
collect_playwright_artifacts() {
  local results_dir="$1" artifact_dir="$2" plugin_name="$3" strip="${4:-}"
  local f sub name base

  COLLECTED_TRACES=0 COLLECTED_SHOTS=0 COLLECTED_VIDEOS=0
  [ -n "$artifact_dir" ] || return 0
  mkdir -p "$artifact_dir"

  # Scenario dir → a filename-safe label. Drops Playwright's 5-hex-char dedupe
  # suffix and the project suffix, then replaces anything outside [A-Za-z0-9._-]
  # so names survive zip/download on every platform (this sanitiser is exactly
  # what one of the two old copies was missing — hence raw "→" in artifact names).
  _scenario_label() {
    local sub="$1"
    [ -n "$strip" ] && sub=$(printf '%s' "$sub" | sed -E "$strip")
    printf '%s' "$sub" | sed -E 's/-[0-9a-f]{5}-chromium$//; s/-chromium$//; s/[^A-Za-z0-9._-]/-/g'
  }

  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")
    name=$(_scenario_label "$sub")
    cp "$f" "$artifact_dir/${plugin_name}-${name}.trace.zip" && COLLECTED_TRACES=$((COLLECTED_TRACES + 1))
  done < <(find "$results_dir" -name 'trace.zip' 2>/dev/null)

  # Screenshots/videos live NEXT TO the trace. Keep Playwright's own -1/-2
  # suffixes (test-failed-1.png, ...) rather than overwriting repeats.
  while IFS= read -r f; do
    sub=$(basename "$(dirname "$f")")
    name=$(_scenario_label "$sub")
    base=$(basename "$f")
    case "$base" in
      *.png)  cp "$f" "$artifact_dir/${plugin_name}-${name}--${base}" && COLLECTED_SHOTS=$((COLLECTED_SHOTS + 1)) ;;
      *.webm) cp "$f" "$artifact_dir/${plugin_name}-${name}--${base}" && COLLECTED_VIDEOS=$((COLLECTED_VIDEOS + 1)) ;;
    esac
  done < <(find "$results_dir" \( -name '*.png' -o -name '*.webm' \) 2>/dev/null)

  return 0
}

# collect_extra_screenshots <glob-dir> <artifact-dir> <pattern>
#
# Spec-rendered screenshots written OUTSIDE test-results (DEC-051 media, e.g.
# the behaviour-*.png a spec saves itself). Adds to COLLECTED_SHOTS.
collect_extra_screenshots() {
  local src_dir="$1" artifact_dir="$2" pattern="${3:-behaviour-*.png}" f
  [ -n "$artifact_dir" ] && [ -d "$src_dir" ] || return 0
  for f in "$src_dir"/$pattern; do
    [ -e "$f" ] || continue
    cp "$f" "$artifact_dir/" && COLLECTED_SHOTS=$((COLLECTED_SHOTS + 1))
  done
  return 0
}

# report_collected <harness-label>
report_collected() {
  echo "[$1] copied ${COLLECTED_TRACES:-0} trace(s), ${COLLECTED_SHOTS:-0} screenshot(s), ${COLLECTED_VIDEOS:-0} video(s) to ARTIFACT_DIR (open a trace: npx playwright show-trace <file>)"
}
