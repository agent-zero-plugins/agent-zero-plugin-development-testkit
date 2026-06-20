---
name: rotate-plugin-credentials
description: "Playbook for refreshing the per-plugin secret env vars consumed by deployed plugins — when an upstream API key was leaked, an OAuth refresh token expired, or you rotate on a cadence. Operator pushes the new value to the env's admin vault, then a pod restart re-projects the K8s Secret and the plugin reads the fresh env var. No descriptor change required."
version: "1.0.0"
author: "Agent Zero Plugins"
tags: ["plugins", "credentials", "rotation", "secret", "operator", "playbook"]
trigger_patterns:
  - "rotate plugin credentials"
  - "refresh plugin secret"
  - "leaked plugin token"
  - "plugin auth expired"
  - "rotate API key"
  - "push new plugin secret"
  - "update plugin credential"
  - "plugin secret rotation"
---

# Rotate plugin credentials

Refresh a deployed plugin's secret env var (API key, OAuth refresh token,
bot token) without changing the env descriptor or redeploying the chart.

## When to load

- A key got leaked / was committed to git accidentally.
- A scheduled rotation cadence (90 days, post-incident).
- The vendor's OAuth refresh token rolled and you have a new one to install.
- The plugin started returning 401 from the upstream API.

If you're rotating MCP credentials (different surface — see
[`rotate-mcp-credentials`](https://github.com/agent-zero-mcps/agen-zero-mcps-skills/blob/main/shared-assets/skills/mcps/rotate-mcp-credentials/SKILL.md)
in the mcps-skills library) — that's a separate flow with its own
`make mcp-pat` / `make mcp-oauth` targets. Plugin rotation is just a
vault write + pod restart; there's no special make target.

## Step 1: Identify the vault key

The descriptor's `secrets[].value-key` IS the vault key. Find it:

```bash
cd ~/src/github.com/nuevanext/agent-zero-infra
grep -A 2 "value-key" envs/<env>.yaml | head
```

Typical pattern:

```yaml
plugins:
  oci:
    - ref: ghcr.io/agent-zero-plugins/apu_governor:2.0.0
      secrets:
        - env: APU_GOVERNOR_API_KEY
          value-key: apu-governor-api-key   # ← this is the vault key
```

The vault entry lives at `a0/<value-key>` (the chart prefixes with `a0/`
when projecting). So:
- descriptor `value-key: apu-governor-api-key`
- vault path: `a0/apu-governor-api-key`
- in-pod file: `/home/agent/.password-store/apu-governor-api-key.gpg`
- in-pod env var: `$APU_GOVERNOR_API_KEY` (after `pass show` in the entrypoint)

## Step 2: Push the new value

```bash
cd ~/src/github.com/nuevanext/agent-zero-infra
secrets-cli edit admin --env <env>
# Inside the unlocked vault shell:
pass insert -f a0/apu-governor-api-key
# Paste the new key on a single line, Enter, then ctrl-D
exit
```

`-f` (force) overwrites the existing entry. Commit + push the vault
update (the `.secrets/` tree is git-tracked, GPG-encrypted):

```bash
git add .secrets/<env>/
git commit -m "rotate(plugins): refresh apu-governor-api-key"
git push
```

## Step 3: Propagate to the cluster

The K8s Secret carrying the projected ciphertext is owned by the
`agent-zero-rbac` chart. Re-running `deploy-rbac` re-projects with the
new vault content:

```bash
make deploy-rbac ENV=<env>
```

This produces a new K8s Secret revision. The agent-zero deployment's pod
template references it by name, so existing pods are unaware until they
restart.

## Step 4: Trigger a pod restart

```bash
kubectl rollout restart deploy/agent-zero -n agent-zero-<env>
```

The new pod's init-secrets hook reads the projected secret, exports it as
`$APU_GOVERNOR_API_KEY`, and A0 imports the plugin which now reads the
fresh value via `os.getenv()`.

## Step 5: Verify

```bash
# Confirm the plugin is up and the env var is set (without leaking the value)
kubectl exec deploy/agent-zero -n agent-zero-<env> -- \
  python3 -c 'import os; print("set" if os.getenv("APU_GOVERNOR_API_KEY") else "missing")'

# Watch logs for any 401s from the upstream API
kubectl logs deploy/agent-zero -n agent-zero-<env> -f | grep -i "apu_governor\|401"
```

If the plugin's upstream calls succeed (no more 401), rotation is
complete.

## Common pitfalls

### "I rotated but the pod still uses the old key"

You skipped `make deploy-rbac` between vault push and pod restart. The
K8s Secret is the bridge — vault → K8s Secret happens at deploy-rbac
time, K8s Secret → pod env happens at pod start. Both steps are
required.

### "The new value didn't take after pod restart"

The agent-zero-rbac chart's K8s Secret only gets a new revision when its
content actually changes. If `make deploy-rbac` was a no-op (Helm thinks
nothing changed), the Secret didn't refresh. Confirm:

```bash
kubectl describe secret a0-runtime-secrets -n agent-zero-<env> | grep -A 1 "Annotations\|Last"
```

If `helm.sh/release-revision` didn't bump, force a redeploy:

```bash
make deploy-rbac ENV=<env> EXTRA_HELM_ARGS="--force"
```

### "Plugin reads on startup; mid-flight rotation needs more than just restart"

If the plugin caches the key in module-level state at import (most do),
a pod restart is enough — `os.getenv()` runs fresh. If the plugin reads
the key from a long-running daemon thread, only a full restart picks up
the change. There's no in-process hot-reload mechanism today.

---

## Related Skills

- **plugin-manifest-contract**: How secrets are declared and consumed
- **consume-plugin-in-env**: First-time wiring (different from rotation)
- **troubleshoot-plugin-deployment**: When verification fails
