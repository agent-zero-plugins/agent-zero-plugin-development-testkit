---
name: a0-plugin-architecture
description: "Comprehensive reference for the Agent Zero plugin system architecture. Covers plugin discovery, manifest format, extension points, lifecycle hooks, tools, API handlers, skills, settings, activation, MCP integration, frontend extensions, and the two-runtime model. Use when someone asks how plugins work, what a plugin can do, or needs to understand the plugin system internals."
version: 1.0.0
author: Agent Zero Community
tags: ["plugins", "architecture", "reference", "internals", "extension-points", "lifecycle"]
trigger_patterns:
  - "how do plugins work"
  - "plugin architecture"
  - "plugin system"
  - "what can a plugin do"
  - "plugin internals"
  - "extension points"
  - "plugin lifecycle"
  - "plugin reference"
  - "plugin guide"
---

# Agent Zero Plugin Architecture — Complete Reference

This skill documents every aspect of the Agent Zero plugin system: discovery, manifest, extension points, tools, API handlers, skills, settings, activation, hooks, frontend extensions, MCP integration, and the two-runtime model.

Related skills:
- `/a0/skills/a0-create-plugin/SKILL.md` — Step-by-step plugin creation
- `/a0/skills/a0-plugin-router/SKILL.md` — Routes plugin tasks to specialist skills
- `/a0/skills/a0-debug-plugin/SKILL.md` — Troubleshooting plugins
- `/a0/skills/a0-contribute-plugin/SKILL.md` — Publishing to the Plugin Index

Primary references:
- `/a0/docs/agents/AGENTS.plugins.md`
- `/a0/docs/developer/plugins.md`
- `/a0/helpers/plugins.py` — Discovery, toggle, config resolution
- `/a0/helpers/extension.py` — Extension base class, `@extensible` decorator
- `/a0/helpers/tool.py` — Tool base class
- `/a0/helpers/api.py` — ApiHandler base class, security decorators
- `/a0/helpers/skills.py` — Skill discovery, `get_skill_roots()`

---

## 1. Architecture Overview

Agent Zero uses a **convention-over-configuration** plugin model. Plugins are directories discovered by the presence of a `plugin.yaml` manifest. Each plugin can contribute:

| Capability | Directory/File | Description |
|---|---|---|
| **Manifest** | `plugin.yaml` | Required. Name, version, settings scope, activation rules |
| **Agent Tools** | `tools/` | Python `Tool` subclasses — new capabilities the agent can invoke |
| **API Handlers** | `api/` | `ApiHandler` subclasses — custom HTTP endpoints |
| **Shared Helpers** | `helpers/` | Shared Python logic importable by tools/extensions |
| **Prompt Templates** | `prompts/` | Markdown templates injected into agent prompts |
| **Agent Profiles** | `agents/<profile>/agent.yaml` | Subagent definitions distributed by the plugin |
| **Skills** | `skills/<name>/SKILL.md` | Markdown skill files discoverable by the agent |
| **Backend Extensions** | `extensions/python/<point>/` | Named lifecycle hooks (system_prompt, monologue_start, etc.) |
| **Implicit Hooks** | `extensions/python/_functions/<module>/<qualname>/<start\|end>/` | Hook into any `@extensible`-decorated function |
| **Frontend Extensions** | `extensions/webui/<point>/` | HTML/JS injected into core UI breakpoints |
| **Settings UI** | `webui/config.html` | Plugin-specific settings panel in the WebUI |
| **Full Pages** | `webui/main.html` | Complete plugin pages/components |
| **Model Providers** | `conf/model_providers.yaml` | Add/override LLM and embedding providers |
| **Default Config** | `default_config.yaml` | Fallback settings values |
| **Plugin Script** | `execute.py` | User-triggered manual operations (setup, migration, repair) |
| **Runtime Hooks** | `hooks.py` | Framework-internal hooks (`install()`, `pre_update()`, config transforms) |
| **Activation Toggles** | `.toggle-1` / `.toggle-0` | File-based ON/OFF per scope |
| **Thumbnail** | `webui/thumbnail.{png,jpg,webp}` | Plugin list thumbnail image |
| **README** | `README.md` | Shown in Plugin List UI and Plugin Hub |
| **LICENSE** | `LICENSE` | Shown in Plugin List UI; required for Plugin Index submission |

