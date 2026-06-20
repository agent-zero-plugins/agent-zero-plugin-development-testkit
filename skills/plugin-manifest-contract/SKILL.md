---
name: plugin-manifest-contract
description: "Reference for the agent-zero-plugins manifest contract: secrets hygiene rules, env-var conventions, plugins/<name>.meta.yaml shape, and the static checks the gate repo's publish workflow enforces. Load this when authoring a new plugin, reviewing a plugin PR against agent-zero-vendor-plugins, or trying to understand why CI rejected a zip. Covers: which env vars come from where (default_config.yaml vs config.json vs operator env), what's allowed in the UI, the meta.yaml ↔ plugin.yaml ↔ source forward-sync, and the env-var naming convention."
version: "1.0.0"
author: "Agent Zero Plugins"
tags: ["plugins", "contract", "manifest", "secrets", "gate", "reference"]
trigger_patterns:
  - "plugin manifest contract"
  - "plugin secrets hygiene"
  - "meta.yaml shape"
  - "plugin.meta.yaml"
  - "agent-zero plugin contract"
  - "os.getenv plugin"
  - "default_config.yaml plugin"
  - "plugin secrets"
  - "plugin env vars"
  - "plugin manifest"
  - "review plugin PR"
  - "is this plugin conformant"
  - "why did CI reject my plugin"
---

# Plugin manifest contract

