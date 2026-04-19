"""Regression: access to a method on an A0 class imported from a module
must not false-positive as "fabricated attribute".

Before the fix, `from helpers.ui_server import UiServerRuntime;
UiServerRuntime.build_asgi_app` was flagged because the audit resolved
``helpers.ui_server.UiServerRuntime.build_asgi_app`` → popped to
``helpers.ui_server`` and checked if ``build_asgi_app`` was a module-
level name (it isn't — it's a method on the class).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from a0_plugin_testkit.real.a0_api import (
    assert_a0_api_usage_ok,
    audit_a0_api_usage,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
PINNED_A0 = REPO_ROOT / ".agent-zero"


@pytest.fixture(scope="session", autouse=True)
def _use_pinned_a0(monkeypatch_session) -> None:
    assert (PINNED_A0 / "agent.py").is_file()
    monkeypatch_session.setenv("A0_ROOT", str(PINNED_A0))


@pytest.fixture(scope="session")
def monkeypatch_session() -> pytest.MonkeyPatch:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_class_attribute_access_not_flagged(tmp_path: Path) -> None:
    """Accessing a method on an imported A0 class → no finding."""
    plugin = tmp_path / "p"
    plugin.mkdir()
    (plugin / "plugin.yaml").write_text(
        "name: p\ntitle: X\ndescription: Y\nversion: 0.1.0\n", encoding="utf-8"
    )
    (plugin / "hooks.py").write_text(
        "from helpers.ui_server import UiServerRuntime\n"
        "\n"
        "def install(**_):\n"
        "    original = UiServerRuntime.build_asgi_app\n"
        "    UiServerRuntime.build_asgi_app = original\n",
        encoding="utf-8",
    )
    audit = audit_a0_api_usage(plugin)
    assert audit.ok, [(f.module_path, f.attr) for f in audit.findings]


def test_module_attribute_still_flagged(tmp_path: Path) -> None:
    """A fabricated module-level function is STILL caught — the class-attr
    exemption must not weaken the core contract."""
    plugin = tmp_path / "p"
    plugin.mkdir()
    (plugin / "plugin.yaml").write_text(
        "name: p\ntitle: X\ndescription: Y\nversion: 0.1.0\n", encoding="utf-8"
    )
    (plugin / "hooks.py").write_text(
        "from helpers import settings\n"
        "def install(**_):\n"
        "    settings.set_setting('x', 1)\n",
        encoding="utf-8",
    )
    audit = audit_a0_api_usage(plugin)
    assert not audit.ok
    assert any(f.attr == "set_setting" for f in audit.findings)
