# CI budget + nightly upstream-compat — design

Two capabilities for the devkit, built against
`agent-zero-plugin-development-testkit` and its four consumers
(`chat-comments`, `diff-visualizer`, `mermaid-diagrams`, `share-chat`).

Everything below that states an API behaviour was **probed live on 2026-08-05**,
not assumed. Where an endpoint does not give us what the operator asked for, that
is said plainly rather than papered over.

---

## Part 0 — what the GitHub API actually gives us

I probed four candidate sources before designing anything. Three of the four are
either dead or useless here.

| # | Endpoint | Result | Verdict |
|---|---|---|---|
| 1 | `GET /orgs/{org}/settings/billing/actions` | **HTTP 410** "This endpoint has been moved." (`gh` also reports it wants `admin:org`) | Dead. |
| 2 | `GET /orgs/{org}/settings/billing/shared-storage` | **HTTP 410**, same | Dead. |
| 3 | `GET /repos/{r}/actions/runs/{id}/timing` | Reachable with a plain repo `GITHUB_TOKEN`, but returns **`billable.UBUNTU.total_ms = 0`** on every run | **Useless here** — see below. |
| 4 | `GET /organizations/{org}/settings/billing/usage?year=&month=` | **Works.** Real per-repo, per-day minutes | The only true billing source. |

### 3 is a trap, and it is the obvious thing to reach for

`/timing` looks exactly like the answer. It is not. Three real
`chat-comments` runs returned:

```json
{"billable":{"UBUNTU":{"total_ms":0,"jobs":2,
  "job_runs":[{"job_id":92153588155,"duration_ms":0},
              {"job_id":92156121906,"duration_ms":0}]}},
 "run_duration_ms":810000}
```

All four consumer repos are **public**, and public-repo Actions minutes are free,
so GitHub reports **zero billable milliseconds**. A budget built on `/timing`
would report `0 min` for every plugin forever and look like it worked. The design
therefore *deliberately does not use it*, and the generated record says so on its
face so nobody "fixes" it back later.

`run_duration_ms` in the same payload is real, but it is whole-run wall clock
including queue and idle gaps between jobs — not a cost figure.

### 4 works, with one structural limitation that shapes the whole design

```
GET /organizations/agent-zero-plugins/settings/billing/usage?year=2026&month=8
```

returns one row per (day, repo, SKU) — 191 rows for August, covering **27 repos
including all four consumers**:

```json
{"date":"2026-08-04T00:00:00Z","product":"actions","sku":"Actions Linux",
 "quantity":78.0,"unitType":"Minutes","netAmount":0.0,
 "repositoryName":"agent-zero-plugin-chat-comments"}
```

So **minutes are real and per-repo**. Two caveats worth stating:

- **The unfiltered call lies by omission.** With no `year`/`month` it returns
  only **8 aggregate rows** covering 5 repos. With `?year=&month=` it returns
  **191**. Anyone probing this endpoint casually would conclude our plugins have
  no CI usage. They do.
- **`read:org` was sufficient** on the operator PAT — this one does *not* need
  `admin:org`, unlike the two dead endpoints.

**The limitation that drives the architecture:** a workflow's `GITHUB_TOKEN` is
repo-scoped. There is no `permissions:` key that grants org billing — the
capability does not exist in the workflow token model at all. So **tier 3 is
unreachable from inside a plugin repo's own CI unless an org PAT is supplied as
a secret.** I did not work around this, because the available workarounds all
involve inventing a number.

### What we use instead, and what it is honestly worth

`GET /repos/{r}/actions/runs/{id}/jobs` gives per-job `started_at` /
`completed_at` on any token. Summing `(completed − started)` across jobs is a
**runner-wall-clock proxy** — always available, no secret. Since GitHub bills
per job rounded up to the whole minute, it tracks the real figure closely but is
not identical to it.

**It is not the same measurement as tier 3, and the record never implies it is.**
Measured live on `chat_comments` over the same 30 days:

