---
name: a0-plugin-testkit
description: "Shared test scaffolding for Agent Zero plugin repos. Scrapes A0's source at runtime for canonical extension-point IDs, JS hooks, plugin lifecycle hooks, and module attribute names — exposes them as fast pytest assertions. Ships A0 fakes, a live FastA2A fixture, a static validator, a dependency audit, and an A0-API audit. Load whenever building, extending, or debugging tests in any plugin repo that vendors or submodules this testkit."
version: "0.2.0"
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

Keep L0 fast — they run on every save. Use `pytestmark = pytest.mark.component` / `integration` at the top of files in higher layers so selective runs work (`pytest -m unit`).

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

AST-walks the plugin, resolves local names bound to A0-internal modules (`from helpers import settings`, `import helpers.settings as s`, aliases, …), and for each `<local>.<attr>` access verifies `<attr>` exists as a public top-level in the real A0 module source. Catches the "I called `helpers.settings.set_setting` but A0's real API is `set_settings_delta`" class of bug — the one that passes mypy but blows up at first use.

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
| "Is the whole plugin structurally valid for the Plugin Hub?" | `static_validate(plugin_dir)` + `assert_validator_clean` |
| "Unit test my hooks.py without importing A0?" | `install_fake_a0_helpers(monkeypatch)` + `import_plugin_module(...)` |
| "Component-test my A2A client against a real FastA2A?" | `scripted_a2a_server(scripts={…})` |

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

Not every helper belongs in the testkit. Lift a helper when it meets **all** of:

- It doesn't reference plugin-domain symbols (no `livekit_*`, no `compact_*`, etc.).
- A second plugin has already hit the same need (YAGNI applied to the testkit itself).
- The API is simple enough to stabilise — no heavy configuration surface.

Stays plugin-local when:

- It's a domain check ("LK server downloader caches the binary"), even if the pattern is generic.
- It's a shape test on your plugin's own HTML / JS files.
- It's a business-logic unit test.

If in doubt, keep it plugin-local — refactoring later is cheap; extracting then re-extracting is not.

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
