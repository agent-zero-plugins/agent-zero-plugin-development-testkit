# testkit `e2e/` — shared L3 Playwright harness for A0 plugin repos

The Python testkit (`src/a0_plugin_testkit/`) is the L0/L1/L2 scaffolding.
This `e2e/` tree is the **L3** scaffolding: Playwright-driven browser
tests against a fresh `agent0ai/agent-zero:latest` docker container with
seeded creds + plugin settings.

## What's here

```
e2e/
├── compose-base.yml            A0 container + ports 50011/50012 + pip-cache + command seed
├── Makefile.e2e                includeable: e2e-up / e2e-down / e2e-fresh / e2e-test / e2e-servers
├── scripts/
│   ├── e2e-up.sh               port probe + token + compose up + healthcheck + instance.env
│   └── e2e-down.sh
├── pages/
│   ├── LoginPage.ts            /login
│   ├── PluginsPage.ts          open / isInstalled / uninstall / installFromZip
│   └── ChatPage.ts             sidebar + newChat (plugin UI NOT included here)
├── fixtures/index.ts           createA0Fixtures(): credentials + loggedInPage + pluginsPage + chatPage
├── global-setup.ts             loadInstanceEnv() reader
└── playwright-base.config.ts   baseConfig(consumerE2EDir): spread into your config
```

## Consumer wiring (three hooks)

### 1. `Makefile` — include the targets + declare plugin knobs

```make
# Plugin-specific knobs (all optional; the LiveKit plugin example):
E2E_EXTRA_PORTS          := 50013:50013
E2E_COMPOSE_OVERRIDES    := docker/e2e.compose.override.yml
E2E_PLUGIN_SETTINGS_JSON := tests/e2e/plugin-settings.json
E2E_INSTANCE_ENV_EXTRA   := A0_LK_RTC_TCP_PORT=50013

# Include the targets at the bottom of your Makefile so the vars above
# are seen when the include-file expands.
-include tests/_testkit/e2e/Makefile.e2e
```

| Var | Purpose |
|---|---|
| `E2E_EXTRA_PORTS` | Space-separated `host:container` mappings; probed + published. Required for LK media (50013:50013). |
| `E2E_COMPOSE_OVERRIDES` | Extra compose files layered on top of `compose-base.yml`. Rare — only needed for plugin-specific container mounts / env vars that the settings-JSON seed can't express. |
| `E2E_PLUGIN_SETTINGS_JSON` | A JSON file whose keys merge into `/a0/usr/settings.json`. Typically `{"plugin_<name>": {...}}`. |
| `E2E_INSTANCE_ENV_EXTRA` | Extra `KEY=value` lines appended to `tests/e2e/.e2e/instance.env` so specs read plugin-specific values. |

### 2. `tests/e2e/playwright.config.ts` — spread the base

```ts
import { defineConfig } from "@playwright/test";
import { baseConfig } from "../_testkit/e2e/playwright-base.config";

export default defineConfig({
  ...baseConfig(__dirname),
  testDir: "./specs",
});
```

### 3. `tests/e2e/fixtures.ts` — compose on top

```ts
import { createA0Fixtures } from "../_testkit/e2e/fixtures";
import { MyPluginConfigPage } from "./pages/MyPluginConfigPage";

export const MY_PLUGIN_DISPLAY_NAME = "My Plugin";

export const test = createA0Fixtures().extend<{
  installedMyPlugin: void;
  configPage: MyPluginConfigPage;
}>({
  installedMyPlugin: async ({ pluginsPage }, use) => {
    if (!(await pluginsPage.isInstalled(MY_PLUGIN_DISPLAY_NAME))) {
      await pluginsPage.installFromZip(
        process.env.MY_PLUGIN_ZIP!, MY_PLUGIN_DISPLAY_NAME,
      );
    }
    await pluginsPage.close();
    await use();
  },
  configPage: async ({ loggedInPage }, use) => {
    await use(new MyPluginConfigPage(loggedInPage));
  },
});
export { expect } from "@playwright/test";
```

## Zero-config path

A plugin with no extra ports + no settings-seed can just drop the three
hooks above with empty `E2E_*` vars and a no-op `installedMyPlugin`. The
harness brings up A0 on 50011/50012 alone.

## Operational notes

- **`.e2e-cache/pip/`** (host path, plugin repo root, gitignored): pip
  cache persists between `e2e-fresh` runs so the first-time livekit-agents
  / heavy plugin install (~5 min over the wire) becomes ~30s on warm
  cache. The testkit scripts create this dir on `e2e-up`.
- **`tests/e2e/.e2e/instance.env`** (gitignored): written per-run with
  `A0_BASE_URL`, creds, `A0_MCP_SERVER_TOKEN`, and anything the plugin
  passed via `E2E_INSTANCE_ENV_EXTRA`.
- **Port same-on-both-sides**: extra ports should publish `N:N` whenever
  media / ICE candidates are involved — LK advertises the port it's bound
  to, so the browser needs to reach the container at the same number.
- **Manual mode still works**: `A0_BASE_URL=http://... npm test` in
  `tests/e2e/` bypasses the hermetic container entirely. Useful for
  targeting a long-running dev A0.

## Related

- `skill/SKILL.md` — the testkit skill, with the L3 section covering
  conventions (Page Object patterns, serial mode, end-state asserts).
- The first adopter, `agent-zero-plugin-livekit`, is the canonical
  example of the wiring model above.