| | value | scope |
|---|---|---|
| billed (tier 3) | **454.0 min** | whole repo, *every* workflow, rounded up per job |
| observed (tier 4) | **199.8 min** | `plugin-e2e` only |

The 2.3× gap is not error — it is `devkit-sync` + `unit` + Dependabot + rounding.
An early draft of the record showed these as adjacent bare numbers, which reads
as "one of these is wrong". The shipped version labels each with its scope and
carries a one-line note explaining the difference. **Use billed for the invoice,
observed for what the e2e suite costs.**

One more honesty note: `netAmount` was **not** always `$0.00` despite the repos
being public (`chat_comments` 30-day net was **$1.60**, `share_chat` **$0.16**).
The naive "public means free" assumption does not hold in this org's billing
data. The record reports whatever the API returns and does not assert the repos
are free.

---

## Part A — CI budget / e2e record per plugin

### Where the record lives, and why

The operator asked for a record "on every one of the plugin records", showing CI
minutes, when e2e last ran, and its result. Options considered:

| Option | Durable | Zero churn | Verdict |
|---|---|---|---|
| Committed `docs/CI-BUDGET.md` | yes | **no** — a commit (or PR) per run whose only delta is a timestamp | **rejected** |
| Job summary only | **no** — dies with the run | yes | insufficient alone |
| README badge | yes | no (same commit churn), and cannot show minutes | insufficient |
| shields.io endpoint badge | yes | yes | needs external JSON hosting we don't have |
| **Long-lived issue, body upserted in place** | **yes** | **yes** | **chosen** |

**Chosen: all three tiers of output, with the issue as the durable one.**

1. **Job summary** on every invocation — free, immediate, on the run page.
2. **`ci-budget.json` artifact** — machine-readable, so a future fleet roll-up
   has something to consume without re-querying.
3. **One long-lived issue per repo**, titled `CI budget — <plugin>`, label
   `ci-budget`, whose **body is replaced in place**.

Why the issue wins:

- **Zero commits, zero PRs, zero branches.** This is the hard constraint after
  the devkit-sync deletion. A committed markdown file fails it outright.
- **Editing an issue body sends no notification**, so it can refresh as often as
  we like without training anyone to filter it out.
- **Durable and permalinked**, unlike a job summary that vanishes with the run's
  retention.
- It is already where maintainers look, and it is pinnable per repo.

### Staleness is a failure, not a footnote

`ci-budget.py` **exits 2** when there is no completed e2e run in the window, and
the record renders `⚠️ never` rather than a blank. This is the same defect class
as devkit-sync's silent three-week no-op: a record that quietly says nothing is
worse than no record. `fail-on-stale` (default `false`) promotes it to a red
job once the fleet's cadence is steady.

### Cadence

Weekly (`cron: 40 6 * * 1`), not per-PR. It is a rolling 30-day view — running
it per-PR would spend runner time to change a timestamp. Also
`workflow_dispatch`-able for an on-demand read. The job itself is a handful of
API calls, ~20s, no containers.

### Files

- `scripts/ci-budget.py` → `e2e/scripts/ci-budget.py`
- `scripts/upsert-record-issue.sh` → `e2e/ci/upsert-record-issue.sh`
- `workflows/ci-budget.yml` → `.github/workflows/ci-budget.yml` (reusable)
- `templates/ci-budget.caller.yml` → `templates/`, distributed by
  `make link-workflows`

`BILLING_READ_TOKEN` is an **optional** secret. Absent, the record is fully
useful and states in words that billed minutes are unavailable and why. Present,
tier 3 lights up. Both paths are live-verified below.

---

## Part B — nightly upstream-compat

### The gap it closes (verified, not assumed)

