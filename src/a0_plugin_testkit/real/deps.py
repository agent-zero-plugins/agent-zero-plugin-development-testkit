"""Static dependency audit for A0 plugins.

Classic failure mode: a plugin imports ``livekit.api`` (or any other package)
but never declares it as a runtime dependency. On a fresh A0 install, the
import crashes Flask's dispatch of the plugin's API handler with
``ModuleNotFoundError: No module named 'livekit'`` — AFTER the user has
clicked a button.

This module catches that class of bug statically:

  1. Parse A0's ``requirements.txt`` to learn what packages A0 guarantees.
  2. Walk the plugin tree and extract every top-level import from ``.py``
     files via the ``ast`` module (no execution needed).
  3. Collapse each import to its top-level distribution equivalent via a
     small pip-name ↔ import-name map.
  4. Anything not in (stdlib | A0-internal | A0-required | plugin-declared)
     is flagged.

Plugin declares its extra runtime deps via a plain ``requirements.txt`` at
the plugin root (same format as pip). Also supports a ``REQUIRED_PACKAGES``
list in ``hooks.py`` as a fallback.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #

# Modules that ship with Python (subset — the common ones plugins touch). The
# fallback uses ``sys.stdlib_module_names`` when available (3.10+).
_STDLIB_FALLBACK = frozenset({
    "abc", "argparse", "ast", "asyncio", "base64", "collections", "concurrent",
    "contextlib", "copy", "dataclasses", "datetime", "enum", "errno", "functools",
    "hashlib", "hmac", "importlib", "inspect", "io", "itertools", "json",
    "logging", "math", "os", "pathlib", "pickle", "random", "re", "secrets",
    "shlex", "shutil", "signal", "socket", "string", "struct", "subprocess",
    "sys", "tempfile", "textwrap", "threading", "time", "traceback", "types",
    "typing", "unittest", "urllib", "uuid", "warnings", "wave", "weakref",
    "xml", "zipfile",
})
_STDLIB: frozenset[str] = frozenset(
    getattr(sys, "stdlib_module_names", _STDLIB_FALLBACK)
) or _STDLIB_FALLBACK

# A0-internal top-level modules (imports that resolve inside the A0 repo).
_A0_INTERNAL = frozenset({
    "agent",         # agent.py at A0 root
    "helpers",       # helpers/ package
    "initialize",    # initialize.py
    "models",        # models.py
    "plugins",       # built-in plugins package
    "python",        # python/ tools/extensions package
    "tools",         # core tools
    "webui",         # not really imported but exclude for safety
    "usr",           # plugins live under usr/plugins/<name>
})

# Map pip distribution names → the top-level Python module they install.
# Maintained by hand: extend as new plugins surface surprises. Keys and values
# are both normalised with ``_norm()``.
_PIP_TO_IMPORT = {
    "livekit-api": "livekit",              # pip "livekit-api" → import "livekit.api"
    "livekit-agents": "livekit",           # pip "livekit-agents" → import "livekit.agents"
    "livekit-blingfire": "livekit",
    "livekit-protocol": "livekit",
    "livekit-plugins-silero": "livekit",
    "pyyaml": "yaml",
    "python-dotenv": "dotenv",
    "pillow": "pil",
    "beautifulsoup4": "bs4",
    "gitpython": "git",
    "giturlparse": "giturlparse",
    "faiss-cpu": "faiss",
    "openai-whisper": "whisper",
    "sentence-transformers": "sentence_transformers",
    "python-multipart": "multipart",
    "pyjwt": "jwt",
    "types-protobuf": "google",  # stub package
    "flask-basicauth": "flask_basicauth",
    "flaredantic": "flaredantic",
    "langchain-core": "langchain_core",
    "langchain-community": "langchain_community",
    "langchain-unstructured": "langchain_unstructured",
    "duckduckgo-search": "duckduckgo_search",
    "fastmcp": "fastmcp",
    "fasta2a": "fasta2a",
    "sounddevice": "sounddevice",
    "soundfile": "soundfile",
    "eval-type-backport": "eval_type_backport",
    "opentelemetry-api": "opentelemetry",
    "opentelemetry-sdk": "opentelemetry",
    "opentelemetry-exporter-otlp": "opentelemetry",
    "docstring-parser": "docstring_parser",
    "types-protobuf": "google",
    "prometheus-client": "prometheus_client",
}


def _norm(name: str) -> str:
    """Lowercase + collapse ``-`` and ``_`` so pip names compare cleanly."""
    return name.strip().lower().replace("-", "_")


# Normalised lookup (both keys and values use ``_norm()``).
_PIP_TO_IMPORT_NORM = {_norm(k): _norm(v) for k, v in _PIP_TO_IMPORT.items()}


@dataclass(frozen=True)
class _ImportSite:
    module: str            # top-level package, e.g. "livekit" (from "livekit.api")
    path: str              # relative-to-plugin-dir
    lineno: int


# --------------------------------------------------------------------------- #
# Parse requirements files
# --------------------------------------------------------------------------- #

_REQ_LINE_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._\-]*)")


def _parse_requirements(path: Path) -> set[str]:
    """Extract normalised pip names from a ``requirements.txt``-style file."""
    names: set[str] = set()
    if not path.is_file():
        return names
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _REQ_LINE_RE.match(line)
        if m:
            names.add(_norm(m.group(1)))
    return names


def _parse_hooks_required_packages(hooks_py: Path) -> set[str]:
    """Fallback: parse ``REQUIRED_PACKAGES = [...]`` (a list of pip spec strings)
    from the plugin's hooks.py via AST, without executing it."""
    names: set[str] = set()
    if not hooks_py.is_file():
        return names
    try:
        tree = ast.parse(hooks_py.read_text(encoding="utf-8"))
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "REQUIRED_PACKAGES"
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    spec = elt.value
                    # strip version specifiers: "livekit-api>=1.0" → "livekit-api"
                    m = _REQ_LINE_RE.match(spec)
                    if m:
                        names.add(_norm(m.group(1)))
    return names


