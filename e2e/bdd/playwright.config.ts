import { defineConfig } from "@playwright/test";
import { defineBddConfig } from "playwright-bdd";
const P = process.env.PLUGIN_BDD_DIR; // the plugin's tests/e2e (features/ + steps/)
const testDir = defineBddConfig({
  // featuresRoot must contain BOTH the devkit-common and plugin features.
  // In production both live under the plugin repo; locally they're split, so "/".
  featuresRoot: process.env.BDD_FEATURES_ROOT || "/",
  importTestFrom: "bdd-fixtures.ts",
  features: ["features/**/*.feature", ...(P ? [`${P}/features/**/*.feature`] : [])],
  steps: ["bdd-fixtures.ts", "steps/**/*.ts", ...(P ? [`${P}/steps/**/*.ts`] : [])],
});
export default defineConfig({
  testDir, reporter: [["list"]], timeout: 120000, workers: 1, fullyParallel: false,
  // trace = the rich single-file artifact (network + DOM snapshots + console + video + timeline),
  // viewable via `npx playwright show-trace` / trace.playwright.dev. Default: only failing scenarios
  // (retain-on-failure); set BDD_TRACE=on (the workflow's capture-all-traces dispatch input) for every one.
  use: {
    baseURL: process.env.A0_BASE || "http://localhost:8099",
    video: "on",
    screenshot: "on",
    trace: (process.env.BDD_TRACE as any) || "retain-on-failure",
  },
});
