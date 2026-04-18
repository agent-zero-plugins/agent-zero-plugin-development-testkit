"""Assertions used across plugin-repo tests.

Design: *one helpful failure message per assertion*. Tests should read like
prose; failures should read like diagnosis.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import ast
import re

from .discovery import (
    KNOWN_HTML_SURFACES,
    KNOWN_JS_HOOKS,
    KNOWN_PLUGIN_HOOKS,
    discover_html_surfaces,
    discover_js_hooks,
    discover_plugin_hooks,
)


# Thumbnail conventions, discovered from A0's helpers/plugins.py:269.
# Discovery order (A0 uses the first match): png, jpg, jpeg, gif, webp.
PLUGIN_THUMBNAIL_EXTS: tuple[str, ...] = ("png", "jpg", "jpeg", "gif", "webp")
# Plugin Index guidance (docs/developer/plugins.md): thumbnails should be
# reasonably small. A0 serves them at /plugins/<name>/webui/thumbnail.<ext>.
DEFAULT_THUMBNAIL_MAX_BYTES = 50 * 1024  # 50 KB — generous for local plugins


# --------------------------------------------------------------------------- #
# Extension surface assertions.
# --------------------------------------------------------------------------- #


def assert_valid_surface(surface: str, *, a0_root: Path | None = None) -> None:
    """Fail with a helpful message if ``surface`` is not a real A0 HTML surface."""
    valid = discover_html_surfaces(a0_root) if a0_root else KNOWN_HTML_SURFACES.resolve()
    if surface in valid:
        return
    suggestions = difflib.get_close_matches(surface, list(valid), n=3, cutoff=0.6)
    hint = f"  did you mean: {', '.join(suggestions)}?\n" if suggestions else ""
    raise AssertionError(
        f"unknown HTML extension surface: {surface!r}\n"
        f"{hint}"
        f"  A0 declares its valid surfaces via <x-extension id=\"...\"> in webui/. "
        f"Known surfaces ({len(valid)}): {sorted(valid)}"
    )


def assert_valid_js_hook(hook: str, *, a0_root: Path | None = None) -> None:
    """Fail with a helpful message if ``hook`` is not a real A0 JS hook name."""
    valid = discover_js_hooks(a0_root) if a0_root else KNOWN_JS_HOOKS.resolve()
    if hook in valid:
        return
    suggestions = difflib.get_close_matches(hook, list(valid), n=3, cutoff=0.6)
    hint = f"  did you mean: {', '.join(suggestions)}?\n" if suggestions else ""
    raise AssertionError(
        f"unknown JS hook: {hook!r}\n"
        f"{hint}"
        f"  A0 dispatches JS hooks via callJsExtensions(name, ...) in webui/js/. "
        f"Known hooks ({len(valid)}): {sorted(valid)}"
    )


def assert_extension_at_surface(
    plugin_dir: Path,
    surface: str,
    *,
    pattern: str = "*",
    a0_root: Path | None = None,
) -> Path:
    """Assert the plugin contributes at least one file at the given surface.

    - Validates ``surface`` against A0's known list (catches typos like
      ``chat_toolbar`` instead of ``chat-input-bottom-actions-start``).
    - Asserts at least one file matching ``pattern`` exists under
      ``<plugin_dir>/extensions/webui/<surface>/``.

    Returns the first matching file path (useful for follow-up content asserts).
    """
    assert_valid_surface(surface, a0_root=a0_root)

    folder = plugin_dir / "extensions" / "webui" / surface
    if not folder.is_dir():
        raise AssertionError(
            f"plugin has no contribution at HTML surface {surface!r}\n"
            f"  expected dir: {folder}\n"
            f"  (plugin_dir={plugin_dir})"
        )
    matches = sorted(folder.glob(pattern))
    if not matches:
        raise AssertionError(
            f"plugin dir {folder} exists but contains no files matching {pattern!r}"
        )
    return matches[0]


def assert_js_at_hook(
    plugin_dir: Path,
    hook: str,
    *,
    pattern: str = "*.js",
    a0_root: Path | None = None,
) -> Path:
    """Like ``assert_extension_at_surface`` but for JS hooks."""
    assert_valid_js_hook(hook, a0_root=a0_root)

    folder = plugin_dir / "extensions" / "webui" / hook
    if not folder.is_dir():
        raise AssertionError(
            f"plugin has no JS contribution at hook {hook!r}\n"
            f"  expected dir: {folder}\n"
            f"  (plugin_dir={plugin_dir})"
        )
    matches = sorted(folder.glob(pattern))
    if not matches:
        raise AssertionError(
            f"plugin dir {folder} exists but contains no files matching {pattern!r}"
        )
    return matches[0]


def assert_no_stray_extension_folders(
    plugin_dir: Path, *, a0_root: Path | None = None
) -> None:
    """Fail if any ``extensions/webui/<name>/`` folder uses a fabricated name.

    This is the assertion that would have caught the ``chat_toolbar`` bug at
    test time. Walks the plugin's webui-extension tree and complains about any
    subfolder whose name is neither a known HTML surface nor a known JS hook.
    """
    webui_ext = plugin_dir / "extensions" / "webui"
    if not webui_ext.is_dir():
        return  # no webui extensions — trivially fine

    html_surfaces = (
        discover_html_surfaces(a0_root) if a0_root else KNOWN_HTML_SURFACES.resolve()
    )
    js_hooks = discover_js_hooks(a0_root) if a0_root else KNOWN_JS_HOOKS.resolve()
    valid = html_surfaces | js_hooks

    strays: list[tuple[str, list[str]]] = []
    for child in sorted(webui_ext.iterdir()):
        if not child.is_dir():
            continue
        if child.name in valid:
            continue
        suggestions = difflib.get_close_matches(child.name, list(valid), n=3, cutoff=0.6)
        strays.append((child.name, suggestions))

    if strays:
        lines = ["plugin contributes to unknown extension points:"]
        for name, suggestions in strays:
            hint = f" (did you mean: {', '.join(suggestions)}?)" if suggestions else ""
            lines.append(f"  - extensions/webui/{name}/{hint}")
        lines.append(
            f"  Valid extension-point names are scraped from A0's webui at runtime; "
            f"{len(html_surfaces)} HTML surfaces and {len(js_hooks)} JS hooks are currently known."
        )
        raise AssertionError("\n".join(lines))


# --------------------------------------------------------------------------- #
# Thumbnail assertions.
# --------------------------------------------------------------------------- #


# Minimum bytes for each format's magic number lookup.
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPG_SIG = b"\xff\xd8\xff"
_GIF_SIGS = (b"GIF87a", b"GIF89a")
_WEBP_SIG = b"RIFF"  # full check also looks for "WEBP" at offset 8


def _looks_like(ext: str, head: bytes) -> bool:
    ext = ext.lower()
    if ext == "png":
        return head.startswith(_PNG_SIG)
    if ext in ("jpg", "jpeg"):
        return head.startswith(_JPG_SIG)
    if ext == "gif":
        return head.startswith(_GIF_SIGS)
    if ext == "webp":
        return head.startswith(_WEBP_SIG) and head[8:12] == b"WEBP"
    return False


def find_plugin_thumbnail(plugin_dir: Path) -> Path | None:
    """Return the path to the plugin's thumbnail, or None if none exists."""
    webui = plugin_dir / "webui"
    for ext in PLUGIN_THUMBNAIL_EXTS:
        candidate = webui / f"thumbnail.{ext}"
        if candidate.is_file():
            return candidate
    return None


