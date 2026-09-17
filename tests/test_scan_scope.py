"""Self-tests for DEC-083 — root-layout audits scan shipped plugin code only.

Root-layout repos (``.devkit.yml`` ``plugin_dir: .``) keep their dev scaffolding
inside the audited tree; the whole-tree audits must skip it (mirroring the
reusable workflow's zip excludes) while still auditing everything that ships.
"""

from __future__ import annotations

from pathlib import Path

from a0_plugin_testkit.real.deps import audit_dependencies
from a0_plugin_testkit.real.validator import static_validate
from a0_plugin_testkit.scan_scope import is_repo_scaffolding


# ----- predicate ------------------------------------------------------------ #


def test_scaffolding_trees_are_detected() -> None:
    for rel in (
        "tests/conftest.py",
        "tests/_testkit/src/a0_plugin_testkit/x.py",
        ".github/workflows/plugin-e2e.yml",
        ".claude/temp/notes.py",
        ".gemini/styleguide.md",
        "dist/plugin.zip",
        "artifacts/trace.zip",
        ".git/config",
    ):
        assert is_repo_scaffolding(rel), rel


def test_shipped_plugin_code_is_not_detected() -> None:
    for rel in (
        "hooks.py",
        "__init__.py",
        "extensions/python/system_prompt/_10_nudge.py",
        "api/handlers.py",
        "skills/mermaid/SKILL.md",
        "webui/thumbnail.png",
    ):
        assert not is_repo_scaffolding(rel), rel


def test_boundary_root_test_file_is_not_scaffolding() -> None:
    # The predicate matches directories, not file names — a root-level
    # ``test_hook.py`` is still audited. (The security check's separate
    # ``test_`` heuristic is deliberately not duplicated here.)
    assert not is_repo_scaffolding("test_hook.py")


# ----- dependency audit ----------------------------------------------------- #


def _fake_a0_root(tmp_path: Path) -> Path:
    root = tmp_path / "fake-a0"
    root.mkdir()
    (root / "requirements.txt").write_text("", encoding="utf-8")
    return root


def test_deps_audit_skips_scaffolding_but_not_plugin_code(tmp_path: Path) -> None:
    plugin = tmp_path / "my_plugin"
    (plugin / "tests").mkdir(parents=True)
    (plugin / "tests" / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (plugin / "hooks.py").write_text(
        "import pandas\n", encoding="utf-8"  # undeclared on purpose
    )
    audit = audit_dependencies(plugin, a0_root=_fake_a0_root(tmp_path))

    audited = {site.path for site in audit.third_party}
    assert "tests/conftest.py" not in audited, "scaffolding must be skipped"
    assert "hooks.py" in audited, "shipped code must still be audited"
    assert [site.module for site in audit.undeclared] == ["pandas"]


# ----- validator ------------------------------------------------------------- #


def _root_layout_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "my-plugin-repo"  # repo name ≠ plugin name (root layout)
    repo.mkdir()
    (repo / ".devkit.yml").write_text("plugin_dir: .\n", encoding="utf-8")
    (repo / "plugin.yaml").write_text(
        "name: my_plugin\ntitle: X\ndescription: Y\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    return repo


def test_dir_mismatch_not_enforced_for_root_layout(tmp_path: Path) -> None:
    report = static_validate(_root_layout_repo(tmp_path))
    codes = {f.code for f in report.findings}
    assert "manifest.name.dir_mismatch" not in codes


def test_dir_mismatch_still_enforced_for_subdir_layout(tmp_path: Path) -> None:
    # Same mismatched name, but no .devkit.yml inside the plugin dir → the
    # invariant still holds (subdir layout, and runtime usr/plugins/<name>).
    plugin = _root_layout_repo(tmp_path).rename(tmp_path / "my_plugin_wrong_dir")
    (plugin / ".devkit.yml").unlink()
    report = static_validate(plugin)
    codes = {f.code for f in report.findings}
    assert "manifest.name.dir_mismatch" in codes


def test_pycache_in_scaffolding_is_not_flagged(tmp_path: Path) -> None:
    repo = _root_layout_repo(tmp_path)
    (repo / "tests" / "__pycache__").mkdir(parents=True)
    (repo / "tests" / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
    report = static_validate(repo)
    pycache = [f for f in report.findings if f.code == "structure.pycache"]
    assert pycache == [], "scaffolding __pycache__ must not be flagged"

    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
    report = static_validate(repo)
    pycache = [f for f in report.findings if f.code == "structure.pycache"]
    assert [f.path for f in pycache] == ["__pycache__"]