def _expected_import_modules(pip_names: set[str]) -> set[str]:
    """Translate pip names → top-level import modules they provide.

    ``pip_names`` must already be passed through :func:`_norm`. Any pip name
    in :data:`_PIP_TO_IMPORT_NORM` maps to its real import module; others
    default to the pip name itself (works for the common case where the pip
    and import names agree after normalisation).
    """
    return {_PIP_TO_IMPORT_NORM.get(name, name) for name in pip_names}


# --------------------------------------------------------------------------- #
# Extract imports from plugin source
# --------------------------------------------------------------------------- #


def _extract_top_level_imports(py: Path) -> list[_ImportSite]:
    """All ``import X`` / ``from X import ...`` top-level names in a .py file."""
    sites: list[_ImportSite] = []
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return sites
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                sites.append(_ImportSite(module=top, path=str(py), lineno=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports entirely (node.level > 0).
            if node.level > 0 or not node.module:
                continue
            top = node.module.split(".")[0]
            sites.append(_ImportSite(module=top, path=str(py), lineno=node.lineno))
    return sites


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


@dataclass
class DependencyAudit:
    plugin_dir: Path
    a0_provided: set[str]           # top-level import names A0 guarantees
    plugin_declared: set[str]       # top-level import names this plugin declares
    third_party: list[_ImportSite]  # imports flagged as third-party (neither stdlib nor A0-internal)
    undeclared: list[_ImportSite]   # subset of third_party that nobody declared

    @property
    def ok(self) -> bool:
        return not self.undeclared


def audit_dependencies(
    plugin_dir: Path, *, a0_root: Path | None = None
) -> DependencyAudit:
    """Run the static dependency audit against ``plugin_dir``."""
    plugin_dir = Path(plugin_dir).resolve()

    # A0-provided: parse A0's requirements.txt → set of top-level import modules.
    if a0_root is None:
        from ..discovery import find_a0_root
        a0_root = find_a0_root(plugin_dir)
    a0_reqs = _parse_requirements(a0_root / "requirements.txt")
    a0_provided = _expected_import_modules(a0_reqs)
    # Flask is a meta-package; add its common adjuncts that real plugins import.
    a0_provided.update({"flask", "starlette", "asgiref", "httpx", "aiohttp", "pydantic", "openai", "litellm", "anthropic", "jinja2", "werkzeug", "markupsafe"})

    # Plugin-declared: requirements.txt at plugin root + REQUIRED_PACKAGES list in hooks.py.
    plugin_reqs = _parse_requirements(plugin_dir / "requirements.txt")
    plugin_reqs |= _parse_hooks_required_packages(plugin_dir / "hooks.py")
    plugin_declared = _expected_import_modules(plugin_reqs)

    # Sweep imports.
    third_party: list[_ImportSite] = []
    undeclared: list[_ImportSite] = []
    for py in plugin_dir.rglob("*.py"):
        rel = py.relative_to(plugin_dir).as_posix()
        for site in _extract_top_level_imports(py):
            mod = _norm(site.module)
            if mod in _STDLIB or mod in _A0_INTERNAL:
                continue
            pretty = _ImportSite(module=site.module, path=rel, lineno=site.lineno)
            third_party.append(pretty)
            if mod in a0_provided or mod in plugin_declared:
                continue
            undeclared.append(pretty)

    return DependencyAudit(
        plugin_dir=plugin_dir,
        a0_provided=a0_provided,
        plugin_declared=plugin_declared,
        third_party=third_party,
        undeclared=undeclared,
    )


def assert_dependencies_declared(audit: DependencyAudit) -> None:
    """Fail the test if any plugin import is not declared anywhere."""
    if audit.ok:
        return
    lines = [
        f"{len(audit.undeclared)} undeclared third-party import(s) in {audit.plugin_dir}:",
    ]
    for site in audit.undeclared:
        lines.append(f"  - {site.path}:{site.lineno}  imports {site.module!r}")
    lines.append(
        "  Fix: add the package to requirements.txt at plugin root, or declare it "
        "as REQUIRED_PACKAGES = [...] in hooks.py. Extend a0_plugin_testkit.real.deps."
        "_PIP_TO_IMPORT if the pip-name → import-name mapping is non-trivial."
    )
    raise AssertionError("\n".join(lines))


__all__ = (
    "DependencyAudit",
    "audit_dependencies",
    "assert_dependencies_declared",
)
