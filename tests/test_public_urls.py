"""Self-tests for ``assert_no_naked_container_urls_in_public_response``.

Uses tmp_path to build synthetic plugin directories that exhibit each
variant the check is designed to catch — the red-first evidence for the
assertion is baked into these tests.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from a0_plugin_testkit.real.public_urls import (
    DEFAULT_EXEMPT_KEYS,
    assert_no_naked_container_urls_in_public_response,
    audit_public_urls,
)


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


# ----- positive paths (passes) ------------------------------------------------ #


def test_empty_plugin_passes(tmp_path: Path) -> None:
    assert_no_naked_container_urls_in_public_response(tmp_path)


def test_plugin_with_only_exempt_keys_passes(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "token.py", """
        def build_token_response(*, livekit_url, signal_proxy_path):
            return {
                "url": signal_proxy_path,
                "internal_url": livekit_url,
                "host": "127.0.0.1",
            }
    """)
    assert_no_naked_container_urls_in_public_response(tmp_path)


# ----- negative: passthrough of url-param ------------------------------------- #


def test_passthrough_url_param_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "token.py", """
        def build_token_response(*, livekit_url, api_key):
            return {"url": livekit_url, "token": "t"}
    """)
    with pytest.raises(AssertionError) as exc:
        assert_no_naked_container_urls_in_public_response(tmp_path)
    msg = str(exc.value)
    assert "passthrough" not in msg  # Internal term, don't expose it
    assert "parameter name suggests a URL" in msg
    assert "livekit_url" in msg
    assert "token.py" in msg


def test_passthrough_in_apihandler_process_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "token.py", """
        class LiveKitToken:
            async def process(self, input, request):
                livekit_url = "ws://does-not-matter"
                return {"url": livekit_url}
    """)
    # Process method: its "livekit_url" is a local, not a param — the
    # check only flags passthrough of PARAMS, not local names. But the
    # literal default would be caught by the literal branch when
    # appropriate. Here we assert the non-matching path passes cleanly.
    # (Process methods with URL-like params get caught by the direct-
    #  passthrough case, covered by test_process_param_passthrough_flagged.)
    assert_no_naked_container_urls_in_public_response(tmp_path)


def test_process_param_passthrough_flagged(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "redir.py", """
        class Redir:
            async def process(self, input, request, livekit_url="ws://x"):
                return {"url": livekit_url}
    """)
    with pytest.raises(AssertionError, match="livekit_url"):
        assert_no_naked_container_urls_in_public_response(tmp_path)


# ----- negative: hardcoded literal ------------------------------------------ #


def test_hardcoded_container_url_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "t.py", """
        def build_token_response(**kwargs):
            return {"url": "ws://127.0.0.1:7880", "token": "x"}
    """)
    with pytest.raises(AssertionError) as exc:
        assert_no_naked_container_urls_in_public_response(tmp_path)
    assert "127.0.0.1" in str(exc.value)


@pytest.mark.parametrize("host", ["localhost", "0.0.0.0", "host.docker.internal"])
def test_other_container_hosts_flagged(tmp_path: Path, host: str) -> None:
    _write(tmp_path / "api" / "t.py", f"""
        def build_x_response():
            return {{"url": "ws://{host}:9000"}}
    """)
    with pytest.raises(AssertionError, match=host):
        assert_no_naked_container_urls_in_public_response(tmp_path)


# ----- exempt keys ---------------------------------------------------------- #


def test_exempt_keys_do_not_trigger(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "preflight.py", """
        def build_preflight_response(livekit_url):
            return {
                "internal_url": livekit_url,
                "host": "127.0.0.1",
                "livekit_url": "ws://127.0.0.1:7880",
            }
    """)
    assert_no_naked_container_urls_in_public_response(tmp_path)


def test_custom_exempt_keys(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "t.py", """
        def build_x_response():
            return {"debug_only": "ws://127.0.0.1:9000", "url": "/ok"}
    """)
    # Default: flagged (debug_only isn't in the default exempt set).
    with pytest.raises(AssertionError):
        assert_no_naked_container_urls_in_public_response(tmp_path)
    # Custom: debug_only exempted → pass.
    assert_no_naked_container_urls_in_public_response(
        tmp_path, exempt_keys=DEFAULT_EXEMPT_KEYS | {"debug_only"},
    )


# ----- flow through local binding -------------------------------------------- #


def test_local_binding_returns_are_inspected(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "t.py", """
        def build_token_response(*, livekit_url):
            resp = {"url": livekit_url}
            return resp
    """)
    with pytest.raises(AssertionError, match="livekit_url"):
        assert_no_naked_container_urls_in_public_response(tmp_path)


# ----- scope: only api/ directory, not worker code --------------------------- #


def test_worker_code_is_not_scanned(tmp_path: Path) -> None:
    """Plugin worker code can legitimately reference 127.0.0.1 (internal calls)."""
    _write(tmp_path / "worker" / "w.py", """
        def something():
            return {"url": "ws://127.0.0.1:7880"}
    """)
    assert_no_naked_container_urls_in_public_response(tmp_path)


# ----- audit return shape ---------------------------------------------------- #


def test_audit_returns_structured_findings(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "t.py", """
        def build_one_response(*, livekit_url):
            return {"url": livekit_url}

        def build_two_response():
            return {"url": "ws://localhost:1234"}
    """)
    audit = audit_public_urls(tmp_path)
    assert not audit.ok
    kinds = sorted(f.value_kind for f in audit.findings)
    assert kinds == ["hardcoded_literal", "passthrough_param"]
    # Function names carried through for diagnostics.
    fn_names = {f.function for f in audit.findings}
    assert fn_names == {"build_one_response", "build_two_response"}