All four consumers' `.devkit.yml` files were read directly. **None sets
`a0_image`**, so all four inherit the reusable workflow's default —
`ghcr.io/nuevanext/agent-zero:latest-nonroot`, the private fork. The fleet's e2e
today proves *"works on the fork"* and says **nothing** about *"still works on
upstream"*.

The machinery genuinely does mostly exist: `plugin-e2e.yml` accepts `a0_image`,
and `sample-plugin-e2e.yml` already boots `docker.io/agent0ai/agent-zero:latest`.
What is missing is the scheduled fan-out and a place the result is seen. That is
all this adds.

### How it differs from the deleted devkit-sync nightly

devkit-sync burned 189 runs for 29 merged bumps, then silently no-op'd for three
weeks. Three concrete structural differences:

**1. Change-gated, not calendar-gated.**
A ~20s `probe` job resolves the upstream **manifest digest** anonymously from
Docker Hub and only fans out when the digest actually moved since the last green
full run. State lives in `actions/cache` keyed by digest — no commits, no state
file, no PR. Live-verified:

```
$ bash scripts/upstream-digest.sh docker.io/agent0ai/agent-zero:latest
sha256:8c5eff81a46fc956bc247e01a345beadc09acbeecf31873324b843dacf937c4c
```

The probe still runs **every night**, so detection latency is unchanged (≤24h).
Only the expensive part is gated.

**2. It cannot silently no-op.** Four independent guards:
- the probe **hard-fails** if it cannot resolve a digest (a shrug-and-exit-0
  probe is exactly how devkit-sync died unnoticed);
- an **empty matrix is a hard error**, not a vacuous pass;
- a **`MAX_SKIP_DAYS: 7` floor** forces a full run even if upstream never moves;
- the `report` job asserts that *if the probe requested a fan-out, the matrix
  actually produced a result* — otherwise it fails.
- Every outcome stamps a `last checked` timestamp into the record, so staleness
  is visible on the artifact itself.

**3. Zero PR churn.** It never opens a PR and never commits. Its only write is
**one** long-lived issue in `MODE=only-on-failure`: opened when a plugin breaks
against upstream, **closed automatically** when the fleet is green again. An open
issue always means "act"; there is no steady-state noise to learn to ignore.

### Signal someone sees

Primary: the **scheduled workflow's own red X**, which GitHub emails to the
workflow owner on a scheduled-run failure. Secondary and durable: the
auto-opening record issue. Tertiary: per-leg Playwright traces uploaded
`if: failure()` only — a green nightly uploading four full trace sets every week
is storage the operator pays for and nobody opens.

### Cost/benefit — the honest numbers

Real per-plugin e2e durations, measured from the most recent green run of each:

| plugin | e2e job |
|---|---|
| chat-comments | 12m 39s |
| diff-visualizer | 13m 02s |
| mermaid-diagrams | 11m 00s |
| share-chat | 5m 49s |
| **one full fan-out** | **≈ 42 min** |

Upstream release cadence, from Docker Hub tag timestamps (`v2.8` 08-01, `v2.7`
07-27, `v2.6` 07-23, `v2.5` 07-17, `v2.4` 07-10, `v2.3` 07-09, `v2.2` 07-02,
`v2.1` 06-26, `v2.0` 06-24) — **≈ 9 releases in 6 weeks ≈ 1.5/week ≈ 6.5/month.**

| strategy | runner-min / month |
|---|---|
| naive calendar nightly (30 × 42) | **≈ 1,275** |
| digest-gated (≈7 full runs + 30 probes) | **≈ 295 + ~10** |

**≈ 76% cheaper for identical detection latency.** Because upstream ships more
often than weekly, the `MAX_SKIP_DAYS` floor will rarely fire — it is insurance
against upstream going quiet, not a routine cost.

