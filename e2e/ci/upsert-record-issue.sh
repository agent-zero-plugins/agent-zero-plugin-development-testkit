#!/usr/bin/env bash
#
# Upsert a single long-lived GitHub issue whose BODY is the record.
#
# WHY AN ISSUE AND NOT A COMMITTED FILE
#   A committed docs/CI-BUDGET.md would be rewritten on every run, so every e2e
#   run would produce a commit (or a PR) whose only content is a changed
#   timestamp. That is precisely the churn that got the nightly devkit-sync
#   deleted — 189 runs, 29 useful bumps. An issue body is:
#     * durable and permalinked (unlike a job summary, which dies with the run),
#     * editable in place with zero commits, zero PRs, zero branch noise,
#     * already where maintainers look, and pinnable per repo,
#     * silent on edit (editing a body sends no notification), so it can update
#       as often as we like without training anyone to ignore it.
#
# ANTI-STALENESS
#   MODE=only-on-failure closes the issue when everything is green and (re)opens
#   it when something is red — so an OPEN issue always means "act on this", and
#   its absence is not ambiguous. The nightly's own last-run timestamp is written
#   into the body either way, so "it silently stopped running" is visible rather
#   than invisible.
#
# Env:
#   GH_TOKEN            token with issues:write on $REPO
#   REPO                owner/name
#   TITLE               exact issue title used as the upsert key
#   BODY_FILE           file whose contents become the issue body
#   LABEL               label to apply/create (default: ci-budget)
#   MODE                always | only-on-failure   (default: always)
#   STATUS              ok | fail  — consulted only when MODE=only-on-failure
#
# Never fails the caller: record-keeping must not turn a green run red.
set -euo pipefail

: "${REPO:?set REPO}"
: "${TITLE:?set TITLE}"
: "${BODY_FILE:?set BODY_FILE}"
LABEL="${LABEL:-ci-budget}"
MODE="${MODE:-always}"
STATUS="${STATUS:-ok}"

[ -f "$BODY_FILE" ] || { echo "::warning::$BODY_FILE missing — nothing to upsert"; exit 0; }

# Ensure the label exists (idempotent; ignore "already exists").
gh label create "$LABEL" --repo "$REPO" \
  --color 0e8a16 --description "Automated devkit record — do not close by hand" \
  >/dev/null 2>&1 || true

# Find the existing record issue by exact title, open OR closed, so we reuse the
# same one forever instead of accumulating a new issue per run.
num=$(gh issue list --repo "$REPO" --label "$LABEL" --state all --limit 50 \
        --json number,title \
        --jq "[.[] | select(.title == \"$TITLE\")] | first | .number" 2>/dev/null || echo "")
[ "$num" = "null" ] && num=""

if [ -z "$num" ]; then
  if [ "$MODE" = "only-on-failure" ] && [ "$STATUS" = "ok" ]; then
    echo "all green and no existing record issue — nothing to open"
    exit 0
  fi
  num=$(gh issue create --repo "$REPO" --title "$TITLE" \
          --body-file "$BODY_FILE" --label "$LABEL" \
          --json number --jq .number 2>/dev/null \
        || gh issue create --repo "$REPO" --title "$TITLE" \
             --body-file "$BODY_FILE" --label "$LABEL" | grep -oE '[0-9]+$')
  echo "created record issue #$num"
else
  gh issue edit "$num" --repo "$REPO" --body-file "$BODY_FILE" >/dev/null
  echo "updated record issue #$num (body replaced, no comment, no notification)"
fi

if [ "$MODE" = "only-on-failure" ]; then
  if [ "$STATUS" = "ok" ]; then
    gh issue close "$num" --repo "$REPO" \
      --comment "All plugins green against upstream — closing. This issue reopens automatically on the next red night." \
      >/dev/null 2>&1 || true
    echo "green → record issue #$num closed"
  else
    gh issue reopen "$num" --repo "$REPO" >/dev/null 2>&1 || true
    echo "red → record issue #$num open"
  fi
fi

echo "record: https://github.com/$REPO/issues/$num"