---

## 2. Plugin Discovery

### Directory Roots (priority order)

1. `usr/plugins/` — User/custom plugins (highest priority)
2. `plugins/` — Core/built-in plugins

On name collisions, **user plugins take precedence**. Discovery logic is in `helpers/plugins.py`:

```python
def get_plugin_roots(plugin_name: str = "") -> List[str]:
    return [
        files.get_abs_path(files.USER_DIR, files.PLUGINS_DIR, plugin_name),
        files.get_abs_path(files.PLUGINS_DIR, plugin_name),
    ]
```

A directory is recognized as a plugin if it contains `plugin.yaml`. Hidden directories (starting with `.`) are ignored.

### File Watchers

The framework registers watchdogs on plugin directories. Changes to `extensions/`, `.toggle-*` files, or `hooks.py` trigger automatic cache invalidation and frontend reload notifications. Python file changes also trigger module namespace purging.

---

## 3. Plugin Manifest (`plugin.yaml`)

Every plugin **must** have a `plugin.yaml` at its root:

```yaml
name: my_plugin              # ^[a-z0-9_]+$, must match dir name
title: My Plugin             # UI display name
description: What it does.   # Short summary
version: 1.0.0               # Semantic version
settings_sections:           # Which Settings tabs show this plugin
  - agent                    # Valid: agent, external, mcp, developer, backup
per_project_config: false    # Enable project-scoped settings/toggles
per_agent_config: false      # Enable agent-profile-scoped settings/toggles
always_enabled: false        # Force ON, disable toggle controls (framework use)
```

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | `""` | Plugin identifier. Required for Plugin Index. Must be `^[a-z0-9_]+$` |
| `title` | string | `""` | UI display name |
| `description` | string | `""` | Short plugin summary |
| `version` | string | `""` | Plugin version string |
| `settings_sections` | list | `[]` | Settings tabs: `agent`, `external`, `mcp`, `developer`, `backup` |
| `per_project_config` | bool | `false` | Enables project-scoped settings and toggle rules |
| `per_agent_config` | bool | `false` | Enables agent-profile-scoped settings and toggle rules |
| `always_enabled` | bool | `false` | Forces ON, hides toggle controls in UI |

---

## 4. Recommended Directory Structure

```
usr/plugins/<plugin_name>/
├── plugin.yaml                   # Required: manifest
├── execute.py                    # Optional: user-triggered plugin script
├── hooks.py                      # Optional: framework runtime hooks
├── default_config.yaml           # Optional: fallback settings defaults
├── README.md                     # Optional locally; required for Plugin Index
├── LICENSE                       # Optional locally; required for Plugin Index
├── conf/
│   └── model_providers.yaml      # Optional: add/override model providers
├── api/                          # API handlers (ApiHandler subclasses)
├── tools/                        # Agent tools (Tool subclasses)
├── helpers/                      # Shared Python logic
├── prompts/                      # Prompt templates (agent.system.tool.*.md)
├── skills/                       # Skill files (SKILL.md per skill)
│   └── my-skill/
│       └── SKILL.md
├── agents/                       # Agent profiles
│   └── <profile>/
│       └── agent.yaml
├── extensions/
│   ├── python/<extension_point>/ # Named backend lifecycle hooks
│   ├── python/_functions/...     # Implicit @extensible hooks
│   └── webui/<extension_point>/  # Frontend HTML/JS contributions
└── webui/
    ├── config.html               # Plugin settings UI
    ├── main.html                 # Full plugin page
    ├── thumbnail.png             # Plugin list thumbnail
    └── *.js                      # Supporting scripts
```

---

## 5. Agent Tools (`tools/`)

Tools are Python classes that subclass `Tool` from `helpers/tool.py`. They are **NOT** MCP tools — they are Agent Zero's native tool system.

