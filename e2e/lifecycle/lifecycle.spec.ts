// Generic plugin lifecycle spec (SPEC §5.4/§5.5 + DEC-053/056) — the
// template-method core, now MULTI-SPEC.
//
// One nested-A0 boot. The plugin is installed once, then each behaviour spec
// group runs as its OWN Playwright test (so it gets its OWN video recording —
// ≤10 groups per plugin), then the plugin is uninstalled once. Groups are
// supplied by the harness via BEHAVIOUR_SPECS=[{name,path}] (JSON); a single
// legacy BEHAVIOUR_FILE is treated as one group named "behaviour".
//
//   install → verify-installed [common + hook] →
//     ∀ group: behaviour: <group>  (drives the live UI, own video) →
//   uninstall → verify-uninstalled [common + hook]
import { execFileSync, execSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { pathToFileURL } from "node:url";

import { test, expect } from "./fixtures";

const ZIP = process.env.PLUGIN_ZIP;
const DISPLAY = process.env.PLUGIN_DISPLAY_NAME;
const PLUGIN_NAME = process.env.PLUGIN_NAME; // on-disk dir name (plugin.yaml `name`)
const A0_CONTAINER = process.env.A0_CONTAINER ?? "a0-lifecycle";
const HOOK_DIR = process.env.HOOK_DIR; // dir holding verify-installed / verify-uninstalled
const CASE_NAME = process.env.CASE_NAME ?? "default";
const REPORT_DIR = process.env.A0_REPORT_DIR ?? "/tmp";

// ≤10 behaviour spec groups (DEC-056), JSON [{name, path}]. Back-compat: a single
// BEHAVIOUR_FILE => one group "behaviour". Absent => no behaviour groups (logged).
let SPECS: Array<{ name: string; path: string }> = [];
try {
  SPECS = JSON.parse(process.env.BEHAVIOUR_SPECS ?? "[]");
} catch {
  SPECS = [];
}
if (!SPECS.length && process.env.BEHAVIOUR_FILE) {
  SPECS = [{ name: "behaviour", path: process.env.BEHAVIOUR_FILE }];
}

test.beforeAll(() => {
  for (const [k, v] of Object.entries({ PLUGIN_ZIP: ZIP, PLUGIN_DISPLAY_NAME: DISPLAY, PLUGIN_NAME }))
    if (!v) throw new Error(`${k} must be set`);
  if (!SPECS.length)
    console.log(`::warning::no behaviour spec for ${PLUGIN_NAME} — install-only coverage (DEC-053 gap)`);
});

// On failure, dump any open modals/backdrops so the CI log shows what (if
// anything) intercepted clicks — invaluable across the diverse plugin fleet.
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

/** Run a per-plugin bash hook if it exists. Pass/fail by exit code (Appendix E.4). */
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
      A0_REPORT_DIR: REPORT_DIR,
    },
  });
}

// Serial: install → each behaviour group (own video) → uninstall, one boot. The
// plugin install is backend state, so it persists across each test's fresh page.
test.describe.serial(`lifecycle [${CASE_NAME}]`, () => {
  test("install → verify-installed", async ({ pluginsPage }) => {
    if (await pluginsPage.isInstalled(DISPLAY!)) await pluginsPage.uninstall(DISPLAY!);
    expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(false);

    await pluginsPage.installFromZip(ZIP!, DISPLAY!);
    expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(true);

    // verify-installed — common stage (devkit): the plugin's files landed.
    expect(inA0ok(`test -d /a0/usr/plugins/${PLUGIN_NAME} && test -f /a0/usr/plugins/${PLUGIN_NAME}/plugin.yaml`)).toBe(true);
    // verify-installed — per-plugin bash hook (container/API checks).
    runHook("verify-installed");
  });

  // One test (one video) per behaviour group — drives the live authenticated UI.
  for (const spec of SPECS) {
    test(`behaviour: ${spec.name}`, async ({ pluginsPage }) => {
      const page = pluginsPage.page;
      if (!fs.existsSync(spec.path)) throw new Error(`behaviour spec not found: ${spec.path}`);
      const mod = await import(pathToFileURL(spec.path).href);
      const fn = mod.default ?? mod.behaviour;
      if (typeof fn !== "function") throw new Error(`${spec.path} must default-export an async function`);
      await fn({ page, expect, pluginName: PLUGIN_NAME, displayName: DISPLAY, baseURL: process.env.A0_BASE_URL });
      try {
        await page.screenshot({ path: path.join(REPORT_DIR, `behaviour-${spec.name}.png`) });
      } catch (e) {
        console.log("behaviour screenshot failed:", String(e));
      }
    });
  }

  test("uninstall → verify-uninstalled", async ({ pluginsPage }) => {
    await pluginsPage.open();
    await pluginsPage.uninstall(DISPLAY!);
    expect(await pluginsPage.isInstalled(DISPLAY!)).toBe(false);

    // verify-uninstalled — common stage: the plugin's OWN dir is gone (ambient
    // builtin dirs A0 lazily creates are not residue — DEC-029).
    expect(inA0ok(`test ! -d /a0/usr/plugins/${PLUGIN_NAME}`)).toBe(true);
    runHook("verify-uninstalled");
  });
});
