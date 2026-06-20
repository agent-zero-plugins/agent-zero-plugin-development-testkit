---
name: a0-bootstrap-plugin
description: "Bootstrap a new Agent Zero plugin repository with full build system, quality tooling, CI pipeline, testing, and skill symlink support. Use when creating a new plugin repo from scratch, scaffolding a plugin project, or setting up the build/test/release pipeline for an Agent Zero plugin."
version: "1.0.0"
author: "Agent Zero Operator"
tags: ["plugins", "bootstrap", "scaffolding", "build-system", "ci", "testing"]
trigger_patterns:
  - "bootstrap plugin"
  - "new plugin repo"
  - "scaffold plugin"
  - "create plugin repository"
  - "set up plugin project"
  - "plugin build system"
  - "plugin ci pipeline"
---

# Bootstrap an Agent Zero Plugin Repository

This skill documents the complete process for creating a production-ready Agent Zero plugin repository — the same tooling, structure, and conventions used in `agent-zero-plugin-gitnexus`.

## Overview

An Agent Zero plugin repo is a **build/packaging** project. It takes an upstream tool (typically a Claude plugin, MCP server, or standalone tool) and packages it as a self-contained Agent Zero plugin with:

- A `Makefile`-driven build system
- Quality gates (linting, type checking, formatting)
- Behavioral tests (not unit tests — test what the plugin *does*)
- CI/CD pipeline with automated releases
- Pre-commit hooks
- Shared skills via submodule

---

## 1. Repository Structure

```
agent-zero-plugin-<name>/
├── Makefile                        # Build system — the entry point
├── pyproject.toml                  # Python tooling config (ruff, mypy, pytest)
├── .pre-commit-config.yaml         # Pre-commit hooks
├── .yamllint.yml                   # YAML linting config
├── .gitignore                      # Standard ignores + generated symlinks
├── .gitmodules                     # Submodule declarations
├── CLAUDE.md                       # Agent instructions for this repo
├── README.md                       # User-facing documentation
├── LICENSE                         # License file
├── src/                            # Plugin source files (our code)
│   ├── hooks.py                    # MCP server registration on enable/disable
│   ├── execute.py                  # User-triggered action (e.g., re-index)
│   ├── default_config.yaml         # Default plugin settings
│   ├── plugin.yaml.tpl             # Template — version injected at build
│   ├── skill-meta.json             # Tags & trigger patterns per skill
│   ├── prompts/                    # System prompt for tool awareness
│   │   └── agent.system.tool.<name>.md
│   └── extensions/                 # Agent Zero lifecycle extensions
│       └── python/
│           └── system_prompt/
│               └── _70_<name>_context.py
├── scripts/                        # Build scripts
│   ├── gen-plugin-yaml.py          # Template → plugin.yaml
│   └── transform-skills.py         # Enrich SKILL.md frontmatter
├── tests/                          # Behavioral test suite
│   ├── conftest.py                 # Shared fixtures
│   ├── test_build_golden.py        # Build output structure and content
│   ├── test_transform_behavior.py  # Skill transformation pipeline
│   ├── test_hooks_behavior.py      # MCP registration/unregistration
│   └── test_schema.py              # skill-meta.json ↔ upstream sync
├── upstream/                       # Git submodule — DO NOT EDIT
├── skills/                         # Git submodule — operator skills
├── dist/                           # Build output (gitignored)
└── .github/workflows/
    └── build.yml                   # CI pipeline
```

---

## 2. Initialize the Repository

```bash
# Create the repo
mkdir agent-zero-plugin-<name>
cd agent-zero-plugin-<name>
git init

# Add the upstream tool as a submodule
git submodule add <upstream-repo-url> upstream

# Add the shared plugins-org skills as a submodule
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugins-skills.git .skills
```

---

## 3. pyproject.toml

This is the single config file for all Python tooling:

```toml
[project]
name = "agent-zero-plugin-<name>"
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = [
  "E", "W",   # pycodestyle
  "F",         # pyflakes
  "I",         # isort
  "UP",        # pyupgrade
  "B",         # bugbear — catches real bugs
  "SIM",       # simplify
  "RUF",       # ruff-specific
]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "scripts"]
```

