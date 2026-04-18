"""Canonical enumeration of A0 extension points, scraped from source.

Two namespaces, often confused:

1. **HTML surfaces** — DOM breakpoints declared as ``<x-extension id="...">``
   in A0's webui. A plugin puts an ``.html`` file under
   ``extensions/webui/<surface>/`` and the framework inserts it at that
   breakpoint. Example surfaces:
     - ``chat-input-bottom-actions-start``
     - ``sidebar-quick-actions-main-start``
     - ``welcome-actions-end``

2. **JS hooks** — lifecycle event names passed to ``callJsExtensions(name, ...)``
   from core webui JS. A plugin puts a ``.js`` / ``.mjs`` file under
   ``extensions/webui/<hook>/`` exporting a ``default async function`` which
   is dynamically imported and invoked. Example hooks:
     - ``initFw_start``, ``initFw_end``
     - ``json_api_call_before``, ``json_api_call_after``, ``json_api_call_error``
     - ``get_message_handler``, ``get_tool_message_handler``
     - ``set_messages_before_loop``, ``set_messages_after_loop``

The two namespaces share the ``extensions/webui/<name>/`` folder layout, but
the valid ``<name>`` values are **disjoint**. Putting an ``.html`` file under
a JS hook folder does nothing; putting a ``.js`` file under an HTML-surface
folder does nothing.

This module scrapes the canonical lists from the A0 source at runtime (rather
than hard-coding them) so they stay in sync with whichever A0 commit the
testkit is loaded against.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# --------------------------------------------------------------------------- #
# Locating A0.
# --------------------------------------------------------------------------- #

_A0_ENV_OVERRIDE = "A0_ROOT"
_DEFAULT_SUBMODULE_NAME = ".agent-zero"


def find_a0_root(start: Path | str | None = None) -> Path:
    """Locate the A0 source root.

    Preference order:
      1. ``$A0_ROOT`` environment variable (if set and points at a dir with
         ``agent.py``).
      2. Walk up from ``start`` (if given) looking for a directory named
         ``.agent-zero`` containing ``agent.py``.
      3. Walk up from this file's location. Works in the normal case where
         the testkit lives in the plugin repo alongside ``.agent-zero``.

    Raises ``FileNotFoundError`` if A0 can't be located.
    """
    import os

    env_override = os.environ.get(_A0_ENV_OVERRIDE, "").strip()
    if env_override:
        candidate = Path(env_override).resolve()
        if (candidate / "agent.py").is_file():
            return candidate

    search_starts: list[Path] = []
    if start is not None:
        search_starts.append(Path(start).resolve())
    # Always also try walking up from this file — the testkit lives in the
    # plugin repo, so its own __file__ is a reliable fallback when `start`
    # is a tmp dir or anywhere else without a sibling .agent-zero.
    search_starts.append(Path(__file__).resolve())

    for origin in search_starts:
        for parent in (origin, *origin.parents):
            candidate = parent / _DEFAULT_SUBMODULE_NAME
            if (candidate / "agent.py").is_file():
                return candidate

    raise FileNotFoundError(
        f"Could not locate A0 source root. Set {_A0_ENV_OVERRIDE}=/path/to/agent-zero "
        f"or ensure a `{_DEFAULT_SUBMODULE_NAME}/` submodule sits at the repo root."
    )


# --------------------------------------------------------------------------- #
# HTML surface scraping.
# --------------------------------------------------------------------------- #

_X_EXTENSION_RE = re.compile(r'<x-extension\s+id="([^"]+)"', re.IGNORECASE)


@lru_cache(maxsize=4)
def discover_html_surfaces(a0_root: Path | None = None) -> frozenset[str]:
    """Return the set of ``<x-extension id="...">`` IDs found in A0's webui.

    Scans every ``.html`` file under ``<a0_root>/webui/``. Results are cached
    per ``a0_root`` so repeated calls in the same test session are cheap.
    """
    root = a0_root or find_a0_root()
    webui = root / "webui"
    if not webui.is_dir():
        return frozenset()

    found: set[str] = set()
    for html in webui.rglob("*.html"):
        try:
            text = html.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _X_EXTENSION_RE.finditer(text):
            found.add(match.group(1))
    return frozenset(found)


# --------------------------------------------------------------------------- #
# JS hook scraping.
# --------------------------------------------------------------------------- #

# Matches `callJsExtensions("hook_name", …)` and
# `extensions.callJsExtensions("hook_name", …)`. The hook name must be a
# bare identifier (no template interpolation).
_JS_HOOK_RE = re.compile(
    r'callJsExtensions\(\s*[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]', re.MULTILINE
)


@lru_cache(maxsize=4)
def discover_js_hooks(a0_root: Path | None = None) -> frozenset[str]:
    """Return the set of JS hook names passed to ``callJsExtensions()``."""
    root = a0_root or find_a0_root()
    webui = root / "webui"
    if not webui.is_dir():
        return frozenset()

    found: set[str] = set()
    for js in webui.rglob("*.js"):
        try:
            text = js.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _JS_HOOK_RE.finditer(text):
            found.add(match.group(1))
    return frozenset(found)


# --------------------------------------------------------------------------- #
# Plugin-lifecycle hook scraping.
# --------------------------------------------------------------------------- #

# Python-side hooks are invoked from A0 via helpers.plugins.call_plugin_hook().
# We scrape every `call_plugin_hook(<plugin>, "<hook_name>", ...)` call from
# A0's source to learn the canonical set. This is the ONLY reliable truth —
# several skills and docs historically mentioned hook names (e.g.
# ``on_plugin_enabled``) that A0 doesn't actually call.
_PLUGIN_HOOK_RE = re.compile(
    r'call_plugin_hook\([^,)]+,\s*[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]'
)

_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


@lru_cache(maxsize=4)
def discover_plugin_hooks(a0_root: Path | None = None) -> frozenset[str]:
    """Return the canonical plugin-lifecycle hook names A0 dispatches to.

    Found by grepping every ``call_plugin_hook(<plugin>, "<name>", ...)`` in
    A0's Python source (excluding `.git`, `node_modules`, etc.). As of A0
    current, this includes ``install``, ``pre_update``, ``uninstall``, and
    the config-transform trio ``get_plugin_config`` / ``save_plugin_config``
    / ``get_default_plugin_config``.
    """
    root = a0_root or find_a0_root()
    if not root.is_dir():
        return frozenset()

    found: set[str] = set()
    for py in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in py.parts):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _PLUGIN_HOOK_RE.finditer(text):
            found.add(m.group(1))
    return frozenset(found)


# --------------------------------------------------------------------------- #
# Module-level eager-but-lazy constants.
# --------------------------------------------------------------------------- #
# Users can do `from a0_plugin_testkit.discovery import KNOWN_HTML_SURFACES`
# and pay the scrape cost once, the first time either constant is touched.
# Implemented as a lazy proxy so module import stays cheap (no scraping until
# first use, and no hard failure if A0 can't be found until you actually
# depend on it).


class _LazySet:
    """Set-like object that defers one-time scraping until first use."""

    __slots__ = ("_loader", "_cached")

    def __init__(self, loader):  # loader: Callable[[], frozenset[str]]
        self._loader = loader
        self._cached: frozenset[str] | None = None

    def _resolve(self) -> frozenset[str]:
        if self._cached is None:
            self._cached = self._loader()
        return self._cached

    def __contains__(self, item: object) -> bool:
        return item in self._resolve()

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())

    def __repr__(self) -> str:
        if self._cached is None:
            return "<LazySet (unresolved)>"
        return f"<LazySet size={len(self._cached)}>"

    def resolve(self) -> frozenset[str]:
        """Force resolution and return the underlying frozenset."""
        return self._resolve()


KNOWN_HTML_SURFACES = _LazySet(discover_html_surfaces)
KNOWN_JS_HOOKS = _LazySet(discover_js_hooks)
KNOWN_PLUGIN_HOOKS = _LazySet(discover_plugin_hooks)


__all__ = (
    "find_a0_root",
    "discover_html_surfaces",
    "discover_js_hooks",
    "discover_plugin_hooks",
    "KNOWN_HTML_SURFACES",
    "KNOWN_JS_HOOKS",
    "KNOWN_PLUGIN_HOOKS",
)
