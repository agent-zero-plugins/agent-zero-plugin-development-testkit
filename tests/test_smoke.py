"""Smoke tests for the testkit — runs against the pinned ``.agent-zero`` submodule.

Each discover-helper must come back with a non-empty set containing a handful of
stable names. If any of these fail, either the A0 submodule pin was bumped to a
commit that broke the source layout, or the scrapers drifted. Either way we
want to catch it HERE (in the testkit repo) rather than have every consumer
plugin repo notice independently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from a0_plugin_testkit.assertions import (
    PLUGIN_THUMBNAIL_EXTS,
    assert_valid_js_hook,
    assert_valid_plugin_hook,
    assert_valid_surface,
)
from a0_plugin_testkit.discovery import (
    KNOWN_HTML_SURFACES,
    KNOWN_JS_HOOKS,
    KNOWN_PLUGIN_HOOKS,
    find_a0_root,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
PINNED_A0 = REPO_ROOT / ".agent-zero"


@pytest.fixture(scope="session", autouse=True)
def _use_pinned_a0(monkeypatch_session) -> None:
    """Point the scrapers at the testkit's own ``.agent-zero`` submodule.

    Without this, the walk-up heuristic would stop at the testkit checkout
    (which has no parent ``.agent-zero``) and raise ``FileNotFoundError``.
    """
    assert (PINNED_A0 / "agent.py").is_file(), (
        f"pinned .agent-zero submodule missing at {PINNED_A0} — "
        f"run `git submodule update --init --recursive`"
    )
    monkeypatch_session.setenv("A0_ROOT", str(PINNED_A0))


@pytest.fixture(scope="session")
def monkeypatch_session() -> pytest.MonkeyPatch:
    """Session-scoped monkeypatch — pytest only ships function-scoped by default."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


# --------------------------------------------------------------------------- #
# Discovery — does the scraper find the pinned A0 source?
# --------------------------------------------------------------------------- #


def test_find_a0_root_resolves_to_pinned_submodule() -> None:
    found = find_a0_root()
    assert found.resolve() == PINNED_A0.resolve(), (
        f"find_a0_root returned {found}, expected {PINNED_A0}"
    )


def test_html_surfaces_include_well_known_ids() -> None:
    # Stable IDs that have lived in A0's webui for many commits.
    stable = {
        "chat-input-bottom-actions-start",
        "sidebar-quick-actions-main-start",
        "welcome-actions-end",
        "plugins-list-header-buttons",
    }
    missing = stable - set(KNOWN_HTML_SURFACES)
    assert not missing, (
        f"scraper missed stable HTML surfaces {missing}; "
        f"found {len(KNOWN_HTML_SURFACES)} total"
    )


def test_js_hooks_include_well_known_events() -> None:
    stable = {"initFw_start", "initFw_end", "json_api_call_before"}
    missing = stable - set(KNOWN_JS_HOOKS)
    assert not missing, (
        f"scraper missed stable JS hooks {missing}; found {len(KNOWN_JS_HOOKS)} total"
    )


def test_plugin_hooks_include_canonical_lifecycle_names() -> None:
    stable = {"install", "pre_update", "uninstall"}
    missing = stable - set(KNOWN_PLUGIN_HOOKS)
    assert not missing, (
        f"scraper missed canonical plugin hooks {missing}; "
        f"found {len(KNOWN_PLUGIN_HOOKS)} total"
    )


# --------------------------------------------------------------------------- #
# Assertions — positive + negative paths exercise difflib suggestions.
# --------------------------------------------------------------------------- #


def test_assert_valid_surface_accepts_real_id() -> None:
    assert_valid_surface("chat-input-bottom-actions-start")


def test_assert_valid_surface_rejects_typo_with_suggestion() -> None:
    with pytest.raises(AssertionError) as exc:
        assert_valid_surface("chat_toolbar")
    msg = str(exc.value)
    assert "unknown HTML extension surface" in msg
    assert "did you mean" in msg.lower()


def test_assert_valid_js_hook_rejects_typo() -> None:
    with pytest.raises(AssertionError, match="unknown JS hook"):
        assert_valid_js_hook("iniFw_end")  # missing 't'


def test_assert_valid_plugin_hook_rejects_on_plugin_enabled() -> None:
    """The historical gotcha: ``on_plugin_enabled`` is NOT a real A0 hook."""
    with pytest.raises(AssertionError, match="unknown plugin hook"):
        assert_valid_plugin_hook("on_plugin_enabled")


def test_plugin_thumbnail_extensions_stable() -> None:
    # Guard against accidental reordering — first-match discovery order
    # has to match A0's source (.agent-zero/helpers/plugins.py).
    assert PLUGIN_THUMBNAIL_EXTS == ("png", "jpg", "jpeg", "gif", "webp")
