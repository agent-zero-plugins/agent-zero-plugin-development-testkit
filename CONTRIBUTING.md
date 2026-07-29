# Contributing to agent-zero-plugin-development-testkit

Thanks for helping improve the devkit! This repo is **the standard + the machinery** for the whole
Agent Zero plugin fleet, so changes here ripple into every consumer repo. Read this before opening a PR.

## Ground rules

1. **The SPEC is the law.** [`SPEC.md`](SPEC.md) is a numbered REQ/DEC contract. Any behaviour change
   must either satisfy an existing requirement or add/amend one in the same PR. Never silently
   contradict a numbered decision.
2. **Branches + PRs only.** No direct pushes to `main`. Branch names follow the existing patterns
   (`feat/…`, `fix/…`, `docs/…`, `spec/…`, `guardrails/…`).
3. **Never test against a live operator A0.** Iterate against a disposable A0 (devcontainer or
   host-podman on a non-80 port). See the `no-live-a0-for-testing` skill under `skills/`.
4. **Red-first.** New assertions/helpers ship with a test that fails against the pre-fix state.
   Paste the red output in the PR description.
5. **Keep the public API stable.** `a0_plugin_testkit` import paths are consumed by every plugin repo
   via submodule. New modules/functions are fine; renames are breaking changes.

## Dev setup

```bash
git clone --recurse-submodules https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit
cd agent-zero-plugin-development-testkit
python -m pip install -e ".[fasta2a]" pytest pytest-asyncio
```

## Test layers

| Layer | Command | Needs |
|---|---|---|
| Static pytest (fast smoke) | `pytest` | Python only — no A0 boot |
| Lifecycle e2e | `e2e/harness/run-lifecycle.sh` | devcontainer (`devcontainer/Containerfile`) |
| BDD e2e | `e2e/harness/run-bdd.sh` | devcontainer + nested rootless A0 |

CI runs `sample-plugin-e2e` on every PR to `main` — the full package → install → verify → uninstall
lifecycle of `examples/sample-plugin` on the real deploy image. Your PR must keep it green.

## PR checklist

- [ ] `pytest` green locally
- [ ] SPEC updated (new/amended REQ/DEC) if behaviour changed
- [ ] `CHANGELOG.md` entry + version bump if consumer-visible
- [ ] Docs (`README.md`, `skills/`, `templates/`) updated in the same PR
- [ ] No new dependency without discussion in the PR description

## Releases

Tags follow semver (`vX.Y.Z`). Consumer repos pin the submodule to a tag/commit and bump explicitly —
see `devkit-sync.yml` for the automated sync flow.

## Questions / security

Open a GitHub issue for anything non-sensitive. For vulnerabilities see [`SECURITY.md`](SECURITY.md).
