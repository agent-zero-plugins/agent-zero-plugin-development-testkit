#!/usr/bin/env python3
"""
Build the per-plugin CI budget / e2e record.

WHY THIS IS A SCRIPT AND NOT INLINE YAML
    Same reason as e2e/ci/prune-artifacts.sh: it is called from the reusable
    ci-budget.yml AND from the nightly upstream-compat.yml, and it is the kind
    of logic (pagination, unit conversion, graceful degradation) that rots
    instantly when copy-pasted into two workflows.

WHAT THE GITHUB API ACTUALLY GIVES US  (probed 2026-08-05, not assumed)

  1. repos/{r}/actions/runs/{id}/timing  →  billable.UBUNTU.total_ms
     Reachable with the workflow's own GITHUB_TOKEN (actions:read).
     USELESS HERE: it returns 0 for every run on these repos, because they are
     PUBLIC and public-repo Actions minutes are free, so GitHub reports zero
     *billable* time. Verified on three real chat-comments runs:
         {"billable":{"UBUNTU":{"total_ms":0,...}},"run_duration_ms":810000}
     We therefore do NOT use it as the minute source. run_duration_ms is real
     but is whole-run wall clock including queue/idle between jobs.

  2. GET /orgs/{org}/settings/billing/actions      →  HTTP 410 "moved"
     GET /orgs/{org}/settings/billing/shared-storage →  HTTP 410 "moved"
     Both are gone. gh additionally reports they'd want admin:org. Dead ends.

  3. GET /organizations/{org}/settings/billing/usage?year=&month=
     THE one that works. Needs an ORG-scoped token (read:org was enough for
     the operator PAT; the endpoint is on the "enhanced billing platform").
     Returns one row per (day, repo, SKU):
         {"date":"2026-08-04...","product":"actions","sku":"Actions Linux",
          "quantity":78.0,"unitType":"Minutes","netAmount":0.0,
          "repositoryName":"agent-zero-plugin-chat-comments"}
     So MINUTES ARE REAL AND PER-REPO. netAmount is 0.0 because public repos
     are free — the *cost* is genuinely zero, the *minutes* are not.
     LIMITATION: a workflow's GITHUB_TOKEN is repo-scoped and has no billing
     permission at all (there is no `permissions:` key that grants it), so this
     tier only lights up when an org PAT is provided as a secret. Without it we
     say so in the record rather than inventing a number.

  4. repos/{r}/actions/runs/{id}/jobs → per-job started_at/completed_at.
     Always reachable, no secret. Summing (completed-started) over jobs is our
     ALWAYS-AVAILABLE minute proxy. It is runner wall clock, which is what
     GitHub rounds up per job to bill, so it tracks tier-3 closely — it is a
     proxy, and the record labels it as one.

Output (stdout is the markdown record; --json-out writes the machine copy):
    minutes_billed   from (3) when available, else null + a stated reason
    minutes_observed from (4), always
    last e2e run: when, conclusion, duration, commit, link
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"


def _get(url: str, token: str) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "a0-devkit-ci-budget",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt_dur(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _age(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "never"
    d = now - dt
    if d < timedelta(hours=1):
        return f"{int(d.total_seconds() // 60)}m ago"
    if d < timedelta(days=1):
        return f"{int(d.total_seconds() // 3600)}h ago"
    return f"{d.days}d ago"


# ---------------------------------------------------------------- runs / jobs

def collect_runs(repo: str, token: str, workflow: str, days: int) -> list[dict]:
    """Runs of `workflow` in the last `days`. Repo-scoped: always available."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    page = 1
    while page <= 10:  # hard cap: 1000 runs is far more than any window needs
        url = (
            f"{API}/repos/{repo}/actions/runs"
            f"?per_page=100&page={page}&exclude_pull_requests=false"
        )
        try:
            data = _get(url, token)
        except urllib.error.HTTPError as e:  # pragma: no cover - network
            print(f"::warning::runs query failed: {e}", file=sys.stderr)
            break
        runs = data.get("workflow_runs", [])  # type: ignore[union-attr]
        if not runs:
            break
        stop = False
        for r in runs:
            created = _iso(r.get("created_at"))
            if created and created < cutoff:
                stop = True
                continue
            if workflow and r.get("name") != workflow:
                continue
            out.append(r)
        if stop:
            break
        page += 1
    return out


