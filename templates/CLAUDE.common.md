<!-- a0:common:start -->
<!--
  SHARED block, identical across every agent-zero-plugins repo. Maintained in the devkit
  (templates/CLAUDE.common.md) and refreshed by devkit-sync (DEC-046). Do NOT hand-edit this
  block in a consumer repo — edits here are overwritten. Put repo-specific guidance OUTSIDE
  the markers, below.
-->

# Agent Zero plugin — common Claude guidelines

This repository is an **Agent Zero plugin** built to the org **Plugin Quality & Structure
Standard**. The binding contract is the SPEC, committed in the devkit:
`agent-zero-plugins/agent-zero-plugin-development-testkit/SPEC.md` (query it for authoritative
REQ/DEC; it is the system of record, not anyone's memory — DEC-045).

## Layout (DEC-042/043)
- Plugin source — the exact install payload — lives at `usr/plugins/<name>/` (mirrors the A0
  runtime path), **unless** this repo declares `.devkit.yml plugin_dir:` (forks / build-generated).
- The standardization wrapper: `tests/_testkit` (the vendored devkit submodule — the **only**
  submodule), `tests/e2e/hooks/`, `.github/workflows/{plugin-e2e,devkit-sync}.yml`, `Makefile`
  (`-include tests/_testkit/e2e/Makefile.devkit`), `.devkit.yml`, `README.md`, `DEVELOPING.md`,
  `LICENSE`, `docs/media/`, `scripts/doctor.py`.

## The local dev/test loop
Work inside the devkit devcontainer (see `DEVELOPING.md`). The frozen targets (SPEC Appendix E.1):
`make build` → `make e2e` (boots nested rootless A0, then per case
`install → verify-installed [+ behaviour + doctor] → uninstall → verify-uninstalled` → teardown)
→ `make media` to refresh `docs/media/`. **Reproduce CI locally before pushing.**

## What the standard requires of a change here
- **Behaviour verify** (DEC-053): `tests/e2e/hooks/verify-installed` must drive the live A0 over
  the wire (Playwright on `A0_BASE_URL` / HTTP), asserting a plugin-specific effect — not just
  file/dependency presence.
- **Doctor** (DEC-052): `scripts/doctor.py` runs inside A0, exit `0` iff healthy (deps importable,
  config keys/types vs `default_config.yaml`, extension files present + import-clean).
- **Docs** (DEC-048): keep `README.md` to the fixed skeleton (Appendix E.8); `docs/media/` holds
  the harness-captured screenshot + behaviour GIF.
- **Compatibility** (DEC-049): keep `.devkit.yml a0_compat: upstream | fork-required` accurate;
  `fork-required` names the change and links the A0 fork.
- **License** (DEC-050): first-party code is Apache-2.0; vendored upstream keeps its own license.
- `make conformance` must stay green (structural checks). Don't reimplement devkit logic in-repo
  (DEC-015): the harness, workflows, and templates live in the devkit.

## Authoring skills
The devkit vendors the curated authoring skills under `tests/_testkit/skills/`
(a0-plugin-architecture, a0-bootstrap-plugin, author-plugin-from-template,
plugin-manifest-contract, a0-plugin-testkit, troubleshoot-plugin-deployment,
rotate-plugin-credentials). Load the relevant one when building/extending/debugging.
<!-- a0:common:end -->

<!-- Repo-specific guidance goes below this line (kept across syncs). -->
