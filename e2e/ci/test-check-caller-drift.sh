#!/usr/bin/env bash
#
# Self-test for check-caller-drift.sh.
#
# WHY A POSITIVE CONTROL AND NOT JUST A SMOKE RUN
#   A drift checker that silently passes is strictly worse than no checker: it
#   converts "nobody is looking" into "someone is looking and says it's fine".
#   The only way to trust a green run is to prove the same code goes red on a
#   drift you planted on purpose. Case 1 below is that proof — and it plants the
#   two drifts that actually happened in this fleet (a missing dispatch input, a
#   missing `actions: write`), not invented ones.
#
#   The negative controls matter just as much: cases 4-6 plant the differences
#   the checker MUST tolerate. Without them the honest fix for a noisy checker is
#   to loosen it, and nothing would catch the loosening going too far.
#
# Runs fully in a temp dir against synthetic fixtures — never touches a repo.
# Exit: 0 all cases pass · 1 a case failed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/check-caller-drift.sh"
[ -x "$CHECK" ] || chmod +x "$CHECK"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

TEMPLATES="$WORK/templates"
mkdir -p "$TEMPLATES"

cat > "$TEMPLATES/plugin-e2e.caller.yml" <<'YAML'
# plugin-e2e — caller template.
name: plugin-e2e

on:
  pull_request:
    branches: ["main", "master"]
  workflow_dispatch:
    inputs:
      capture_all_traces:
        description: "Capture a Playwright trace for EVERY scenario (not just failures)"
        type: boolean
        default: false

permissions:
  contents: read
  pull-requests: write
  actions: write

jobs:
  e2e:
    uses: agent-zero-plugins/agent-zero-plugin-development-testkit/.github/workflows/plugin-e2e.yml@main
    secrets: inherit
    with:
      capture-all-traces: ${{ inputs.capture_all_traces || false }}
YAML

cat > "$TEMPLATES/devkit-sync.caller.yml" <<'YAML'
# devkit-sync — caller template.
name: devkit-sync

on:
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  sync:
    uses: agent-zero-plugins/agent-zero-plugin-development-testkit/.github/workflows/devkit-sync.yml@main
    with:
      devkit-submodule-path: "tests/_testkit"
    secrets:
      SKILLS_SYNC_APP_CLIENT_ID: ${{ secrets.SKILLS_SYNC_APP_CLIENT_ID }}
      SKILLS_SYNC_APP_PRIVATE_KEY: ${{ secrets.SKILLS_SYNC_APP_PRIVATE_KEY }}
YAML

# A consumer that is, by construction, a byte-identical copy — the in-sync base
# every case mutates from.
new_consumer() {
  local dir="$WORK/$1"
  rm -rf "$dir"; mkdir -p "$dir/.github/workflows"
  cp "$TEMPLATES/plugin-e2e.caller.yml"   "$dir/.github/workflows/plugin-e2e.yml"
  cp "$TEMPLATES/devkit-sync.caller.yml"  "$dir/.github/workflows/devkit-sync.yml"
  echo "$dir"
}

pass=0; fail=0
# expect <want-exit> <case-name> <consumer-dir> [grep-pattern ...]
expect() {
  local want="$1" name="$2" dir="$3"; shift 3
  local out rc
  out="$(TEMPLATES_DIR="$TEMPLATES" "$CHECK" "$dir" 2>&1)"; rc=$?
  local ok=1
  [ "$rc" -eq "$want" ] || ok=0
  local pat
  for pat in "$@"; do grep -qF -- "$pat" <<<"$out" || ok=0; done
  if [ "$ok" -eq 1 ]; then
    pass=$((pass + 1)); echo "PASS  $name (exit $rc)"
  else
    fail=$((fail + 1))
    echo "FAIL  $name (exit $rc, wanted $want)"
    sed 's/^/        /' <<<"$out"
  fi
}

echo "--- positive controls: real drifts, must be DETECTED ---"

# Case 1 — the two incidents that actually happened, on one repo.
d="$(new_consumer c1-real-incidents)"
python3 - "$d/.github/workflows/plugin-e2e.yml" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
# share-chat: caller predated capture_all_traces, so the dispatch input and the
# `with:` that forwards it were both absent.
t = t.replace('''  workflow_dispatch:
    inputs:
      capture_all_traces:
        description: "Capture a Playwright trace for EVERY scenario (not just failures)"
        type: boolean
        default: false
''', '  workflow_dispatch:\n')
t = t.replace('''    with:
      capture-all-traces: ${{ inputs.capture_all_traces || false }}
''', '')
# DEC-074: actions: write hand-propagated to 4 repos, one PR each.
t = t.replace('  actions: write\n', '')
open(p, 'w').write(t)
PY
expect 1 "missing capture_all_traces input + actions: write" "$d" \
  "[missing] on.workflow_dispatch.inputs.capture_all_traces.type" \
  "[missing] jobs.e2e.with.capture-all-traces" \
  "[missing] permissions.actions"

