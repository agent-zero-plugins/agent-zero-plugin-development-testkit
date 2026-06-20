# Adopting the plugin quality standard

How a plugin repo gets the common build/test/CI interface. Everything heavy lives
in the devkit; your repo carries only its source, two verify hooks, and a thin
caller workflow. (Automated bootstrap is a follow-up; these are the manual steps.)

## 1. Vendor the devkit

```bash
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit tests/_testkit
```

## 2. Add the per-plugin verify hooks (the only variant steps)

Create `tests/e2e/hooks/verify-installed` and (optionally)
`tests/e2e/hooks/verify-uninstalled` — language-agnostic executables. The devkit
runs them with this env: `A0_BASE_URL`, `A0_USERNAME`, `A0_PASSWORD`,
`A0_CONTAINER`, `PLUGIN_NAME`, `CASE_NAME`, `A0_REPORT_DIR`. **Pass/fail = exit code.**

```bash
#!/usr/bin/env bash
set -euo pipefail
# Assert your plugin actually took effect — Playwright, curl against
# $A0_BASE_URL, or container-exec, your choice:
podman exec "$A0_CONTAINER" test -f "/a0/usr/plugins/$PLUGIN_NAME/webui/main.html"
```

The devkit already does the common checks (plugin dir + manifest landed on
install; the plugin's own dir gone on uninstall). Your hook adds the
plugin-specific assertions.

## 3. Add the caller workflow

`.github/workflows/e2e.yml`:

```yaml
name: e2e
on: { pull_request: { branches: [main] }, workflow_dispatch: {} }
jobs:
  e2e:
    uses: agent-zero-plugins/agent-zero-plugin-development-testkit/.github/workflows/plugin-e2e.yml@v1
    with:
      plugin_dir: usr/plugins/my_plugin      # dir with plugin.yaml
      plugin_display_name: "My Plugin"        # title on the plugin card
      # a0_image: ghcr.io/.../agent-zero:fork-tag   # override only if you depend on the fork
```

## 4. (Optional) local runs

Add to your `Makefile`:

```makefile
PLUGIN_DIR          := usr/plugins/my_plugin
PLUGIN_DISPLAY_NAME := My Plugin
-include tests/_testkit/e2e/Makefile.devkit
```

Then `make e2e` runs the whole lifecycle locally in the devcontainer (needs
rootless podman + `/dev/fuse`). `make up` boots A0 for manual exploration.

## That's it

`make conformance` checks your repo exposes the common targets. The devkit owns
boot, login, install, uninstall, onboarding-suppression, residue checks, and the
reusable CI — you own your plugin and its two hooks.
