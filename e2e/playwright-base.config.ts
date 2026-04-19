import { devices, PlaywrightTestConfig } from "@playwright/test";
import * as path from "node:path";

import { loadInstanceEnv } from "./global-setup";

/**
 * Shared Playwright config fragment for L3 e2e suites across plugin
 * repos. Consumer plugin's ``playwright.config.ts`` spreads the result
 * of ``baseConfig(__dirname)`` and adds ``testDir`` + ``projects`` on top.
 *
 * ``__dirname`` here refers to the consumer's e2e directory (the
 * place where ``playwright.config.ts`` itself lives) — that's what
 * ``globalSetup`` needs as an anchor to find ``.e2e/instance.env``.
 *
 * Loads the per-run ``instance.env`` (written by the testkit's
 * e2e-up.sh) at config-module load time, so the config-level
 * ``process.env.A0_*`` reads below see the hermetic values. The
 * ``globalSetup`` hook re-runs the loader for workers spawned after
 * config load.
 */
export function baseConfig(consumerE2EDir: string): PlaywrightTestConfig {
  // Run the loader against the CONSUMER's e2e dir. If we used our own
  // __dirname (under tests/_testkit/e2e), we'd miss the consumer's
  // .e2e/instance.env.
  loadInstanceEnvFor(consumerE2EDir);

  const BASE_URL = process.env.A0_BASE_URL ?? "http://localhost:50011";

  return {
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI
      ? [["github"], ["html", { open: "never" }]]
      : "list",
    testIgnore: ["**/node_modules/**", "**/vendor/**", "**/.skills/**"],
    globalSetup: path.resolve(__dirname, "global-setup.ts"),
    use: {
      baseURL: BASE_URL,
      trace: "retain-on-failure",
      screenshot: "only-on-failure",
      video: "retain-on-failure",
      actionTimeout: 15_000,
      navigationTimeout: 20_000,
    },
    projects: [
      {
        name: "chromium",
        use: { ...devices["Desktop Chrome"] },
      },
    ],
  };
}

/**
 * Load the consumer's own ``.e2e/instance.env`` if present.
 *
 * The loader in ``global-setup.ts`` takes no args (it uses its own
 * ``__dirname``, which would be the testkit's — wrong anchor). This
 * wrapper reuses the same parsing logic but anchors on the consumer's
 * e2e dir.
 */
function loadInstanceEnvFor(consumerE2EDir: string): void {
  const envFile = path.resolve(consumerE2EDir, ".e2e", "instance.env");
  loadInstanceEnv(envFile);
}