```python
from helpers.tool import Tool, Response

class MyTool(Tool):
    async def execute(self, **kwargs) -> Response:
        # self.agent — the agent instance
        # self.args — LLM-provided arguments (dict)
        # self.name — tool name
        # self.message — raw message
        result = do_something(self.args.get("input", ""))
        return Response(message=result, break_loop=False)
```

### How Tools Are Discovered

The framework scans `prompts/agent.system.tool.*.md` files from all enabled plugins. Each matching file becomes a tool description in the system prompt. The tool class is discovered from `tools/` by matching the tool name the LLM outputs.

### Tool Prompt Template

Create `prompts/agent.system.tool.<tool_name>.md` to describe your tool to the LLM:

```markdown
### my_tool
short description of what the tool does
args:
- `input`: description of the argument
- `mode`: `fast` or `thorough`
rules:
- rule 1
- rule 2
examples:
1 example usage
~~~json
{
    "thoughts": ["I need to..."],
    "headline": "Using my tool",
    "tool_name": "my_tool",
    "tool_args": {
        "input": "value",
        "mode": "fast"
    }
}
~~~
```

### Tool Dispatch

When the LLM outputs a `tool_name`:
- If it contains `.` → MCP tool → `MCPConfig.call_tool()`
- If no `.` → native tool → `agent.get_tool()` → matches `Tool` subclass

---

## 6. API Handlers (`api/`)

API handlers create custom HTTP endpoints at `POST /api/plugins/<plugin_name>/<handler_name>`. They subclass `ApiHandler` from `helpers/api.py`.

```python
from helpers.api import ApiHandler, Request

class MyHandler(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        # input — parsed JSON body
        # request — Flask Request object
        return {"success": True, "data": "result"}
```

### Security Model

Every handler has four security class methods that can be overridden:

```python
class MyHandler(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True          # Default: True — session-based login

    @classmethod
    def requires_csrf(cls) -> bool:
        return True          # Default: follows requires_auth()

    @classmethod
    def requires_loopback(cls) -> bool:
        return False         # Restrict to localhost only

    @classmethod
    def requires_api_key(cls) -> bool:
        return False         # X-API-KEY header validation

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]      # Allowed HTTP methods
```

| Guard | What It Does | Default |
|---|---|---|
| `requires_auth` | Session-based login check, redirects to login page | **ON** |
| `requires_csrf` | Validates `X-CSRF-Token` header or cookie against session | Follows `requires_auth` |
| `requires_loopback` | Restricts to 127.0.0.1/::1, returns 403 for remote | OFF |
| `requires_api_key` | Validates `X-API-KEY` header against `mcp_server_token` | OFF |

The framework applies these as **stacked decorators** during route registration. A plugin API handler is **authenticated + CSRF-protected by default**.

### Route Format

```
POST /api/plugins/<plugin_name>/<handler_filename_without_py>
```

Example: `api/test_connection.py` → `POST /api/plugins/my_plugin/test_connection`

---

## 7. Backend Extensions (`extensions/python/`)

### Named Lifecycle Extension Points

These are specific moments in the agent lifecycle where plugins can inject behavior. Create a Python file in `extensions/python/<point>/` that subclasses `Extension`:

```python
from helpers.extension import Extension
from agent import LoopData

class MyExtension(Extension):
    async def execute(self, **kwargs):
        # self.agent — the agent instance (or None)
        pass
```

### Complete Extension Point Reference

The following extension points are called during the agent lifecycle, listed in execution order:

#### Agent Initialization
| Point | When | Key kwargs |
|---|---|---|
| `agent_init` | Agent instance created (sync) | `agent` |

#### Monologue Loop (outer)
| Point | When | Key kwargs |
|---|---|---|
| `monologue_start` | Monologue begins | `loop_data` |
| `monologue_end` | Monologue completes | `loop_data` |

