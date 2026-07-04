# Changelog

All notable changes to the plugin devkit. This project follows [Semantic Versioning](https://semver.org).

Consumers track the **latest release tag** (not `main`) — the `devkit-sync` workflow bumps a repo's
`tests/_testkit` pin to the newest tag nightly, and `make update-devkit` defaults to it. See `CLAUDE.md`.

**What a MAJOR bump means for the devkit** (a change that could fail a previously-green consumer):
the frozen Make target contract (SPEC Appendix E.1), the reusable workflow inputs/behaviour, the
`Makefile.devkit` / `.devkit.yml` interface, or a tightening of the enforcement gates.
**MINOR** = new backward-compatible targets/checks/assets. **PATCH** = fixes that don't change the contract.

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
