import { expect, Locator, Page } from "@playwright/test";

/**
 * Page Object for Agent Zero's Plugins panel.
 *
 * Surface covered by this class:
 *   - opening the panel from the top nav
 *   - locating a specific installed plugin by display name
 *   - uninstalling a plugin (via More-actions → Delete)
 *   - launching the Install dialog and uploading a ZIP
 *
 * What it deliberately does NOT do:
 *   - configure the plugin (that's a per-plugin concern; each plugin's
 *     Config page should get its own Page Object when tested)
 *   - browse the Plugin Hub (roadmap — add a `browseHub()` method when
 *     we need it)
 */
export class PluginsPage {
  readonly page: Page;

  // Top-level panel locators
  readonly topNavButton: Locator;
  readonly panel: Locator;
  readonly customTab: Locator;
  readonly installButton: Locator;

  // Install dialog locators
  readonly installDialog: Locator;
  readonly zipTab: Locator;
  readonly zipFileInput: Locator;

  constructor(page: Page) {
    this.page = page;
    this.topNavButton = page.getByRole("button", { name: "Plugins", exact: true });
    // The Plugins modal's heading scopes everything underneath it. Scoping
    // by the heading means the selectors don't collide with the "Plugins"
    // tile on the dashboard welcome screen.
    this.panel = page.locator(":has(> :has-text('Plugins'))").first();
    this.customTab = page.getByRole("tab", { name: "Custom" });
    this.installButton = page.getByRole("button", { name: /Install/ });

    this.installDialog = page.getByRole("heading", { name: "Install Plugin" }).locator("..").locator("..");
    this.zipTab = page.getByRole("tab", { name: /ZIP/ });
    // A0's ZIP upload is a styled drop-zone; the real <input type="file">
    // is hidden. Playwright's setInputFiles works on the hidden input
    // directly — no need to simulate the click.
    this.zipFileInput = this.installDialog.locator('input[type="file"]');
  }

  /**
   * Locate the card of an *installed* plugin. Scoped by two signatures
   * the Browse catalog doesn't share:
   *   - an <img alt="<displayName>"> (plugin icon inside the card)
   *   - a "More actions" kebab (only installed plugins have it)
   * `.last()` pinpoints the innermost matching div (the card).
   */
  installedCard(displayName: string): Locator {
    return this.page
      .locator("div")
      .filter({ has: this.page.getByRole("img", { name: displayName, exact: true }) })
      .filter({ has: this.page.getByRole("button", { name: "More actions" }) })
      .last();
  }

  /** Open the Plugins panel from the top nav. */
  async open(): Promise<void> {
    await this.topNavButton.click();
    await expect(this.customTab).toBeVisible();
  }

  /** Close the Plugins panel (× button in its header). Safe if already closed. */
  async close(): Promise<void> {
    const closeBtn = this.page
      .getByRole("heading", { name: "Plugins" })
      .locator("..")
      .getByRole("button", { name: "×" });
    if (await closeBtn.isVisible().catch(() => false)) {
      await closeBtn.click();
      await expect(this.customTab).not.toBeVisible();
    }
  }

  /**
   * Return the card for the named plugin (as shown in the Custom tab),
   * or null when the plugin isn't installed. Uses the display name
   * exposed in `generic` text, not the internal slug.
   */
  pluginCard(displayName: string): Locator {
    // A plugin card is a generic container whose first descendant holds
    // the display name. We match the name inside the Custom tab's list.
    return this.page.locator("generic", { hasText: displayName }).first();
  }

  /** True iff a plugin with this display name is currently installed.
   *  Scoped to the Custom tab's card (not the Browse catalog or toasts).
   *
   *  Waits up to ``timeoutMs`` for the card to appear — the Plugins
   *  panel hydrates its list asynchronously after ``open()``, so a
   *  naked ``count()`` called immediately can race and return 0 while
   *  the panel is still loading. Returns ``false`` only after the
   *  timeout expires with the card genuinely absent.
   */
  async isInstalled(displayName: string, timeoutMs = 3_000): Promise<boolean> {
    try {
      await this.installedCard(displayName).first().waitFor({
        state: "visible",
        timeout: timeoutMs,
      });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Uninstall the plugin by display name. No-op if not installed.
   *
   * Flow:
   *   1. Locate the card (scoped by the plugin's icon image + the
   *      per-card "More actions" kebab; `.last()` pinpoints the
   *      innermost matching container i.e. the card itself).
   *   2. Click its kebab menu.
   *   3. Click Delete in the opened flyout.
   *   4. Wait for the card to disappear.
   */
  async uninstall(displayName: string): Promise<void> {
    if (!(await this.isInstalled(displayName))) return;

    const card = this.installedCard(displayName);
    await card.getByRole("button", { name: "More actions" }).click();

    // A0 uses inline two-click confirmation for destructive actions
    // (see .agent-zero/webui/js/confirmClick.js):
    //   first click  — button text flips to "Confirm", 2s timeout starts
    //   second click — confirms and fires the action
    // The Delete button carries a stable `plugin-dropdown-delete` class
    // (doesn't change across click states). Scope to the card so we
    // never race against another plugin's dropdown.
    const deleteBtn = card.locator(".plugin-dropdown-delete");
    await deleteBtn.waitFor({ state: "visible" });
    await deleteBtn.click();
    await deleteBtn.click();

    // Wait for the CARD to disappear, not the display-name text (which
    // can reappear in the Browse catalog, a success toast, etc.).
    await expect(this.installedCard(displayName)).toHaveCount(0, { timeout: 30_000 });
  }

  /**
   * Install a plugin from a local ZIP file.
   *
   * @param zipPath  Absolute (or cwd-relative) path to the plugin zip.
   * @param expectedDisplayName  Display name to wait for in the Custom
   *                             tab after install. Lets the caller pin
   *                             the expected post-install state.
   */
  async installFromZip(zipPath: string, expectedDisplayName: string): Promise<void> {
    await this.installButton.click();
    await expect(this.installDialog).toBeVisible();

    await this.zipTab.click();
    await this.zipFileInput.setInputFiles(zipPath);

    // A0's ZIP install is a three-step form:
    //   1. pick the file (drop-zone highlights, stages it)
    //   2. click "Install Plugin"  → pops a security-warning modal
    //   3. click "Install Anyway"  → actually POSTs the upload
    // Missing (3) leaves the dialog open and nothing leaves the browser.
    await this.installDialog
      .getByRole("button", { name: /Install Plugin/ })
      .click();
    await this.page
      .getByRole("button", { name: /Install Anyway/ })
      .click();

    // Wait for the server-side install to finish. A0's pluginInstallStore
    // flips `result` once the POST resolves — the dialog renders a
    // success panel ("Plugin installed: <name>") at that point. Pip
    // install inside the container can take ~30–60s on a cold cache.
    await expect(
      this.installDialog.getByText(/Plugin installed:/),
    ).toBeVisible({ timeout: 90_000 });

    // A0 does NOT auto-refresh the Plugins list after install — and
    // plugin-contributed extension HTML (e.g. the Talk button in the
    // chat bar) only wires up at page load. A full reload is how the
    // UX actually transitions to "plugin active". Do the reload here
    // so every spec downstream of this helper gets the post-install
    // UI state for free.
    await this.page.reload();

    // After reload we're back on the root page; re-open the Plugins
    // panel so the caller (and post-conditions) can see the card.
    await this.open();
    await expect(this.installedCard(expectedDisplayName)).toBeVisible({
      timeout: 10_000,
    });
  }
}
