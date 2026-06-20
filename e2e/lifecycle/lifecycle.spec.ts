// Generic plugin lifecycle spec (SPEC §5.4/§5.5).
//
// Drives the UI half of the template-method lifecycle against a running A0:
//   install → verify-installed (card present) → uninstall →
//   verify-uninstalled (card gone)
//
// The container-level checks (filesystem residue baseline/diff) wrap this spec
// in run-lifecycle.sh. The per-config matrix (cases.yaml) and per-plugin hooks
// (Appendix E.4) layer on in increment 1c.
import { test, expect } from "./fixtures";

const ZIP = process.env.PLUGIN_ZIP;
const NAME = process.env.PLUGIN_DISPLAY_NAME;

test.beforeAll(() => {
  if (!ZIP || !NAME) {
    throw new Error("PLUGIN_ZIP and PLUGIN_DISPLAY_NAME must be set");
  }
});

test("install → verify-installed → uninstall → verify-uninstalled", async ({
  pluginsPage,
}) => {
  // Clean slate: a prior aborted run could leave it installed.
  if (await pluginsPage.isInstalled(NAME!)) {
    await pluginsPage.uninstall(NAME!);
  }
  expect(await pluginsPage.isInstalled(NAME!)).toBe(false);

  // install + verify-installed (UI card present)
  await pluginsPage.installFromZip(ZIP!, NAME!);
  expect(await pluginsPage.isInstalled(NAME!)).toBe(true);

  // uninstall + verify-uninstalled (UI card gone)
  await pluginsPage.uninstall(NAME!);
  expect(await pluginsPage.isInstalled(NAME!)).toBe(false);
});
