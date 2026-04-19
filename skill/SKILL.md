---
name: a0-plugin-testkit
description: "Shared test scaffolding for Agent Zero plugin repos. Scrapes A0's source at runtime for canonical extension-point IDs, JS hooks, plugin lifecycle hooks, and module attribute names — exposes them as fast pytest assertions. Ships A0 fakes, a live FastA2A fixture, a static validator, a dependency audit, and an A0-API audit. Meant to be actively evolved by consumer repos — load whenever building, extending, debugging, OR contributing back new reusable testing assets."
version: "0.3.0"
author: "agent-zero-operator"
tags: ["plugins", "testing", "testkit", "pytest", "extension-points", "a2a", "hooks"]
trigger_patterns:
  - "plugin testkit"
  - "a0_plugin_testkit"
  - "assert_extension_at_surface"
  - "assert_no_dead_plugin_hooks"
  - "assert_plugin_has_thumbnail"
  - "audit_dependencies"
  - "audit_a0_api_usage"
  - "scripted_a2a_server"
  - "KNOWN_HTML_SURFACES"
  - "how do I test my A0 plugin"
  - "why is my extension point not working"
  - "why is my hook never called"
  - "valid extension point name"
  - "valid plugin hook name"
  - "contribute to the testkit"
  - "add a new assertion to the testkit"
  - "bump testkit submodule"
---

# a0-plugin-testkit — shared plugin-test scaffolding

A small Python package (`a0_plugin_testkit`) that captures the test patterns every Agent Zero plugin repo needs. It exists because A0's own docs historically said "search the source" for canonical names — which is how a plugin author wrote `extensions/webui/chat_toolbar/` (invalid) and `on_plugin_enabled()` (never called) and shipped a plugin that compiled cleanly yet did nothing visible.

The testkit eliminates that class of bug by **scraping A0's own source for canonical truth** (`<x-extension id>` IDs, `callJsExtensions(name)` names, `call_plugin_hook(name)` names, module public attrs) and exposing it as pytest assertions. Every assertion points at a real shipped-bug it would have caught.

---

## When to load this skill

- Writing or modifying tests in any repo that uses `a0_plugin_testkit`.
- Onboarding a fresh plugin repo to the testkit.
- Debugging a plugin that "installs but doesn't do anything" / "installs but crashes on first HTTP hit" / "toggle exists but does nothing" — testkit has a dedicated check for each.
- Adding a new capability to the testkit itself.

## When NOT to load this skill

- Writing plugin runtime code with no test surface — use `a0-create-plugin` / `a0-plugin-architecture`.
- Debugging A0 framework internals — not the testkit's concern.

---

## Where it lives

**Today** (phase 1): vendored inside `agent-zero-plugin-livekit` at [`tests/_testkit/src/a0_plugin_testkit/`](../../_testkit/src/a0_plugin_testkit/), consumed via `pyproject.toml`'s `pythonpath = ["tests/_testkit/src"]`.

**Tomorrow** (once a second plugin adopts it): extracted to a standalone repo `agent-zero-plugin-testkit`, consumed as a git submodule at `.testkit/`. Imports stay identical — `from a0_plugin_testkit.X import Y` — so extraction is a filesystem move, not an import rewrite.

No PyPI. Versioning is commit-pin on the submodule, same distribution pattern as `.skills`.

---

## Installing the testkit into a fresh plugin repo

1. **Vendor or submodule it.** Either copy `tests/_testkit/` from this repo, or (once extracted) `git submodule add https://github.com/agent-zero-operator/agent-zero-plugin-testkit .testkit`.

