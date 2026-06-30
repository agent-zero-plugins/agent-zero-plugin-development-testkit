import { test as base, createBdd } from "playwright-bdd";
import { createA0Fixtures } from "../fixtures";
import { PluginsPage, suppressOnboarding } from "../pages/PluginsPage";
import { LoginPage } from "../pages/LoginPage";

const USER = () => process.env.A0_USERNAME || "admin";
const PASS = () => process.env.A0_PASSWORD || "admin";

// Devkit batteries-included lifecycle: install the plugin once per worker before
// any scenario, uninstall after all — so behaviour scenarios run against the
// installed plugin without any per-feature ordering hacks (DEC-063).
const a0 = createA0Fixtures(base as any);
export const test = a0.extend<{}, { installedPlugin: void }>({
  installedPlugin: [
    async ({ browser }, use) => {
      const ZIP = process.env.PLUGIN_ZIP;
      const DISPLAY = process.env.PLUGIN_DISPLAY_NAME;
      // Gate-3 seam-off red-proof (DEC-066): run the behaviour scenarios on the
      // SAME instance with the plugin NOT installed — honest scenarios must go RED
      // (the seam endpoint 404s). If they pass, they're fake-green.
      if (process.env.BDD_SKIP_INSTALL === "1") {
        await use();
        return;
      }
      const withPanel = async (fn: (pp: PluginsPage) => Promise<void>) => {
        const ctx = await browser.newContext({ baseURL: process.env.A0_BASE || "http://localhost:8099" });
        const page = await ctx.newPage();
        await suppressOnboarding(page);
        const lp = new LoginPage(page);
        await lp.goto();
        await lp.login(USER(), PASS());
        const pp = new PluginsPage(page);
        await pp.open();
        await fn(pp);
        await ctx.close();
      };
      if (ZIP && DISPLAY)
        await withPanel(async (pp) => {
          if (!(await pp.isInstalled(DISPLAY))) await pp.installFromZip(ZIP, DISPLAY);
        });
      await use();
      if (ZIP && DISPLAY)
        await withPanel(async (pp) => {
          if (await pp.isInstalled(DISPLAY)) await pp.uninstall(DISPLAY);
        });
    },
    { scope: "worker", auto: true },
  ],
});
export const { Given, When, Then, Before, After, BeforeAll, AfterAll } = createBdd(test);
