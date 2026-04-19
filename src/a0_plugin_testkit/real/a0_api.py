"""Static audit: plugin's use of A0-internal module APIs matches reality.

Classic failure mode: a plugin writes ``helpers.settings.set_setting(...)``
because the name *sounds right*, but A0's actual module only exports
``set_settings`` / ``set_settings_delta`` / ``get_settings``. No linter
catches this (both names type-check as ``Any``); the failure only surfaces
at plugin-install time inside A0 as ``AttributeError: module
'helpers.settings' has no attribute 'set_setting'``.

This module AST-walks every Python file in the plugin, resolves local names
bound to A0-internal modules, finds each attribute access on those modules,
and cross-references against the real module's public top-level names
(function defs, class defs, and module-level assignments, all after
excluding names starting with ``_``).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# A0-internal top-level modules whose attribute access we'll track. Anything
# else (stdlib, pip packages) is out of scope for this check.
_A0_INTERNAL_TOPLEVEL = frozenset({
    "agent", "helpers", "initialize", "models", "plugins", "python", "tools",
})


@dataclass(frozen=True)
class A0ApiFinding:
    plugin_file: str          # relative-to-plugin-dir
    lineno: int
    module_path: str          # e.g. "helpers.settings"
    attr: str                 # e.g. "set_setting"
    suggestions: tuple[str, ...] = ()


@dataclass
class A0ApiAudit:
    plugin_dir: Path
    a0_root: Path
    findings: list[A0ApiFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


# --------------------------------------------------------------------------- #
# Resolve an A0 module path → its source file
# --------------------------------------------------------------------------- #


def _resolve_a0_module(a0_root: Path, module_path: str) -> Path | None:
    """Return the .py (or __init__.py) file for an A0 module path like 'helpers.settings'.

    Walks segments: helpers → `<a0_root>/helpers/__init__.py` OR `<a0_root>/helpers/`;
    then settings → `<a0_root>/helpers/settings.py` OR `<a0_root>/helpers/settings/__init__.py`.
    """
    parts = module_path.split(".")
    current = a0_root
    for i, part in enumerate(parts):
        candidate_py = current / f"{part}.py"
        candidate_pkg = current / part
        last = i == len(parts) - 1
        if last:
            if candidate_py.is_file():
                return candidate_py
            init = candidate_pkg / "__init__.py"
            if init.is_file():
                return init
            # Empty-package dir with no __init__.py still counts as a namespace
            # package — but we can't introspect its "exports" statically, so
            # we give up on this path.
            return None
        if candidate_pkg.is_dir():
            current = candidate_pkg
            continue
        if candidate_py.is_file():
            # A .py shadows subsequent attrs — means later parts are attributes,
            # not submodules.
            return None
        return None
    return None


# --------------------------------------------------------------------------- #
# Extract the public top-level names of an A0 module (via AST)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=64)
def _module_public_names(module_file: Path) -> frozenset[str]:
    try:
        tree = ast.parse(module_file.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return frozenset()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if not node.target.id.startswith("_"):
                names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            # Re-exports: `from .X import Y` exposes Y at the parent.
            for alias in node.names:
                exposed = alias.asname or alias.name
                if not exposed.startswith("_") and exposed != "*":
                    names.add(exposed)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                exposed = (alias.asname or alias.name).split(".")[0]
                if not exposed.startswith("_"):
                    names.add(exposed)
    return frozenset(names)


@lru_cache(maxsize=64)
def _module_class_names(module_file: Path) -> frozenset[str]:
    """Just the ClassDef names in a module — used to distinguish
    attribute access on an imported class vs. on an imported module.
    """
    try:
        tree = ast.parse(module_file.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return frozenset()
    return frozenset(
        node.name for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    )


# --------------------------------------------------------------------------- #
# Resolve local names in a plugin file → A0 module paths
# --------------------------------------------------------------------------- #


def _collect_a0_bindings(tree: ast.AST) -> dict[str, str]:
    """Return local-name → A0 module path for imports that land on A0 modules.

    Examples:
      from helpers import settings           → {"settings": "helpers.settings"}
      from helpers import settings as s      → {"s":        "helpers.settings"}
      import helpers.settings as hs          → {"hs":       "helpers.settings"}
      import helpers                         → {"helpers":  "helpers"}
      from agent import AgentContext         → {"AgentContext": "agent.AgentContext"}
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                continue
            top = node.module.split(".")[0]
            if top not in _A0_INTERNAL_TOPLEVEL:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings[local] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in _A0_INTERNAL_TOPLEVEL:
                    continue
                local = alias.asname or top
                bindings[local] = alias.name
    return bindings


