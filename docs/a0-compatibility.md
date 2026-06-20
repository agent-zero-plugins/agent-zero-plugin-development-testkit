# Agent Zero compatibility — per-plugin classification (theme 4, DEC-049/054)

_Generated 2026-06-20 from a git-history + source analysis of the 19 standardized plugins
against the A0 forks. Authoritative source for each plugin's `a0_compat`._

## Fork topology (two-tier)

| Fork | Repo / branch | Role | Image |
|---|---|---|---|
| **Internal** | `NuevaNext/agent-zero@nuevanext` (private) | Fast-moving; where fork features land; periodically rebased into upstreamable change-groups. **Current** test/deploy target for `fork-required`. | `ghcr.io/nuevanext/agent-zero` |
| **Public** | `agent-zero-operator/agent-zero` (public) | Visible upstreaming fork; should carry one open PR to upstream per change-group. **Target** reference once maintained (DEC-054, Q-029). | _tbd (repoint, Q-029)_ |
| **Upstream** | `agent0ai/agent-zero` | Stock upstream; e2e default image; the `upstream` compat baseline. | `agent0ai/agent-zero:latest` |

> Note: `agent-zero-operator/agent-zero` today carries only **infra** changes (non-root
> Dockerfile, init hooks, LiteLLM routing, scheduler tooling) and **none** of the plugin
> `@extensible` seams — so it is not yet a valid test target. The plugin seams live only in
> the internal `NuevaNext/agent-zero@nuevanext`.

## Classification — 18 `upstream` / 1 `fork-required`

| Plugin | a0_compat | Fork capability needed | Evidence | Confidence |
|---|---|---|---|---|
| context-scoping | **fork-required** | `@extensible` seams on `_memory.get_agent_memory_subdir`, `_memory.Memory.search_recall`, `subagents.get_all_agents_list`, `skills.list_skills`, `skills.list_skill_catalog` | README states it; seam present in `NuevaNext/agent-zero` (`get_agent_memory_subdir` search hit), absent in `agent-zero-operator/agent-zero` (0 hits) and stock upstream | High |
| livekit, commands, ask-user-question, mermaid-diagrams, conversational-mode, claude-code-profile, mcp-tool-filter, intent-graph, detailed-prompts, fullscreen-toggle, chat-comments, diff-visualizer, chat-goals, browser-interactive, share-chat, task-controls, gitnexus, wip-radar | **upstream** | — | Bind only to upstream-native surfaces (`toggle_plugin`, `build_prompt`, named webui injection points, standard extension dirs); e2e passes on stock `agent0ai/agent-zero:latest` | High |

## The masking finding (validates DEC-053 + DEC-049)

`context-scoping` is the proof case for behaviour-level verify:

- It has **no `.devkit.yml`** → its e2e runs on the **default stock `agent0ai/agent-zero:latest`**, where its required seams are absent.
- It has **no `tests/e2e/hooks/verify-installed`** behaviour hook → its e2e is the generic install/uninstall lifecycle only.
- **Therefore its CI is green while its scoping is inert** on the image under test — a presence-only test masking a real regression.

This is exactly what DEC-053 (behaviour verify must drive the live instance over the wire) and DEC-049 (`fork-required` must be *proven* on the fork image, not asserted) exist to prevent.

**Fleet-wide:** **18 of 19** plugins ship **no** `verify-installed` behaviour hook (only `wip-radar` has one). Adding a behaviour hook per plugin is therefore the highest-value item in the Cycle-2 fan-out.

## Actions implied

1. **context-scoping** → reference `fork-required` retrofit: `.devkit.yml` `a0_compat: fork-required` + `a0_image: ghcr.io/nuevanext/agent-zero` (with private-ghcr CI auth) + a real behaviour `verify-installed` hook that exercises scoping against the live instance.
2. **The other 18** → `a0_compat: upstream`; add behaviour hooks during the fan-out.
3. **Repoint (Q-029)** → when the public fork is maintained, flip `fork-required` `a0_image` to the public image + add fork/PR README links (DEC-054).