#### Message Loop (inner, per-iteration)
| Point | When | Key kwargs |
|---|---|---|
| `message_loop_start` | Each iteration begins | `loop_data` |
| `message_loop_prompts_before` | Before system prompt is built | `loop_data` |
| `system_prompt` | System prompt assembly | `system_prompt` (list), `loop_data` |
| `message_loop_prompts_after` | After system prompt + history are set | `loop_data` |
| `before_main_llm_call` | Just before LLM call | `loop_data` |
| `reasoning_stream_chunk` | Each reasoning token chunk | `loop_data`, `stream_data` |
| `reasoning_stream_end` | Reasoning stream complete | `loop_data` |
| `response_stream_chunk` | Each response token chunk | `loop_data`, `stream_data` |
| `response_stream_end` | Response stream complete | `loop_data` |
| `message_loop_end` | Iteration complete | `loop_data` |
| `message_loop_exception` | Exception during iteration | `loop_data`, `exception` |

#### Tool Execution
| Point | When | Key kwargs |
|---|---|---|
| `tool_execute_before` | Before tool runs | `tool`, `loop_data` |
| `tool_execute_after` | After tool runs | `tool`, `response`, `loop_data` |
| `tool_output_update` | Tool output being rendered | `ctx` (mutable content) |

#### History
| Point | When | Key kwargs |
|---|---|---|
| `hist_add_before` | Before message added to history (sync) | `data` |
| `hist_add_tool_result` | Tool result added to history (sync) | `data` |

#### LLM Calls
| Point | When | Key kwargs |
|---|---|---|
| `chat_model_call_before` | Before chat model call | `loop_data` |
| `chat_model_call_after` | After chat model call | `loop_data` |
| `util_model_call_before` | Before utility model call | `loop_data` |
| `util_model_call_after` | After utility model call | `loop_data` |

#### Process Chain
| Point | When | Key kwargs |
|---|---|---|
| `process_chain_end` | Agent processing chain completes | `data` |

#### Framework
| Point | When | Key kwargs |
|---|---|---|
| `startup_migration` | Framework startup migrations | — |
| `job_loop` | Each iteration of the job loop | — |
| `banners` | UI banner rendering | — |
| `error_format` | Error formatting | — |
| `user_message_ui` | User message UI rendering | — |

### Extension File Naming

Files are sorted alphabetically, so use numeric prefixes to control execution order:

```
extensions/python/system_prompt/
├── _10_main_prompt.py      # runs first
├── _11_tools_prompt.py
├── _12_mcp_prompt.py
├── _70_my_plugin.py        # your plugin runs here
```

### Example: System Prompt Extension

```python
# extensions/python/system_prompt/_70_my_context.py
from helpers.extension import Extension
from agent import LoopData

class MyContextPrompt(Extension):
    async def execute(
        self,
        system_prompt: list[str] = [],
        loop_data: LoopData = LoopData(),
        **kwargs,
    ):
        if not self.agent:
            return
        system_prompt.append(
            self.agent.read_prompt("agent.system.my_context.md")
        )
```

---

## 8. Implicit Hooks (`@extensible` / `_functions/`)

The `@extensible` decorator (in `helpers/extension.py`) wraps any function with automatic start/end extension points.

### How It Works

When a function is decorated with `@extensible`:

```python
@extensible
def get_api_key(service: str) -> str:
    ...
```

Two implicit extension points are created:
- `_functions/<module_path>/<qualname>/start` — runs **before** the function
- `_functions/<module_path>/<qualname>/end` — runs **after** the function

For `models.get_api_key`, the paths become:
- `_functions/models/get_api_key/start`
- `_functions/models/get_api_key/end`

### Hooking Into an @extensible Function

Place an `Extension` subclass at the corresponding path:

```python
# extensions/python/_functions/models/get_api_key/start/my_override.py
from helpers.extension import Extension

class OverrideApiKey(Extension):
    def execute(self, data: dict = {}, **kwargs):
        # data["args"] — positional args (mutable)
        # data["kwargs"] — keyword args (mutable)
        # data["result"] — set to short-circuit the function
        # data["exception"] — set to force-raise
        data["result"] = "my-custom-key"  # skip original function
```

### Mutable `data` Payload

| Key | Description |
|---|---|
| `data["args"]` | Positional args tuple — extensions may replace/mutate |
| `data["kwargs"]` | Keyword args dict — extensions may replace/mutate |
| `data["result"]` | Set to short-circuit the wrapped function (skip execution) |
| `data["exception"]` | Set to a `BaseException` to force-raise |

