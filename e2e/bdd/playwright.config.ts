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
  use: { baseURL: process.env.A0_BASE || "http://localhost:8099", video: "on", screenshot: "on" },
});
