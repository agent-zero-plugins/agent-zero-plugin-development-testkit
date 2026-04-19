import * as fs from "node:fs";
import * as path from "node:path";

/**
 * Load a ``KEY=value`` env file into ``process.env``.
 *
 * Called from two places:
 *   - Synchronously at the top of ``playwright-base.config.ts`` (via the
 *     ``baseConfig(consumerE2EDir)`` helper) so the config's own
 *     ``process.env.A0_*`` reads see the hermetic values.
 *   - Again as Playwright's ``globalSetup`` hook so any lazily-loaded
 *     module (e.g. worker imports) also sees them.
 *
 * Silent no-op when the file is absent — lets "point at already-running
 * A0" workflows keep working without a hermetic harness:
 *
 *     A0_BASE_URL=http://localhost:50002 npm test
 *
 * Never overwrites already-set env vars, so explicit shell-level exports
 * always win.
 *
 * @param envFile absolute path to the instance.env file. When omitted,
 *                defaults to ``<repo-root>/tests/e2e/.e2e/instance.env``
 *                inferred by walking up from this file (this file is at
 *                ``<repo-root>/tests/_testkit/e2e/global-setup.ts``).
 *                Consumer plugins with non-standard layouts can pass an
 *                explicit path via ``baseConfig(consumerE2EDir)``.
 */
export function loadInstanceEnv(envFile?: string): void {
  const target =
    envFile ??
    path.resolve(__dirname, "..", "..", "..", "tests", "e2e", ".e2e", "instance.env");
  if (!fs.existsSync(target)) return;

  const raw = fs.readFileSync(target, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const m = trimmed.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (!m) continue;
    const [, key, value] = m;
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

export default async function globalSetup(): Promise<void> {
  // Invoked by Playwright with no args. Uses the default path
  // (plugin-at-<root>/tests/e2e, testkit-at-<root>/tests/_testkit layout).
  loadInstanceEnv();
}
