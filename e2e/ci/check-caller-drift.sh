#!/usr/bin/env bash
#
# Caller-workflow drift check — does a consumer's copied caller still match the
# devkit template it was copied from?
#
# WHY THIS EXISTS
#   `make link-workflows` COPIES templates/{plugin-e2e,devkit-sync}.caller.yml
#   into a consumer's .github/workflows/. `devkit-sync` then keeps the SUBMODULE
#   pin current but deliberately never writes .github/workflows/ (its
#   GITHUB_TOKEN may not push workflow files). So the vendored devkit advances
#   while the copied caller stands still, and nothing anywhere notices.
#
#   That is not hypothetical. Two live examples:
#     * share-chat's caller predated the `capture_all_traces` dispatch input by
#       weeks — the input existed in the reusable workflow, the repo just could
#       not reach it, and no run ever failed to say so.
#     * `actions: write` (count-based artifact retention, DEC-074) had to be
#       hand-propagated to four repos in four separate PRs, because a reusable
#       workflow's permissions are CAPPED BY THE CALLER's grant. The prune step
#       degraded to a warning instead of failing — silent, again.
#   Both failure modes are invisible at runtime. A checker is the only detector.
#
# WHAT COUNTS AS DRIFT (and why not a byte diff)
#   Byte-for-byte would be trivially correct and useless: every comment reflow in
#   the devkit — e.g. the DEC-079 rewrite of the devkit-sync header — would fire
#   on all consumers at once, and a checker that cries wolf gets `|| true`'d
#   within a week. So this compares the EXECUTABLE CONTRACT of the YAML:
#
#     compared    name, triggers (`on`), permissions, job ids, `uses` refs,
#                 `with` inputs, `secrets` (inherit vs the explicit key set),
#                 dispatch input names/types/defaults
#     ignored     comments, whitespace, quoting, key order, scalar-list order
#                 (`branches: [main, master]` is a set), and the human-prose
#                 `description:` of a dispatch input
#
#   Rationale for that line: everything on the left changes what CI DOES, and
#   both real incidents above are on the left. Everything on the right changes
#   only how the file reads. Ignoring `description` is the one judgement call —
#   it is UI prose in the Actions run dialog, and letting a wording fix fail four
#   repos is exactly how the signal gets ignored.
#
#   Drift is reported in three flavours, all fatal, because they rot differently:
#     missing  template has it, consumer does not  — the silent-rot case above
#     changed  both have it, values differ         — a local edit or a stale value
#     extra    consumer has it, template does not  — a local edit that the NEXT
#              `make link-workflows` will silently delete
#
# USAGE
#   check-caller-drift.sh [consumer-repo-root ...]     # default: .
#
#   In consumer CI (the vendored copy, no args) it checks the repo it runs in
#   against its own pinned devkit templates — so the check advances exactly when
#   the submodule does. Locally, pass repo roots to sweep the fleet:
#     check-caller-drift.sh ~/src/.../agent-zero-plugin-*
#
# Env:
#   TEMPLATES_DIR   devkit templates/ dir. Auto-detected when unset, in order:
#                   <script>/../../templates (vendored: e2e/ci/ -> devkit root),
#                   <script>/../templates, then each consumer's tests/_testkit.
#   GITHUB_ACTIONS  when "true", drift is emitted as ::error:: annotations too.
#
# Exit: 0 no drift · 1 drift found · 2 usage/setup error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The two files this check owns. Consumer basename -> template basename.
# Anything else in .github/workflows/ (a repo's own unit.yml, say) is not ours.
CALLERS=(
  "plugin-e2e.yml:plugin-e2e.caller.yml"
  "devkit-sync.yml:devkit-sync.caller.yml"
)

