"""Static audit: plugin HTTP responses don't hand out container-local URLs.

Classic failure mode: a plugin in a containerised A0 returns a URL like
``ws://127.0.0.1:7880`` from its API handler. A0 *inside the container*
can reach it; the browser on the host cannot. The browser surfaces a
generic "Failed to fetch" and the user has no idea what's wrong.

This module AST-walks a plugin's ``api/`` directory, finds public response
builders (``ApiHandler.process`` methods and top-level ``build_*_response``
helpers), and flags two patterns that reliably leak a container URL:

  1. **Passthrough**: a function parameter whose name contains ``url`` is
     returned verbatim as the value of a non-exempt dict key (e.g.
     ``return {"url": livekit_url, ...}``).
  2. **Hardcoded**: a literal string containing ``127.0.0.1`` / ``localhost``
     / ``0.0.0.0`` / ``host.docker.internal`` is the value of a non-exempt
     dict key.

Exempt keys are the ones known to carry the internal URL *intentionally*
for diagnostics (``internal_url``, ``livekit_url``, ``host``) — the browser
does not connect using them.

The check is intentionally narrow: it does not try to resolve subscripts
into settings dicts or follow arbitrary data flow. It catches the direct
bug; broader coverage belongs in runtime tests with ``FakeSettings``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


CONTAINER_HOST_PATTERNS: tuple[str, ...] = (
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "host.docker.internal",
)

DEFAULT_EXEMPT_KEYS: frozenset[str] = frozenset({
    # Keys whose whole point is to carry the internal URL for diagnostics.
    "internal_url",
    "livekit_url",
    "host",
    # The signaling proxy's in-container target, surfaced for debugging.
    "upstream_url",
    "probe_url",
    # Socket-level fields that are host:port pairs, not browser targets.
    "hostname",
})

_URL_PARAM_HINTS: tuple[str, ...] = ("url", "endpoint", "uri")


@dataclass(frozen=True)
class UrlFinding:
    plugin_file: str
    function: str
    lineno: int
    key: str
    value_kind: str   # "passthrough_param" | "hardcoded_literal"
    detail: str       # for passthrough: parameter name; for literal: the matched host

    def format(self) -> str:
        if self.value_kind == "passthrough_param":
            return (
                f"  - {self.plugin_file}:{self.lineno}  {self.function}(...) "
                f"returns {self.key!r}: <param {self.detail!r}> "
                f"— parameter name suggests a URL; value passes through unchanged, "
                f"embedding whatever the caller supplies (in managed mode that is "
                f"a container-local URL)"
            )
        return (
            f"  - {self.plugin_file}:{self.lineno}  {self.function}(...) "
            f"returns {self.key!r}: {self.detail!r} — literal contains a "
            f"container-local host"
        )


@dataclass
class UrlAudit:
    plugin_dir: Path
    findings: list[UrlFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


def _contains_container_host(s: str) -> str | None:
    """Return the first matched container-host pattern in ``s``, or None."""
    for pat in CONTAINER_HOST_PATTERNS:
        if pat in s:
            return pat
    return None


def _looks_urlish_param(name: str) -> bool:
    lname = name.lower()
    return any(h in lname for h in _URL_PARAM_HINTS)


def _is_response_builder(node: ast.AST) -> bool:
    """Top-level ``build_*_response`` or method ``process`` on an ApiHandler."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name.startswith("build_") and node.name.endswith("_response")
    return False


def _handler_process_methods(tree: ast.Module) -> list[ast.AsyncFunctionDef | ast.FunctionDef]:
    """Every ``process`` method declared on a class in the module."""
    out: list[ast.AsyncFunctionDef | ast.FunctionDef] = []
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "process":
                out.append(item)
    return out