**The honest caveat:** at ~1.5 releases/week the digest changes often enough that
this is *not* nearly-free — it is roughly 295 min/month, ~23% of a naive nightly
but still a real recurring spend. Whether that is worth it depends on one
question the operator should answer, not me: **do these plugins need to work on
upstream A0 at all, or only on the fork they are deployed against?** If only the
fork, this workflow is ~295 min/month of information nobody acts on and should
not be adopted. If upstream compatibility is a shipped promise, this is the
cheapest way to hold it, and the current state — where *nothing* tests upstream —
means the promise is untested today.

A cheaper variant if the answer is "nice to have": change `MAX_SKIP_DAYS` to 14
and add a `plugins` subset so only the two most upstream-coupled plugins run per
digest. I did not default to that because a partial check that silently omits
plugins is the ambiguity this whole design is trying to remove.

### `secrets` in `if:` — avoided by construction

Per the explicit warning: the `secrets` context is **not** permitted in an `if:`
expression; using it invalidates the entire workflow file and the run dies as
`startup_failure` with zero jobs. `ci-budget.yml` therefore probes
`BILLING_READ_TOKEN` in a **`run:` step** (where secrets *are* available via
`env:`) and branches on `steps.creds.outputs.have_billing`. This mirrors the
existing pattern already proven in `plugin-e2e.yml`'s "Detect whether App
credentials are available" step. `upstream-compat.yml` uses no secrets at all —
the upstream image is public and the digest probe is anonymous.

---

## Validation performed

```
YAML  (python3 -c "import yaml; yaml.safe_load(open(...))")
  OK  workflows/ci-budget.yml
  OK  workflows/upstream-compat.yml
  OK  templates/ci-budget.caller.yml

bash -n
  OK  scripts/upsert-record-issue.sh
  OK  scripts/upstream-digest.sh

shellcheck                      CLEAN (both scripts, zero findings)
python3 -m py_compile           OK  scripts/ci-budget.py
```

**Live end-to-end runs against the real API** (not mocks):

- `upstream-digest.sh` → resolved the real Docker Hub digest anonymously.
- `ci-budget.py` **without** a billing token (simulating `GITHUB_TOKEN`) →
  rendered a complete record, billed minutes marked *not available* with the
  reason. rc=0.
- `ci-budget.py` **with** the org token → tier 3 lit up: `454.0 min`,
  `net $1.60`, `20.768 GB-hours`. rc=0.
- `ci-budget.py` against `share-chat` → `105.0 min` / `54.3 min` observed. rc=0.
- **Stale path**: asked for a workflow that has never run → rendered
  `⚠️ never — no completed upstream-compat run in the last 30 days` and
  **exited 2**, as designed.

### Not validated

The two workflows have **not been executed on GitHub Actions** — that needs a
commit to a repo, which this task explicitly forbids. YAML validity, script
correctness and every API call they make are verified; job wiring
(`needs`/`outputs`/matrix `fromJSON`) is reviewed but not run. The nested-A0 leg
in `upstream-compat.yml` is adapted from the proven `plugin-e2e.yml` body with
one real change — the plugin is checked out into `plugin/` and mounted at
`/plugin`, because this workflow runs in the *devkit's* workspace rather than the
consumer's. That path change is the highest-risk untested detail and should be
the first thing a trial `workflow_dispatch` exercises.

---

## Install map

| built here | goes to |
|---|---|
| `scripts/ci-budget.py` | devkit `e2e/scripts/ci-budget.py` |
| `scripts/upsert-record-issue.sh` | devkit `e2e/ci/upsert-record-issue.sh` |
| `scripts/upstream-digest.sh` | devkit `e2e/ci/upstream-digest.sh` |
| `workflows/ci-budget.yml` | devkit `.github/workflows/ci-budget.yml` |
| `workflows/upstream-compat.yml` | devkit `.github/workflows/upstream-compat.yml` |
| `templates/ci-budget.caller.yml` | devkit `templates/` + one line in `link-workflows` |

`upstream-compat.yml` lives **only** in the devkit and needs no consumer change —
it checks the plugin repos out itself. Only `ci-budget` needs a caller
distributed to the four consumers.
