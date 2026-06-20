# Agent Zero compatibility — per-plugin classification (theme 4, DEC-049/054)

_Result of a rigorous 19-subagent audit, 2026-06-20. One agent per plugin cloned the repo and
compared its **full** A0-coupling surface — webui `<x-extension>` points, `@extensible` seam
targets (checking the **decorator**, not just the function definition), A0 module/symbol imports,
API routes, frontend globals, and plugin-system assumptions — against both the internal fork
(`NuevaNext/agent-zero@nuevanext`) and **current stock upstream** (`agent0ai/agent-zero`), and
mined the fork's git log for plugin-specific commits. Authoritative source for each plugin's
`a0_compat`._

## Result: 1 `fork-required` / 18 `upstream` (all high confidence)

| Plugin | a0_compat | Fork-only surfaces (vs current stock upstream) | Confidence |
|---|---|---|---|
| **context-scoping** | **fork-required** | 7 `@extensible` seams (see below) | high |
| commands, ask-user-question, mermaid-diagrams, conversational-mode, claude-code-profile, mcp-tool-filter, intent-graph, detailed-prompts, fullscreen-toggle, chat-comments, diff-visualizer, chat-goals, browser-interactive, share-chat, task-controls, gitnexus, wip-radar, livekit | **upstream** | none | high |

## The reconciliation — historical fork contribution ≠ current fork dependency

The fork **did** make many plugin-supporting changes — **27 `@extensible` seams** and ~200
plugin/extensibility commits. That history is real. **But the audit shows the great majority were
upstreamed** and are now in stock `agent0ai/agent-zero`: the whole webui `<x-extension>` framework
and points (`page-head`, `chat-top-end`, `chat-input-box-*`, `sidebar-*`, `chats-header-controls`),
`init_a0` being `@extensible`, the `usr/plugins/<name>/` discovery, the `api/` plugin area, the
notification system, `get_api_key`, the secrets-manager seams, and the `initFw.js` framework
directives. So a plugin can use a surface the fork *originated* yet be fully `upstream`-compatible
**today**, because that surface now ships in stock upstream.

The net: **historical fork work was large and mostly succeeded** (upstreamed). The **current**
fork-only residue is narrow — only the seams below, used by one plugin.

## The lone fork-required plugin: context-scoping

It hooks **7 `@extensible` seams the fork added and that are not yet upstreamed** (each function
either doesn't exist upstream, or exists **without** the `@extensible` decorator — in which case
the plugin's `_functions` hook **silently no-ops** on stock upstream):

| Seam | Fork location | Upstream status |
|---|---|---|
| `get_agent_memory_subdir` | `plugins/_memory/helpers/memory.py` | exists, **not decorated** (fork commit `a531a361`, added "for context-scoping plugin") |
| `Memory.search_recall` | `plugins/_memory/helpers/memory.py` | **absent** (fork commit `02488975`) |
| `get_behaviour_rules` | `plugins/_memory/.../_20_behaviour_prompt.py` | **absent** (fork commit `02488975`) |
| `get_scope_active_skills` | `helpers/skills.py` | exists, **not decorated** (fork commit `6bd63c23`) |
| `list_skill_catalog` | `helpers/skills.py` | exists, **not decorated** |
| `list_skills` | `helpers/skills.py` | exists, **not decorated** |
| `get_all_agents_list` | `helpers/subagents.py` | exists, **not decorated** |

## The masking gotcha (validates DEC-053 + DEC-049)

context-scoping currently has **no `.devkit.yml`** (so its e2e runs on stock upstream, where these
seams are inert) **and no `verify-installed` behaviour hook** (so its e2e is the generic lifecycle
only). Result: **its CI is green while its scoping silently does nothing on the image under test.**
A presence-only test masking a real regression — exactly what behaviour-level verify (DEC-053) and
the e2e-matrix proof (DEC-049) exist to catch. Fleet-wide, **18 of 19 plugins ship no behaviour
hook**, so adding them is the top fan-out priority.

## Caveat & the durable verification

This audit is **static** (thorough, file+line, decorator-aware, all high confidence) — but the
*self-maintaining* proof is the **e2e behaviour matrix** (DEC-049): once each plugin has a
behaviour hook (DEC-053), run it on stock upstream **and** the fork image; the image where its
behaviour passes *is* its `a0_compat`. Static classification rots as changes upstream; the matrix
does not. Treat this table as the current best evidence, to be confirmed by the matrix.

## Actions implied

1. **context-scoping** → reference `fork-required` retrofit: `.devkit.yml` `a0_compat: fork-required`
   + `a0_image: ghcr.io/nuevanext/agent-zero` (needs private-ghcr CI auth) + a behaviour
   `verify-installed` hook that exercises scoping against the live instance.
2. **The other 18** → `a0_compat: upstream`; add behaviour hooks during the fan-out so the matrix
   can keep these honest.
3. **Repoint (Q-029)** → when the public fork (`agent-zero-operator/agent-zero`) is maintained,
   flip context-scoping's `a0_image` to the public image + add fork/PR README links (DEC-054).
