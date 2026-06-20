# Adopting the plugin quality standard

A plugin repo vendors **only the devkit** (this repo) as a direct submodule, and
gets the common build/test/CI interface from it. No `.skills` — the devkit is
self-contained. The devkit's own sync mechanism keeps it current.

## 1. Layout (DEC-042/043)

- **First-party plugins**: put the plugin source — the install payload — at
  **`usr/plugins/<name>/`** (mirrors the A0 runtime path). Nothing else to declare.
- **Forks you upstream / build-generated plugins**: keep the existing layout and
  add a `.devkit.yml` at the repo root declaring where the source is:
  ```yaml
  plugin_dir: dist/gitnexus        # where plugin.yaml lives
  display_name: "GitNexus"          # optional; else plugin.yaml title
  a0_image: ghcr.io/.../agent-zero:fork   # optional; only if you need the fork image
  ```

## 2. Vendor the devkit (the ONLY submodule)

```bash
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit tests/_testkit
# If migrating off the old skills mechanism:
git submodule deinit -f .skills && git rm -f .skills && rm -f .github/workflows/skills-sync.yml
```

## 3. Per-plugin verify hooks (the only variant steps — optional)

Create `tests/e2e/hooks/verify-installed` and/or `verify-uninstalled`
(language-agnostic executables; env: `A0_BASE_URL`, `A0_USERNAME`, `A0_PASSWORD`,
`A0_CONTAINER`, `PLUGIN_NAME`, `CASE_NAME`, `A0_REPORT_DIR`; pass/fail = exit code).
The devkit already does the common checks (manifest + files landed on install;
the plugin's own dir gone on uninstall), so hooks are optional — add them to
assert your plugin's specific behavior.

## 4. Wire the Makefile + render the workflows

```makefile
# Makefile
-include tests/_testkit/e2e/Makefile.devkit
```

```bash
make link-workflows   # copies devkit-sync.yml + plugin-e2e.yml into .github/workflows/
git add .github/workflows/devkit-sync.yml .github/workflows/plugin-e2e.yml && git commit
```

(The caller workflows must be committed once by hand — `GITHUB_TOKEN` can't push
workflow files during the nightly sync.)

## 5. Secrets

The reusable workflows mint the shared sync **GitHub App** token to clone the
private devkit submodule. The repo needs the App secrets
`SKILLS_SYNC_APP_CLIENT_ID` / `SKILLS_SYNC_APP_PRIVATE_KEY` (already present on
repos that used skills-sync — same App). The App must be installed
(Contents:Read) on the devkit repo.

## What you get

- **`plugin-e2e.yml`** runs the full install → verify-installed → uninstall →
  verify-uninstalled lifecycle (A0 nested + rootless) on every PR.
- **`devkit-sync.yml`** keeps `tests/_testkit` current nightly (auto-merge PR).
- `make e2e` / `make up` for local runs (needs rootless podman + `/dev/fuse`).
- `make conformance` checks the common targets are exposed.
