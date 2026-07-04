# CLAUDE.md — agent-zero-plugin-development-testkit

Guidance for Claude Code (and any agent) working in or with this devkit. The devkit is the **single
source of truth** for how Agent Zero plugins are built, tested, documented, and shipped. The canonical
design is [`SPEC.md`](SPEC.md); the readable map is [`README.md`](README.md); the enforcement gates and
their fixes are in [`docs/BDD-GATES.md`](docs/BDD-GATES.md).

---

## Distribution — how a repo imports the devkit *with all its assets*

The devkit distributes in **two channels**, and both matter:

1. **The submodule = referenced-in-place content** (auto-freshened). Everything under `tests/_testkit/…`
   is used *where it sits*: the e2e harness, the `bdd_lint.py`, the playwright-bdd layer, the Makefile
   fragment, the `.gemini` source, the pytest library.
2. **Root-level assets = copied/symlinked once** (GitHub Actions, Gemini, and `make` only read these from
   the repo root, never from a submodule): the caller workflows in `.github/workflows/` and `.gemini/` are
   **copied**; the plugin-facing **skills** are **symlinked** into `.claude/skills/` (Claude Code follows
   symlinks, so they auto-refresh on a devkit bump). All done by `make link-devkit` and committed. So a
   developer/agent cloning the plugin gets the machinery *and* the runbook skills (`a0-plugin-e2e-bdd`, …).

### New repo — the full import (gets everything, including the Makefiles)

```bash
# 1. Vendor the devkit as a submodule (it IS the content; no PyPI/registry).
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit tests/_testkit

# 2. One-shot adopt: writes the root Makefile + .devkit.yml (inferred from plugin.yaml),
#    copies the root-level assets (caller workflows + .gemini), installs the pre-commit hook.
bash tests/_testkit/init.sh

# 3. Review + commit.
git add .gitmodules tests/_testkit Makefile .devkit.yml .github/workflows .gemini && git commit -m "chore: adopt plugin devkit"
```

`init.sh` is idempotent — re-run it after a devkit bump to re-copy the root assets. It writes a root
Makefile whose single `-include` gives the frozen target set **plus** the BDD verification targets (the
fragment `-include`s `e2e/make/bdd.mk`):

| Target | What it does |
|---|---|
| `make verify` | Tier-1 static gates (feature-purity · honesty · traceability) — **fast, no A0; run before every commit** |
| `make install-hooks` | install a git pre-commit hook that runs `make verify` |
| `make e2e` | full behaviour suite in the devcontainer — **auto-selects `run-bdd` if `tests/e2e/features/` exists**, else the classic lifecycle; forwards `.devkit.yml e2e_pod_env` seam vars |
| `make package` / `build` / `up` / `conformance` | package the zip / assemble / boot A0 to explore / assert the frozen targets exist |
| `make link-devkit` (`link-workflows` + `link-gemini` + `link-skills`) | copy/symlink all devkit-shipped assets (workflows, `.gemini`, `.claude/skills`) |

### Keeping it fresh

- The **`devkit-sync`** workflow bumps the `tests/_testkit` submodule pin to the latest devkit `main`
  nightly. Because the submodule *is* the content, the harness / lint / BDD layer / Makefile fragment /
  `.gemini` source all update automatically on the bump.
- **Root-copied files do NOT auto-update** (nightly sync only moves the pin; `GITHUB_TOKEN` can't push
  workflow files). When a caller workflow or `.gemini` styleguide changes upstream, re-run
  `make link-devkit` and commit. **Skills are the exception** — they're *symlinks* into the submodule, so
  they refresh automatically when the pin bumps; no re-link needed.
- **Skills provenance (avoid drift):** `skills/` in the devkit is a *distribution snapshot* — the
  **canonical homes are split across skill repos**: `a0-plugin-e2e-bdd` → `agent-zero-operator-skills`;
  `a0-plugin-architecture` / `a0-bootstrap-plugin` / `author-plugin-from-template` /
  `plugin-manifest-contract` / `rotate-plugin-credentials` / `troubleshoot-plugin-deployment` →
  `agent-zero-plugins-skills`; `a0-plugin-testkit` is vendored. A maintainer **manually copies** the
  changed skill(s) from the right repo into `skills/` before cutting a release (no automated sync target —
  the sources are split, so a one-source helper would be misleading).

### The four enforcement layers a consumer gets (fastest-first)

`make verify` / pre-commit hook → `.gemini` AI review → CI (`plugin-e2e`: lint + seam-off red-proof +
e2e, hard-fail) → publish gate (verified-publish blocks shipping). Adoption is **per-repo on the
submodule bump + `make link-devkit`** — hard the instant a repo is on the new devkit, no fleet breakage.

---

## Versioning & releases (DEC-067)

The devkit ships **SemVer release tags** (`vMAJOR.MINOR.PATCH`), starting at **v1.0.0**. Consumers track
the **latest tag within their MAJOR channel**, not `main`: `devkit-sync` and `make update-devkit` bump
only within the consumer's major (`.devkit.yml devkit_major`, default **1**), so **a new MAJOR is never
force-adopted** — MINOR/PATCH auto-flow, but moving to the next major is deliberate. `main` is the
integration branch; releases are cut from it.

- **Opting into a new major** (e.g. **v2.0.0**, which hard-requires BDD tests): `make update-devkit
  DEVKIT_REF=v2.0.0`, then set `devkit_major: 2` in `.devkit.yml`. Do it when the plugin is ready to meet
  the new major's requirements — not before.

- **MAJOR** — could fail a previously-green consumer: the frozen Make targets (Appendix E.1), reusable
  workflow inputs/behaviour, the `Makefile.devkit`/`.devkit.yml` interface, or a gate tightening.
- **MINOR** — backward-compatible new targets/checks/assets. **PATCH** — non-contract fixes.
- **Cutting a release:** update `CHANGELOG.md`, merge to `main`, then `git tag vX.Y.Z <commit>` + push +
  a GitHub release. History + the exact policy live in [`CHANGELOG.md`](CHANGELOG.md).

---

## Working *on* the devkit itself

- **Author decisions in the SPEC.** Non-trivial changes get a numbered `DEC-NNN` + `REQ` in `SPEC.md`
  (method: the `spec-driven-development` skill). Don't leave a decision only in code or a commit message.
- **Gates change ⇒ update all three faces:** the enforcer (`e2e/lint/bdd_lint.py`, `e2e/harness/`), the
  reference (`docs/BDD-GATES.md`), and the review styleguide (`.gemini/styleguide.md`) — keep them in sync.
- **Makefile fragments:** the frozen targets live in `e2e/Makefile.devkit`; BDD targets in
  `e2e/make/bdd.mk` (included by the fragment). No inline comments on `VAR ?=` lines (Make folds trailing
  spaces into the value).
- **The reusable workflows** (`.github/workflows/plugin-e2e.yml`, `devkit-sync.yml`) are consumed
  `@main` by every plugin — treat them as a public contract; keep changes backward-compatible.
- **Never test against the operator's live A0** — boot a disposable instance (see `no-live-a0-for-testing`).
- Method/runbook for authoring a plugin's BDD e2e: the `a0-plugin-e2e-bdd` skill.
