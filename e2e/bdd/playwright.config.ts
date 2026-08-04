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
// Red-proof mode (Gate 3, DEC-066 / DEC-070): the suite runs with the plugin NOT
// installed, so EVERY scenario is expected to fail. Capturing video + a
// retain-on-failure trace for every one of those expected failures is pure I/O
// cost for artifacts nobody reads (the gate's signal is the pass COUNT, not the
// artifacts). Disable capture in red-proof mode only — the real run below is
// unaffected, so debuggability of genuine failures is unchanged.
const RED_PROOF = process.env.BDD_SKIP_INSTALL === "1";

export default defineConfig({
  testDir, reporter: [["list"]], timeout: 120000, workers: 1, fullyParallel: false,
  // trace = the rich single-file artifact (network + DOM snapshots + console + video + timeline),
  // viewable via `npx playwright show-trace` / trace.playwright.dev.
  //
  // Default "on" (DEC-073): a GREEN run must leave evidence too, otherwise there
  // is no baseline to diff a later regression against and a scenario can only be
  // diagnosed after it has already broken. This default was "retain-on-failure",
  // which is the same defect DEC-073 fixed in playwright-base.config.ts — the
  // BDD suite kept its own copy of the setting and was missed. Override with
  // BDD_TRACE / the workflow's trace-mode input.
  use: {
    baseURL: process.env.A0_BASE || "http://localhost:8099",
    video: RED_PROOF ? "off" : "on",
    screenshot: RED_PROOF ? "off" : "on",
    trace: RED_PROOF ? "off" : ((process.env.BDD_TRACE as any) || "on"),
  },
});