def job_seconds(repo: str, run_id: int, token: str) -> float:
    """Summed per-job runner wall clock. Our always-available minute proxy."""
    try:
        data = _get(f"{API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token)
    except urllib.error.HTTPError:  # pragma: no cover - network
        return 0.0
    total = 0.0
    for j in data.get("jobs", []):  # type: ignore[union-attr]
        a, b = _iso(j.get("started_at")), _iso(j.get("completed_at"))
        if a and b and b > a:
            total += (b - a).total_seconds()
    return total


# ------------------------------------------------------------------- billing

def billed_minutes(org: str, repo_name: str, token: str | None, days: int) -> dict:
    """
    Tier-3 authoritative minutes from the enhanced-billing usage endpoint.

    Returns {"available": False, "reason": ...} when we have no org token, which
    is the DEFAULT for a plugin repo running on GITHUB_TOKEN. We never guess.
    """
    if not token:
        return {
            "available": False,
            "reason": (
                "no org-scoped billing token supplied "
                "(GITHUB_TOKEN is repo-scoped and cannot read org billing)"
            ),
        }
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    months = {(now.year, now.month), (cutoff.year, cutoff.month)}
    minutes = 0.0
    net = 0.0
    gross = 0.0
    gb_hours = 0.0
    seen = False
    for year, month in sorted(months):
        url = (
            f"{API}/organizations/{org}/settings/billing/usage"
            f"?year={year}&month={month}"
        )
        try:
            data = _get(url, token)
        except urllib.error.HTTPError as e:
            return {
                "available": False,
                "reason": f"billing usage endpoint returned HTTP {e.code}",
            }
        for it in data.get("usageItems", []):  # type: ignore[union-attr]
            if it.get("repositoryName") != repo_name:
                continue
            d = _iso(it.get("date"))
            if d and d < cutoff:
                continue
            seen = True
            if it.get("unitType") == "Minutes":
                minutes += float(it.get("quantity") or 0)
                net += float(it.get("netAmount") or 0)
                gross += float(it.get("grossAmount") or 0)
            elif it.get("unitType") == "GigabyteHours":
                gb_hours += float(it.get("quantity") or 0)
    return {
        "available": True,
        "minutes": round(minutes, 1),
        "storage_gb_hours": round(gb_hours, 3),
        "net_usd": round(net, 4),
        "gross_usd": round(gross, 4),
        "note": (
            "netAmount is $0.00 because this repo is PUBLIC and public-repo "
            "Actions minutes are free. The minutes are real; the bill is not."
        )
        if seen and net == 0
        else "",
    }


# -------------------------------------------------------------------- record

def build_record(args: argparse.Namespace) -> dict:
    now = datetime.now(timezone.utc)
    org = args.repo.split("/")[0]
    repo_name = args.repo.split("/")[1]

    runs = collect_runs(args.repo, args.token, args.workflow, args.days)
    finished = [r for r in runs if r.get("status") == "completed"]

    observed = 0.0
    # Cost control: per-run /jobs is one API call each. Cap how many we walk;
    # beyond the cap we report what we measured and say the window was capped.
    walked = finished[: args.max_run_lookups]
    for r in walked:
        observed += job_seconds(args.repo, r["id"], args.token)

    last = finished[0] if finished else None
    last_seconds = job_seconds(args.repo, last["id"], args.token) if last else 0.0

    passes = sum(1 for r in finished if r.get("conclusion") == "success")
    fails = sum(1 for r in finished if r.get("conclusion") == "failure")

    billing = billed_minutes(org, repo_name, args.billing_token, args.days)

    return {
        "schema": "a0-devkit/ci-budget@1",
        "generated_at": now.isoformat(),
        "repo": args.repo,
        "plugin": args.plugin,
        "workflow": args.workflow,
        "window_days": args.days,
        "runs_total": len(finished),
        "runs_measured": len(walked),
        "runs_capped": len(finished) > len(walked),
        "runs_success": passes,
        "runs_failure": fails,
        "minutes_observed": round(observed / 60, 1),
        "minutes_billed": billing,
        "last_run": None
        if not last
        else {
            "id": last["id"],
            "conclusion": last.get("conclusion"),
            "event": last.get("event"),
            "created_at": last.get("created_at"),
            "age": _age(_iso(last.get("created_at")), now),
            "duration": _fmt_dur(last_seconds),
            "duration_seconds": round(last_seconds),
            "sha": (last.get("head_sha") or "")[:8],
            "url": last.get("html_url"),
        },
    }


def render(rec: dict) -> str:
    ico = {"success": "✅", "failure": "❌", "cancelled": "⚪", "timed_out": "⏱️"}
    last = rec["last_run"]
    b = rec["minutes_billed"]

    if b["available"]:
        billed = f"**{b['minutes']} min** (net ${b['net_usd']:.2f})"
        billed_note = b.get("note") or ""
    else:
        billed = "_not available_"
        billed_note = b["reason"]

    # These two numbers are NOT the same measurement and must never be shown as
    # if one validated the other. Measured live on chat_comments: 454 billed min
    # vs 199.8 observed min over the same 30 days. The gap is not error — billing
    # is REPO-WIDE (devkit-sync, unit, Dependabot, every workflow) and rounds each
    # job up to a whole minute, while `observed` is filtered to one workflow.
    scope_note = (
        f"Scopes differ by design: **billed** is repo-wide across *all* workflows "
        f"and rounds each job up to a whole minute; **observed** is `{rec['workflow']}` "
        f"only. Use billed for the invoice, observed for what the e2e suite costs."
    )

    lines = [
        f"## CI budget — `{rec['plugin']}`",
        "",
        f"Window: last **{rec['window_days']} days** · workflow `{rec['workflow']}` "
        f"· generated {rec['generated_at'][:16].replace('T', ' ')} UTC",
        "",
        "| | |",
        "|---|---|",
    ]
    if last:
        lines += [
            f"| **e2e last ran** | [{last['created_at'][:16].replace('T', ' ')} UTC]({last['url']}) "
            f"({last['age']}) |",
            f"| **result** | {ico.get(last['conclusion'], '❔')} `{last['conclusion']}` "
            f"on `{last['sha']}` (via `{last['event']}`) |",
            f"| **that run took** | {last['duration']} |",
        ]
    else:
        lines += [
            f"| **e2e last ran** | ⚠️ **never** — no completed `{rec['workflow']}` run "
            f"in the last {rec['window_days']} days |",
            "| **result** | — |",
            "| **that run took** | — |",
        ]
    lines += [
        f"| **runs in window** | {rec['runs_total']} "
        f"({rec['runs_success']} ✅ / {rec['runs_failure']} ❌) |",
        f"| **minutes billed** _(whole repo, all workflows)_ | {billed} |",
        f"| **minutes observed** _(`{rec['workflow']}` only, runner wall clock)_ | "
        f"{rec['minutes_observed']} min over {rec['runs_measured']} run(s)"
        + (" _(window capped)_" if rec["runs_capped"] else "")
        + " |",
    ]
    if b["available"] and b.get("storage_gb_hours"):
        lines.append(
            f"| **artifact storage** _(whole repo)_ | {b['storage_gb_hours']} GB-hours |"
        )
    lines += ["", f"> {scope_note}"]
    if billed_note:
        lines += ["", f"> {billed_note}"]
    lines += [
        "",
        "<sub>`minutes (observed)` is summed per-job runner wall clock from the "
        "Actions API — a proxy, always available. `minutes (billed)` is the "
        "authoritative org billing figure and only appears when an org-scoped "
        "token is configured. The per-run `/timing` endpoint is deliberately "
        "unused: it reports 0 billable ms on public repos.</sub>",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Generate the plugin CI budget record.")
    p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--plugin", required=True)
    p.add_argument("--workflow", default="plugin-e2e", help="workflow NAME to budget")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--max-run-lookups", type=int, default=40)
    p.add_argument("--json-out", default="")
    p.add_argument("--md-out", default="")
    p.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    p.add_argument(
        "--billing-token",
        default=os.environ.get("BILLING_TOKEN", "") or None,
        help="org-scoped PAT for /organizations/{org}/settings/billing/usage",
    )
    args = p.parse_args()
    if not args.token:
        print("::error::no GITHUB_TOKEN", file=sys.stderr)
        return 1

    rec = build_record(args)
    md = render(rec)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
            fh.write("\n")
    if args.md_out:
        with open(args.md_out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
    print(md)

    # Staleness is a FAILURE MODE, not a footnote. If the operator asked for
    # "when last they ran", a record that quietly says "never" is the devkit-sync
    # bug again. Exit non-zero so a human sees it.
    if args.days and rec["last_run"] is None:
        print(
            f"::error::no completed {args.workflow} run in {args.days} days "
            f"for {args.repo}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
