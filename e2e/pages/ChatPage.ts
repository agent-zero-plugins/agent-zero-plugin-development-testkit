import { expect, Locator, Page } from "@playwright/test";

/**
 * Page Object for an Agent Zero chat view — the main workspace after
 * login, where the sidebar holds a list of chats and the central pane
 * holds the conversation + chat-input toolbar.
 *
 * Generic surface covered:
 *   - starting a new chat (sidebar "New Chat" button)
 *   - the chat list (sidebar)
 *
 * Plugin-specific surface lives in subclasses in the consumer repo —
 * e.g. a plugin that contributes a button at `chat-input-bottom-actions-*`
 * should expose its button + modal locators in its own Page Object,
 * extending this one if useful.
 */
export class ChatPage {
  readonly page: Page;
  readonly newChatButton: Locator;
  readonly chatList: Locator;

  constructor(page: Page) {
    this.page = page;
    this.newChatButton = page.getByRole("button", { name: "New Chat", exact: true });
    this.chatList = page.getByRole("list").first();
  }

  /** Start a new chat from the sidebar. Waits for a fresh chat to
   *  appear in the chat list (i.e. the sidebar count grew). */
  async startNewChat(): Promise<void> {
    const before = await this.chatList.getByRole("listitem").count();
    await this.newChatButton.click();
    await expect
      .poll(async () => this.chatList.getByRole("listitem").count(), {
        timeout: 10_000,
      })
      .toBeGreaterThan(before);
  }
}
