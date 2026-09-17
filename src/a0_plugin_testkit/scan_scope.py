"""Scan scope for whole-tree audits — plugin code vs repo scaffolding.

Root-layout plugins (``.devkit.yml`` ``plugin_dir: .``) keep their dev
scaffolding INSIDE the audited tree: the test suite + the vendored ``_testkit``
submodule, caller workflows, local agent dirs, build output. None of that is
shipped plugin code — the reusable plugin-e2e workflow's zip step already
excludes the same set when packaging a root-layout plugin — so the whole-tree
audits (deps, A0-API usage, validator structure checks) skip it too.

No-ops for subdir layouts (``plugin_dir: usr/plugins/<name>``): none of these
folders sit inside a nested plugin dir, so those audits behave exactly as
before.
"""
from __future__ import annotations

# First path segment (relative to the plugin dir) that marks repo scaffolding.
# Mirrors the zip excludes of the reusable plugin-e2e workflow, plus
# local-only build output that never exists on a CI runner.
_REPO_SCAFFOLD_DIRS = frozenset({
    "tests",        # plugin's own suite + the vendored _testkit submodule
    ".github",      # caller workflows
    ".skills",      # devkit-linked skills
    ".agent-zero",  # vendored A0 source (inside _testkit)
    ".git",
    ".devkit.yml",  # standardization wrapper (root layout only)
    ".gitmodules",
    ".gitignore",
    "dist",         # packaged zips
    "artifacts",    # e2e artifacts
    ".claude",      # local agent workspace
    ".gemini",      # local agent styleguide
})


def is_repo_scaffolding(rel_posix: str) -> bool:
    """True if a plugin-dir-relative POSIX path belongs to repo scaffolding.

    Only the FIRST segment is matched, so e.g. ``tests/_testkit/src/x.py``
    and ``dist/foo.zip`` are scaffolding, while ``extensions/python/x.py``
    and a root-level ``hooks.py`` are not.
    """
    return rel_posix.split("/", 1)[0] in _REPO_SCAFFOLD_DIRS
