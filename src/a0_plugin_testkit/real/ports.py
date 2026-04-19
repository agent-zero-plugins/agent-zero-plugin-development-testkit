"""Static audit: every listening port the plugin opens is declared to the user.

Classic failure mode: a plugin runs an auxiliary subprocess that listens on
some port (a STUN/TURN server, a local LLM gateway, a media SFU, a vector
DB) and hands the browser a URL reaching it. The container isn't publishing
that port; the browser can't reach it; the error is cryptic.

The user needs to know which ports the plugin requires *before* they run
the A0 container — at install time and in the settings UI. This check
guarantees the plugin declares every port it opens in a discoverable place.

The preferred declaration is a top-level ``extra_ports`` list in
``plugin.yaml``. If A0 ever rejects unknown manifest keys, the fallback is
a docker-publish example in the plugin's ``description`` field or in
``README.md`` — the check accepts either.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


# Flags across common subprocess-launching conventions. The first capture
# group is the port (literal number) when the pattern is present.
_PORT_FLAG_PATTERNS: tuple[re.Pattern[str], ...] = (
    # `--rtc.tcp_port 7881` or `--rtc.tcp_port=7881`
    re.compile(r"--rtc\.tcp_port[=\s]+(\d{2,5})"),
    # `--rtc.port_range_start 7900`
    re.compile(r"--rtc\.port_range_start[=\s]+(\d{2,5})"),
    # Generic `--port 8080` (but not A0's own --port used for the web UI —
    # supervisors don't tend to name that).
    re.compile(r"(?<!web[-_])--port[=\s]+(\d{2,5})"),
    # `--bind-port`, `--listen`, etc.
    re.compile(r"--bind-port[=\s]+(\d{2,5})"),
    re.compile(r"--listen[=\s]+(\d{2,5})"),
)


@dataclass(frozen=True)
class PortFinding:
    source_file: str   # relative-to-plugin-dir
    lineno: int
    flag_snippet: str
    port: int


@dataclass
class PortDeclarationAudit:
    plugin_dir: Path
    opened_ports: list[PortFinding] = field(default_factory=list)
    declared_ports: frozenset[int] = frozenset()
    declared_in: str = ""   # "plugin.yaml:extra_ports" | "description" | "README.md" | ""

    @property
    def ok(self) -> bool:
        opened = {p.port for p in self.opened_ports}
        return opened.issubset(self.declared_ports)

    @property
    def undeclared(self) -> list[PortFinding]:
        return [p for p in self.opened_ports if p.port not in self.declared_ports]


# --------------------------------------------------------------------------- #
# Collect opened ports by AST-walking helper / supervisor Python files
# --------------------------------------------------------------------------- #


def _collect_strings_in_list(node: ast.AST) -> list[tuple[str, int]]:
    """Every string constant under ``node``, with line numbers."""
    out: list[tuple[str, int]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append((sub.value, sub.lineno))
        elif isinstance(sub, ast.JoinedStr):
            # f-strings: collect their literal parts only — we can only match
            # on constant text, not runtime-interpolated values.
            for val in sub.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    out.append((val.value, val.lineno))
    return out


def _scan_for_port_flags(py_file: Path) -> list[PortFinding]:
    """Find every recognisable ``--port`` flag in the file's string constants."""
    rel = py_file.name
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    findings: list[PortFinding] = []
    for s, lineno in _collect_strings_in_list(tree):
        for pat in _PORT_FLAG_PATTERNS:
            for m in pat.finditer(s):
                findings.append(PortFinding(
                    source_file=rel, lineno=lineno, flag_snippet=m.group(0),
                    port=int(m.group(1)),
                ))

    # Also scan LIST literals of command arguments — common pattern:
    #   cmd = ["livekit-server", "--rtc.tcp_port", str(port), ...]
    # Detect `--rtc.tcp_port` followed by a numeric-looking next element.
    for node in ast.walk(tree):
        if not isinstance(node, ast.List):
            continue
        elts = node.elts
        for i, elt in enumerate(elts):
            if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                continue
            for pat in (r"--rtc\.tcp_port$", r"--port$", r"--bind-port$", r"--listen$"):
                if re.match(pat, elt.value):
                    # next elt must be a numeric literal
                    if i + 1 < len(elts):
                        nxt = elts[i + 1]
                        if isinstance(nxt, ast.Constant) and isinstance(nxt.value, int):
                            findings.append(PortFinding(
                                source_file=rel, lineno=nxt.lineno,
                                flag_snippet=f"{elt.value} {nxt.value}",
                                port=int(nxt.value),
                            ))
                        elif isinstance(nxt, ast.Constant) and isinstance(nxt.value, str):
                            if nxt.value.isdigit():
                                findings.append(PortFinding(
                                    source_file=rel, lineno=nxt.lineno,
                                    flag_snippet=f"{elt.value} {nxt.value}",
                                    port=int(nxt.value),
                                ))
    return findings


# --------------------------------------------------------------------------- #
# Collect declared ports from plugin.yaml / description / README
# --------------------------------------------------------------------------- #