Every plugin admitted to
[`agent-zero-vendor-plugins`](https://github.com/agent-zero-plugins/agent-zero-vendor-plugins)
follows this contract. The publish workflow enforces what can be checked
statically; the rest is gated on PR review. The same contract applies to
plugins authored from scratch in
[`agent-zero-new-plugin-template`](https://github.com/agent-zero-plugins/agent-zero-new-plugin-template)
and to vendored plugins forked into the org.

## Why this exists

A plugin's zip is pulled to `/a0/usr/plugins/<name>/` by
[`init-60-plugins-oci.sh`](https://github.com/NuevaNext/agent-zero-infra/blob/main/helm/agent-zero/hooks/init-60-plugins-oci.sh)
on every pod boot. The zip is **publicly visible** to anyone with `read:packages`
on the registry (which is, by design, broad). So:

- **The zip is plaintext**. Anything inside it — `default_config.yaml`, source code,
  webui HTML — leaks.
- **A0's UI is operator-editable at runtime**. Whatever the UI accepts gets
  written to `config.json` on the PVC. UI inputs aren't a credential channel
  even if they look like one.
- **Operator-pushed env vars are the one credential channel**. The chart's
  per-plugin `secrets:` mechanism decrypts a vault entry in-pod and exports
  it as an env var the plugin can `os.getenv()`. No on-disk leakage path.

The three rules below mechanically enforce this split.

---

## Rule 1: Secrets come from env vars only

A plugin that needs a credential MUST read it via `os.getenv()` / `os.environ`:

```python
api_key = os.getenv("APU_GOVERNOR_API_KEY")
if not api_key:
    raise RuntimeError("APU_GOVERNOR_API_KEY env var is required")
```

Operators populate it via the agent-zero-infra chart's `secrets:` block:

```yaml
agent:
  plugins:
    oci:
      - ref: ghcr.io/agent-zero-plugins/apu_governor:2.0.0
        defaults: omar-github
        secrets:
          - env: APU_GOVERNOR_API_KEY
            value-key: apu-governor-api-key   # vault entry, GPG-decrypted in-pod
```

### Forbidden

The publish workflow rejects a zip if any of these are present:

1. **`default_config.yaml`** declares a secret-named key, *even with a placeholder value*:
   ```yaml
   # ✗ REJECTED — key shape leaks even if value is empty
   api_key: ""
   auth_token: PLACEHOLDER
   ```
   The shape is what creates the leak surface — A0's UI sees the key and may
   render a settings prompt that writes the operator's input to `config.json`.

2. **Python source** reads a secret-named key from a config dict:
   ```python
   # ✗ REJECTED — config dict is publicly readable
   key = config["api_key"]
   token = settings.get("auth_token")
   ```

3. **WebUI HTML** prompts for a secret:
   ```html
   <!-- ✗ REJECTED — UI is not a credential channel -->
   <input type="password" name="api_key">
   <input name="auth_token">
   ```

The secret-name pattern (case-insensitive, word-boundary anchored) catches:
`api_key`, `api-key`, `apikey`, `secret`, `token`, `password`, `credential`,
`auth_key`. False-positive avoidance: `tokenizer` and `secret_sauce_for_recipes`
won't match (no leading/trailing underscore or word boundary).

---

## Rule 2: Non-secret config is fine in either channel

For poll intervals, feature flags, choice-of-backend — anything you'd be
comfortable seeing in a `git diff` — both `default_config.yaml` (bundled
defaults) and env vars are acceptable:

| Channel | Populated by | When to use |
|---|---|---|
| `default_config.yaml` (bundled) | Plugin author | Sensible defaults baked into the zip |
| `config.json` (runtime, A0 UI) | User typing in A0's UI | User-tunable settings |
| Env var via chart `config:` | Operator declaring per-env in descriptor | Fleet-wide overrides; env-specific values |

A plugin should resolve in that order (operator > user > author defaults).
The chart's per-plugin `config:` block populates env vars:

```yaml
agent:
  plugins:
    oci:
      - ref: ghcr.io/agent-zero-plugins/apu_governor:2.0.0
        config:
          - env: APU_GOVERNOR_POLLING_INTERVAL_SECONDS
            value: 30
```

---

## Rule 3: Every plugin has a `<name>.meta.yaml` companion

The metadata file is the **operator's reference** when wiring
`agent.plugins.oci[<name>]` — instead of grepping the plugin's source, look
in `plugins/<name>.meta.yaml`.

```yaml
# plugins/<plugin_name>.meta.yaml
name: <plugin_name>          # MUST match the basename of the companion zip
version: <semver>            # MUST match the plugin.yaml inside the zip
summary: <one-line description>

# env vars the plugin reads via os.getenv() / os.environ[...]
# Empty list = plugin needs nothing from operator beyond its bundled
# default_config.yaml. Most plugins fall in this bucket.
env: []
```

For plugins that DO read operator-provided env vars:

```yaml
env:
  - name: APU_GOVERNOR_POLLING_INTERVAL_SECONDS
    kind: config              # operator-provided literal
    default: 60               # informational (used if operator doesn't override)
    description: Seconds between automatic poll cycles.

  - name: APU_GOVERNOR_API_KEY
    kind: secret              # operator-provided vault reference
    description: |
      API key for the upstream service. Operator pushes via
      `pass insert a0/<key>` then references it in
      agent.plugins.oci[].secrets: with value-key matching the vault entry.
```

### CI-enforced sync

The publish workflow rejects a PR if:

1. A `<name>.zip` is missing its companion `<name>.meta.yaml`.
2. `meta.name` doesn't equal the zip's basename.
3. `meta.version` doesn't equal the `plugin.yaml`'s `version:` inside the zip.
4. **Forward sync**: any `env[].name` in meta isn't referenced by an
   `os.getenv("NAME")` / `os.environ["NAME"]` / `os.environ.get("NAME")` call
   in the plugin's `.py` source. Catches operator-facing API drift (operator
   declares it, plugin never reads it).

**Intentional gap** — backward sync (every `os.getenv()` declared in meta) is
NOT enforced today. Some plugins legitimately use A0 framework-level env
vars (`API_KEY_OPENAI`, `AUTH_LOGIN`) that operators don't wire per-plugin.
Tracking those would require a whitelist; deferred until it bites.

---

## Rule 4: Zips ship source only

The sanity-check step in `publish.yml` rejects a zip carrying:

- `__pycache__/`, `.pyc`, `.pyo` — Python bytecode caches
- nested `.zip` files — usually leftover release artifacts mistakenly committed
- `node_modules/`, `.git/` — environment-specific or VCS pollution
- Compiled native libraries: `.so`, `.dylib`, `.dll`

It also warns (doesn't reject) on zips larger than 5 MB. Plugins ship source —
if you're over 5 MB, you've probably committed a model file or build output.

Re-export from a clean checkout if the workflow fails on these:

```bash
# Inside the plugin source repo
git stash; git clean -fdx
zip -r ../<name>.zip <name>/ -x '*.pyc' -x '__pycache__/*' -x '.git/*'
```

---

## Env-var naming convention

Prefix env vars with the plugin name in CAPS_SNAKE_CASE to avoid collisions
across plugins running in the same A0 process:

```
APU_GOVERNOR_API_KEY                              ← good
APU_GOVERNOR_POLLING_INTERVAL_SECONDS             ← good
API_KEY                                           ← bad: collides if two plugins both want one
POLLING_INTERVAL                                  ← bad: too generic
```

This is convention, not statically enforced — but PR review will catch
unprefixed names.

---

## Static checks summary (publish.yml)

| Check | What it catches | Where |
|---|---|---|
| Sanity-check zip contents | Bytecode, nested archives, native libs, pollution | Step 1 |
| Secrets hygiene — config keys | Secret-named keys in `default_config.yaml` | Step 2 rule 1 |
| Secrets hygiene — config reads | `config["api_key"]` etc. in `.py` source | Step 2 rule 2 |
| Secrets hygiene — UI prompts | `<input type="password">` or secret-named names | Step 2 rule 3 |
| Metadata sync — companion meta | Missing `<name>.meta.yaml` | Step 3 |
| Metadata sync — name match | `meta.name` ≠ zip basename | Step 3 |
| Metadata sync — version match | `meta.version` ≠ `plugin.yaml.version` | Step 3 |
| Metadata sync — forward env | `meta.env[].name` not used in source | Step 3 |

When a rule fires, the workflow fails with a pointer to the offending file.
Operator fixes at the source (the plugin's own repo, not the gate repo) and
re-PRs against `agent-zero-vendor-plugins`.

---

## Related Skills

- **contribute-plugin-to-gate**: Step-by-step for getting a plugin into the gate repo
- **author-plugin-from-template**: Greenfield-author a new plugin from `agent-zero-new-plugin-template`
- **rotate-plugin-credentials**: Push fresh secrets to a deployed plugin without redeploying the chart
- **consume-plugin-in-env**: Operator side — wiring `agent.plugins.oci[]` in agent-zero-infra
- **troubleshoot-plugin-deployment**: Debugging failed plugin pulls / loads / secret resolution
