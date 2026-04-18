"""Static plugin validator — fast deterministic checks for CI.

A0's built-in `_plugin_validator` runs an LLM audit — thorough but slow and
expensive. For per-commit testing we want fast, deterministic checks. This
module encodes the mechanical subset of A0's checklist (manifest, structure,
extension points, obvious security anti-patterns) and returns a structured
report.

For LLM-based deep audit, use `a0_plugin_testkit.real.llm_validator` (once the
fake-LLM harness is in place).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import yaml

from ..discovery import (
    discover_html_surfaces,
    discover_js_hooks,
)


_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_VALID_SETTINGS_SECTIONS = {"agent", "external", "mcp", "developer", "backup"}

# Patterns that almost certainly indicate a committed secret.
# Tight set by design: false positives here burn developer trust.
_SECRET_PATTERNS = [
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{30,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("jwt", re.compile(r"\bey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]

_EVAL_EXEC_RE = re.compile(r"(?<!\w)(?:eval|exec)\s*\(")

DEFAULT_CHECKS: tuple[str, ...] = (
    "manifest",
    "structure",
    "extension_points",
    "security",
)


@dataclass(frozen=True)
class ValidationFinding:
    check: str        # "manifest" | "structure" | "extension_points" | "security"
    severity: str     # "error" | "warning" | "info"
    code: str         # machine-friendly, e.g. "manifest.name.missing"
    message: str      # human-readable
    path: str | None = None  # relative-to-plugin-dir path when applicable

    def __str__(self) -> str:
        loc = f" [{self.path}]" if self.path else ""
        return f"{self.severity.upper():7}  {self.code}{loc}: {self.message}"


@dataclass
class ValidationReport:
    plugin_dir: Path
    findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    def summary(self) -> str:
        lines = [f"ValidationReport({self.plugin_dir}): {len(self.findings)} findings"]
        for f in self.findings:
            lines.append(f"  {f}")
        if not self.findings:
            lines.append("  (clean)")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Individual check implementations
# --------------------------------------------------------------------------- #


def _check_manifest(plugin_dir: Path) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    manifest = plugin_dir / "plugin.yaml"

    if not manifest.is_file():
        findings.append(ValidationFinding(
            check="manifest",
            severity="error",
            code="manifest.missing",
            message="plugin.yaml not found at plugin root",
            path="plugin.yaml",
        ))
        return findings

    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        findings.append(ValidationFinding(
            check="manifest",
            severity="error",
            code="manifest.parse_error",
            message=f"plugin.yaml failed to parse: {e}",
            path="plugin.yaml",
        ))
        return findings

    if not isinstance(data, dict):
        findings.append(ValidationFinding(
            check="manifest",
            severity="error",
            code="manifest.not_mapping",
            message="plugin.yaml top level must be a mapping",
            path="plugin.yaml",
        ))
        return findings

    for key in ("name", "title", "description", "version"):
        if not data.get(key):
            findings.append(ValidationFinding(
                check="manifest",
                severity="error",
                code=f"manifest.{key}.missing",
                message=f"plugin.yaml missing or empty field: {key}",
                path="plugin.yaml",
            ))

    name = data.get("name")
    if isinstance(name, str):
        if not _NAME_RE.match(name):
            findings.append(ValidationFinding(
                check="manifest",
                severity="error",
                code="manifest.name.format",
                message=f"plugin name {name!r} must match {_NAME_RE.pattern}",
                path="plugin.yaml",
            ))
        if name != plugin_dir.name:
            findings.append(ValidationFinding(
                check="manifest",
                severity="error",
                code="manifest.name.dir_mismatch",
                message=f"plugin.yaml name={name!r} must equal dir name {plugin_dir.name!r}",
                path="plugin.yaml",
            ))

    sections = data.get("settings_sections") or []
    if isinstance(sections, list):
        invalid = [s for s in sections if s not in _VALID_SETTINGS_SECTIONS]
        if invalid:
            findings.append(ValidationFinding(
                check="manifest",
                severity="error",
                code="manifest.sections.invalid",
                message=f"unknown settings_sections: {invalid} "
                        f"(valid: {sorted(_VALID_SETTINGS_SECTIONS)})",
                path="plugin.yaml",
            ))
    else:
        findings.append(ValidationFinding(
            check="manifest",
            severity="warning",
            code="manifest.sections.not_list",
            message="settings_sections should be a list",
            path="plugin.yaml",
        ))

    for bool_key in ("per_project_config", "per_agent_config", "always_enabled"):
        if bool_key in data and not isinstance(data[bool_key], bool):
            findings.append(ValidationFinding(
                check="manifest",
                severity="warning",
                code=f"manifest.{bool_key}.not_bool",
                message=f"{bool_key} should be boolean (got {type(data[bool_key]).__name__})",
                path="plugin.yaml",
            ))

    return findings


def _check_structure(plugin_dir: Path) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    hooks = plugin_dir / "hooks.py"
    if hooks.is_file():
        body = hooks.read_text(encoding="utf-8", errors="ignore")
        has_enable = "on_plugin_enabled" in body
        has_disable = "on_plugin_disabled" in body
        if has_enable and not has_disable:
            findings.append(ValidationFinding(
                check="structure",
                severity="warning",
                code="structure.hooks.asymmetric",
                message="hooks.py defines on_plugin_enabled but not on_plugin_disabled",
                path="hooks.py",
            ))
        if has_disable and not has_enable:
            findings.append(ValidationFinding(
                check="structure",
                severity="warning",
                code="structure.hooks.asymmetric",
                message="hooks.py defines on_plugin_disabled but not on_plugin_enabled",
                path="hooks.py",
            ))

    # Catch __pycache__ accidentally zipped in.
    pycache_dirs = list(plugin_dir.rglob("__pycache__"))
    for pd in pycache_dirs:
        findings.append(ValidationFinding(
            check="structure",
            severity="warning",
            code="structure.pycache",
            message="__pycache__ directory present — should be gitignored / zip-excluded",
            path=str(pd.relative_to(plugin_dir)),
        ))

    # config.html must coexist with settings_sections (warn, don't error).
    config_html = plugin_dir / "webui" / "config.html"
    manifest = plugin_dir / "plugin.yaml"
    if manifest.is_file():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("settings_sections") and not config_html.is_file():
                findings.append(ValidationFinding(
                    check="structure",
                    severity="warning",
                    code="structure.missing_config_html",
                    message="settings_sections declared but webui/config.html is missing",
                    path="webui/config.html",
                ))
        except yaml.YAMLError:
            pass  # manifest check already reported the parse error

    return findings


def _check_extension_points(
    plugin_dir: Path, *, a0_root: Path | None = None
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    webui_ext = plugin_dir / "extensions" / "webui"
    if not webui_ext.is_dir():
        return findings

    html_surfaces = discover_html_surfaces(a0_root) if a0_root else discover_html_surfaces()
    js_hooks = discover_js_hooks(a0_root) if a0_root else discover_js_hooks()
    valid = html_surfaces | js_hooks

    for child in sorted(webui_ext.iterdir()):
        if not child.is_dir():
            continue
        if child.name in valid:
            # Optional: warn if an HTML-surface folder contains .js or vice-versa.
            is_html = child.name in html_surfaces
            is_js = child.name in js_hooks
            html_files = list(child.glob("*.html"))
            js_files = list(child.glob("*.js")) + list(child.glob("*.mjs"))
            if is_html and not is_js and not html_files:
                findings.append(ValidationFinding(
                    check="extension_points",
                    severity="warning",
                    code="extension_points.html_surface.empty",
                    message=f"HTML surface folder has no .html files",
                    path=str(child.relative_to(plugin_dir)),
                ))
            if is_js and not is_html and not js_files:
                findings.append(ValidationFinding(
                    check="extension_points",
                    severity="warning",
                    code="extension_points.js_hook.empty",
                    message=f"JS hook folder has no .js/.mjs files",
                    path=str(child.relative_to(plugin_dir)),
                ))
            continue

        findings.append(ValidationFinding(
            check="extension_points",
            severity="error",
            code="extension_points.unknown",
            message=f"unknown extension-point name {child.name!r} "
                    f"(not in {len(html_surfaces)} HTML surfaces or {len(js_hooks)} JS hooks)",
            path=str(child.relative_to(plugin_dir)),
        ))

    return findings


def _check_security(plugin_dir: Path) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for py in plugin_dir.rglob("*.py"):
        try:
            body = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(py.relative_to(plugin_dir))

        # Skip obviously test-scoped files — they may legitimately probe eval/exec.
        is_test = "/tests/" in f"/{rel}/" or rel.startswith("tests/") or "/test_" in f"/{rel}"

        if _EVAL_EXEC_RE.search(body) and not is_test:
            findings.append(ValidationFinding(
                check="security",
                severity="warning",
                code="security.eval_or_exec",
                message="eval() or exec() found — audit carefully",
                path=rel,
            ))

    # Scan every text-ish file for secret patterns.
    scan_suffixes = {".py", ".yaml", ".yml", ".json", ".md", ".html", ".js", ".mjs", ".ts", ".toml", ".env", ".conf"}
    for f in plugin_dir.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in scan_suffixes:
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(f.relative_to(plugin_dir))
        for kind, pat in _SECRET_PATTERNS:
            if pat.search(body):
                findings.append(ValidationFinding(
                    check="security",
                    severity="error",
                    code=f"security.secret.{kind}",
                    message=f"likely committed {kind} — remove and rotate",
                    path=rel,
                ))

    return findings


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def static_validate(
    plugin_dir: Path,
    *,
    checks: Sequence[str] | None = None,
    a0_root: Path | None = None,
) -> ValidationReport:
    """Run the static checks against ``plugin_dir`` and return a ``ValidationReport``."""
    plugin_dir = Path(plugin_dir).resolve()
    selected = tuple(checks) if checks else DEFAULT_CHECKS
    report = ValidationReport(plugin_dir=plugin_dir)

    if "manifest" in selected:
        report.findings.extend(_check_manifest(plugin_dir))
    if "structure" in selected:
        report.findings.extend(_check_structure(plugin_dir))
    if "extension_points" in selected:
        report.findings.extend(_check_extension_points(plugin_dir, a0_root=a0_root))
    if "security" in selected:
        report.findings.extend(_check_security(plugin_dir))

    return report


def assert_validator_clean(
    report: ValidationReport,
    *,
    allow_warnings: bool = True,
) -> None:
    """Fail the test if the report has errors (optionally also if warnings)."""
    problems: list[ValidationFinding] = list(report.errors)
    if not allow_warnings:
        problems.extend(report.warnings)
    if not problems:
        return
    raise AssertionError(
        f"static_validate({report.plugin_dir}) reported "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s):\n"
        + "\n".join(f"  {f}" for f in problems)
    )


__all__ = (
    "ValidationFinding",
    "ValidationReport",
    "DEFAULT_CHECKS",
    "static_validate",
    "assert_validator_clean",
)
