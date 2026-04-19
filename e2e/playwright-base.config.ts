import type { PlaywrightTestConfig } from "@playwright/test";
import * as path from "node:path";

import { loadInstanceEnv } from "./global-setup";

/**
 * Shared Playwright config fragment for L3 e2e suites across plugin
 * repos. Consumer plugin's ``playwright.config.ts`` spreads the result
 * of ``baseConfig(__dirname)`` and adds ``testDir`` + ``projects`` on top.
 *
 * Why this file uses ``import type`` only (no runtime
 * ``@playwright/test`` import): the testkit lives in a submodule at
 * ``tests/_testkit/`` — Node's module resolution from here walks up to
 * the filesystem root and never reaches ``tests/e2e/node_modules``
 * where the consumer's ``@playwright/test`` actually lives. Types
 * flow across submodule boundaries; runtime imports don't. The
 * ``devices`` map the consumer wants applied to a browser project is
 * passed in as an argument — the consumer imports it themselves from
 * its own ``node_modules``.
 */
export type BaseConfigOptions = {
  /**
   * A ``devices`` entry (e.g. ``devices["Desktop Chrome"]``) to apply
   * to the default ``chromium`` project. Pass your own Playwright
   * ``devices`` import result.
   */
  desktopChromeDevice?: Record<string, unknown>;
};

export function baseConfig(
  consumerE2EDir: string,
  opts: BaseConfigOptions = {},
): PlaywrightTestConfig {
  // Run the loader against the CONSUMER's e2e dir. If we used our own
  // __dirname (under tests/_testkit/e2e), we'd miss the consumer's
  // .e2e/instance.env.
  loadInstanceEnv(path.resolve(consumerE2EDir, ".e2e", "instance.env"));

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
        use: { ...(opts.desktopChromeDevice ?? {}) },
      },
    ],
  };
}