2. **Put it on `pythonpath`.** In the consumer repo's `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   pythonpath = [".", "tests/_testkit/src"]   # or ".testkit/src" when submoduled
   asyncio_mode = "auto"
   markers = [
     "unit: fast L0 tests, no subprocess, no network",
     "component: L1 tests, A0 in-process or fixtures",
     "integration: L2 tests, real services",
   ]
   ```

3. **Wire the `plugin_dir` fixture.** Every assertion takes `plugin_dir: Path` — declare it once in `tests/conftest.py`:
   ```python
   from pathlib import Path
   import pytest

   @pytest.fixture(scope="session")
   def plugin_dir() -> Path:
       return (Path(__file__).resolve().parent.parent
               / "usr" / "plugins" / "<your_plugin_name>")
   ```

4. **Ensure A0 is reachable.** Most assertions need to read from A0's source. The testkit looks for:
   1. `$A0_ROOT` env var, if set.
   2. A `.agent-zero/` submodule at the repo root (standard in agent-zero-operator plugin repos).
   3. Walking up from the testkit's own location.
   If none resolve, assertions raise with an actionable message.

5. **Run the suite inside a container.** The lean `docker/dev.Dockerfile` in this repo is a good template — Python 3.11 + the pinned deps in `requirements-dev.txt`. Never `pip install` the testkit's deps on the host.

---

## Test pyramid conventions

| Layer | Location | Scope | Speed | Examples in this repo |
|---|---|---|---|---|
| **L0 unit** | `tests/unit/` | one function / class, no subprocess, no network | <1s | `test_hooks.py`, `test_keys_derivation.py` |
| **L1 component** | `tests/component/` | one subsystem end-to-end with fixtures / fakes | 1–5s | `test_extension_surface.py`, `test_plugin_validator.py`, `test_a0_client.py` (via `scripted_a2a_server`) |
| **L2 integration** | `tests/integration/` | real services (e.g. `livekit-server`) + synthetic participants | 10–60s | `test_synthetic_user.py` |
| **L3 browser (e2e)** | `tests/e2e/` | Playwright + TypeScript driving a live A0 UI | 3–30s | `specs/01-setup.spec.ts` (login + uninstall), `specs/02-install.spec.ts` (install from zip) |

Keep L0 fast — they run on every save. Use `pytestmark = pytest.mark.component` / `integration` at the top of files in higher layers so selective runs work (`pytest -m unit`). L3 is a separate Node toolchain — see below.

### L3 — Playwright e2e against a live A0

L0/L1/L2 cover plugin code. **L3 covers the UX** — the one slice the
Python pyramid can't reach because A0 renders the Plugins panel, the
install dialog, and per-plugin Config modals in the browser. Use L3
sparingly: it's the slowest layer and the only one that needs a running
A0 to pass. Anything expressible at L0–L2 should stay there.

**Stack** (bootstrapped first in `agent-zero-plugin-livekit`):

- **`@playwright/test`** (TypeScript). Native test runner — trace viewer,
  UI mode, auto-wait semantics, first-class Page Object ergonomics.
- **Not** `pytest-playwright`. Keeping the browser layer in TS avoids
  coupling the existing `pytest` pyramid to a Node install, and keeps
  Playwright's best tooling (codegen, `--ui`, trace) on its native path.

**Pre-requisite: the Playwright MCP tool is assumed available to the
agent** at authoring time. We use `@playwright/mcp` (configured in the
consumer repo's `.mcp.json`) so the agent can interactively drive a
browser while designing Page Objects — take accessibility snapshots,
discover selectors, verify flows. Consumers should wire it exactly like
any other project-scoped MCP server — see `manage-mcp/SKILL.md` for the
`make link-mcp` flow and auto-approval. The MCP is **not** a runtime
dependency of the tests themselves (those use plain `@playwright/test`);
it's a dev-time authoring affordance.

**Conventions** (live in `tests/e2e/` of the consumer repo):

| Thing | Convention |
|---|---|
| Layout | `pages/<Name>Page.ts` Page Objects · `specs/NN-<topic>.spec.ts` tests · `fixtures.ts` at root |
| Page Object | One class per A0 page. Expose **verbs** (`login(user, pass)`, `installFromZip(path, name)`), not locators. |
| Selectors | `getByRole("button", { name: "…", exact: true })` — survives re-styling A0. Avoid CSS/XPath. |
| Fixtures | `credentials` → `loggedInPage` → pre-opened page-object fixtures, composed in `fixtures.ts`. |
| Parallelism | `workers: 1` + `test.describe.configure({ mode: 'serial' })` whenever a spec mutates A0 runtime state (plugin install/uninstall, settings writes). Parallel = races. |
| Assertions | Assert on **end state** — card in Custom tab, heading visible — not on toasts (toasts are racy). |
| Config | `A0_BASE_URL`, `A0_USERNAME`, `A0_PASSWORD`, and plugin-specific `<NAME>_PLUGIN_ZIP` via env, with sensible dev defaults. |
| Dependencies | Playwright pinned in `tests/e2e/package.json`. Gitignore `node_modules/`, `test-results/`, `playwright-report/`, `blob-report/`, and `.playwright-mcp/`. |
| Run | `cd tests/e2e && npm install && npx playwright install chromium && npm test` |

### L3 — what the testkit ships vs what the plugin writes

The testkit's `e2e/` tree now provides the reusable harness; the plugin
writes only the plugin-specific specifics. Every A0 plugin repo wires
this in via three small hooks — no copy-paste scaffolding.

**Testkit provides** (in `tests/_testkit/e2e/`):

- `compose-base.yml` — A0 container on 50011/50012 + pip-cache mount +
  pre-boot `/a0/usr/.env` and `/a0/usr/settings.json` seed
- `scripts/e2e-up.sh` / `e2e-down.sh` — port probe, random token,
  healthcheck, writes `.e2e/instance.env`
- `Makefile.e2e` — includeable file with `e2e-up` / `e2e-down` /
  `e2e-fresh` / `e2e-test` / `e2e-servers` targets
- `pages/LoginPage.ts`, `pages/PluginsPage.ts` (install / uninstall /
  isInstalled), `pages/ChatPage.ts` (sidebar + new chat only — **no**
  plugin-specific UI)
- `fixtures/index.ts` — `createA0Fixtures()` factory returning a Playwright
  `test` with `credentials` / `loggedInPage` / `pluginsPage` / `chatPage`
- `global-setup.ts` + `playwright-base.config.ts` — pre-wired globalSetup
  + env loader + serial mode + trace-on-failure

**Plugin writes** (three hook files):

1. **`Makefile`** — declare extras, include the targets:

   ```make
   E2E_EXTRA_PORTS          := 50013:50013      # plugin-specific ports (media, SIP, etc.)
   E2E_COMPOSE_OVERRIDES    := docker/e2e.compose.override.yml    # if needed
   E2E_PLUGIN_SETTINGS_JSON := tests/e2e/plugin-settings.json     # {"plugin_<name>":{...}}
   E2E_INSTANCE_ENV_EXTRA   := A0_LK_RTC_TCP_PORT=50013           # vars for Playwright specs

   -include tests/_testkit/e2e/Makefile.e2e
   ```

2. **`tests/e2e/playwright.config.ts`** — spread base:

   ```ts
   import { defineConfig } from "@playwright/test";
   import { baseConfig } from "../_testkit/e2e/playwright-base.config";

   export default defineConfig({
     ...baseConfig(__dirname),
     testDir: "./specs",
   });
   ```

3. **`tests/e2e/fixtures.ts`** — compose plugin-specific fixtures:

   ```ts
   import { createA0Fixtures } from "../_testkit/e2e/fixtures";
   import { MyPluginConfigPage } from "./pages/MyPluginConfigPage";

   export const MY_PLUGIN_DISPLAY_NAME = "My Plugin";
   export const test = createA0Fixtures().extend<{
     installedMyPlugin: void;
     configPage: MyPluginConfigPage;
   }>({
     installedMyPlugin: async ({ pluginsPage }, use) => {
       if (!(await pluginsPage.isInstalled(MY_PLUGIN_DISPLAY_NAME))) {
         await pluginsPage.installFromZip(process.env.MY_PLUGIN_ZIP!, MY_PLUGIN_DISPLAY_NAME);
       }
       await pluginsPage.close();
       await use();
     },
     configPage: async ({ loggedInPage }, use) => {
       await use(new MyPluginConfigPage(loggedInPage));
     },
   });
   export { expect } from "@playwright/test";
   ```

Plugin-specific Page Objects (e.g. a Config modal, or a Talk-button
modal) live in the plugin's `tests/e2e/pages/`. Specs and `package.json`
are plugin-local.

See `tests/_testkit/e2e/README.md` for the full wiring reference,
including the parameter matrix, zero-config path, and operational notes
(pip-cache, same-port publishes for ICE, manual-URL override, etc.).

---

## Capabilities

### `a0_plugin_testkit.discovery` — canonical enumeration (scraped at runtime)

Three sets, all lazy (resolved on first access, cached):

| Constant | What | Scraped from |
|---|---|---|
| `KNOWN_HTML_SURFACES` | `<x-extension id="…">` IDs for HTML breakpoints | `<a0>/webui/**.html` |
| `KNOWN_JS_HOOKS` | names passed to `callJsExtensions("…", …)` | `<a0>/webui/**.js` |
| `KNOWN_PLUGIN_HOOKS` | plugin lifecycle hook names A0 dispatches to (`install`, `pre_update`, `uninstall`, `get_plugin_config`, `save_plugin_config`, `get_default_plugin_config`) | `<a0>/**.py` via `call_plugin_hook(plugin, "<name>", …)` |

```python
from a0_plugin_testkit.discovery import (
    KNOWN_HTML_SURFACES,
    KNOWN_JS_HOOKS,
    KNOWN_PLUGIN_HOOKS,
    find_a0_root,
)

assert "chat-input-bottom-actions-start" in KNOWN_HTML_SURFACES  # ✓
assert "chat_toolbar" in KNOWN_HTML_SURFACES                     # ✗
assert "initFw_end" in KNOWN_JS_HOOKS                            # ✓
assert "install" in KNOWN_PLUGIN_HOOKS                           # ✓
assert "on_plugin_enabled" in KNOWN_PLUGIN_HOOKS                 # ✗ — A0 never calls it
```

`find_a0_root(start=None) -> Path` locates A0 (env override / submodule / walk up).

### `a0_plugin_testkit.assertions` — testable contracts

Each assertion's failure message carries `difflib.get_close_matches` suggestions so typos surface as *"did you mean: chat-top-start?"* instead of *"not equal"*.

```python
from a0_plugin_testkit.assertions import (
    # Surfaces / hooks
    assert_valid_surface,                # str → valid HTML surface?
    assert_valid_js_hook,                # str → valid JS hook?
    assert_valid_plugin_hook,            # str → valid plugin lifecycle hook?
    assert_extension_at_surface,         # plugin contributes HTML at this surface
    assert_js_at_hook,                   # plugin contributes JS at this hook
    assert_no_stray_extension_folders,   # catches any typo under extensions/webui/
    assert_no_dead_plugin_hooks,         # hooks.py has no hook-shaped dead funcs
    # Thumbnail
    assert_plugin_has_thumbnail,         # webui/thumbnail.<ext>: exists, size, magic
    find_plugin_thumbnail,
)
```

Each captures a specific class of shipped bug in this repo — see commits `43f4122` (chat_toolbar), `81683aa` (on_plugin_enabled), `30b95b8` (blank thumbnail card).

### `a0_plugin_testkit.fakes` — A0 stand-ins for unit tests

```python
from a0_plugin_testkit.fakes import (
    FakeSettings,              # get_settings / set_settings_delta / writes list
    install_fake_a0_helpers,   # monkeypatches helpers.settings + helpers.print_style
    import_plugin_module,      # exec a plugin .py by path
)

@pytest.fixture
def hooks(monkeypatch):
    fake = install_fake_a0_helpers(monkeypatch)
    monkeypatch.setattr(
        # Prevent subprocess shell-outs (e.g. pip install) from hook code.
        __import__("subprocess"), "run", lambda *a, **kw: None,
    )
    module = import_plugin_module(str(HOOKS_PATH))
    return module, fake

def test_install_seeds_mcp_token(hooks):
    module, fake = hooks
    fake.update(a2a_server_enabled=True, mcp_server_token="")
    module.install()   # A0's real hook name — NOT on_plugin_enabled
    assert any(k == "mcp_server_token" for k, _ in fake.writes)
```

`FakeSettings` mirrors A0's real API (`get_settings`, `set_settings_delta`), not a fabricated one. Do not teach it `set_setting` — A0's module has no such function, and tests against a lying fake mask real bugs.

### `a0_plugin_testkit.real.fasta2a` — live FastA2A with a scripted worker

```python
from a0_plugin_testkit.real.fasta2a import scripted_a2a_server

async with scripted_a2a_server(
    scripts={"17 times 23": "391", "weather": "Sunny"},
    delays={"slow": 2.0},
    default="I don't know.",
) as (url, worker, app):
    resp = await my_plugin_client.send_message("what is 17 times 23?")
    assert resp.text == "391"
    assert worker.seen == ["what is 17 times 23?"]
```

A real uvicorn + real FastA2A + real HTTP, deterministic responses. Use when a plugin's A2A client needs to exercise the wire protocol. In-process, uses a shared event loop via a custom lifespan so anyio task groups compose cleanly.

### `a0_plugin_testkit.real.validator` — static plugin validator

A0's built-in `_plugin_validator` is LLM-driven (slow, needs a provider). For per-commit gating we want fast + deterministic:

```python
from a0_plugin_testkit.real.validator import static_validate, assert_validator_clean

report = static_validate(plugin_dir)   # DEFAULT_CHECKS: manifest, structure, extension_points, security
assert_validator_clean(report, allow_warnings=False)
```

Checks: required manifest fields + `^[a-z0-9_]+$` name / dir match / valid `settings_sections`; no stray `extensions/webui/<name>/`; hook-symmetry warnings; no committed secrets (OpenAI `sk-*`, Anthropic `sk-ant-*`, GitHub `gh*_*`, JWTs); no `__pycache__` in the tree.

### `a0_plugin_testkit.real.deps` — third-party import audit

```python
from a0_plugin_testkit.real.deps import audit_dependencies, assert_dependencies_declared

audit = audit_dependencies(plugin_dir)
assert_dependencies_declared(audit)
```

AST-walks every plugin `.py`, extracts top-level imports, normalises pip-name ↔ import-name (`livekit-api` → `livekit`, `PyYAML` → `yaml`, …), cross-references against (stdlib ∪ A0-internal ∪ `.agent-zero/requirements.txt` ∪ plugin's own `requirements.txt` / `REQUIRED_PACKAGES` in `hooks.py`). Anything else is flagged with `file:line`. Catches the "plugin installs, crashes on first HTTP hit with `ModuleNotFoundError`" class.

### `a0_plugin_testkit.real.a0_api` — plugin-uses-real-A0-API audit

```python
from a0_plugin_testkit.real.a0_api import audit_a0_api_usage, assert_a0_api_usage_ok

audit = audit_a0_api_usage(plugin_dir)
assert_a0_api_usage_ok(audit)
```

AST-walks the plugin, resolves local names bound to A0-internal modules (`from helpers import settings`, `import helpers.settings as s`, aliases, …), and for each `<local>.<attr>` access verifies `<attr>` exists as a public top-level in the real A0 module source. Correctly handles class-attribute access like `UiServerRuntime.build_asgi_app` (class name at module top-level + method lookup is not a fabricated-module-attr). Catches the "I called `helpers.settings.set_setting` but A0's real API is `set_settings_delta`" class of bug — the one that passes mypy but blows up at first use.

### `a0_plugin_testkit.real.public_urls` — container-URL leakage

```python
from a0_plugin_testkit.real.public_urls import (
    assert_no_naked_container_urls_in_public_response,
)

assert_no_naked_container_urls_in_public_response(plugin_dir)
```

AST-walks `<plugin_dir>/api/*.py`, finds every `ApiHandler.process` method and `build_*_response` helper, and flags container-local URLs leaking to the browser via two patterns:

1. **Passthrough** — a parameter whose name contains "url" is returned as a non-exempt dict key (`return {"url": livekit_url}`).
2. **Hardcoded literal** — a dict value string-contains `127.0.0.1`, `localhost`, `0.0.0.0`, or `host.docker.internal`.

Exempt keys (default: `internal_url`, `host`, `livekit_url`, `upstream_url`, `probe_url`, `hostname`, `livekit_rtc_tcp_port`) carry the in-container URL intentionally for diagnostics; override via the `exempt_keys=` kwarg. Catches the "containerised A0 hands the browser a 127.0.0.1 URL, browser fails with `Failed to fetch`" class.

### `a0_plugin_testkit.real.ports` — undeclared listening ports

```python
from a0_plugin_testkit.real.ports import assert_plugin_declares_required_ports

assert_plugin_declares_required_ports(plugin_dir)
```

AST-walks `<plugin_dir>/helpers/` and `<plugin_dir>/api/` for listening-port flags (`--rtc.tcp_port`, `--port`, `--listen`, `--bind-port`, `--rtc.port_range_start`) in subprocess command-list literals and string args. Cross-references every literal port number found against the plugin's declaration surface — in order:

1. `plugin.yaml` top-level `extra_ports:` list (preferred structured form).
2. `plugin.yaml` `description:` containing `-p <port>:<port>` docker examples.
3. `README.md` containing `-p <port>:<port>` examples.

Any port opened but undeclared fails with a message that prints the exact `extra_ports:` stanza to add. Catches "plugin runs an auxiliary service (TURN, local LLM, SFU, vector DB) whose port the user never knew to publish" — the follow-up class to the container-URL bug above.

Limit: literal ports only; dynamic expressions (`f"--rtc.port_range_start={port + 20}"`) are not caught. Document ports explicitly rather than computing them if you want the assertion to cover them.

---

## Reference flow: what to use when

| Need | Reach for |
|---|---|
| "Did I typo an extension-point name?" | `assert_no_stray_extension_folders(plugin_dir)` |
| "Is my button wired to a real HTML surface?" | `assert_extension_at_surface(plugin_dir, "<surface>", pattern="*.html")` |
| "Is my JS wired to a real hook?" | `assert_js_at_hook(plugin_dir, "<hook>", pattern="*.js")` |
| "Does my hooks.py define functions A0 never calls?" | `assert_no_dead_plugin_hooks(plugin_dir)` |
| "Will my plugin render a blank card in the Plugin List?" | `assert_plugin_has_thumbnail(plugin_dir)` |
| "Will my plugin crash at first HTTP hit with `ModuleNotFoundError`?" | `audit_dependencies(plugin_dir)` + `assert_dependencies_declared` |
| "Did I call an A0 function that doesn't exist?" | `audit_a0_api_usage(plugin_dir)` + `assert_a0_api_usage_ok` |
| "Will my plugin hand the browser a `127.0.0.1` URL that only A0 can reach?" | `assert_no_naked_container_urls_in_public_response(plugin_dir)` |
| "Did I open a listening port without declaring it in plugin.yaml / README?" | `assert_plugin_declares_required_ports(plugin_dir)` |
| "Is the whole plugin structurally valid for the Plugin Hub?" | `static_validate(plugin_dir)` + `assert_validator_clean` |
| "Unit test my hooks.py without importing A0?" | `install_fake_a0_helpers(monkeypatch)` + `import_plugin_module(...)` |
| "Component-test my A2A client against a real FastA2A?" | `scripted_a2a_server(scripts={…})` |
| "Browser-test an install/uninstall/config flow against a live A0?" | L3 — set up `tests/e2e/` with `@playwright/test` (see L3 section above). Pre-req: `@playwright/mcp` wired in consumer's `.mcp.json` for agent-assisted authoring. |

---

## Example — the minimal plugin test file

Drop this in a new repo at `tests/component/test_plugin_shape.py`. It runs in <1 s and catches five classes of regression between commits.

```python
from pathlib import Path
import pytest

from a0_plugin_testkit.assertions import (
    assert_no_stray_extension_folders,
    assert_no_dead_plugin_hooks,
    assert_plugin_has_thumbnail,
)
from a0_plugin_testkit.real.validator import static_validate, assert_validator_clean
from a0_plugin_testkit.real.deps import audit_dependencies, assert_dependencies_declared
from a0_plugin_testkit.real.a0_api import audit_a0_api_usage, assert_a0_api_usage_ok

pytestmark = pytest.mark.component


def test_no_typo_extension_points(plugin_dir: Path) -> None:
    assert_no_stray_extension_folders(plugin_dir)


def test_no_dead_hooks(plugin_dir: Path) -> None:
    assert_no_dead_plugin_hooks(plugin_dir)


def test_thumbnail(plugin_dir: Path) -> None:
    assert_plugin_has_thumbnail(plugin_dir)


def test_static_validator(plugin_dir: Path) -> None:
    assert_validator_clean(static_validate(plugin_dir), allow_warnings=False)


def test_dependencies_declared(plugin_dir: Path) -> None:
    assert_dependencies_declared(audit_dependencies(plugin_dir))


def test_a0_api_usage_valid(plugin_dir: Path) -> None:
    assert_a0_api_usage_ok(audit_a0_api_usage(plugin_dir))
```

When any of these fails the message points at the exact line + file + suggestion. This is the baseline you'd run in CI before anything else — it's the "plugin can at least load and dispatch properly" smoke check.

---

## Methodology — red-first, reproduce-before-you-fix

Every testkit assertion in this repo was written against a **real shipped bug**. The discipline:

1. **When you hit a bug**: write a *failing* test that encodes the contract. Don't fix anything yet.
2. **Verify red**: run the test, see it fail with a clear message (not just "AssertionError: None != True"). If the message is cryptic, improve it first.
3. **Revert / time-travel check**: if the test passes against current code, revert the relevant files (`git checkout HEAD~1 -- <files>`) to confirm it would have caught the pre-fix state. This is the only honest way to know the test has teeth.
4. **Fix**: implement the minimum change to turn the test green.
5. **Commit message**: paste the red output — future-you will appreciate seeing the contract that drives the assertion.

Rule of thumb: **if you write a fix before you write the test that would have caught the bug, you haven't closed the class, only this instance.**

---

## Hard rules

1. **Never hard-code extension-point / hook / API name lists in tests.** Always use the `KNOWN_*` sets or the assertions. They scrape live A0 source, so upgrading the `.agent-zero` submodule automatically adjusts the canonical list. Hard-coded lists drift silently.
2. **Never teach a fake an API A0 doesn't have.** `FakeSettings` matches A0's real method names (`set_settings_delta`, not `set_setting`). A fake with a wider surface than the real thing masks production bugs.
3. **Never require PyPI installs.** Everything must work from in-repo vendoring or a git submodule checkout.
4. **Keep the `a0_plugin_testkit` package name stable.** That's the public API once extracted. Rearranging submodules is fine; renaming the top-level package is a breaking change for every consumer.
5. **Don't duplicate A0 logic that A0 already exposes as a callable.** Where A0 has a programmatic entrypoint (e.g. `LoadWebuiExtensions.process`), prefer wrapping it over reimplementing. Static checks are the exception — `static_validate` deliberately re-encodes A0's `_plugin_validator` rule catalogue to stay fast + deterministic without needing an LLM.

---

## Extending the testkit — when to lift vs keep local

**The testkit is not a black box.** Treat it as a living, shared codebase you're expected to evolve. Every assertion here started as ad-hoc test logic in *some* plugin repo that turned out to generalise; that's the pattern. If you find yourself writing a test whose shape matches another plugin's, you're looking at a testkit contribution.

Lift a helper when it meets **all** of:

- It doesn't reference plugin-domain symbols (no `livekit_*`, no `compact_*`, etc.).
- A second plugin has already hit the same need (or clearly will — YAGNI applied to the testkit itself, but don't be a miser).
- The API is simple enough to stabilise — no heavy configuration surface.

Stays plugin-local when:

- It's a domain check ("LK server downloader caches the binary"), even if the pattern is generic.
- It's a shape test on your plugin's own HTML / JS files.
- It's a business-logic unit test.

If in doubt, keep it plugin-local — refactoring later is cheap; extracting then re-extracting is not.

---

## Contributing back — the spontaneous-contribution workflow

A submodule-based distribution has a nice property: **you contribute to the testkit from inside your consumer plugin repo, without cloning the testkit separately.** Edit the files in `tests/_testkit/`, commit, PR, merge, bump the submodule pointer — the testkit evolves at the pace plugin authors discover things.

### Before you start

- **Red-first.** The new helper/assertion must come with a test that would fail against the current code. If the pattern doesn't have at least one concrete bug (in your plugin or another) it would catch, it's not ready. Paste the red output in the PR description.
- **Keep the `a0_plugin_testkit` public API stable.** New modules and new functions are fine. Renaming existing ones is a breaking change for every consumer repo — avoid unless you're doing a major version bump and sending PRs to the consumers too.
- **Update the skill + README in the same PR.** If you add an assertion, `skill/SKILL.md` needs a row in the reference-flow table and a bullet under Capabilities. `README.md`'s "What's in the box" needs the new name. A helper that ships without discoverability documentation effectively doesn't exist.

### Step-by-step: edit, PR, merge, bump

```bash
# ── 1. Enter the submodule. It's in detached-HEAD state by default —
#     create a branch BEFORE editing or your commits will be orphaned.
cd tests/_testkit
git checkout -b feature/new-helper-name

# ── 2. Edit the testkit in place. Normal editor flow.
$EDITOR src/a0_plugin_testkit/assertions.py
$EDITOR tests/test_smoke.py          # add a self-test
$EDITOR skill/SKILL.md               # update reference-flow + capabilities
$EDITOR README.md                    # update "What's in the box"

# ── 3. Validate the testkit in isolation (the .agent-zero dev submodule
#     pinned in the testkit repo is what self-tests run against).
pytest                               # must stay green

# ── 4. Validate the consumer repo still passes against your WIP testkit.
#     (Consumer's pyproject.toml resolves into tests/_testkit/src/, so
#     your unpushed changes are already live locally.)
cd ../..
make docker-test                     # or the consumer's equivalent

# ── 5. Commit + push the testkit branch.
cd tests/_testkit
git commit -am "feat(assertions): new helper for <case>"
git push origin feature/new-helper-name
#   (If you don't have write access to agent-zero-operator/agent-zero-
#    plugin-development-testkit, `gh repo fork` first and push to your
#    fork's remote instead.)

# ── 6. Open the PR against the testkit repo.
gh pr create \
  --repo agent-zero-operator/agent-zero-plugin-development-testkit \
  --title "feat(assertions): new helper for <case>" \
  --body "..."                       # include the red-first evidence
```

### While the PR is in review

Your consumer repo is pinned to an **unpushed** submodule commit on a non-origin branch. That's fine locally — `pytest` and `make docker-test` both work against your WIP testkit because they read the files on disk. CI will be unhappy because it only sees the pinned main-branch commit; plan to land the bump below at the same time as any consumer work that depends on the new helper.

### After the PR merges

```bash
# ── 7. Point the consumer's submodule at main's new tip.
cd tests/_testkit
git fetch origin
git checkout origin/main             # detached again, at new tip
cd ../..

# ── 8. Verify the full suite still passes against the merged code.
make docker-test

# ── 9. Commit the pointer bump in the CONSUMER repo.
git add tests/_testkit
git commit -m "chore(testkit): bump submodule to <short-sha> (<what-landed>)"
```

The pointer bump and any consumer-side code that depends on the new helper travel in the same branch/PR on the consumer side. That way nothing lands in a state where the consumer imports a helper that doesn't exist yet at the pinned testkit commit.

### Gotchas, numbered so you don't forget

1. **Detached HEAD inside the submodule.** The submodule clones at a pinned commit with no branch checked out. `git checkout -b <name>` before editing — otherwise `git commit` creates a dangling commit you'll lose on the next `git submodule update`.
2. **Don't forget to push the submodule branch.** `git status` in the consumer shows the submodule pointer changed, but the testkit branch itself lives in your local `.git/modules/tests/_testkit/` until you push.
3. **Keep the skill + README in sync with the code.** The biggest single value of the testkit is that authors *discover* what's available without reading the source. A new helper without a Capabilities entry and a reference-flow row is a helper that only its author knows about.
4. **Consumer repos should never fork the package name.** If you need a radically different shape, contribute a submodule under `a0_plugin_testkit.<new_subpackage>` (like `real.*`) rather than repackaging.
5. **Preserve the "red-first" evidence.** The PR description should include the exact failing output the new assertion produces against the pre-fix state. Every current assertion has this in its original commit message — match the standard.

### What belongs in the testkit repo vs in this skill

- Testkit repo `tests/test_smoke.py` — behavioural self-tests of the helpers (fast, deterministic, <1s).
- This skill — narrative + usage patterns + contribution workflow. If you add a capability, update BOTH.

---

## Roadmap (ordered)

1. ✅ `discovery` — HTML surfaces, JS hooks, plugin hooks.
2. ✅ `assertions` — surface / hook / thumbnail / dead-hook / stray-folder / positive-negative sanity.
3. ✅ `fakes` — `FakeSettings` + `install_fake_a0_helpers` + `import_plugin_module`.
4. ✅ `real.fasta2a` — scripted FastA2A server.
5. ✅ `real.validator` — static checks (manifest / structure / extension points / security).
6. ✅ `real.deps` — third-party import audit.
7. ✅ `real.a0_api` — plugin-uses-real-A0-API audit.
8. `real.llm` — OpenAI-compatible fake LLM sidecar, unlocking real full-loop integration tests.
9. Direct `handler.process({}, request=None)` helper — fake Flask + Lock fixture.
10. Compose-driven "A0-with-plugin-installed" harness.
11. `playwright.A0Page` page-object for browser coverage.
12. LLM-based `_plugin_validator` wrapper (uses `real.llm`).
13. Reusable GitHub Actions workflows.
14. **Extract to `agent-zero-plugin-testkit` repo** when plugin #2 adopts the testkit.

---

## Related skills

- [`a0-create-plugin`](../../../.claude/skills/a0-create-plugin/SKILL.md) — runtime conventions (Store Gating, AgentContext, settings UI). Read-only (vendored).
- [`a0-plugin-architecture`](../../../.claude/skills/a0-plugin-architecture/SKILL.md) — exhaustive reference for plugin internals.
- [`a0-debug-plugin`](../../../.claude/skills/a0-debug-plugin/SKILL.md) — diagnose a misbehaving plugin at runtime.
- [`a0-bootstrap-plugin`](../../../.claude/skills/a0-bootstrap-plugin/SKILL.md) — scaffolding a fresh plugin repo.
- [`livekit-plugin-dev`](../../../.claude/skills/livekit-plugin-dev/SKILL.md) — this repo's plugin-specific guidance.

The testkit **complements** those — it fills the testing-patterns gap that none of them cover today, and it is the only skill that will land in *every* plugin repo by submodule.