def assert_plugin_has_thumbnail(
    plugin_dir: Path,
    *,
    max_bytes: int = DEFAULT_THUMBNAIL_MAX_BYTES,
) -> Path:
    """Assert the plugin ships a valid thumbnail image A0 will surface in its UI.

    Rules (matching A0's behaviour in `helpers/plugins.py:269-274`):

      * File lives at ``<plugin>/webui/thumbnail.<ext>`` for some ext in
        ``PLUGIN_THUMBNAIL_EXTS``.
      * Non-empty and actually the claimed format (magic bytes match).
      * Size <= ``max_bytes`` — default 50 KB, relaxed vs. the Plugin Index's
        20 KB guidance because local plugins can be a bit bigger without
        breaking anything.

    Returns the path of the discovered thumbnail.
    """
    thumb = find_plugin_thumbnail(plugin_dir)
    if thumb is None:
        webui = plugin_dir / "webui"
        candidates = ", ".join(f"thumbnail.{e}" for e in PLUGIN_THUMBNAIL_EXTS)
        raise AssertionError(
            f"plugin has no thumbnail image\n"
            f"  expected one of: {candidates}\n"
            f"  under: {webui}\n"
            f"  A0 renders plugins with a thumbnail as cards in the Plugin List; "
            f"plugins without one render as a blank tile."
        )

    size = thumb.stat().st_size
    if size == 0:
        raise AssertionError(f"thumbnail {thumb} exists but is empty")
    if size > max_bytes:
        raise AssertionError(
            f"thumbnail {thumb} is {size} bytes > max_bytes={max_bytes}\n"
            f"  Community Plugin Index guidance is ≤ 20 KB; A0 has no hard limit "
            f"locally but serving large thumbnails slows the Plugin List."
        )

    with thumb.open("rb") as fh:
        head = fh.read(16)
    if not _looks_like(thumb.suffix.lstrip("."), head):
        raise AssertionError(
            f"thumbnail {thumb} has extension {thumb.suffix} but its magic bytes "
            f"({head[:8].hex()}) do not match that format"
        )
    return thumb