_YAML_PORT_IN_LIST = re.compile(r"port:\s*(\d{2,5})")
_DOCKER_PUBLISH_RE = re.compile(r"-p\s+(\d{2,5})(?::\d{2,5})?(?:/(?:tcp|udp))?\b")


def _parse_yaml_extra_ports(plugin_yaml: Path) -> list[int]:
    """Minimal YAML extraction — avoids adding a yaml dep if not already present.

    Looks for a top-level ``extra_ports:`` block, then collects any
    ``port: <int>`` lines underneath it (until a blank line or a top-level
    key with no indentation).
    """
    if not plugin_yaml.is_file():
        return []
    ports: list[int] = []
    in_block = False
    with plugin_yaml.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if in_block:
                # Still inside block if the line is indented.
                if line.startswith(" ") or line.startswith("\t") or line.startswith("-"):
                    m = _YAML_PORT_IN_LIST.search(stripped)
                    if m:
                        ports.append(int(m.group(1)))
                    continue
                # De-dented back to top level → end of block.
                in_block = False
                # fall through to check if this new top-level key is another extra_ports
            if stripped.startswith("extra_ports:"):
                in_block = True
    return ports


def _parse_description_ports(plugin_yaml: Path) -> list[int]:
    """Scan plugin.yaml's description field for ``-p <port>`` examples."""
    if not plugin_yaml.is_file():
        return []
    text = plugin_yaml.read_text(encoding="utf-8", errors="ignore")
    return [int(m.group(1)) for m in _DOCKER_PUBLISH_RE.finditer(text)]


def _parse_readme_ports(plugin_dir: Path) -> list[int]:
    readme = plugin_dir / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8", errors="ignore")
    return [int(m.group(1)) for m in _DOCKER_PUBLISH_RE.finditer(text)]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def audit_port_declarations(plugin_dir: Path) -> PortDeclarationAudit:
    plugin_dir = Path(plugin_dir).resolve()

    opened: list[PortFinding] = []
    helpers_dir = plugin_dir / "helpers"
    if helpers_dir.is_dir():
        for py in sorted(helpers_dir.rglob("*.py")):
            opened.extend(_scan_for_port_flags(py))
    # Supervisors sometimes live under api/ too.
    api_dir = plugin_dir / "api"
    if api_dir.is_dir():
        for py in sorted(api_dir.rglob("*.py")):
            opened.extend(_scan_for_port_flags(py))

    plugin_yaml = plugin_dir / "plugin.yaml"
    declared_yaml = _parse_yaml_extra_ports(plugin_yaml)
    declared_desc = _parse_description_ports(plugin_yaml)
    declared_readme = _parse_readme_ports(plugin_dir)

    declared_source = ""
    if declared_yaml:
        declared = set(declared_yaml)
        declared_source = "plugin.yaml:extra_ports"
    elif declared_desc:
        declared = set(declared_desc)
        declared_source = "plugin.yaml:description"
    elif declared_readme:
        declared = set(declared_readme)
        declared_source = "README.md"
    else:
        declared = set()

    return PortDeclarationAudit(
        plugin_dir=plugin_dir,
        opened_ports=opened,
        declared_ports=frozenset(declared),
        declared_in=declared_source,
    )


def assert_plugin_declares_required_ports(plugin_dir: Path) -> None:
    """Fail if the plugin opens listening ports it doesn't declare to users.

    Declaration is accepted in any of:
      1. ``plugin.yaml`` top-level ``extra_ports:`` list (preferred).
      2. ``plugin.yaml`` ``description:`` containing ``-p <port>`` docker examples.
      3. ``README.md`` containing ``-p <port>`` docker examples.

    Class-of-bug: any plugin running an auxiliary service (TURN, STT, local
    LLM, vector DB, media SFU) can strand the user the same way. Reusable
    across all A0 plugins.
    """
    audit = audit_port_declarations(plugin_dir)
    if audit.ok:
        return
    undeclared = audit.undeclared
    lines = [
        f"plugin opens port(s) it does not declare to users "
        f"({len(undeclared)} undeclared, declared_in={audit.declared_in or 'none'}):"
    ]
    for p in undeclared:
        lines.append(
            f"  - {p.source_file}:{p.lineno}  {p.flag_snippet}  (port {p.port})"
        )
    lines.append(
        "  Declare each port in plugin.yaml's top-level extra_ports list, e.g.:\n"
        "      extra_ports:\n"
        "        - port: 7881\n"
        "          protocol: tcp\n"
        "          purpose: \"LiveKit media (ICE-TCP). Publish: -p 7881:7881\"\n"
        "  Or — if A0's manifest schema rejects unknown top-level keys — include "
        "a ``-p <port>:<port>`` example in the description: field or README.md."
    )
    raise AssertionError("\n".join(lines))


__all__ = (
    "PortFinding",
    "PortDeclarationAudit",
    "audit_port_declarations",
    "assert_plugin_declares_required_ports",
)
