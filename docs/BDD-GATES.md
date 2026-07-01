# BDD enforcement gates — what failed, what it means, how to cross it

Your `plugin-e2e` build went red and pointed you here. This is the complete map of the
behaviour-BDD enforcement gates (devkit SPEC §5.14, DEC-059–066): every check, the exact error you'll
see, why it exists, and how to make it pass. Nothing here is advisory — each gate is machine-checked,
because humans *and* AI agents both cut corners under deadline.

**Two tiers.** Tier-1 runs in your plugin's own `plugin-e2e` (where the test files live). Tier-2 runs
at the `agent-zero-vendor-plugins` gate when you publish. The gates only apply once your repo bumps its
`tests/_testkit` submodule to a devkit that has them — adoption is per-repo.

**The order a build runs them:** `bdd-lint` (static, fails fast) → devcontainer build → boot A0 →
`run-bdd` red-proof (plugin not installed) → `run-bdd` real run (plugin installed) → [at publish] gate
verified-publish.

---

## Run the gates before you commit (don't wait for CI)

The Tier-1 static gates are fast and need no A0 — run them locally and CI won't surprise you:

```bash
make verify                       # the 3 static gates (feature-purity, honesty, traceability)
python3 tests/_testkit/e2e/lint/bdd_lint.py .   # same thing, if you have no Makefile
make install-hooks                # git pre-commit hook that runs `make verify` automatically
make e2e                          # full run (auto-selects run-bdd: lint + red-proof + e2e) on a nested A0
```

These come **for free** with the standard fragment — a plugin Makefile that has
`-include tests/_testkit/e2e/Makefile.devkit` already provides `verify` / `install-hooks` / `e2e` (the
fragment `-include`s the BDD targets). Same gates as CI, so green locally ⇒ green in the gate.

---

## Tier-1, repo level (your `plugin-e2e`)

### Gate 1 — feature-purity  `[bdd-lint]`

- **You'll see:** `✘ [feature-purity] <file>.feature:<line>  CSS class selector ('.ask-modal') in step …`
  (or `DOM id selector (#…)`, `internal/DOM API name (querySelector/evaluate/getContext/…)`,
  `attribute selector`, `framework directive (x-…)`).
- **Why:** a `.feature` describes *behaviour in a human's words*. Selectors, DOM ids, store names, and
  API calls are *how* the test drives the product — they belong in the step layer, not the scenario.
  Leaking them makes the spec unreadable and couples it to the implementation.
- **Cross it:** rewrite the `Given/When/Then` in plain language ("I pick an option and submit"), and
  move the selector/seam/probe into the matching step definition in `tests/e2e/steps/`.

### Gate 2 — honesty  `[bdd-lint]`

Three checks under one gate:

- **Tracked `@skip`.** `✘ [honesty] <file>.feature:<line>  @skip without a tracked reason`
  - *Why:* a silent skip is invisible lost coverage. *Cross it:* add a `#` comment in the scenario body
    saying **why** it's skipped and where it's tracked (issue/ref), e.g. `# tool-side validation — unit-tier, AUQ-E2E-1`.
- **No swallowed failures.** `✘ [honesty] <file>.steps.ts:<line>  empty catch block …` /
  `.catch() recovers silently instead of failing`
  - *Why:* a `catch {}` or a `.catch(() => null)` turns a real failure into a green pass — the worst kind
    of lie. *Cross it:* let the error propagate, or re-assert with `expect(...)`. Reserve `try/catch` for
    genuinely un-enableable env (a real agent turn, OS clipboard) and assert *something* in it.
- **The four docs exist.** `✘ [honesty] docs/spec/<doc>.md  required doc missing`
  - *Why:* the 4-doc model (DEC-060) is the spec-driven trail. *Cross it:* create all four under
    `docs/spec/`: `behaviour-spec.md`, `implementation-plan.md`, `e2e.feature.md`, `e2e-steps-spec.md`.

### Gate 4 — traceability  `[bdd-lint]`

