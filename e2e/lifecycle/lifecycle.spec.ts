// Generic plugin lifecycle spec (SPEC §5.4/§5.5) — the template-method core.
//
// The skeleton lives here (devkit); a plugin supplies only the variant steps as
// language-agnostic hook executables (Appendix E.4):
//   tests/e2e/hooks/verify-installed     (optional)
//   tests/e2e/hooks/verify-uninstalled   (optional)
//
// Per the active case the harness runs, in order:
//   install → [common verify-installed] → [plugin verify-installed hook] →
//   uninstall → [common verify-uninstalled] → [plugin verify-uninstalled hook]
//
// The spec runs in Node inside the devcontainer, so container-level checks use
// `podman exec` and hooks are spawned with the documented env context.
import { execFileSync, execSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { pathToFileURL } from "node:url";

import type { Page } from "@playwright/test";

import { test, expect } from "./fixtures";

const ZIP = process.env.PLUGIN_ZIP;
const DISPLAY = process.env.PLUGIN_DISPLAY_NAME;
const PLUGIN_NAME = process.env.PLUGIN_NAME; // on-disk dir name (plugin.yaml `name`)
const A0_CONTAINER = process.env.A0_CONTAINER ?? "a0-lifecycle";
const HOOK_DIR = process.env.HOOK_DIR; // dir holding verify-installed / verify-uninstalled
const BEHAVIOUR_FILE = process.env.BEHAVIOUR_FILE; // tests/e2e/behaviour.mjs (DEC-053 in-browser seam)
const CASE_NAME = process.env.CASE_NAME ?? "default";
const REPORT_DIR = process.env.A0_REPORT_DIR ?? "/tmp";

test.beforeAll(() => {
  for (const [k, v] of Object.entries({ PLUGIN_ZIP: ZIP, PLUGIN_DISPLAY_NAME: DISPLAY, PLUGIN_NAME }))
    if (!v) throw new Error(`${k} must be set`);
});

// On failure, dump any open modals/backdrops so the CI log shows what (if
// anything) was intercepting clicks — invaluable for diagnosing UI-harness
// edges across the diverse plugin fleet.
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    try {
      const overlays = await page
        .locator("div.modal.show, div.modal-backdrop")
        .evaluateAll((els) =>
          els.map((e) => ({
            modalPath: e.getAttribute("data-modal-path"),
            cls: e.className,
            display: getComputedStyle(e).display,
            pe: getComputedStyle(e).pointerEvents,
          })),
        );
      console.log("::group::open overlays at failure");
      console.log(JSON.stringify(overlays, null, 2));
      console.log("::endgroup::");
    } catch (e) {
      console.log("overlay dump failed:", String(e));
    }
  }
});

/** Run a shell command inside the nested A0 container; throws on non-zero. */
function inA0(cmd: string): void {
  execSync(`podman exec ${A0_CONTAINER} sh -c ${JSON.stringify(cmd)}`, { stdio: "pipe" });
}
function inA0ok(cmd: string): boolean {
  try { inA0(cmd); return true; } catch { return false; }
}

/** Run a per-plugin hook if it exists. Pass/fail by exit code (Appendix E.4). */
function runHook(name: string): void {
  if (!HOOK_DIR) return;
  const hook = path.join(HOOK_DIR, name);
  if (!fs.existsSync(hook)) return;
  execFileSync("bash", [hook], {
    stdio: "inherit",
    env: {
      ...process.env,
      A0_BASE_URL: process.env.A0_BASE_URL ?? "",
      A0_USERNAME: process.env.A0_USERNAME ?? "admin",
      A0_PASSWORD: process.env.A0_PASSWORD ?? "admin",
      A0_CONTAINER,
      PLUGIN_NAME: PLUGIN_NAME ?? "",
      CASE_NAME,
      A0_REPORT_DIR: process.env.A0_REPORT_DIR ?? "/tmp",
    },
  });
}

/**
 * In-browser behaviour seam (SPEC DEC-053): a plugin ships
 * `tests/e2e/behaviour.mjs` default-exporting `async ({ page, expect,
 * pluginName, displayName, baseURL }) => {…}`. It drives the LIVE authenticated
 * A0 page and asserts a plugin-specific observable effect — the falsifiable,
 * over-the-wire behaviour check (vs the bash hook's container/API checks). It
 * also produces `behaviour.png` (the DEC-051 media source). Absent file ⇒ skip
 * (logged, so the missing-behaviour-test gap is visible).
 */
async function runBehaviour(page: Page): Promise<void> {
  if (!BEHAVIOUR_FILE) {
    console.log(`::warning::no behaviour.mjs for ${PLUGIN_NAME} — install-only coverage (DEC-053 gap)`);
    return;
  }
  if (!fs.existsSync(BEHAVIOUR_FILE)) throw new Error(`BEHAVIOUR_FILE not found: ${BEHAVIOUR_FILE}`);
  const mod = await import(pathToFileURL(BEHAVIOUR_FILE).href);
  const fn = mod.default ?? mod.behaviour;
  if (typeof fn !== "function") throw new Error(`${BEHAVIOUR_FILE} must default-export an async function`);
  await fn({ page, expect, pluginName: PLUGIN_NAME, displayName: DISPLAY, baseURL: process.env.A0_BASE_URL });
  try {
    await page.screenshot({ path: path.join(REPORT_DIR, "behaviour.png") });
  } catch (e) {
    console.log("behaviour screenshot failed:", String(e));
  }
}

test(`lifecycle [${CASE_NAME}]: install → verify-installed → uninstall → verify-uninstalled`, async ({
  pluginsPage,
}) => {
  // Clean slate.
  if (await pluginsPage.isInstalled(DISPLAY!)) await pluginsPage.uninstall(DISPLAY!);
  expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(false);

  // install
  await pluginsPage.installFromZip(ZIP!, DISPLAY!);
  expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(true);

  // verify-installed — common stage (devkit): the plugin's files landed.
  expect(inA0ok(`test -d /a0/usr/plugins/${PLUGIN_NAME} && test -f /a0/usr/plugins/${PLUGIN_NAME}/plugin.yaml`)).toBe(true);
  // verify-installed — per-plugin hook (variant step).
  runHook("verify-installed");
  // verify-installed — in-browser behaviour seam (DEC-053): drive the live UI
  // and assert a plugin-specific effect; also captures the DEC-051 media.
  await runBehaviour(pluginsPage.page);

  // uninstall
  await pluginsPage.uninstall(DISPLAY!);
  expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(false);

  // verify-uninstalled — common stage: the plugin's OWN dir is gone (ambient
  // builtin dirs A0 lazily creates are not residue — DEC-029).
  expect(inA0ok(`test ! -d /a0/usr/plugins/${PLUGIN_NAME}`)).toBe(true);
  // verify-uninstalled — per-plugin hook (variant step).
  runHook("verify-uninstalled");
});
