---
name: author-plugin-from-template
description: "Playbook for greenfield-authoring a new agent-zero plugin from agent-zero-new-plugin-template, with the manifest contract baked in from line one. Covers: scaffolding the plugin.yaml, default_config.yaml, __init__.py, and webui/ surface; choosing between tool/extension/hook plugin shapes; writing the companion meta.yaml; testing locally; building the zip; PR'ing into agent-zero-vendor-plugins for publication."
version: "1.0.0"
author: "Agent Zero Plugins"
tags: ["plugins", "scaffold", "greenfield", "template", "playbook"]
trigger_patterns:
  - "write a plugin"
  - "new plugin"
  - "author plugin"
  - "create plugin"
  - "scaffold plugin"
  - "plugin from scratch"
  - "plugin template"
  - "agent-zero-new-plugin-template"
  - "plugin.yaml"
---

# Author a new A0 plugin from the template

Greenfield-build an Agent Zero plugin from
[`agent-zero-new-plugin-template`](https://github.com/agent-zero-plugins/agent-zero-new-plugin-template)
with the manifest contract baked in from line one — so it sails through
`agent-zero-vendor-plugins`'s gate CI without rework.

## When to load

You want to extend A0 with a new capability — adding tools, hooks,
extensions, or UI surface — and no existing plugin covers it. The
[`agent-zero-plugin-development-testkit`](https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit)
is for testing; this skill is for *authoring*.

If there's already a community/upstream plugin that almost fits, prefer
adapting it for the contract before forking; see
[`contribute-plugin-to-gate`](../contribute-plugin-to-gate/SKILL.md) §"Decision: is the plugin already conformant?"
for the path.

---

## Step 1: Clone the template

```bash
cd ~/src/agent-zero-plugins
git clone --template=https://github.com/agent-zero-plugins/agent-zero-new-plugin-template \
  https://github.com/agent-zero-plugins/agent-zero-plugin-<name>.git
cd agent-zero-plugin-<name>

# Or via gh:
gh repo create agent-zero-plugins/agent-zero-plugin-<name> \
  --template agent-zero-plugins/agent-zero-new-plugin-template \
  --private \
  --clone
```

The template ships:
- `<placeholder>/plugin.yaml` — fill in `name`, `version`, `description`
- `<placeholder>/__init__.py` — entry-point stubs for tools/extensions/hooks
- `<placeholder>/default_config.yaml` — for NON-SECRET defaults only (see contract)
- `<placeholder>/webui/` — optional UI assets
- `meta.yaml` — companion gate-repo metadata (paste into the gate PR later)
- `tests/` — wired against the [plugin-development-testkit](https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit)

---

## Step 2: Pick the plugin shape

A0 plugins extend the framework in three primary ways:

| Shape | Purpose | Where it hooks |
|---|---|---|
| **Tool** | New tool the agent can call (e.g. `web_search`, `code_runner`) | Exported from `__init__.py` via the tool decorator |
| **Extension** | Modify A0's behavior at well-known extension points | `extensions/<phase>/<order>_<name>.py` |
| **Hook** | Run code on lifecycle events (chat created, message sent, …) | Registered in `__init__.py` against the hook API |

A single plugin can mix shapes. Authoritative spec: read existing approved
plugins under `~/src/agent-zero-plugins/agent-zero-vendor-plugins/plugins/`
for canonical examples (`chat_rename` is a hook; `apu_governor` is an
extension).

---

## Step 3: Apply the manifest contract from line one

The contract is enforced statically by the gate. Author with it in mind —
retrofitting is annoying:

### Secrets

```python
# ✓ DO — env vars are the credential channel
import os

def _api_key() -> str:
    key = os.getenv("MY_PLUGIN_API_KEY")
    if not key:
        raise RuntimeError("MY_PLUGIN_API_KEY env var is required")
    return key
```

```python
# ✗ DON'T — config dict is publicly readable; UI input writes to PVC
api_key = config["api_key"]        # rejected by CI
token = settings.get("auth_token") # rejected by CI
```

### Non-secret config

```yaml
# default_config.yaml — only NON-SECRET defaults
polling_interval_seconds: 60
backend: openai
debug: false
```

Reading them in code (after the chart populates env vars via `config:`):

```python
INTERVAL = int(os.getenv("MY_PLUGIN_POLLING_INTERVAL_SECONDS", "60"))
BACKEND = os.getenv("MY_PLUGIN_BACKEND", "openai")
```

Resolution order: operator env > A0 UI `config.json` > plugin
`default_config.yaml`. Implement the cascade in `__init__.py`.

### WebUI

```html
<!-- ✓ DO — text inputs, dropdowns, toggles for non-secret values -->
<input type="text" name="backend" />
<select name="polling_interval"> ... </select>
```

```html
<!-- ✗ DON'T — UI is not a credential channel -->
<input type="password" name="api_key" />   <!-- rejected by CI -->
<input name="auth_token" />                <!-- rejected by CI -->
```

### Env-var naming

Prefix everything with the plugin name in CAPS_SNAKE_CASE:

```
MY_PLUGIN_API_KEY                  ← good
MY_PLUGIN_POLLING_INTERVAL_SECONDS ← good
API_KEY                            ← bad: collides with other plugins
```

---

## Step 4: Test locally

Use the
[`agent-zero-plugin-development-testkit`](https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit)
to drive the plugin without spinning up a full A0 cluster:

```bash
# Add the testkit
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit.git .testkit

# Run the smoke tests
pytest tests/
```

Useful smoke tests that the gate CI does NOT cover (so the testkit catches
them):
- Plugin import doesn't crash on missing optional env vars
- Tool/extension/hook is correctly registered
- WebUI templates render against canned A0 state
- Missing required env var produces a clear error, not a stack trace

---

## Step 5: Author the `<name>.meta.yaml`

This goes in the gate PR, NOT inside the zip. Use the template's
`meta.yaml` as your starting point. See
[`plugin-manifest-contract`](../plugin-manifest-contract/SKILL.md) §"Rule 3"
for the full field list.

Minimal:

```yaml
name: my_plugin
version: "0.1.0"
summary: One-line description for catalogs and pickers
env: []
```

---

## Step 6: Build the zip + open the gate PR

See [`contribute-plugin-to-gate`](../contribute-plugin-to-gate/SKILL.md)
for the zip-build + PR flow. The summary:

```bash
git stash && git clean -fdx
zip -r /tmp/my_plugin.zip my_plugin/ \
  -x '*.pyc' -x '__pycache__/*' -x '.git/*' \
  -x 'node_modules/*' -x '*.so' -x '*.dylib' -x '*.dll'

cd ~/src/agent-zero-plugins/agent-zero-vendor-plugins
git checkout -b add-my_plugin-v0.1.0
cp /tmp/my_plugin.zip plugins/
cp ~/src/agent-zero-plugins/agent-zero-plugin-my_plugin/meta.yaml plugins/my_plugin.meta.yaml
git add plugins/my_plugin.{zip,meta.yaml}
git commit -m "feat(my_plugin): add v0.1.0 — <summary>"
gh pr create --fill
```

After merge: the plugin is published at
`ghcr.io/agent-zero-plugins/my_plugin:0.1.0` and consumable from any
`agent-zero-infra` env.

---

## Related Skills

- **plugin-manifest-contract**: The non-negotiable rules
- **contribute-plugin-to-gate**: Zip + PR + publish flow
- **consume-plugin-in-env**: Operator-side wiring
- **troubleshoot-plugin-deployment**: When your plugin doesn't load in-pod
