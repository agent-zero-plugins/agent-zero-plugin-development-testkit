# Changelog

All notable changes to the plugin devkit. This project follows [Semantic Versioning](https://semver.org).

Consumers track the **latest release tag** (not `main`) — the `devkit-sync` workflow bumps a repo's
`tests/_testkit` pin to the newest tag nightly, and `make update-devkit` defaults to it. See `CLAUDE.md`.

**What a MAJOR bump means for the devkit** (a change that could fail a previously-green consumer):
the frozen Make target contract (SPEC Appendix E.1), the reusable workflow inputs/behaviour, the
`Makefile.devkit` / `.devkit.yml` interface, or a tightening of the enforcement gates.
**MINOR** = new backward-compatible targets/checks/assets. **PATCH** = fixes that don't change the contract.

## v2.1.5 — 2026-08-04

- **Fix: traces still were not captured on green runs in consumers** (DEC-073, completing it).
  v2.1.4 changed the trace default to `on` in `playwright-base.config.ts`, but two other places
  still forced `retain-on-failure` and won: the reusable workflow hardcoded
  `BDD_TRACE: ${{ inputs.capture-all-traces && 'on' || 'retain-on-failure' }}`, and the BDD suite
  keeps its **own** `e2e/bdd/playwright.config.ts` whose default was also `retain-on-failure`.
  Consumers therefore still shipped `copied 0 trace(s)` on a green run — the exact defect DEC-073
  was written to fix, reported as fixed while two of the three settings still disagreed.
  New `trace-mode` input (default `on`) replaces the boolean flip; `capture-all-traces` is kept for
  caller compatibility but is now a no-op in the default direction.

## v2.1.4 — 2026-08-04

- **Fix: Dependabot PRs could never go green** (DEC-075). The reusable workflow declared its
  App-token secrets `required: true`, but Dependabot runs receive no repo secrets — so every
  dependency bump failed with `Input required and not supplied: app-id`, a failure unrelated to the
  bump itself. Five PRs across the fleet were red for this reason. All secrets are now optional and
  each consuming step is guarded on presence; the devkit is a public repo, so the submodule clones
  anonymously by default. Consumers with a private devkit are unaffected (the token is still used
  when available). This is also what allows an outside contributor's fork PR to run the suite.
- **De-duplicated the shared e2e logic** (DEC-076). The artifact collector existed twice
  (`run-bdd.sh`, `run-lifecycle.sh`) and had drifted — only one sanitised scenario names, and the
  recent "empty artifact on green runs" fix landed in one copy while the other stayed broken. The
  retention prune existed twice as inline YAML. Now: `e2e/harness/_artifacts.sh` sourced by both
  harnesses, `e2e/ci/prune-artifacts.sh` invoked by both workflows.

- **Fix: e2e runs uploaded a near-empty artifact.** Two independent defects, both of which made a
  *green* run undiagnosable. (1) `trace: retain-on-failure` meant a passing run produced no trace at
  all, so there was no ground truth to diff a later regression against — traces are now **always
  captured** (DEC-073), still overridable via `BDD_TRACE`. (2) Both harnesses (`run-bdd.sh` **and**
  `run-lifecycle.sh`) copied only `trace.zip`, silently dropping the `.png`/`.webm` Playwright writes
  next to it — `screenshot: "on"`/`video: "on"` were always capturing them, nothing shipped them. As a
  result the sample workflow's "convert video → GIF" step had never produced a single GIF. Both
  collectors now ship traces + screenshots + videos, scenario-prefixed and suffix-preserving.
  Measured on the devkit's own self-test: 4 files uploaded before, traces+shots+videos after.
- **New: count-based artifact retention — keep the last N runs** (DEC-074). GitHub has no native
  keep-last-N setting (`retention-days` is time-based only), so the policy is enforced by an explicit
  prune step after upload. New `artifact-keep` input on `plugin-e2e.yml` (**default 5**);
  `retention-days` raised to 90 as a pure backstop so the prune — not expiry — decides what
  disappears. Also applied to the devkit's own `sample-plugin-e2e.yml`, which had no count policy at
  all and had accumulated 25 live artifacts.
  **Consumer action:** the prune needs `actions: write`, and a reusable workflow's permissions are
  capped by the **caller's** grant. Re-run `make link-workflows` to pick up the updated caller
  template; until then the prune warns instead of pruning (non-fatal by design).

## v2.1.3 — 2026-07-10

- **Fix: ESM-safe type imports in the e2e page objects.** `ChatPage`/`PluginsPage`/`LoginPage` value-imported
  the type-only `Locator`/`Page` exports from `@playwright/test`. That crashes with
  `does not provide an export named 'Locator'` when a consumer repo's `tests/e2e/package.json` declares
  `"type": "module"` (e.g. a pre-existing spec suite), which flips the whole step-import chain to strict ESM.
  Now `import type`. Surfaced by gitnexus's v2 adoption.

## v2.1.2 — 2026-07-04

- **Skills: durable debugging/lifecycle learnings (from the chat-radar v2 adoption).**
  - `a0-plugin-e2e-bdd` → "Debugging & harness truths": isolate what a symptom *proves* before fixing
    (renders-blank-live = environment/global-collision; renders-in-pod-but-empty = data/seed, e.g. an
    `/import_chat` 404); an asserting test can encode the wrong spec intent; harness plumbing (features/
    flips the harness + retires the seed hook, filesystem seed seam via `A0_CONTAINER`, fresh page +
    `workers=1` state leak, escape `/` in Cucumber, `BDD_SKIP_INSTALL` hides install-path bugs);
    admin-merge-past-infra-red discipline; delegate-but-review.
  - `a0-plugin-architecture` §22 → shared-page/lifecycle/state gotchas: IIFE-wrap inline classic scripts
    (window-global collision across 30+ plugins); OCI deploy skips install/enable hooks → self-register at
    a startup seam; gitignore runtime data dirs; no split-brain state; best-effort side-effects must never
    fail the main path.
  - `troubleshoot-plugin-deployment` → "setup never ran after OCI deploy" symptom + fix.

## v2.1.1 — 2026-07-04

- **Skill (`a0-plugin-e2e-bdd`): fixture patterns for seamless UI plugins.** Captures the three patterns
  proven across share-chat / fullscreen-toggle / mermaid-diagrams / diff-visualizer / chat-comments —
  pure-UI control, render-a-code-block (inject the node A0 emits; wait for the CDN renderer *before*
  injecting; assert the rendered output, not the transient `data-…-processed` marker; feed diff2html a
  full git diff), and store-driven (drive public store methods, assert observable effects) — plus the
  local-A0 boot gotcha (neutralize `run_sshd`; reinstall chromium after cache eviction).

## v2.1.0 — 2026-07-04

- **Playwright traces replace the webm→GIF artifact.** Every captured scenario now ships a single
  `trace.zip` (network + DOM snapshots + console + video + timeline), viewable with
  `npx playwright show-trace <file>` or trace.playwright.dev. Both harnesses (`run-bdd`, `run-lifecycle`)
  collect `trace.zip`; the flaky `ffmpeg`→GIF step is gone. Artifact renamed `e2e-recording-*` → `e2e-traces-*`.
- **Capture scope:** failing scenarios by default (`retain-on-failure`). Run the `plugin-e2e` workflow via
  **workflow_dispatch with `capture_all_traces: true`** to capture a trace for *every* scenario
  (threads through to `BDD_TRACE=on`). Locally: `BDD_TRACE=on make e2e`.
- Consumers re-run `make link-workflows` to pick up the new dispatch input (the default already flows via `@main`).

## v2.0.1 — 2026-07-04

- **Fix: lint the repo root, not `plugin_dir`.** `bdd_lint` is now run against the repo root (where
  `tests/e2e/` and `docs/spec/` actually live, per `run-bdd`), fixing subdir-layout plugins
  (`plugin_dir: usr/plugins/<name>`) where the lint previously looked in the wrong place. No effect on
  root-layout plugins.

## v2.0.0 — 2026-07-04  (BREAKING)

- **BDD behaviour tests are now mandatory** (DEC-069). `bdd_lint` **hard-fails a plugin with no
  `tests/e2e/features/`** — the previous "self-skip for non-BDD plugins" was a silent loophole (no tests
  ⇒ no gate ⇒ green). There is no lifecycle-only escape; every plugin on the devkit must ship behaviour
  tests. **This is why it's a major bump** — it fails every currently-green non-BDD plugin.
- **Rollout via a major-version channel** — `devkit-sync` and `make update-devkit` now bump only within
  your major (`.devkit.yml devkit_major`, default `1`), so the nightly sync never force-jumps a repo to
  v2. Adopt deliberately: `make update-devkit DEVKIT_REF=v2.0.0` and set `devkit_major: 2`. MINOR/PATCH
  releases still auto-flow within the channel.

## v1.1.1 — 2026-07-01

- **Dropped the misleading `sync-skills` make target.** It only searched one source repo, but the
  plugin-facing skills are split across `agent-zero-operator-skills` and `agent-zero-plugins-skills` (plus
  one vendored), so it would silently miss most of them. Refreshing `skills/` before a release is a manual
  copy from each skill's canonical repo (documented in `CLAUDE.md`).

## v1.1.0 — 2026-07-01

- **Devkit ships the plugin-facing skills** (DEC-068). `make link-skills` (folded into `link-devkit`,
  run by `init.sh`) symlinks the devkit's `skills/` into a plugin's `.claude/skills/` — so a developer or
  agent in a bare plugin clone gets the runbook skills (`a0-plugin-e2e-bdd`, `a0-plugin-architecture`, …),
  not just the machinery. Symlinks auto-refresh on a devkit bump. Added `a0-plugin-e2e-bdd` to the set.

## v1.0.0 — 2026-07-01

First tagged release — the production standard, proven across the plugin fleet (19 plugins on the shared
harness; the ask-user-question BDD pilot green on the fork image).

- **Devkit core:** reproducible devcontainer; reusable `plugin-e2e` + `devkit-sync` workflows; the pytest
  static-assertion library; the playwright lifecycle + in-browser behaviour hooks; the frozen Make target
  set via `e2e/Makefile.devkit`.
- **Two-tier A0 fork model + fork-first e2e** (DEC-049/054/055): default test image is the deployed fork.
- **Cycle-3 behaviour-first BDD e2e** (DEC-059–065): the 5-subagent spec pipeline, the 4-doc model, the
  deterministic LLM-less seam, and the batteries-included playwright-bdd layer.
- **Two-tier enforcement** (DEC-066): Tier-1 repo gates (feature-purity · honesty · traceability ·
  seam-off red-proof) hard-fail in `plugin-e2e`; Tier-2 verified-publish at the gate; a merge-guard for
  free private repos; the `.gemini` AI-reviewer styleguide; local `make verify` + a pre-commit hook.
- **One-command adoption + upgrades** (DEC-067): `bash tests/_testkit/init.sh`, `make link-devkit`,
  `make update-devkit` (defaults to the latest release tag).
