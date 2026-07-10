import { expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

/**
 * Page Object for Agent Zero's `/login` page.
 *
 * Kept minimal: a couple of fields + a submit. Selectors target
 * accessibility roles so re-styling the page doesn't break tests.
 */
export class LoginPage {
  readonly page: Page;
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.usernameInput = page.getByRole("textbox", { name: "Username" });
    this.passwordInput = page.getByRole("textbox", { name: "Password" });
    this.submitButton = page.getByRole("button", { name: "Login" });
  }

  /** Navigate to the login page. */
  async goto(): Promise<void> {
    await this.page.goto("/login");
    await expect(this.usernameInput).toBeVisible();
  }

  /** Fill credentials and submit. Waits until we land on the dashboard. */
  async login(username: string, password: string): Promise<void> {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
    // A0 redirects to `/` on success. We assert on a post-login landmark
    // (the top-nav "Plugins" button) rather than the URL alone, so a
    // silent auth failure shows up as a timeout on this line.
    await expect(
      this.page.getByRole("button", { name: "Plugins", exact: true }),
    ).toBeVisible();
  }
}
