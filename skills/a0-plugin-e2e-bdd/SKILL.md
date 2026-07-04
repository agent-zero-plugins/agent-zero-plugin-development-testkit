---
name: a0-plugin-e2e-bdd
description: End-to-end runbook to spec, build, and ship behaviour-first BDD e2e for an Agent Zero plugin — the 5-subagent authoring pipeline, the deterministic LLM-less seam, the CI/devkit wiring, the local→CI loop, and the machine-checked enforcement gates (Tier-1 lint + seam-off red-proof; Tier-2 verified-publish). Use when asked to spec, e2e-test, BDD, add behaviour tests, or wire/ship a plugin's tests. Canonical method: agent-zero-plugin-development-testkit SPEC §5.14 / DEC-059–066 + docs/BDD-GATES.md.
version: 1.1.0
tags: ["plugins", "e2e", "bdd", "gherkin", "spec", "testkit", "playwright"]
trigger_patterns:
  - "bdd spec for plugin"
  - "e2e tests for plugin"
  - "behaviour spec for plugin"
  - "spec-driven e2e"
  - "gherkin feature for plugin"
  - "add behaviour tests"
---

# A0 Plugin — Spec-driven BDD e2e

The method that turns a plugin's *code* into a **behaviour contract** and runnable e2e. Canonical
decisions live in the devkit `SPEC.md` (§5.14, DEC-059–064); this skill is how an agent *runs* it.

The non-negotiable idea: **the `.feature` describes observable behaviour in domain language — never
implementation.** Selectors, stores, DOM ids, seams, probes, triggers live in the **step layer**, not
the feature. Reverse-engineering from code biases toward implementation tests, so the `.feature` is
sourced from the **behaviour spec**, not the e2e/Playwright spec.

## Enact it end-to-end (the spine — follow top to bottom)

The full journey, not just the docs. Each step links to a section below.

0. **Prereqs.** Cloned plugin repo; live A0 source at `/a0`; the plugin's `tests/_testkit` submodule on
   devkit **`main`** (carries the playwright-bdd layer, `run-bdd.sh`, and the gates). Use a **disposable**
   A0 to iterate — never the operator's live instance (`no-live-a0-for-testing`).
1. **Author the four docs** via the 5-step subagent pipeline → commit to `docs/spec/`. *(§ pipeline)*
2. **Build the seam** if the plugin has agent-driven behaviour ("the agent asks…") → `api/<plugin>_probe.py`,
   env-gated; declare it in `.devkit.yml`. *(§ Build the seam)*
3. **Write features + steps** under `tests/e2e/{features,steps}` — features mirror `e2e.feature.md`
   (behaviour only); steps hold every selector/seam call. *(§ Wire it into CI)*
4. **Iterate to green on the local fast loop.** *(§ local fast loop)*
5. **Verify in CI** — push; `plugin-e2e` auto-runs `run-bdd` (lint → seam-off red-proof → e2e). Cross every
   gate. *(§ enforcement gates + `tests/_testkit/docs/BDD-GATES.md`)*
6. **Ship** — add `source_repo` + `source_commit` to the plugin's `meta.yaml` in the gate repo so
   verified-publish lets it through. *(§ Ship through the gate)*

## The four living documents (per plugin, `docs/spec/`, plugin-specific only)

| Doc | Answers | Depth |
|---|---|---|
| `behaviour-spec.md` | what the plugin does | behaviour-first; reads like the BDD |
| `implementation-plan.md` | how the plugin is built | locks the **product's** internals |
| `e2e.feature.md` | behaviour as executable spec | domain language, zero impl |
| `e2e-steps-spec.md` | how the tests bind to the product | low-level: selectors, seams, probes |

`#2` and `#4` are the **same depth, different concern** (product internals vs test wiring). These are
**plugin-specific** — common lifecycle (install/uninstall/boot/probe-enable) is **never** copied here;
it ships from the devkit (DEC-062/063) and is linked via the `tests/_testkit` submodule.

## The pipeline (5 steps, each a typed subagent)

Run these as **separate subagents** — the orchestration *is* the method (one-shot underperforms).
Always pass each agent: the cloned repo, live A0 source at `/a0`, and the hard rules below.