### Currently @extensible Functions

| Function | Module | What It Does |
|---|---|---|
| `get_api_key(service)` | `models` | Returns API key for a service |
| `get_secrets_manager()` | `helpers.secrets` | Returns the secrets manager instance |
| `get_project_secrets_manager()` | `helpers.secrets` | Returns project-scoped secrets manager |
| `get_default_secrets_manager()` | `helpers.secrets` | Returns default secrets manager |
| Several UI server methods | `helpers.ui_server` | UI server lifecycle |

---

## 9. Skills (`skills/`)

Plugins **can** bundle skills. The skill discovery system explicitly scans plugin directories.

### Skill Roots (from `helpers/skills.py`)

```python
plugins = files.find_existing_paths_by_pattern("plugins/*/skills")
usr_plugins = files.find_existing_paths_by_pattern("usr/plugins/*/skills")
plugins_agents = files.find_existing_paths_by_pattern("plugins/*/agents/*/skills")
usr_plugins_agents = files.find_existing_paths_by_pattern("usr/plugins/*/agents/*/skills")
```

All four paths are included in `get_skill_roots()`. Skills from plugins are labeled in the UI:
- `"Community plugin"` for `usr/plugins/`
- `"Built-in plugin"` for `plugins/`

### Skill File Format

```yaml
---
name: "my-skill"
description: "When to use this skill"
version: "1.0.0"
author: "Your Name"
tags: ["category1", "category2"]
trigger_patterns:
  - "keyword1"
  - "phrase that triggers this"
---

# Skill Title

Your skill instructions go here...
```

### Skill Placement in Plugin

```
usr/plugins/my_plugin/
├── skills/
│   ├── my-skill/
│   │   └── SKILL.md
│   └── another-skill/
│       └── SKILL.md
```

---

## 10. Runtime Hooks (`hooks.py`)

Plugins can include an optional `hooks.py` at the plugin root. The framework loads it on demand and calls exported functions by name via `helpers.plugins.call_plugin_hook()`.

### Built-in Hook Functions

| Hook | When Called | Purpose |
|---|---|---|
| `install()` | After plugin is copied into place | Post-install setup |
| `pre_update()` | Before pulling new plugin code | Pre-update cleanup |
| `uninstall()` | Before plugin deletion | Cleanup |
| `get_plugin_config(default, agent, project_name, agent_profile)` | When config is loaded | Transform/validate config |
| `save_plugin_config(settings, project_name, agent_profile)` | When config is saved | Transform before persist |
| `get_default_plugin_config(file_path)` | When default config is loaded | Override default loading |
| `on_plugin_enabled()` | When plugin is toggled ON | Registration, setup |
| `on_plugin_disabled()` | When plugin is toggled OFF | Cleanup, unregistration |

### Example: Config Transform Hook

```python
# hooks.py
from plugins._my_plugin.helpers.runtime import coerce_config

def get_plugin_config(default=None, **kwargs):
    return coerce_config(default)

def save_plugin_config(settings=None, **kwargs):
    return coerce_config(settings)
```

### Runtime Environment

`hooks.py` runs inside the **Agent Zero framework runtime** (`/opt/venv-a0` in Docker), NOT the agent execution runtime (`/opt/venv`). If you `pip install` from `hooks.py`, packages go into the framework environment.

---

## 11. Plugin Script (`execute.py`)

User-triggered from the Plugin List UI. Never runs automatically.

```python
import subprocess
import sys

def main():
    print("Running setup...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "requests"],
        text=True,
    )
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
```

Guidelines:
- Return `0` on success, non-zero on failure
- Print progress for user feedback
- Make it safe to rerun
- Do not leave permanent system modifications without a cleanup path

---

## 12. Settings System

### Config Resolution (highest priority first)

```
1. project/.a0proj/agents/<profile>/plugins/<name>/config.json
2. project/.a0proj/plugins/<name>/config.json
3. usr/agents/<profile>/plugins/<name>/config.json
4. usr/plugins/<name>/config.json
5. plugins/<name>/default_config.yaml  ← fallback defaults
```