# Case 2 — a stale `uses` ref. Pins the consumer to an old devkit no matter what
# the submodule says; the most consequential single-token drift there is.
d="$(new_consumer c2-stale-uses)"
sed -i 's|plugin-e2e.yml@main|plugin-e2e.yml@v1|' "$d/.github/workflows/plugin-e2e.yml"
expect 1 "stale reusable-workflow ref (@v1 vs @main)" "$d" "[changed] jobs.e2e.uses"

# Case 3 — devkit-sync still on the retired nightly schedule (DEC-079), and a
# secret key dropped. Proves the second file is really checked, not just the first.
d="$(new_consumer c3-stale-sync)"
python3 - "$d/.github/workflows/devkit-sync.yml" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
t = t.replace('on:\n  workflow_dispatch:',
              'on:\n  schedule:\n    - cron: "0 4 * * *"\n  workflow_dispatch:')
t = t.replace('      SKILLS_SYNC_APP_PRIVATE_KEY: ${{ secrets.SKILLS_SYNC_APP_PRIVATE_KEY }}\n', '')
open(p, 'w').write(t)
PY
expect 1 "retired nightly schedule + dropped secret" "$d" \
  "[extra]   on.schedule" \
  "[missing] jobs.sync.secrets.SKILLS_SYNC_APP_PRIVATE_KEY"

echo
echo "--- negative controls: cosmetic differences, must be TOLERATED ---"

# Case 4 — comments and blank lines. The devkit rewrote the whole devkit-sync
# header for DEC-079; if that fired on every consumer the check gets ignored.
d="$(new_consumer c4-comments)"
python3 - "$d/.github/workflows/devkit-sync.yml" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
t = t.replace('# devkit-sync — caller template.',
              '# devkit-sync — caller template (SPEC DEC-044).\n#\n# Rewritten header.\n# ON DEMAND ONLY (DEC-079).\n')
open(p, 'w').write(t + "\n\n")
PY
expect 0 "comment rewrite + trailing blank lines" "$d" "in sync"

# Case 5 — quoting, key order, and branch-list order. Same contract, different
# spelling; a line-diff would flag all three.
d="$(new_consumer c5-formatting)"
python3 - "$d/.github/workflows/plugin-e2e.yml" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
t = t.replace('branches: ["main", "master"]', "branches: [master, main]")
t = t.replace('''permissions:
  contents: read
  pull-requests: write
  actions: write''', '''permissions:
  actions: write
  pull-requests: write
  contents: read''')
open(p, 'w').write(t)
PY
expect 0 "requoting, reordered keys, reordered branch list" "$d" "in sync"

# Case 6 — the one judgement call, asserted explicitly so a future tightening
# has to change this test on purpose rather than by accident.
d="$(new_consumer c6-description)"
sed -i 's|description: "Capture a Playwright trace.*|description: "Trace every scenario"|' \
  "$d/.github/workflows/plugin-e2e.yml"
expect 0 "reworded dispatch-input description (prose only)" "$d" "in sync"

echo
echo "--- structural cases ---"

# Case 7 — clean copy. Guards against a checker that flags everything, which
# would make cases 1-3 pass for the wrong reason.
d="$(new_consumer c7-clean)"
expect 0 "untouched copy" "$d" "OK: 2 caller file(s)"

# Case 8 — half-adopted: one caller deleted. devkit-sync cannot restore it.
d="$(new_consumer c8-half)"
rm "$d/.github/workflows/devkit-sync.yml"
expect 1 "caller file deleted entirely" "$d" "devkit-sync.yml: NOT PRESENT"

# Case 9 — a repo that never adopted the devkit must not fail a fleet sweep.
d="$WORK/c9-nonadopter"; mkdir -p "$d/.github/workflows"
echo "name: unit" > "$d/.github/workflows/unit.yml"
expect 0 "non-adopter repo is skipped, not failed" "$d" "no devkit caller workflows — skipped"

# Case 10 — a fleet sweep: one bad repo must fail the whole run.
good="$(new_consumer c10-good)"
bad="$(new_consumer c10-bad)"
sed -i 's|  actions: write||' "$bad/.github/workflows/plugin-e2e.yml"
out="$(TEMPLATES_DIR="$TEMPLATES" "$CHECK" "$good" "$bad" 2>&1)"; rc=$?
if [ "$rc" -eq 1 ] && grep -qF "DRIFT: 1 repo(s)" <<<"$out"; then
  pass=$((pass + 1)); echo "PASS  multi-repo sweep fails on one bad repo (exit $rc)"
else
  fail=$((fail + 1)); echo "FAIL  multi-repo sweep (exit $rc)"; sed 's/^/        /' <<<"$out"
fi

echo
echo "passed: $pass  failed: $fail"
[ "$fail" -eq 0 ] || exit 1
echo "SELF-TEST OK — the checker detects planted drift and tolerates cosmetics."