# --------------------------------------------------------------------------- #
# hooks.py assertions.
# --------------------------------------------------------------------------- #


# Patterns that *look like* a plugin lifecycle hook — used to flag likely-dead
# functions in hooks.py. A match doesn't prove the function is meant to be a
# hook; it just suggests the author expected A0 to call it. Combined with the
# canonical hook list, a pattern match outside the list → likely bug.
_HOOKLIKE_PATTERNS = (
    re.compile(r"^on_"),
    re.compile(r"^(pre|post|before|after)_"),
    re.compile(
        r"^(install|uninstall|enable|disable|activate|deactivate|setup|teardown)$"
    ),
)


def _looks_hooklike(name: str) -> bool:
    return any(p.match(name) for p in _HOOKLIKE_PATTERNS)


def assert_valid_plugin_hook(name: str, *, a0_root: Path | None = None) -> None:
    """Fail with a helpful message if ``name`` is not a real A0 plugin hook."""
    valid = (
        discover_plugin_hooks(a0_root) if a0_root else KNOWN_PLUGIN_HOOKS.resolve()
    )
    if name in valid:
        return
    suggestions = difflib.get_close_matches(name, list(valid), n=3, cutoff=0.5)
    hint = f"  did you mean: {', '.join(suggestions)}?\n" if suggestions else ""
    raise AssertionError(
        f"unknown plugin hook: {name!r}\n"
        f"{hint}"
        f"  A0 invokes plugin hooks via helpers.plugins.call_plugin_hook() — valid "
        f"names come from grepping A0's source. Known hooks ({len(valid)}): {sorted(valid)}"
    )


def assert_no_dead_plugin_hooks(
    plugin_dir: Path, *, a0_root: Path | None = None
) -> None:
    """Plugin's hooks.py may only define functions A0 actually calls.

    Parses hooks.py with ``ast`` (no execution), collects top-level public
    function names, and flags any that look like lifecycle hooks (match
    ``_HOOKLIKE_PATTERNS``) but are not in the canonical hook list.

    This is the assertion that would have caught ``on_plugin_enabled`` /
    ``on_plugin_disabled`` — names propagated in some docs but that A0 never
    dispatches to, so setup code inside them silently never ran.
    """
    hooks_py = plugin_dir / "hooks.py"
    if not hooks_py.is_file():
        return

    valid = (
        discover_plugin_hooks(a0_root) if a0_root else KNOWN_PLUGIN_HOOKS.resolve()
    )

    try:
        tree = ast.parse(hooks_py.read_text(encoding="utf-8"))
    except SyntaxError as e:
        raise AssertionError(f"{hooks_py} failed to parse: {e}") from e

    dead: list[tuple[str, int, list[str]]] = []
    for node in tree.body:  # top-level only
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name.startswith("_"):
            continue  # private helpers
        if name in valid:
            continue
        if _looks_hooklike(name):
            suggestions = difflib.get_close_matches(name, list(valid), n=3, cutoff=0.5)
            dead.append((name, node.lineno, suggestions))

    if dead:
        lines = [
            f"hooks.py defines {len(dead)} hook-shaped function(s) A0 never calls:"
        ]
        for name, lineno, suggestions in dead:
            hint = f" (did you mean: {', '.join(suggestions)}?)" if suggestions else ""
            lines.append(f"  - hooks.py:{lineno}  def {name}(...){hint}")
        lines.append(
            f"  Valid plugin hook names are scraped at runtime; {len(valid)} currently "
            f"known: {sorted(valid)}"
        )
        raise AssertionError("\n".join(lines))


__all__ = (
    "assert_valid_surface",
    "assert_valid_js_hook",
    "assert_extension_at_surface",
    "assert_js_at_hook",
    "assert_no_stray_extension_folders",
    "find_plugin_thumbnail",
    "assert_plugin_has_thumbnail",
    "assert_valid_plugin_hook",
    "assert_no_dead_plugin_hooks",
    "PLUGIN_THUMBNAIL_EXTS",
    "DEFAULT_THUMBNAIL_MAX_BYTES",
)
