import { defineConfig } from "@playwright/test";

import { baseConfig } from "../playwright-base.config";

// Self-contained config for the devkit's generic lifecycle suite. A0_BASE_URL
// and creds come from the environment (exported by run-lifecycle.sh from the
// instance env file a0-up.sh writes).
export default defineConfig({
  ...baseConfig(__dirname),
  testDir: ".",
  // Generous per-test timeout: installing a real plugin's pip deps in the
  // nested A0 can take minutes (e.g. livekit-agents). Playwright's 30s default
  // fires long before installFromZip's own 90s "Plugin installed:" wait.
  timeout: 300_000,
});
