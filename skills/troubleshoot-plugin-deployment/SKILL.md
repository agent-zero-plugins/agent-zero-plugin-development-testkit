---
name: troubleshoot-plugin-deployment
description: "Diagnostic playbook for plugins that fail to publish, pull, unzip, import, or load in-pod. Catalogues the failure modes seen during the gate-repo + OCI publish rollout with kubectl/oras/gh commands and the root cause + fix for each. Load when a plugin isn't appearing in A0's /api/plugins_list, when init-60-plugins-oci.sh logs a failure, or when the gate CI rejects a PR."
version: "1.0.0"
author: "Agent Zero Plugins"
tags: ["plugins", "troubleshooting", "debug", "kubernetes", "oci", "playbook"]
trigger_patterns:
  - "plugin not loading"
  - "plugin missing"
  - "plugin not in A0"
  - "debug plugin"
  - "plugin pull failed"
  - "plugin import error"
  - "troubleshoot plugin"
  - "init-60-plugins-oci failed"
  - "plugin oci error"
  - "ImagePullBackOff plugin"
  - "gate CI rejected"
  - "plugin not found in /api/plugins_list"
---

# Troubleshoot a plugin deployment

Diagnostic recipes for the failure modes hit during the gate +
agent-zero-infra plugin rollout. Each entry: **symptom → diagnose → fix**.

The plugin journey has five hops, any of which can fail:

```
1. Author writes plugin     (agent-zero-plugin-<name>/)
        ↓ zip + meta
2. Gate accepts PR          (agent-zero-vendor-plugins)
        ↓ publish.yml
3. OCI artifact published   (ghcr.io/agent-zero-plugins/<name>:<v>)
        ↓ init-60-plugins-oci.sh oras pull
4. Pod unzips to PVC        (/a0/usr/plugins/<name>/)
        ↓ A0 import
5. Plugin live in A0        (/api/plugins_list → is_custom: true)
```

Identify the hop where it broke, then jump to that section.

---

## Hop 2 → "Gate CI rejected my PR"

### Symptom: "sanity-check zip contents" failed

CI log shows: `forbidden contents: __pycache__/`, `.pyc`, etc.

**Diagnose**:
```bash
unzip -l plugins/<name>.zip | grep -E '(__pycache__|\.pyc|\.zip|node_modules|\.git/)'
```

**Fix**: rebuild from a clean checkout — see
[`contribute-plugin-to-gate`](../contribute-plugin-to-gate/SKILL.md)
Step 2 for the exact `zip -x` flags.

### Symptom: "manifest contract" failed — secret-named key in default_config.yaml

CI log shows: `default_config.yaml has secret-named keys: api_key`

**Diagnose**:
```bash
unzip -p plugins/<name>.zip <name>/default_config.yaml | grep -iE 'api[_-]?key|secret|token|password|credential|auth[_-]?key'
```

**Fix**: remove the key from `default_config.yaml`. If the plugin genuinely
needs that credential, it must come from `os.getenv()` — see
[`plugin-manifest-contract`](../plugin-manifest-contract/SKILL.md) Rule 1.

### Symptom: "manifest contract" failed — code reads secrets from config

CI log shows: `code reads secrets from config: <file>:<line>: config["api_key"]`

**Fix**: replace the `config[...]` / `settings.get(...)` read with
`os.getenv("PLUGIN_NAME_API_KEY")`. Don't add the env var name to
`default_config.yaml` to "make it work" — that re-triggers Rule 1.

### Symptom: "metadata sync" failed — missing meta.yaml

CI log shows: `missing companion plugins/<name>.meta.yaml`

**Fix**: author it. Minimal form for a self-contained plugin:
```yaml
name: <name>
version: "<version>"
summary: <one-line>
env: []
```

### Symptom: "metadata sync" failed — version mismatch

CI log shows: `meta.version=2.0.0 but plugin.yaml version=1.9.0`

**Diagnose**:
```bash
yq -r .version plugins/<name>.meta.yaml
unzip -p plugins/<name>.zip <name>/plugin.yaml | yq -r .version
```

**Fix**: bump whichever is stale. The two MUST match. Common cause —
you bumped the inner `plugin.yaml` in the plugin source repo but forgot
to update the gate-repo `<name>.meta.yaml` when you copied the new zip
in.

### Symptom: "metadata sync" failed — forward env mismatch

CI log shows: `meta declares env 'FOO_BAR' but no os.getenv/os.environ reference found in source`

