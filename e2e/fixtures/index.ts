import type { Page, TestType } from "@playwright/test";

import { ChatPage } from "../pages/ChatPage";
import { LoginPage } from "../pages/LoginPage";
import { PluginsPage, suppressOnboarding } from "../pages/PluginsPage";

/**
 * Base e2e fixtures shared across A0 plugin repos.
 *
 * Why ``TestType`` is imported as a type + the consumer's ``test`` is
 * passed in as an argument: the testkit lives in a submodule whose
 * parent directories don't contain ``node_modules/@playwright/test``,
 * so any runtime import from here fails. The consumer's
 * ``fixtures.ts`` does the runtime ``import { test }`` and passes it
 * to ``createA0Fixtures(test)``.
 *
 * Fixtures provided by ``createA0Fixtures(test)``:
 *   - ``credentials``   — resolved from env vars with admin/admin defaults
 *   - ``loggedInPage``  — a ``Page`` already past the login screen
 *   - ``pluginsPage``   — a ``PluginsPage`` with the panel open
 *   - ``chatPage``      — a ``ChatPage`` (does NOT start a new chat)
 *
 * Usage (consumer plugin's ``tests/e2e/fixtures.ts``):
 *
 *   import { test as base } from "@playwright/test";
 *   import { createA0Fixtures } from "../_testkit/e2e/fixtures";
 *   import { MyPluginConfigPage } from "./pages/MyPluginConfigPage";
 *
 *   export const test = createA0Fixtures(base).extend<{
 *     installedMyPlugin: void;
 *     configPage: MyPluginConfigPage;
 *   }>({
 *     installedMyPlugin: async ({ pluginsPage }, use) => {
 *       if (!(await pluginsPage.isInstalled("My Plugin"))) {
 *         await pluginsPage.installFromZip(process.env.MY_PLUGIN_ZIP!, "My Plugin");
 *       }
 *       await pluginsPage.close();
 *       await use();
 *     },
 *     configPage: async ({ loggedInPage }, use) => {
 *       await use(new MyPluginConfigPage(loggedInPage));
 *     },
 *   });
 *   export { expect } from "@playwright/test";
 */

export type Credentials = { username: string; password: string };

export type A0BaseFixtures = {
  credentials: Credentials;
  loggedInPage: Page;
  pluginsPage: PluginsPage;
  chatPage: ChatPage;
};

/**
 * Given the consumer's Playwright ``test`` export, return a `test`
 * extended with A0 base fixtures. Consumer typically immediately
 * calls ``.extend(...)`` again to layer plugin-specific fixtures.
 */
export function createA0Fixtures<T extends TestType<any, any>>(base: T) {
  return base.extend<A0BaseFixtures>({
    credentials: async ({}, use) => {
      await use({
        username: process.env.A0_USERNAME ?? "admin",
        password: process.env.A0_PASSWORD ?? "admin",
      });
    },

    loggedInPage: async ({ page, credentials }, use) => {
      // Neutralize A0's first-run onboarding modal before any navigation — it
      // auto-opens with no provider key and would intercept all clicks.
      await suppressOnboarding(page);
      const login = new LoginPage(page);
      await login.goto();
      await login.login(credentials.username, credentials.password);
      await use(page);
    },

    pluginsPage: async ({ loggedInPage }, use) => {
      const plugins = new PluginsPage(loggedInPage);
      await plugins.open();
      await use(plugins);
    },

    chatPage: async ({ loggedInPage }, use) => {
      await use(new ChatPage(loggedInPage));
    },
  });
}

// Re-export the Page Objects so plugins can type-hint / extend them
// without a second import path.
export { ChatPage, LoginPage, PluginsPage };