def _param_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """All positional/keyword/kwonly parameter names of the function."""
    args = fn.args
    names: set[str] = set()
    for a in list(args.args) + list(args.kwonlyargs) + list(args.posonlyargs):
        names.add(a.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _locally_bound_dicts(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, ast.Dict]:
    """Assignments of dict literals to local names, so we can follow ``x = {...}; return x``."""
    bindings: dict[str, ast.Dict] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if isinstance(node.value, ast.Dict):
                    bindings[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.value, ast.Dict):
                bindings[node.target.id] = node.value
    return bindings


def _dicts_in_return_chain(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Dict]:
    """Every dict literal that can flow out of this function.

    Catches:
      return {"x": 1}
      resp = {"x": 1}; resp["y"] = 2; return resp   (the dict literal; mutations ignored)
      return func(**{"x": 1})                        (dicts in call kwargs, loose)
    """
    bindings = _locally_bound_dicts(fn)
    out: list[ast.Dict] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Return):
            val = node.value
            if isinstance(val, ast.Dict):
                out.append(val)
            elif isinstance(val, ast.Name) and val.id in bindings:
                out.append(bindings[val.id])
    return out


def _check_dict(
    plugin_file: str,
    fn_name: str,
    fn_params: set[str],
    dict_node: ast.Dict,
    exempt_keys: frozenset[str],
) -> list[UrlFinding]:
    findings: list[UrlFinding] = []
    for k, v in zip(dict_node.keys, dict_node.values):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            continue
        key = k.value
        if key in exempt_keys:
            continue
        # Case 1 — value is a parameter name whose label hints "URL".
        if isinstance(v, ast.Name) and v.id in fn_params and _looks_urlish_param(v.id):
            findings.append(UrlFinding(
                plugin_file=plugin_file, function=fn_name,
                lineno=getattr(v, "lineno", dict_node.lineno),
                key=key, value_kind="passthrough_param", detail=v.id,
            ))
            continue
        # Case 2 — value is a string literal containing a container host.
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            hit = _contains_container_host(v.value)
            if hit:
                findings.append(UrlFinding(
                    plugin_file=plugin_file, function=fn_name,
                    lineno=getattr(v, "lineno", dict_node.lineno),
                    key=key, value_kind="hardcoded_literal", detail=hit,
                ))
    return findings


def audit_public_urls(
    plugin_dir: Path,
    *,
    api_subdir: str = "api",
    exempt_keys: frozenset[str] = DEFAULT_EXEMPT_KEYS,
) -> UrlAudit:
    """Walk ``plugin_dir/<api_subdir>/**/*.py``; collect findings."""
    plugin_dir = Path(plugin_dir).resolve()
    audit = UrlAudit(plugin_dir=plugin_dir)
    api_dir = plugin_dir / api_subdir
    if not api_dir.is_dir():
        return audit

    for py in sorted(api_dir.rglob("*.py")):
        rel = py.relative_to(plugin_dir).as_posix()
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for node in tree.body:
            if _is_response_builder(node):
                candidates.append(node)  # type: ignore[arg-type]
        candidates.extend(_handler_process_methods(tree))

        for fn in candidates:
            params = _param_names(fn)
            for dct in _dicts_in_return_chain(fn):
                audit.findings.extend(
                    _check_dict(rel, fn.name, params, dct, exempt_keys)
                )
    return audit


def assert_no_naked_container_urls_in_public_response(
    plugin_dir: Path,
    *,
    api_subdir: str = "api",
    exempt_keys: frozenset[str] = DEFAULT_EXEMPT_KEYS,
) -> None:
    """Fail if any public response builder leaks a container-local URL.

    Catches the "plugin in containerised A0 hands browser a 127.0.0.1 URL"
    bug statically, before the browser surfaces a generic Failed to fetch.
    """
    audit = audit_public_urls(plugin_dir, api_subdir=api_subdir, exempt_keys=exempt_keys)
    if audit.ok:
        return
    lines = [
        f"plugin response builder(s) expose container-local URLs to the browser "
        f"({len(audit.findings)} finding(s)):"
    ]
    for f in audit.findings:
        lines.append(f.format())
    lines.append(
        "  The browser cannot reach a URL that resolves to the container's "
        "loopback. Return a same-origin proxy URL (e.g. via the A0 published "
        "port) or the public host URL, and keep the container-local URL under "
        f"an exempt key for diagnostics. Exempt keys: {sorted(exempt_keys)}"
    )
    raise AssertionError("\n".join(lines))


__all__ = (
    "CONTAINER_HOST_PATTERNS",
    "DEFAULT_EXEMPT_KEYS",
    "UrlFinding",
    "UrlAudit",
    "audit_public_urls",
    "assert_no_naked_container_urls_in_public_response",
)