consumers=("$@")
[ ${#consumers[@]} -eq 0 ] && consumers=(".")

# Resolve the templates dir once if it is fleet-wide; otherwise resolve per
# consumer from its own vendored devkit, so each repo is judged against the
# devkit ref IT pinned — not against whatever happens to be checked out here.
resolve_templates() {
  local consumer="$1"
  if [ -n "${TEMPLATES_DIR:-}" ]; then echo "$TEMPLATES_DIR"; return; fi
  local cand
  for cand in \
    "$SCRIPT_DIR/../../templates" \
    "$SCRIPT_DIR/../templates" \
    "$consumer/tests/_testkit/templates"
  do
    [ -d "$cand" ] && { (cd "$cand" && pwd); return; }
  done
  return 1
}

compare() {
  # compare <template.yml> <consumer.yml> <label>
  # Prints one line per drifting path; exits 1 via its own return code.
  TPL="$1" CUR="$2" LABEL="$3" python3 - <<'PY'
import os, re, sys
import yaml

tpl_path, cur_path, label = os.environ["TPL"], os.environ["CUR"], os.environ["LABEL"]

# Prose-only paths. Everything NOT matched here is part of the contract.
IGNORE = [
    re.compile(r"^on\.workflow_dispatch\.inputs\.[^.]+\.description$"),
]

def load(path):
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    # YAML 1.1 resolves a bare `on:` key to the boolean True. Every workflow
    # file hits this; normalise before anything else touches the tree.
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc

def flatten(node, prefix=""):
    """Dotted-path -> scalar. Scalar lists collapse to a sorted canonical string
    because trigger lists (`branches`, `paths`) are sets, not sequences; lists
    holding structure keep their index, where order can matter."""
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(node, list):
        if all(not isinstance(i, (dict, list)) for i in node):
            out[prefix] = "[" + ", ".join(sorted(str(i) for i in node)) + "]"
        else:
            for i, v in enumerate(node):
                out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = node
    return out

def contract(path):
    return {k: v for k, v in flatten(load(path)).items()
            if not any(rx.match(k) for rx in IGNORE)}

tpl, cur = contract(tpl_path), contract(cur_path)

rows = []
for key in sorted(set(tpl) | set(cur)):
    if key not in cur:
        rows.append(("missing", key, tpl[key], None))
    elif key not in tpl:
        rows.append(("extra", key, None, cur[key]))
    elif tpl[key] != cur[key]:
        rows.append(("changed", key, tpl[key], cur[key]))

if not rows:
    sys.exit(0)

print(f"  {label}: {len(rows)} drifted path(s)")
for kind, key, want, got in rows:
    if kind == "missing":
        print(f"    - [missing] {key}\n        template: {want!r}\n        consumer: <absent>")
    elif kind == "extra":
        print(f"    - [extra]   {key}\n        template: <absent>\n        consumer: {got!r}")
    else:
        print(f"    - [changed] {key}\n        template: {want!r}\n        consumer: {got!r}")
sys.exit(1)
PY
}

drifted=0
checked=0

for consumer in "${consumers[@]}"; do
  [ -d "$consumer" ] || { echo "::error::not a directory: $consumer" >&2; exit 2; }
  name="$(basename "$(cd "$consumer" && pwd)")"

  # A repo with no caller at all is not this check's business — it never adopted
  # the devkit. Skipping beats failing every unrelated repo in a fleet sweep.
  have_any=0
  for pair in "${CALLERS[@]}"; do
    [ -f "$consumer/.github/workflows/${pair%%:*}" ] && have_any=1
  done
  [ "$have_any" -eq 1 ] || { echo "== $name: no devkit caller workflows — skipped"; continue; }

  templates="$(resolve_templates "$consumer")" || {
    echo "::error::could not locate devkit templates/ for $name (set TEMPLATES_DIR)" >&2
    exit 2
  }

  echo "== $name (templates: $templates)"
  repo_drift=0
  for pair in "${CALLERS[@]}"; do
    caller="${pair%%:*}"; template="${pair##*:}"
    cur="$consumer/.github/workflows/$caller"
    tpl="$templates/$template"
    [ -f "$tpl" ] || { echo "::error::missing template $tpl" >&2; exit 2; }
    if [ ! -f "$cur" ]; then
      # Half-adopted: one caller present, the other never copied or deleted.
      echo "  $caller: NOT PRESENT (template exists) — run 'make link-workflows'"
      repo_drift=1; continue
    fi
    checked=$((checked + 1))
    compare "$tpl" "$cur" "$caller" || repo_drift=1
  done

  if [ "$repo_drift" -eq 1 ]; then
    drifted=$((drifted + 1))
    [ "${GITHUB_ACTIONS:-}" = "true" ] && \
      echo "::error::$name: caller workflows drifted from the devkit templates — run 'make link-workflows'"
  else
    echo "  in sync"
  fi
done

echo
if [ "$drifted" -gt 0 ]; then
  echo "DRIFT: $drifted repo(s) out of sync across $checked caller file(s)."
  echo "Fix: run 'make link-workflows' in each, review the diff, and commit."
  exit 1
fi
echo "OK: $checked caller file(s) match their devkit templates."