**Key decisions:**
- `ignore_missing_imports = true` — Agent Zero stubs don't exist in this repo
- `pythonpath = ["src", "scripts"]` — so pytest can import both
- `line-length = 99` — wider than default, narrower than chaos
- Bugbear (`B`) catches real bugs like mutable default arguments

---

## 4. Pre-commit Hooks

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
        args: [--allow-multiple-documents]
      - id: check-json
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict

  - repo: https://github.com/adrienverge/yamllint
    rev: v1.35.1
    hooks:
      - id: yamllint
        args: [-c, .yamllint.yml]
        files: \.(yaml|yml)$
```

Install with: `pre-commit install`

### `.yamllint.yml`

```yaml
extends: default
rules:
  line-length:
    max: 120
  truthy:
    check-keys: false
  document-start: disable
```

---

## 5. Makefile (Build System)

The Makefile is the single entry point for all operations. Key design principles:

- **Dependency tracking** — only rebuild when sources change (stamp files)
- **Submodule-aware** — `submodule` target initializes recursively
- **Quality gates** — `make ci` runs the full pipeline: lint → typecheck → build → verify → test
- **Skills integration** — `link-skills` / `unlink-skills` delegate to the skills submodule

### Template

```makefile
SHELL := /bin/bash
.DEFAULT_GOAL := build

# ── Paths ──────────────────────────────────────────────────────────────────────
UPSTREAM         := upstream
SKILLS_SUBMODULE := skills
# Adjust these to match your upstream's structure:
# UPSTREAM_PLUGIN  := $(UPSTREAM)/path-to-plugin-dir
# PLUGIN_JSON      := $(UPSTREAM_PLUGIN)/plugin.json  # or wherever version lives
SRC              := src
SCRIPTS          := scripts
DIST             := dist
BUILD_DIR        := $(DIST)/<plugin-name>
ZIP_NAME         := <plugin-name>-a0-plugin.zip
ZIP_PATH         := $(DIST)/$(ZIP_NAME)

# ── Derived values ───────────────────────────────────────────────────────────
# Extract version from upstream metadata:
VERSION := $(shell python3 -c "import json; print(json.load(open('$(PLUGIN_JSON)'))['version'])" 2>/dev/null || echo '0.0.0')

# ── Source files for dependency tracking ─────────────────────────────────────
SRC_FILES := $(shell find $(SRC) -type f 2>/dev/null)

.PHONY: build clean verify help submodule lint typecheck test ci link-skills unlink-skills

## build: Build the plugin zip (default target)
build: $(ZIP_PATH)

$(ZIP_PATH): $(BUILD_DIR)/.stamp
	@echo "[pack]  Creating $(ZIP_NAME) (v$(VERSION))..."
	@rm -f "$(ZIP_PATH)"
	@cd "$(DIST)" && zip -rq "$(abspath $(ZIP_PATH))" <plugin-name>/
	@echo "[done]  $(ZIP_PATH)"

