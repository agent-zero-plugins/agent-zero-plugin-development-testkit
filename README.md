# agent-zero-plugin-development-testkit

Shared pytest scaffolding for Agent Zero plugin repos. Scrapes A0's own
source at runtime for the canonical names a plugin can legally hook
into — `<x-extension id>` surfaces, `callJsExtensions` hook names,
`call_plugin_hook` lifecycle names, module attribute surfaces — and
exposes them as fast pytest assertions so the "plugin installs but does
nothing" / "plugin crashes on first HTTP hit" / "I called an A0 function
that doesn't exist" class of bug fails at PR time, not after deploy.

First adopter (and origin of every assertion here): **[agent-zero-plugin-livekit](https://github.com/agent-zero-operator/agent-zero-plugin-livekit)**.

## What's in the box

- **`discovery`** — `KNOWN_HTML_SURFACES`, `KNOWN_JS_HOOKS`, `KNOWN_PLUGIN_HOOKS`, `find_a0_root()`.
- **`assertions`** — `assert_extension_at_surface`, `assert_js_at_hook`, `assert_no_stray_extension_folders`, `assert_no_dead_plugin_hooks`, `assert_plugin_has_thumbnail`, plus the positive/negative `assert_valid_*` primitives. Every failure message includes a `difflib` suggestion so typos surface as *"did you mean…?"*.
- **`fakes`** — `FakeSettings`, `install_fake_a0_helpers`, `import_plugin_module`. Mirrors A0's real `helpers.settings` API (no fabricated `set_setting`) so unit tests can't pass against a lying fake.
- **`real.fasta2a`** — `scripted_a2a_server(scripts, delays, default)` context manager yielding a live in-process FastA2A with a deterministic scripted worker. Real uvicorn, real HTTP, canned responses.
- **`real.validator`** — `static_validate(plugin_dir)` → fast + deterministic manifest / structure / extension-point / security (committed-secret scan) checks. Pairs with `assert_validator_clean(report)`.
- **`real.deps`** — `audit_dependencies(plugin_dir)` → AST-walks every plugin `.py`, cross-references third-party imports against A0's `requirements.txt` + the plugin's own declared deps, flags undeclared with `file:line`.
- **`real.a0_api`** — `audit_a0_api_usage(plugin_dir)` → verifies every `helpers.settings.foo`-style attribute access in the plugin resolves to a real public name in A0's module source. Catches fabricated-API bugs that pass type checkers.

## How to use it in a consumer plugin repo

1. **Add as a submodule** (we don't publish to PyPI — versioning is commit-pin):
   ```bash
   git submodule add https://github.com/agent-zero-operator/agent-zero-plugin-development-testkit .testkit
   ```

2. **Put it on `pythonpath`** in your `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   pythonpath = [".", ".testkit/src"]
   ```

3. **Declare the `plugin_dir` fixture** once in `tests/conftest.py`:
   ```python
   from pathlib import Path
   import pytest

   @pytest.fixture(scope="session")
   def plugin_dir() -> Path:
       return Path(__file__).resolve().parent.parent / "usr" / "plugins" / "<your_plugin>"
   ```

4. **Drop in a baseline test file** (5 assertions, ~1 second):
   ```python
   # tests/component/test_plugin_shape.py
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

   def test_no_stray_folders(plugin_dir: Path) -> None:
       assert_no_stray_extension_folders(plugin_dir)

   def test_no_dead_hooks(plugin_dir: Path) -> None:
       assert_no_dead_plugin_hooks(plugin_dir)

   def test_thumbnail(plugin_dir: Path) -> None:
       assert_plugin_has_thumbnail(plugin_dir)

   def test_validator(plugin_dir: Path) -> None:
       assert_validator_clean(static_validate(plugin_dir), allow_warnings=False)

   def test_deps_declared(plugin_dir: Path) -> None:
       assert_dependencies_declared(audit_dependencies(plugin_dir))

   def test_a0_api_usage_valid(plugin_dir: Path) -> None:
       assert_a0_api_usage_ok(audit_a0_api_usage(plugin_dir))
   ```

For the full narrative — methodology, extension guidelines, hard rules,
and the bug-story behind each assertion — read [`skill/SKILL.md`](skill/SKILL.md).
Plugin repos typically symlink it into their `.claude/skills/`, `.github/skills/`,
and `.antigravity/skills/` so Claude Code / Copilot / Antigravity pick it up.

## A0 reachability

Most assertions read from A0's source at import time. They look for A0 in:

1. `$A0_ROOT` environment variable.
2. `<repo>/.agent-zero/` submodule (the standard layout in agent-zero-operator plugin repos).
3. Walking up from the testkit's own location.

If none resolve, assertions raise with an actionable message.

## Design principles

- **Scrape, don't hard-code.** Every list of names (extension points, hooks, API attrs) is derived from the live A0 source the testkit is loaded against. Upgrading A0 automatically adjusts the canonical list.
- **Never teach a fake an API the real thing doesn't have.** `FakeSettings` mirrors A0's real surface (`set_settings_delta`, not `set_setting`). A fake with a wider surface than reality masks production bugs.
- **No PyPI.** Submodule distribution matches how the `agent-zero-operator-skills` library is distributed. Versioning is commit-pin.
- **No heavy runtime deps.** The testkit itself is pure Python + pytest. Individual helpers (like `scripted_a2a_server`) pull in their own extras (`fasta2a`, `uvicorn`, `httpx`) only if the consumer imports them.
- **Red-first.** Every assertion was written against a real shipped bug from the first adopter, with the pre-fix state verified by time-travelling the repo. See the skill for the methodology.

## Extracted from

[`agent-zero-plugin-livekit`](https://github.com/agent-zero-operator/agent-zero-plugin-livekit) — during that plugin's bring-up, eight classes of bug surfaced (invalid extension-point name, undeclared third-party import, dead lifecycle hook, fabricated A0 API call, blank thumbnail, missing preflight, silent subprocess death, unmanaged credential defaults). Each became an assertion here.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
