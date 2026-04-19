"""Self-tests for ``assert_plugin_declares_required_ports``."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from a0_plugin_testkit.real.ports import (
    assert_plugin_declares_required_ports,
    audit_port_declarations,
)


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


# ----- positive paths -------------------------------------------------------- #


def test_plugin_with_no_supervisors_passes(tmp_path: Path) -> None:
    assert_plugin_declares_required_ports(tmp_path)


def test_port_declared_in_plugin_yaml_passes(tmp_path: Path) -> None:
    _write(tmp_path / "helpers" / "sup.py", """
        def make():
            cmd = ["lk-server", "--rtc.tcp_port", "7881"]
            return cmd
    """)
    _write(tmp_path / "plugin.yaml", """
        name: demo
        version: 0.1.0
        extra_ports:
          - port: 7881
            protocol: tcp
            purpose: "LK media. Publish: -p 7881:7881"
    """)
    assert_plugin_declares_required_ports(tmp_path)


def test_port_declared_via_docker_example_in_description_passes(tmp_path: Path) -> None:
    _write(tmp_path / "helpers" / "sup.py", """
        CMD = ["lk-server", "--rtc.tcp_port=7881"]
    """)
    _write(tmp_path / "plugin.yaml", """
        name: demo
        description: |
          Run with -p 7881:7881 to publish the media port.
    """)
    assert_plugin_declares_required_ports(tmp_path)


def test_port_declared_in_readme_passes(tmp_path: Path) -> None:
    _write(tmp_path / "helpers" / "sup.py", """
        CMD = ["lk-server", "--rtc.tcp_port=7881"]
    """)
    _write(tmp_path / "plugin.yaml", "name: demo\n")
    _write(tmp_path / "README.md", "Run `docker run ... -p 7881:7881 ...`.\n")
    assert_plugin_declares_required_ports(tmp_path)


# ----- negative paths -------------------------------------------------------- #


def test_undeclared_tcp_port_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path / "helpers" / "sup.py", """
        def make():
            return ["lk-server", "--rtc.tcp_port", "7881"]
    """)
    _write(tmp_path / "plugin.yaml", "name: demo\n")  # no declaration
    with pytest.raises(AssertionError) as exc:
        assert_plugin_declares_required_ports(tmp_path)
    msg = str(exc.value)
    assert "7881" in msg
    assert "extra_ports" in msg


def test_partially_declared_ports_flagged(tmp_path: Path) -> None:
    """Declaring one port doesn't cover a second."""
    _write(tmp_path / "helpers" / "sup.py", """
        CMD1 = ["lk-server", "--rtc.tcp_port=7881"]
        CMD2 = ["lk-server", "--rtc.port_range_start=7900"]
    """)
    _write(tmp_path / "plugin.yaml", """
        name: demo
        extra_ports:
          - port: 7881
            protocol: tcp
    """)
    with pytest.raises(AssertionError, match="7900"):
        assert_plugin_declares_required_ports(tmp_path)


# ----- matrix over the flag-shape variants ---------------------------------- #


@pytest.mark.parametrize("flag_snippet", [
    '"--rtc.tcp_port", "7881"',
    '"--rtc.tcp_port=7881"',
    '"--port", "7881"',
    '"--port=7881"',
    '"--bind-port=7881"',
    '"--listen=7881"',
])
def test_detects_various_flag_shapes(tmp_path: Path, flag_snippet: str) -> None:
    _write(tmp_path / "helpers" / "sup.py", f"""
        CMD = [{flag_snippet}]
    """)
    _write(tmp_path / "plugin.yaml", "name: demo\n")
    with pytest.raises(AssertionError, match="7881"):
        assert_plugin_declares_required_ports(tmp_path)


# ----- audit shape ---------------------------------------------------------- #


def test_audit_reports_source_and_declaration(tmp_path: Path) -> None:
    _write(tmp_path / "helpers" / "sup.py", """
        CMD = ["lk-server", "--rtc.tcp_port=7881"]
    """)
    _write(tmp_path / "plugin.yaml", """
        name: demo
        extra_ports:
          - port: 7881
    """)
    audit = audit_port_declarations(tmp_path)
    assert audit.ok
    assert audit.declared_in == "plugin.yaml:extra_ports"
    assert 7881 in audit.declared_ports
    assert {p.port for p in audit.opened_ports} == {7881}
