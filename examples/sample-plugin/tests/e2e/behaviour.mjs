// Behaviour seam reference (SPEC DEC-053). The devkit lifecycle runs this against
// the LIVE, authenticated Agent Zero page right after install, and screenshots
// the result as the DEC-051 media. Default-export an async function; throw to
// fail the gate.
//
// Contract — you receive:
//   page        the authenticated Playwright Page (A0 is open + logged in)
//   expect      Playwright's expect
//   pluginName  on-disk name (plugin.yaml `name`)
//   displayName plugin.yaml `title`
//   baseURL     A0 base URL (e.g. http://localhost:80)
//
// A REAL plugin drives its feature and asserts a plugin-specific observable
// effect over the wire, e.g.:
//   await page.goto(baseURL + "/");
//   await expect(page.locator("#my-injected-toolbar-button")).toBeVisible();
//
// The sample plugin ships NO UI feature, so it asserts only that the live app is
// reachable + authenticated — enough to prove the seam end-to-end.
export default async function behaviour({ page, expect, displayName, baseURL }) {
  await page.goto(baseURL + "/", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveTitle(/Agent Zero/i);
  console.log(`[behaviour] ${displayName}: live app reachable + authenticated (sample has no feature to assert)`);
}
