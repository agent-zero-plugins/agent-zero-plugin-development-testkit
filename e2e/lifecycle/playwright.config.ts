import { defineConfig } from "@playwright/test";

import { baseConfig } from "../playwright-base.config";

// Self-contained config for the devkit's generic lifecycle suite. A0_BASE_URL
// and creds come from the environment (exported by run-lifecycle.sh from the
// instance env file a0-up.sh writes).
export default defineConfig({
  ...baseConfig(__dirname),
  testDir: ".",
});
