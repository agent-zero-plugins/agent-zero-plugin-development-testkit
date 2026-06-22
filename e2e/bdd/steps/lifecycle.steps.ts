import { Then } from "../bdd-fixtures";
import { expect } from "@playwright/test";
Then("the plugin is listed as installed", async ({ pluginsPage }) => {
  expect(await pluginsPage.isInstalled(process.env.PLUGIN_DISPLAY_NAME!)).toBe(true);
});