The framework merges top-down. This means a plugin can have different settings per project and per agent profile.

### Settings UI (`webui/config.html`)

The plugin settings wrapper instantiates a local modal context from `$store.pluginSettingsPrototype`. Bind plugin fields to `config.*` and use `context.*` for modal-level state.

### Environment Variable Defaults

Default config values can be overridden via environment variables using the pattern `<plugin_name>__<key>`. Nested keys use double underscores: `my_plugin__section__key`.

---

## 13. Activation Model

### Toggle Files

Activation is file-based and independent per scope:

| File | Meaning |
|---|---|
| `.toggle-1` | Plugin is ON |
| `.toggle-0` | Plugin is OFF |
| (no file) | ON by default |

### Toggle Scopes

| Scope | Toggle File Location |
|---|---|
| **Global** | `usr/plugins/<name>/.toggle-1` or `.toggle-0` |
| **Project** | `project/.a0proj/plugins/<name>/.toggle-1` or `.toggle-0` |
| **Agent profile** | `usr/agents/<profile>/plugins/<name>/.toggle-1` or `.toggle-0` |
| **Project + profile** | `project/.a0proj/agents/<profile>/plugins/<name>/.toggle-1` or `.toggle-0` |

### Resolution Logic

The framework walks toggle paths in reverse order (most specific last wins):

```python
def determined_toggle_from_paths(default: bool, paths: Iterator[str]):
    enabled = default
    for plugin_path in paths:
        if enabled:
            enabled = not files.exists(plugin_path + "/.toggle-0")
        else:
            enabled = files.exists(plugin_path + "/.toggle-1")
    return enabled
```

### WebUI States

| State | Meaning |
|---|---|
| `ON` | Explicit ON or implicit default |
| `OFF` | Explicit OFF rule at selected scope |
| `Advanced` | At least one project/profile-specific override exists |

`always_enabled: true` bypasses OFF state and keeps the plugin ON in both backend and UI.

---

## 14. Frontend Extensions (`extensions/webui/`)

### HTML Breakpoints

Core UI defines insertion points like `<x-extension id="sidebar-quick-actions-main-start"></x-extension>`. To contribute:

1. Place HTML files in `extensions/webui/<extension_point>/`
2. Include a root `x-data` scope
3. Include an `x-move-*` directive (`x-move-to-start`, `x-move-after="#id"`)

### JS Hooks

Place `*.js` files in `extensions/webui/<extension_point>/` and export a default async function. They are called via `callJsExtensions("<point>", context)`.

### Notifications (Not Inline Errors)

Plugin UI must use the **A0 notification system** for errors, success, and warnings:

- **Frontend**: `toastFrontendError(message, title)`, `toastFrontendSuccess(...)`, etc.
- **Backend**: `AgentNotification.error(...)`, `AgentNotification.success(...)`

---

## 15. MCP Integration

Agent Zero has a full MCP **client** (stdio, SSE, streamable HTTP) via `helpers/mcp_handler.py`. MCP servers are configured globally in Settings.

### How MCP Tools Reach the Agent

1. `_12_mcp_prompt.py` extension calls `MCPConfig.get_tools_prompt()`
2. All connected MCP server tools are injected into the system prompt with schemas
3. The LLM sees them alongside native tools and can call them
4. Tool dispatch: `tool_name` with `.` → MCP, without `.` → native

### Registering an MCP Server from a Plugin

Plugins cannot declare MCP servers in `plugin.yaml`. Use `hooks.py` to register programmatically:

```python
# hooks.py
import json
from helpers import settings

def on_plugin_enabled(**kwargs):
    current = json.loads(settings.get_settings().mcp_servers)
    servers = current.get("mcpServers", {})
    if "my_server" not in servers:
        servers["my_server"] = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "my-mcp-server"]
        }
        current["mcpServers"] = servers
        settings.set_setting("mcp_servers", json.dumps(current, indent=2))
```

---

## 16. Model Providers (`conf/model_providers.yaml`)

Plugins can add or override model providers:

```yaml
chat:
  my_custom_provider:
    name: My Custom LLM
    litellm_provider: openai
    kwargs:
      api_base: https://my-llm.example.com/v1

embedding:
  my_custom_embed:
    name: My Embeddings
    litellm_provider: openai
    kwargs:
      api_base: https://my-embed.example.com/v1
```

At startup, the system loads base `conf/model_providers.yaml`, then merges plugin providers. Matching IDs are overwritten, new IDs are appended.

---

## 17. Python Import Rules

For plugin-local Python code, use the fully qualified package path:

```python
# ✅ DO
from usr.plugins.my_plugin.helpers.runtime import do_work
import usr.plugins.my_plugin.helpers.state as state

# ❌ DON'T
sys.path.insert(0, ...)
from helpers.runtime import do_work  # ambiguous
from plugins.my_plugin.helpers.runtime import do_work  # wrong for usr plugins
```

This keeps imports explicit, requires no `sys.path` hacks, and leaves no import wiring behind when the plugin is deleted.

---

## 18. Two Runtimes (Docker)

| Runtime | Path | Purpose |
|---|---|---|
| **Framework** | `/opt/venv-a0` | Runs Agent Zero itself — plugins, hooks, API handlers, extensions |
| **Agent execution** | `/opt/venv` | Where the agent's code execution tool runs user code |

If `hooks.py` does `pip install`, it installs into the **framework runtime**. To install into the agent sandbox, explicitly target `/opt/venv` from a subprocess.

---

## 19. API Surface

Core plugin management endpoint: `POST /api/plugins`

| Action | Purpose |
|---|---|
| `get_config` | Load plugin config for a scope |
| `save_config` | Save plugin config for a scope |
| `list_configs` | List all config scopes |
| `delete_config` | Delete a scoped config |
| `toggle_plugin` | Enable/disable a plugin |
| `get_doc` | Fetch README.md or LICENSE for display |

Plugin-specific endpoints: `POST /api/plugins/<name>/<handler>`

Static assets: `GET /plugins/<name>/<path>`

---

## 20. Plugin Index & Community Sharing

### Two Distinct Manifests

**Runtime manifest** (`plugin.yaml`, inside your plugin — drives Agent Zero):
```yaml
name: my_plugin
title: My Plugin
description: What this plugin does.
version: 1.0.0
```

**Index manifest** (`index.yaml`, submitted to `a0-plugins` repo — drives discoverability):
```yaml
title: My Plugin
description: What this plugin does.
github: https://github.com/yourname/your-plugin-repo
tags:
  - tools
```

### Submission Rules

- One plugin per PR
- Folder name: `^[a-z0-9_]+$` (no hyphens)
- Must match `name` in remote `plugin.yaml`
- GitHub repo must contain `plugin.yaml` + `LICENSE` at root
- `title` max 50 chars, `description` max 500 chars
- `tags`: up to 5, `screenshots`: up to 5 URLs

### Plugin Hub

The built-in `_plugin_installer` plugin provides the Plugin Hub UI. Users can browse, search, filter, and install community plugins without leaving Agent Zero.

---

## 21. Quick Reference: What Goes Where

| "I want to..." | Use this |
|---|---|
| Add a new tool the agent can call | `tools/` + `prompts/agent.system.tool.*.md` |
| Add a custom HTTP endpoint | `api/` (ApiHandler subclass) |
| Inject into the system prompt | `extensions/python/system_prompt/` |
| Hook before/after tool execution | `extensions/python/tool_execute_before/` or `tool_execute_after/` |
| Modify agent history | `extensions/python/hist_add_before/` |
| Override an `@extensible` function | `extensions/python/_functions/<module>/<qualname>/start/` |
| Add UI to the sidebar | `extensions/webui/sidebar-quick-actions-main-start/` |
| Add a settings panel | `webui/config.html` |
| Bundle skills for the agent | `skills/<name>/SKILL.md` |
| Add model providers | `conf/model_providers.yaml` |
| Run setup on install | `hooks.py` → `install()` |
| Provide a manual action | `execute.py` |
| Register an MCP server | `hooks.py` → `on_plugin_enabled()` |
| Distribute agent profiles | `agents/<profile>/agent.yaml` |