$(BUILD_DIR)/.stamp: $(SRC_FILES)
	@echo "[build] Plugin v$(VERSION)"
	@rm -rf "$(BUILD_DIR)"
	@mkdir -p "$(BUILD_DIR)"
	# 1. Generate plugin.yaml from template
	@python3 $(SCRIPTS)/gen-plugin-yaml.py \
		--template  $(SRC)/plugin.yaml.tpl \
		--plugin-json $(PLUGIN_JSON) \
		--output     $(BUILD_DIR)/plugin.yaml
	# 2. Transform skills (if upstream has skills)
	@python3 $(SCRIPTS)/transform-skills.py \
		--skills-dir $(UPSTREAM_SKILLS_DIR) \
		--meta-file  $(SRC)/skill-meta.json \
		--version    $(VERSION) \
		--output-dir $(BUILD_DIR)/skills
	# 3. Copy static source files
	@cp $(SRC)/hooks.py          $(BUILD_DIR)/
	@cp $(SRC)/execute.py        $(BUILD_DIR)/
	@cp $(SRC)/default_config.yaml $(BUILD_DIR)/
	@mkdir -p $(BUILD_DIR)/prompts
	@cp $(SRC)/prompts/*.md      $(BUILD_DIR)/prompts/
	@mkdir -p $(BUILD_DIR)/extensions/python/system_prompt
	@cp $(SRC)/extensions/python/system_prompt/*.py \
		$(BUILD_DIR)/extensions/python/system_prompt/
	# 4. Copy LICENSE and README
	@cp LICENSE $(BUILD_DIR)/ 2>/dev/null || true
	@cp README.md $(BUILD_DIR)/ 2>/dev/null || true
	@touch "$(BUILD_DIR)/.stamp"

## submodule: Initialize / update the upstream submodule
submodule:
	@git submodule update --init --recursive

## clean: Remove all build artifacts
clean:
	@rm -rf "$(DIST)"

## verify: Validate the built plugin structure
verify: $(ZIP_PATH)
	@echo "[verify] Checking plugin structure..."
	@for f in plugin.yaml hooks.py execute.py default_config.yaml; do \
		if [ ! -f "$(BUILD_DIR)/$$f" ]; then \
			echo "  FAIL: Missing $$f"; exit 1; \
		fi; \
		echo "  OK:   $$f"; \
	done
	@# Validate Python syntax
	@for f in $$(find $(BUILD_DIR) -name '*.py'); do \
		python3 -c "import ast; ast.parse(open('$$f').read())" || \
			{ echo "  FAIL: Invalid Python: $$f"; exit 1; }; \
	done
	@echo "[verify] All checks passed ✓"

## lint: Run ruff linter and formatter check
lint:
	@ruff check src/ scripts/ tests/
	@ruff format --check src/ scripts/ tests/

## typecheck: Run mypy on plugin source and scripts
typecheck:
	@mypy src/ scripts/ --ignore-missing-imports

## test: Run behavioral tests
test: build
	@pytest tests/ -v

## ci: Full quality gate (lint → typecheck → build → verify → test)
ci: lint typecheck build verify test
	@echo "All quality gates passed ✓  (v$(VERSION))"

## link-skills: Symlink operator skills into Claude, Copilot & Antigravity locations
link-skills:
	@git submodule update --init --recursive -- $(SKILLS_SUBMODULE)
	@$(MAKE) -C $(SKILLS_SUBMODULE) link-skills PARENT_ROOT=$(CURDIR)

## unlink-skills: Remove operator skill symlinks
unlink-skills:
	@$(MAKE) -C $(SKILLS_SUBMODULE) unlink-skills PARENT_ROOT=$(CURDIR)

## help: Show this help
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /' | column -t -s ':'
```

---

## 6. Source Files

### `src/plugin.yaml.tpl`

Template with placeholders replaced at build time:

```yaml
name: <plugin-name>
title: <Plugin Title>
description: "__DESCRIPTION__"
version: "__VERSION__"
always_enabled: false
settings_sections:
  - agent
per_project_config: true
per_agent_config: false
```

### `src/hooks.py`

Registers/unregisters the MCP server when the plugin is enabled/disabled. Must be **idempotent** — calling `on_plugin_enabled` twice is safe.

Required pattern:

```python
"""Plugin hooks for Agent Zero."""
from __future__ import annotations

import json
import shutil
from typing import Any

from helpers import settings
from helpers.print_style import PrintStyle

PLUGIN_NAME = "<name>"

_MCP_SERVER_CONFIG = {
    "mcpServers": {
        "<name>": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "<package>", "mcp"],
            "env": {},
        }
    }
}

def on_plugin_enabled(**kwargs: Any) -> None:
    """Called when the plugin is enabled. Registers the MCP server."""
    # Check prerequisites (e.g., node/npx on PATH)
    if not shutil.which("npx"):
        PrintStyle(...).print("[<Name>] Warning: npx not found.")
        return
    _register_mcp_server()

def on_plugin_disabled(**kwargs: Any) -> None:
    """Called when the plugin is disabled. Removes the MCP server."""
    _unregister_mcp_server()

def _register_mcp_server() -> None:
    """Merge the MCP server into the current mcp_servers setting."""
    current_raw = getattr(settings.get_settings(), "mcp_servers", '{"mcpServers": {}}')
    current = json.loads(current_raw) if isinstance(current_raw, str) else current_raw
    servers = current.get("mcpServers", {})
    if "<name>" in servers:
        return  # Already registered — idempotent
    servers["<name>"] = _MCP_SERVER_CONFIG["mcpServers"]["<name>"]
    current["mcpServers"] = servers
    settings.set_setting("mcp_servers", json.dumps(current, indent=2))

def _unregister_mcp_server() -> None:
    """Remove the MCP server from the mcp_servers setting."""
    current_raw = getattr(settings.get_settings(), "mcp_servers", '{"mcpServers": {}}')
    current = json.loads(current_raw) if isinstance(current_raw, str) else current_raw
    servers = current.get("mcpServers", {})
    if "<name>" not in servers:
        return  # Not registered — noop
    del servers["<name>"]
    current["mcpServers"] = servers
    settings.set_setting("mcp_servers", json.dumps(current, indent=2))
```

**Critical rules:**
- Always guard with `if "<name>" in servers: return` for idempotency
- Always preserve other servers when registering/unregistering
- Wrap in try/except and log errors via `PrintStyle`

### `src/execute.py`

User-triggered action (e.g., re-index, setup). Must be an `async` function:

```python
"""Execute script for Agent Zero."""
from __future__ import annotations

import subprocess
from typing import Any

async def execute(**kwargs: Any) -> str:
    """User-triggered action. Returns a status message."""
    # Run the tool, return result
    result = subprocess.run([...], capture_output=True, text=True, timeout=300)
    return result.stdout if result.returncode == 0 else result.stderr
```

### `src/default_config.yaml`

```yaml
# Default plugin configuration.
pinned_skills:
  - <name>-guide    # Pin the guide skill so the agent always knows the tools
```

### `src/skill-meta.json`

Maps each upstream skill name to Agent Zero metadata:

```json
{
  "<name>-guide": {
    "tags": ["<domain>", "<name>", "reference"],
    "trigger_patterns": [
      "what <name> tools",
      "how to use <name>"
    ]
  }
}
```

**Rule:** Every upstream skill directory must have an entry here. The `test_schema.py` test enforces this.

### `src/prompts/agent.system.tool.<name>.md`

Markdown injected into the system prompt so the agent knows the tools exist:

```markdown
### <Tool Name> — <Domain> Tools

You have access to <Tool Name> MCP tools for <purpose>.

**Available tools** (via MCP):

| Tool | Purpose |
|---|---|
| `<name>_query` | Description |
| `<name>_context` | Description |

**Rules:**
- Before editing, run `<name>_impact` to check blast radius.
- If risk is HIGH, warn the user before proceeding.
```

### `src/extensions/python/system_prompt/_70_<name>_context.py`

The `_70_` prefix controls load order (lower = earlier). This extension reads the prompt template and appends it to the system prompt:

```python
"""Inject tool awareness into the agent system prompt."""
from __future__ import annotations

from typing import Any

from agent import LoopData
from helpers.extension import Extension


class <Name>ContextPrompt(Extension):
    async def execute(
        self,
        system_prompt: list[str] = [],
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ) -> None:
        if not self.agent:
            return
        system_prompt.append(self.agent.read_prompt("agent.system.tool.<name>.md"))
```

---

## 7. Build Scripts

### `scripts/gen-plugin-yaml.py`

Simple string substitution — reads the template, replaces `__VERSION__` and `__DESCRIPTION__` from upstream metadata, writes the output.

### `scripts/transform-skills.py`

Reads each upstream `SKILL.md`, parses YAML frontmatter with **regex** (not a full YAML parser — intentional, to avoid adding PyYAML as a build dependency), enriches it with Agent Zero fields from `skill-meta.json`, and writes the result.

**Design decision:** Regex-based YAML parsing is deliberate. It keeps the build dependency-free (no PyYAML needed at build time). The regex handles simple `key: value` pairs which is all that skill frontmatter uses.

---

## 8. Testing Philosophy

### Principles

- **Behavioral tests** — test what the plugin *does*, not how it's implemented
- **No contract tests** — don't test that a function returns the right type
- **Golden tests** — build the plugin and assert the artifact is structurally correct
- **Schema tests** — catch the most common maintenance mistake: adding a skill upstream and forgetting to update `skill-meta.json`
- **Subprocess-based** — test scripts via their CLI interface, not by importing internals
- **Mock only Agent Zero** — the framework doesn't exist in this repo, so mock `helpers.settings`, `helpers.print_style`, etc.

### Test Structure

```
tests/
├── conftest.py                 # Shared fixtures (built_plugin, upstream_version, etc.)
├── test_build_golden.py        # Build output structure and content
├── test_transform_behavior.py  # Skill transformation pipeline (subprocess-based)
├── test_hooks_behavior.py      # MCP registration/unregistration logic
└── test_schema.py              # skill-meta.json ↔ upstream sync
```

### `conftest.py` Pattern

Session-scoped fixtures that build once and share across all tests:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "<plugin-name>"

@pytest.fixture(scope="session")
def built_plugin() -> Path:
    """Build the plugin once for the entire test session."""
    subprocess.run(["make", "build"], cwd=ROOT, check=True)
    assert DIST.is_dir()
    return DIST

@pytest.fixture(scope="session")
def upstream_version() -> str:
    """Return the version string from upstream metadata."""
    # Read from upstream's version file
    ...

@pytest.fixture(scope="session")
def upstream_skill_names() -> set[str]:
    """Return the set of skill directory names from upstream."""
    ...

@pytest.fixture(scope="session")
def skill_meta() -> dict:
    """Return the parsed skill-meta.json."""
    ...
```

### Key Test Patterns

**Golden test** — build and verify structure:
```python
def test_required_files_present(built_plugin: Path) -> None:
    required = ["plugin.yaml", "hooks.py", "execute.py", "default_config.yaml"]
    for rel in required:
        assert (built_plugin / rel).is_file(), f"Missing: {rel}"
```

**Schema test** — catch forgotten metadata:
```python
def test_every_upstream_skill_has_meta_entry(
    upstream_skill_names: set[str], skill_meta: dict
) -> None:
    missing = upstream_skill_names - set(skill_meta.keys())
    assert not missing, f"Missing from skill-meta.json: {missing}"
```

**Hooks behavioral test** — mock Agent Zero, test observable behavior:
```python
def test_registers_into_empty_config() -> None:
    hooks = _import_hooks()  # import with mocked Agent Zero deps
    mock_settings = _make_mock_settings('{"mcpServers": {}}')
    hooks.settings.get_settings.return_value = mock_settings
    hooks._register_mcp_server()
    result = json.loads(hooks.settings.set_setting.call_args[0][1])
    assert "<name>" in result["mcpServers"]
```

**Transform behavioral test** — subprocess, real filesystem:
```python
def test_skill_gets_enriched(tmp_path: Path) -> None:
    # Create mini-filesystem
    _make_skill(skills_dir, "my-skill", '---\nname: "My Skill"\n---\nBody.\n')
    _make_meta(meta_file, {"my-skill": {"tags": ["t"], "trigger_patterns": ["p"]}})
    # Run the script as a subprocess (exactly like make does)
    result = subprocess.run([sys.executable, str(TRANSFORM_SCRIPT), ...], ...)
    assert result.returncode == 0
    output = (out / "my-skill" / "SKILL.md").read_text()
    assert 'version: "1.0.0"' in output
```

---

## 9. CI Pipeline

### `.github/workflows/build.yml`

Three jobs:

1. **quality** — lint + typecheck (fast, fails early)
2. **build** (depends on quality) — build + verify + test + upload artifact
3. **release** (on `v*` tags, depends on build) — create GitHub Release with zip

```yaml
name: CI

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff mypy pytest pyyaml
      - run: |
          ruff check src/ scripts/ tests/
          ruff format --check src/ scripts/ tests/
      - run: mypy src/ scripts/ --ignore-missing-imports

  build:
    needs: quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pytest pyyaml
      - run: make build
      - run: make verify
      - run: pytest tests/ -v
      - uses: actions/upload-artifact@v4
        with:
          name: <plugin-name>-a0-plugin-v${{ steps.version.outputs.version }}
          path: dist/<plugin-name>-a0-plugin.zip
          retention-days: 90

  release:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: make build
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/<plugin-name>-a0-plugin.zip
          generate_release_notes: true
```

**Critical:** Always use `submodules: recursive` in checkout — the build depends on the upstream submodule.

---

## 10. .gitignore

```gitignore
# Build output
dist/
build/

# Python
.venv/
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Temp
*.tmp
*.bak

# Type checking
.mypy_cache/

# Testing
.pytest_cache/

# Pre-commit
.pre-commit-cache/
```

---

## 11. CLAUDE.md

The `CLAUDE.md` file at the repo root provides agent instructions. It should document:

- Project overview (what this repo is)
- Repository layout (directory tree)
- Key commands (`make`, `make ci`, `make lint`, etc.)
- Development workflow (never edit upstream, run `make ci` before pushing)
- Quality tools table (ruff, mypy, pytest, yamllint, pre-commit)
- Architecture decisions (why regex parsing, why subprocess tests, etc.)
- Testing philosophy (behavioral, golden, schema — no contract tests)
- Common tasks (adding a new upstream skill, changing MCP config, debugging builds)
- CI pipeline description
- Conventions (Python 3.11+, `from __future__ import annotations`, `Path` over `os.path`, etc.)

---

## 12. Conventions

- Python 3.11+, `from __future__ import annotations` in **every** file
- Ruff for formatting (double quotes, 99-char lines)
- Type hints on all function signatures
- Docstrings on all public functions and classes
- `Path` over `os.path` for filesystem operations
- Subprocess calls for testing scripts (test the CLI interface, not internals)
- Never edit files under `upstream/` — that's a git submodule
- Run `make ci` before pushing

---

## 13. Bootstrapping Checklist

When creating a new plugin repo, verify each item:

- [ ] Repository created with `git init`
- [ ] Upstream tool added as submodule at `upstream/`
- [ ] Operator skills added as submodule at `skills/`
- [ ] `pyproject.toml` with ruff, mypy, pytest config
- [ ] `.pre-commit-config.yaml` with ruff, yaml, json, whitespace hooks
- [ ] `.yamllint.yml` with relaxed rules
- [ ] `.gitignore` with build output, Python, IDE, generated symlinks
- [ ] `Makefile` with build, clean, verify, lint, typecheck, test, ci, link-skills targets
- [ ] `src/plugin.yaml.tpl` with `__VERSION__` and `__DESCRIPTION__` placeholders
- [ ] `src/hooks.py` with idempotent MCP registration
- [ ] `src/execute.py` with user-triggered action
- [ ] `src/default_config.yaml` with pinned skills
- [ ] `src/skill-meta.json` with entries for every upstream skill
- [ ] `src/prompts/agent.system.tool.<name>.md` with tool documentation
- [ ] `src/extensions/python/system_prompt/_70_<name>_context.py` extension
- [ ] `scripts/gen-plugin-yaml.py` for template substitution
- [ ] `scripts/transform-skills.py` for skill enrichment
- [ ] `tests/conftest.py` with session-scoped fixtures
- [ ] `tests/test_build_golden.py` for build structure validation
- [ ] `tests/test_hooks_behavior.py` for MCP registration tests
- [ ] `tests/test_schema.py` for skill-meta sync validation
- [ ] `tests/test_transform_behavior.py` for skill transformation tests
- [ ] `.github/workflows/build.yml` with quality → build → release pipeline
- [ ] `CLAUDE.md` with agent instructions
- [ ] `README.md` with user documentation
- [ ] `LICENSE` file
- [ ] `pre-commit install` run
- [ ] `make ci` passes
- [ ] `make link-skills` creates symlinks in `.claude/`, `.copilot/`, `.antigravity/`