def _collect_attr_uses(
    tree: ast.AST, bindings: dict[str, str]
) -> list[tuple[int, str, str]]:
    """Every `<local>.<attr>` use where <local> resolves to an A0 module.

    Returns list of (lineno, resolved_module_path, attr).
    """
    uses: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name):
            continue
        name = node.value.id
        if name not in bindings:
            continue
        uses.append((node.lineno, bindings[name], node.attr))
    return uses


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def audit_a0_api_usage(
    plugin_dir: Path, *, a0_root: Path | None = None
) -> A0ApiAudit:
    """Verify every attribute access on an A0 module is defined in A0's source."""
    plugin_dir = Path(plugin_dir).resolve()
    if a0_root is None:
        from ..discovery import find_a0_root
        a0_root = find_a0_root(plugin_dir)

    audit = A0ApiAudit(plugin_dir=plugin_dir, a0_root=a0_root)
    for py in plugin_dir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        bindings = _collect_a0_bindings(tree)
        if not bindings:
            continue

        for lineno, resolved, attr in _collect_attr_uses(tree, bindings):
            # `resolved` might be either a module path (e.g. "helpers.settings")
            # or a module-plus-symbol path (e.g. "agent.AgentContext"). The
            # heuristic: try resolving as a module first; if that fails, pop
            # the last segment and try again.
            module_file = _resolve_a0_module(a0_root, resolved)
            module_path = resolved
            popped_segment: str | None = None
            if module_file is None and "." in resolved:
                parent, popped_segment = resolved.rsplit(".", 1)
                module_file = _resolve_a0_module(a0_root, parent)
                module_path = parent
            if module_file is None:
                # Couldn't resolve module at all — skip (namespace package or
                # dynamic path). Don't raise false positives.
                continue

            # If the popped segment is a CLASS defined in the parent module,
            # the access is a class-attribute/method lookup. We can't check
            # method names without executing the code — skip. Catching a
            # fabricated method on an imported class is future work.
            if popped_segment and popped_segment in _module_class_names(module_file):
                continue

            public = _module_public_names(module_file)
            if attr in public or attr.startswith("_"):
                continue
            import difflib
            suggestions = tuple(difflib.get_close_matches(attr, list(public), n=3, cutoff=0.5))
            audit.findings.append(A0ApiFinding(
                plugin_file=py.relative_to(plugin_dir).as_posix(),
                lineno=lineno,
                module_path=module_path,
                attr=attr,
                suggestions=suggestions,
            ))

    return audit


def assert_a0_api_usage_ok(audit: A0ApiAudit) -> None:
    if audit.ok:
        return
    lines = [
        f"plugin accesses {len(audit.findings)} attribute(s) that don't exist on "
        f"the real A0 module:"
    ]
    for f in audit.findings:
        hint = f" (did you mean: {', '.join(f.suggestions)}?)" if f.suggestions else ""
        lines.append(
            f"  - {f.plugin_file}:{f.lineno}  {f.module_path}.{f.attr}{hint}"
        )
    lines.append(
        "  Names are cross-referenced against A0's source (function defs, class "
        "defs, module-level assignments, re-exports). Extend "
        "a0_plugin_testkit.real.a0_api._A0_INTERNAL_TOPLEVEL if a new top-level "
        "A0 module surfaces."
    )
    raise AssertionError("\n".join(lines))


__all__ = (
    "A0ApiFinding",
    "A0ApiAudit",
    "audit_a0_api_usage",
    "assert_a0_api_usage_ok",
)