**Fix**: either remove the env declaration from `meta.yaml` (if the
plugin doesn't actually read it), or add the `os.getenv("FOO_BAR")` call
in the plugin source (and rebuild the zip).

---

## Hop 3 → "Artifact didn't publish"

### Symptom: PR merged but no new tags on GHCR

**Diagnose**:
```bash
gh run list --repo agent-zero-plugins/agent-zero-vendor-plugins --branch main --limit 3
gh run view <run-id> --log | tail -50
```

**Common causes**:
- The push didn't touch `plugins/**.zip` / `plugins/**.meta.yaml` (the
  workflow's `paths:` filter excluded it). Fix: trigger via
  `gh workflow run publish.yml --ref main`.
- GHCR auth failed (`oras login` step). The workflow uses
  `${{ secrets.GITHUB_TOKEN }}` which needs `packages: write` permission
  declared at the workflow level — check `permissions:` block.

---

## Hop 4 → "Pod doesn't pull the plugin"

### Symptom: `init-60-plugins-oci.sh` logs `oras pull` failure

**Diagnose**:
```bash
kubectl logs deploy/agent-zero -n agent-zero-<env> -c init-data-dir 2>&1 | grep -A 5 plugins
# Or for the main container's init phase:
kubectl exec deploy/agent-zero -n agent-zero-<env> -- cat /a0/logs/init-60-plugins-oci.log 2>/dev/null
```

**Common causes**:

1. **PAT lacks `read:packages` on `agent-zero-plugins` org**. Symptom:
   `oras pull ... 401 Unauthorized`.
   Fix: rotate the `token_secret` (per `defaults: omar-github`) to a PAT
   with org-scoped `read:packages`.

2. **Wrong tag**. Symptom: `oras pull ... manifest unknown`.
   Fix: check what tags actually exist:
   ```bash
   oras repo tags ghcr.io/agent-zero-plugins/<name>
   ```

3. **PAT user is wrong**. GHCR expects `token_user: x-access-token` for
   PAT auth. `git_defaults` bundle should set it.

### Symptom: pull succeeds but unzip fails

```bash
kubectl exec deploy/agent-zero -n agent-zero-<env> -- \
  ls -la /a0/usr/plugins/<name>/ 2>&1
```

If the directory is empty: the OCI artifact was published with
unexpected media type / structure. Confirm the publish workflow used
`--artifact-type application/vnd.agent-zero.plugin.v1+zip` and pushed
the zip as `application/zip`.

---

## Hop 5 → "Plugin not visible in A0"

### Symptom: `/a0/usr/plugins/<name>/` exists in pod, but `/api/plugins_list` doesn't show it

```bash
# Confirm plugin is unzipped
kubectl exec deploy/agent-zero -n agent-zero-<env> -- \
  ls /a0/usr/plugins/

# Check A0's plugin discovery logs
kubectl logs deploy/agent-zero -n agent-zero-<env> | grep -i "plugin\|/a0/usr/plugins"
```

**Common causes**:

1. **`plugin.yaml` missing or malformed inside the zip**. A0's plugin
   loader requires `<name>/plugin.yaml` at the directory root.
   Fix: re-export the zip ensuring the `plugin.yaml` is at the top of the
   plugin's directory (not nested deeper).

2. **`__init__.py` import error on plugin load**. A0 logs the exception:
   ```
   ImportError: cannot import name X from Y
   ```
   Fix: typically a missing required env var (plugin raises RuntimeError
   on import). Confirm the chart's `secrets:` / `config:` blocks for
   this plugin populate the variables. See [Hop 5 — Symptom: 401 from
   upstream API](#symptom-401-from-upstream-api) for the env-var-set
   verification.

3. **Plugin requires a Python dep that's not in the base image**.
   ```
   ModuleNotFoundError: No module named 'foo'
   ```
   Fix: add `foo` to the env descriptor's `agent.packages.pip:` so
   `init-packages.sh` installs it before A0 starts.

### Symptom: 401 from upstream API

Plugin imports fine; tool calls hit upstream API; get 401 responses.

**Diagnose**: env var is missing or stale.
```bash
kubectl exec deploy/agent-zero -n agent-zero-<env> -- \
  python3 -c 'import os; print("set" if os.getenv("PLUGIN_NAME_API_KEY") else "missing")'
```

If `missing`: the chart's `secrets:` block didn't propagate. Confirm:
- The descriptor's `agent.plugins.oci[].secrets[].env` matches what the
  plugin reads
- The `value-key` matches an existing vault entry (`pass ls a0/` to
  list)
- `make deploy-rbac ENV=<env>` was run after the vault was updated

If `set`: the value is stale; rotate per
[`rotate-plugin-credentials`](../rotate-plugin-credentials/SKILL.md).

---

## "I rolled out a new version and the old behavior is still there"

The `:<version>` ref in the descriptor IS the version pin. If you bumped
it but the old code still runs, one of:

1. **Pod didn't restart**. The chart's `checksum/config` annotation
   triggers a rollout on descriptor change — but `make deploy` is
   required (just `git push`-ing the descriptor doesn't deploy it).

2. **PVC has stale plugin dir + fresh code never overwrote it**. If you
   renamed the plugin between versions, the old `/a0/usr/plugins/<old>/`
   survives. Remove manually:
   ```bash
   kubectl exec deploy/agent-zero -n agent-zero-<env> -- \
     rm -rf /a0/usr/plugins/<old_name>
   kubectl rollout restart deploy/agent-zero -n agent-zero-<env>
   ```

3. **You pinned `:latest` and the tag didn't repoint**. Bump to
   `:<exact-version>` — `:latest` is mutable, but if you didn't bump
   the inner `plugin.yaml` version, GHCR's `:latest` still points at
   the same digest as before.

---

## "The plugin loads, but its setup never ran (scheduled task / schema / dir missing)"

**OCI-deployed plugins do NOT fire the install/enable hooks.** The pod unzips + loads the plugin directly;
A0 only auto-calls `uninstall`. So `hooks.py → install()` / `on_plugin_enabled()` run on *interactive*
install but **not** on OCI rollout — any setup they do (registering a scheduled task, creating schema/dirs,
seeding config) silently never happens in prod.

- **Tell-tale:** works after a manual install in a dev A0 (hooks fired), missing after an OCI deploy.
- **Fix:** self-register idempotently at a **startup seam** (e.g. a `startup_migration` extension that runs
  every boot and no-ops if already set up), not in the enable lifecycle. See `a0-plugin-architecture` §22.

---

## Related Skills

- **plugin-manifest-contract**: The rules every plugin obeys
- **contribute-plugin-to-gate**: Author + publish workflow
- **consume-plugin-in-env**: Operator-side descriptor wiring
- **rotate-plugin-credentials**: Refresh secrets without redeploying
