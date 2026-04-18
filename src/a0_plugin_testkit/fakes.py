"""Lightweight stand-ins for A0 modules, so unit tests run without A0 installed.

Pattern: most plugin tests want to verify *their own* logic, not A0's. Wiring
A0's runtime into every unit test is overkill. Inject these fakes via
``sys.modules`` or ``monkeypatch`` to let plugin code under test import
``helpers.settings``, ``helpers.print_style``, etc. without the real A0.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Iterator


class FakeSettings:
    """In-memory A0 settings stand-in — mirrors A0's real ``helpers.settings`` API.

    Exposes ``get_settings()`` → dict copy and ``set_settings_delta(delta)`` →
    merge-in-place. These are the names A0 actually ships (see
    ``.agent-zero/helpers/settings.py``). ``writes`` records every key/value
    set via ``set_settings_delta`` so tests can assert on the sequence.
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})
        self.writes: list[tuple[str, Any]] = []

    def get_settings(self) -> dict[str, Any]:
        return dict(self._data)

    def set_settings_delta(self, delta: dict[str, Any], apply: bool = True) -> None:
        for k, v in delta.items():
            self.writes.append((k, v))
            self._data[k] = v

    # Convenience for tests.
    def update(self, **kv: Any) -> None:
        self._data.update(kv)


class _NoopPrintStyle:
    """Stand-in for ``helpers.print_style.PrintStyle`` that swallows output."""

    def __init__(self, **_: Any) -> None:
        pass

    def print(self, *_: Any, **__: Any) -> None:
        pass

    def warning(self, *_: Any, **__: Any) -> None:
        pass

    def error(self, *_: Any, **__: Any) -> None:
        pass


def install_fake_a0_helpers(
    monkeypatch: Any,
    *,
    settings: FakeSettings | None = None,
) -> FakeSettings:
    """Inject fake ``helpers.*`` modules into ``sys.modules``.

    Call from a pytest fixture before importing plugin code that does
    ``from helpers import settings``.

    Returns the ``FakeSettings`` instance so the test can assert on writes.
    """
    fs = settings or FakeSettings()

    fake_helpers = types.ModuleType("helpers")
    fake_settings_mod = types.ModuleType("helpers.settings")
    fake_settings_mod.get_settings = fs.get_settings  # type: ignore[attr-defined]
    fake_settings_mod.set_settings_delta = fs.set_settings_delta  # type: ignore[attr-defined]
    fake_print_mod = types.ModuleType("helpers.print_style")
    fake_print_mod.PrintStyle = _NoopPrintStyle  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "helpers", fake_helpers)
    monkeypatch.setitem(sys.modules, "helpers.settings", fake_settings_mod)
    monkeypatch.setitem(sys.modules, "helpers.print_style", fake_print_mod)

    return fs


def import_plugin_module(path: str, module_name: str | None = None) -> Any:
    """Import a plugin's Python file by path, returning the module object.

    Useful in unit tests that exercise a plugin's ``hooks.py`` or similar
    without altering its ``sys.path``.
    """
    import importlib.util
    from pathlib import Path as _P

    spec = importlib.util.spec_from_file_location(
        module_name or f"_plugin_mod_{id(path)}", _P(path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build import spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


__all__ = (
    "FakeSettings",
    "install_fake_a0_helpers",
    "import_plugin_module",
)