| # | Subagent (role) | What we ask it to do | What we expect back | Example finding (real) |
|---|---|---|---|---|
| 1 | **Behaviour-spec author** | Reverse-engineer an after-the-fact behaviour+UI spec from the code; self-review (IEEE-29148). | Numbered `BEH-n`/`UI-n`/`EDGE-n`, traceable to code, complete + unambiguous. | context-scoping: `meta.yaml 0.4.0` vs `plugin.yaml 0.4.3` version drift that would fail the gate; README understated a 7-seam fork dependency as "one seam". |
| 2 | **Implementation-plan author** | Document how the plugin is built — components, data flow, the `@extensible` fork seams it needs, config surface. | A build/impl plan locking low-level *product* internals (distinct from test wiring). | livekit/gitnexus: surfaced which behaviours are fork-only vs upstream. |
| 3 | **E2E-spec author** | Derive comprehensive e2e cases covering every behaviour; ≤10 groups; fixtures via the **real UI**; `dump_live` for seam behaviours. | `E2E-n` cases tracing to `BEH-/UI-`, with goal, fixtures, steps, falsifiable assertions; per-case hard-rules note. | — |
| 4 | **QA-expert reviewer** (`effort: high`) | Review the e2e spec: coverage, correctness (selectors/await-hangs/context assumptions), robustness, verifiability, **hard-rules compliance**. | Numbered findings (Critical/Major/Minor/Gap) + concrete fixes + a verdict. | context-scoping: the **hollow-coverage** trap (34/65 cases silently swallowed) + the zero-global **migrate-latch** ambiguity (issue #21). |
| 5 | **BDD author** → **BDD-expert reviewer** | Build the `.feature` from the **behaviour** spec (behaviour-first, no impl leakage); then a Gherkin-craft review. | A `.feature` (≤10 feature groups) + a craft review (declarative-not-imperative, ubiquitous language, one-behaviour-per-scenario, Given/When/Then discipline) + verdict. | ask-user-question: a hidden **two-in-one** multi-select scenario and a **`Then`-before-`When`** grammar inversion; confirmed no selector/store/DOM leakage. |

Fold step-4 and step-5 review findings back in before committing. Commit all four docs to
`docs/spec/`.

## The hard rules (binding — embed as a preamble in every `.feature`)

1. **Behaviour, not implementation.** No selectors, DOM ids, CSS classes, store/internal-API names,
   function-existence checks, or state-poking in Gherkin. The "how" lives in step definitions.
2. **Real triggers.** Provoke behaviour with real actions ("the agent asks me…", "I submit"), never
   by setting internal flags. *How* a trigger is realised is a step concern (see seams below).
3. **No silent swallow.** Real falsifiable assertions; failure ⇒ RED; per-group `[coverage]` tally.
4. **No fake green.** A scenario is asserted or an explicit `@skip` with a tracked reason (issue link).
5. **Self-provisioning fixtures, through the UI** (e.g. create an A0 project by driving the Projects
   UI — Projects card → "Create project" → title → "Create and continue"; **never** a backend API).
6. **Hermetic & deterministic.** No external keys / live third-party services; seams make
   agent-driven behaviour reproducible. ≤10 grouped features, one webm video each.

## Triggering agent-driven behaviour without an LLM (seams — DEC-064)

"The agent asks…" needs a real trigger. Use a **deterministic seam** that invokes the real handler
(creating the genuine state the user then sees), enabled for e2e only via `.devkit.yml e2e_pod_env`
(e.g. `A0_<PLUGIN>_TEST_PROBE=1`). This extends `dump_live` from *observation* to *triggering*. A real
LLM turn (deterministic stub) is used only when a behaviour is genuinely un-seamable. The seam lives in
the **step layer / plugin test surface**, never in the `.feature`.

## Fixture patterns for seamless UI plugins (pick by shape)

Many plugins have **no** agent-driven behaviour and need **no seam** — just a real trigger for a UI that
renders client-side. Three patterns cover almost all of them; pick by the plugin's shape:

- **Pure-UI control** — a `chat-top-end` button/toggle (share-chat, fullscreen-toggle). Provision a real
  chat (see fork-robustness below) so the toolbar mounts, click the control, assert the **DOM effect**: a
  `body` class, a spied `navigator.clipboard.writeText`, a `.copied` accent. No injection needed.
- **Render-a-code-block** — a `sidebar-end` renderer that turns ` ```mermaid `/` ```diff ` fences into
  SVG / side-by-side (mermaid-diagrams, diff-visualizer). Inject the exact node A0's markdown renderer
  emits (`.markdown-block-wrap > .code-block-wrapper > pre > code.language-<lang>`) as a **new** DOM node
  so the plugin's `MutationObserver` fires. Three traps, all real:
  1. **Wait for the renderer to load *before* injecting.** These import their lib from a CDN; the observer
     is installed only after that resolves. Inject too early and the mutation is missed (observers don't
     see pre-existing nodes). A fixed `waitForTimeout(~9s)` after page load is enough.
  2. **Assert the rendered *output*, not a `data-…-processed` marker.** The renderer usually **replaces**
     the source code block, deleting any marker on it. Poll the stable output (`.d2h-wrapper`, the mermaid
     `<svg>`) — the marker is a transient that vanishes.
  3. **Feed a *valid* payload.** diff2html renders nothing without a full git diff (`diff --git a/… b/…`
     + `index …` headers), not just `---/+++`.
- **Store-driven** — a plugin whose value lives in its own store (chat-comments). Drive the plugin's
  **public store methods** exactly as the UI does (`window.Alpine.store("<name>")`: set the draft field,
  call the action) and assert **observable effects**: a badge count, **persistence across a reload** (the
  backend load/save round-trip), the prompt box (`#chat-input`). This tests real create/persist/send
  without simulating raw text-selection. It's a legitimate trigger (the same entry point the UI calls),
  not state-poking — provided the *assertion* is on the observable effect, never the internal array.

**Local A0 boot gotcha.** A host-podman stock A0 (`agent0ai/agent-zero`) is killed on boot by a failing
`run_sshd` (a supervisor listener kills the whole container on any FATAL child). Neutralize it in the
entrypoint: `printf '#!/bin/sh\nexec tail -f /dev/null\n' > /usr/sbin/sshd`. And re-run
`npx playwright install chromium` after any browser-cache eviction.

## Batteries-included from the devkit (don't rebuild, link)

The devkit ships the playwright-bdd runner/config, the shared step library, and the **common lifecycle
`.feature`(s)+steps** (install/uninstall/boot/probe-enable/onboarding-suppression). A plugin's run
**composes** devkit-common + the plugin's own behaviour `.feature` + plugin-specific steps, via the
`tests/_testkit` submodule. Never copy a lifecycle scenario or a common step into a plugin.

## Develop on the local fast loop, verify in CI

Iterate against a **disposable** A0 — the devkit devcontainer or a host-podman A0 on a non-80 port —
**never the operator's live instance** (see `no-live-a0-for-testing`). Drive it with local Playwright,
screenshot+trace each step to learn real selectors, get the groups green locally, *then* push and
confirm the same green in the `plugin-e2e` CI gate (fork image). Onboarding modal auto-opens with no
LLM key — suppress it (`addInitScript` hiding `[data-modal-path*=_onboarding]` + neutralizing the
backdrop). Fixture-open hangs come from awaiting `openModal`/`openPluginConfig` — always fire-and-forget.

CI runs the devkit's **`run-bdd.sh`** harness automatically for any plugin that ships
`tests/e2e/features/` (else the classic `run-lifecycle.sh`) — no per-repo wiring beyond pinning the
`tests/_testkit` submodule to devkit `main` + a `secrets: inherit` caller. The devcontainer already
carries `playwright-bdd`.

## Fork-robustness gotchas (the tests run on the deployed fork, not stock A0)

These bit the pilot and will bite again — bake them into the step layer:

- **Provision a REAL chat, not a synthetic one.** A client-side `newContext()` with no backing chat is
  *deselected by the fork's chat-restore* on load → any context-scoped poll skips and the UI never
  appears. Create a real persisted chat (`callJsonApi("/chat_create", {})`, the UI's New-Chat path) and
  select that; the restore keeps it.
- **Hide unrelated overlays before clicking.** With no LLM configured the fork shows a `composer-banner`
  that overlays the chat UI and **intercepts clicks**. Hide it (`display:none`) then click the real
  target. `dispatchEvent("click")` is NOT a fix — it bypasses the overlay but does not trigger the
  framework's `@click` handler; you need a genuine click on a clear element.
- **Re-affirm context if needed.** When a poll depends on the active context, keep the loop honest:
  assert the context until the expected UI actually surfaces, rather than assuming one `setContext` sticks.

## Build the seam (recipe)

A test-only API handler that triggers the *real* behaviour with no LLM, gated on for e2e only.

```python
# api/<plugin>_probe.py
import os
from python.helpers.api import ApiHandler, Request, Response

class <Plugin>Probe(ApiHandler):
    @classmethod
    def requires_auth(cls): return True
    async def process(self, input: dict, request: Request):
        if os.environ.get("A0_<PLUGIN>_TEST_PROBE", "") != "1":
            return Response(response={"ok": False, "error": "probe disabled"}, status=403)
        from python.helpers... import state           # the plugin's real state/helpers
        action = input.get("action"); ctx = input.get("context_id")
        if action == "ask":     return {"ok": True, "session_id": state.create_session(ctx, input["questions"])}
        if action == "result":  s = state.get(ctx); return {"ok": True, "found": bool(s), "resolved": s and s.resolved, "result": s and s.result}
        if action == "pending": return {"ok": True, "pending": state.has_pending(ctx)}
        if action == "reset":   state.reset(ctx); return {"ok": True}
        return Response(response={"ok": False, "error": "unknown action"}, status=400)
```

Rules: gate on `A0_<PLUGIN>_TEST_PROBE` (off in prod); call the plugin's **real** code path (don't
reimplement); expose `ask`/`result`/`pending`/`reset`. The step layer calls it via
`callJsonApi("/plugins/<plugin>/<plugin>_probe", {action, context_id, ...})`. Declare it e2e-only:

```yaml
# .devkit.yml
e2e_pod_env:
  A0_<PLUGIN>_TEST_PROBE: "1"
```

## Wire it into CI (checklist)

- `tests/_testkit` submodule pinned to devkit **`main`** (has the BDD layer + gates).
- Caller `.github/workflows/plugin-e2e.yml` → `uses: …development-testkit/.github/workflows/plugin-e2e.yml@main`,
  `secrets: inherit`, and `permissions: { contents: read, pull-requests: write }` (for the merge-guard). Re-pull via `make link-workflows`.
- `tests/e2e/features/*.feature` — the plugin's behaviour, mirroring `e2e.feature.md`. **No** lifecycle scenarios (those ship from the devkit).
- `tests/e2e/steps/*.ts` — import the devkit base: `import { Given, When, Then } from "../../_testkit/e2e/bdd/bdd-fixtures";` Everything implementation-y (selectors, seam calls, the chat_create context, overlay-hide) lives here.
- CI then **auto-runs** `run-bdd.sh` (because `tests/e2e/features/` exists) — no extra config.
- **Local pre-commit:** the standard `-include tests/_testkit/e2e/Makefile.devkit` gives `make verify` (runs
  the Tier-1 static gates (fast, no A0) before you commit; `make install-hooks` wires a git pre-commit
  hook; `make bdd-e2e` runs the full local loop. Same gates as CI — green locally ⇒ green in the gate.

## Ship through the gate

To publish via `agent-zero-vendor-plugins`, add to `plugins/<plugin>.meta.yaml`:

```yaml
source_repo: <org>/<plugin-repo>
source_commit: <sha that has a green plugin-e2e>
```

Verified-publish refuses to publish unless `plugin-e2e` was green on that commit. Omit both = legacy
(unverified) publish.

## The enforcement gates (machine-checked — know them before you write)

These are hard-fail in `plugin-e2e` once a repo is on the new devkit; humans AND agents are the threat
model. **Full reference — every error + how to fix it: `tests/_testkit/docs/BDD-GATES.md`.** In short:

- **feature-purity** — no selectors / DOM ids / store names / API calls in `Given/When/Then`; the "how"
  lives in steps.
- **honesty** — every `@skip` has a tracked `#` reason; no swallowed failures (`catch {}` / `.catch(()=>…)`);
  all four `docs/spec/` docs exist.
- **traceability** — every `BEH-n` in `behaviour-spec.md` is covered in `e2e.feature.md` or tracked-skipped.
- **seam-off red-proof** — the suite is run once with the plugin NOT installed; anything that passes is
  fake-green and fails the build.
- **verified-publish (gate)** — the plugin can't publish unless `plugin-e2e` was green on its
  `source_commit`. This is the real shipping block for private repos (no branch protection): a red PR can
  be merged but can never ship.

Don't try to route around a red gate (broaden a regex, add a bare `@skip`, wrap an assertion in
`try/catch`) — that's exactly the laziness the gates exist to catch. Fix the underlying thing.

## References

- Canonical method + decisions: `agent-zero-plugin-development-testkit/SPEC.md` §5.14, DEC-059–064.
- Reference gold standard: `agent-zero-plugin-ask-user-question/docs/spec/e2e.feature.md`.
- Honesty + seam lineage: DEC-057 (`e2e_pod_env`, no-silent-swallow), DEC-058 (fixture hang fix).
- Related skills: `a0-plugin-architecture`, `a0-review-plugin`, `spec-driven-development`,
  `no-live-a0-for-testing`.