- **You'll see:** `✘ [traceability] docs/spec/e2e.feature.md  BEH-7 is defined in behaviour-spec.md but
  neither covered nor tracked-skipped in e2e.feature.md`
- **Why:** every behaviour you documented must be either tested or explicitly, visibly not-tested —
  coverage can't silently shrink as you add behaviours.
- **Cross it:** in `e2e.feature.md`, either add a scenario that references that `BEH-n`, or add a line to
  the *Tracked skips* section explaining why it isn't a scenario (e.g. `@tool-internal BEH-3 …`).

### Gate 3 — seam-off red-proof  `[run-bdd]`

- **You'll see:** `::error:: seam-off red-proof FAILED — N behaviour scenario(s) passed with no plugin
  installed (fake-green)`
- **Why:** before installing your plugin, the harness runs the suite once on the same A0. With no plugin,
  your seam endpoint 404s, so honest scenarios must go RED. If any **passes**, it isn't actually
  exercising the plugin — it's asserting nothing.
- **Cross it:** make the scenario depend on real plugin behaviour through the seam/UI. If it passes with
  the plugin absent, it's testing the harness, not your plugin — delete or fix it.

### e2e green  `[run-bdd]`

- **You'll see:** the standard playwright `N failed` with per-scenario `✘`.
- **Cross it:** the normal loop — reproduce on the local disposable A0, fix, confirm green. See the
  `a0-plugin-e2e-bdd` skill for the fork-robustness gotchas (real `chat_create` context;
  hide-overlay-then-real-click) that cause most fork-only failures.

---

## Tier-2, gate level (`agent-zero-vendor-plugins` publish)

### Verified-publish

- **You'll see:** `✘ <name>: plugin-e2e on <repo>@<commit> is 'not-green' — refusing to publish`
  (or `'none'` = no e2e check found on that commit, `'query-failed'` = couldn't read it).
- **Why:** the gate can't run your tests (it only holds the zip), so it requires proof that your
  `plugin-e2e` (Tier-1 lint + red-proof + e2e) was **green on the exact commit** the zip came from.
- **Cross it:** ensure your plugin's `plugin-e2e` check is green on `source_commit`, and that
  `source_repo` + `source_commit` in `plugins/<name>.meta.yaml` point at that commit. `none` usually
  means the commit predates the check or it's the wrong SHA; `query-failed` for a private repo means the
  gate needs `GATE_VERIFY_TOKEN` (a PAT with `repo:read`).
- **Opt-out:** omit both fields and the plugin publishes legacy-style (unverified). Once you add them,
  enforcement is hard.

### Why the PR *merge button* isn't hard-blocked (and what we do instead)

On **free private repos**, GitHub does **not** offer required status checks — via neither branch
protection nor rulesets (both are paid: Pro/Team/Enterprise). So nothing GitHub-native can stop a red
PR from being merged. Two layers compensate:

- **Merge-guard (PR-level deterrent).** The `plugin-e2e` workflow's `merge-guard` job converts a PR to
  **draft** when the check is red (and marks it ready when green) — a draft can't be merged via the
  normal button. It's friction + a clear signal, **not** a lock: a maintainer can re-ready a draft, or
  push straight to a branch with no PR. Needs `permissions: pull-requests: write` on the caller (the
  template sets it).
- **Verified-publish (the real block).** Shipping a plugin goes through the gate, which refuses to
  publish unless `plugin-e2e` was green on `source_commit`. So a red plugin **can be merged but can
  never ship**. That's the hard guarantee; the merge-guard just makes the red state obvious earlier.

If you later move repos to a paid tier, add a ruleset requiring the `e2e` check and the merge button is
hard-blocked too — the merge-guard then becomes redundant and can be dropped.

---

## Quick fix-it index

| Error fragment | Gate | Fix |
|---|---|---|
| `selector … in step` | feature-purity | move the "how" to the step layer |
| `@skip without a tracked reason` | honesty | add a `#` reason + ref |
| `catch … swallows` / `.catch() recovers` | honesty | propagate or re-assert |
| `required doc missing` | honesty | add the 4 `docs/spec/` docs |
| `BEH-n … neither covered nor tracked` | traceability | add a scenario or a tracked-skip line |
| `passed with no plugin installed` | red-proof | make the scenario actually use the plugin |
| `refusing to publish` | verified-publish | get plugin-e2e green on `source_commit` |

See also: the `a0-plugin-e2e-bdd` skill (method + fork gotchas) and `SPEC.md` §5.14 / DEC-059–066.
