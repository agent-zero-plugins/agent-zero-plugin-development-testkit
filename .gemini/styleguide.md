# A0 plugin — Code Review Style Guide

Conventions and quality gates every PR to an Agent Zero plugin (or this devkit) must comply with.
Gemini Code Assist applies these during PR review — a **second, plain-language line of defense** in
front of the machine-checked CI gates (devkit `docs/BDD-GATES.md`, SPEC §5.14 / DEC-059–066). CI is the
hard gate; this review catches the same violations earlier and explains them. **Flag, don't rubber-stamp.**

The threat model is laziness — human *and* AI. If a diff looks like it's routing *around* a gate
(loosening a check, adding a bare skip, wrapping an assertion in try/catch), say so explicitly.

## Behaviour-first BDD — the `.feature` files (`tests/e2e/features/*.feature`)

- **Feature-purity (flag as HIGH):** a `Given/When/Then` step must read as plain behaviour. Flag any
  selector (`.kebab-class`, `#id`), DOM/Playwright API (`querySelector`, `evaluate`, `dispatchEvent`),
  store/internal name (`showModal`, `Alpine`, `getContext`, `callJsonApi`, `chat_create`), or framework
  directive (`x-…`) appearing in a scenario. The "how" belongs in the step layer, never the feature.
- Scenarios assert **observable behaviour in domain language**, one behaviour per scenario, proper
  Given/When/Then order. Behaviour is provoked by **real actions**, never by setting an internal flag.

## Honesty (flag as HIGH — these are the lies that pass CI)

- **No bare `@skip`.** Every skipped scenario must carry a `#` comment with the reason + a tracked
  ref/issue. Flag any `@skip` without one.
- **No swallowed failures** in step files: an empty `catch {}`, or a `.catch(() => …)` / `try/catch`
  that recovers instead of failing or re-asserting. Reserve try/catch for genuinely un-enableable env,
  and even then assert *something*.
- **The four `docs/spec/` docs must exist** for a BDD plugin: `behaviour-spec.md`,
  `implementation-plan.md`, `e2e.feature.md`, `e2e-steps-spec.md`. Flag a PR that adds
  `tests/e2e/features/` without them.
- **Traceability:** every `BEH-n` in `behaviour-spec.md` must be covered in `e2e.feature.md` or listed
  as a tracked skip. Flag orphans.
- **No fake green:** a scenario must genuinely assert. A suite that would pass with the plugin
  uninstalled is fake-green (CI's seam-off red-proof catches it; flag designs that look hollow).

## The deterministic seam (`api/<plugin>_probe.py`)

- Must be **env-gated** (`A0_<PLUGIN>_TEST_PROBE`), off in production, and call the plugin's **real**
  code path — never reimplement behaviour in the probe. Flag a seam that's ungated or that fakes logic.
- Seam calls belong in the **step layer**, never in a `.feature`.

## Fork-robustness (the tests run on the deployed fork, not stock A0)

- Flag a step that creates a **synthetic** chat context (`newContext()` with no backing chat) for the
  plugin's polling path — the fork's chat-restore deselects it. Use a **real** chat (`chat_create`).
- Flag clicking a control without handling the no-LLM `composer-banner` overlay (hide it, then real
  click; `dispatchEvent` does not trigger the framework handler).

## Plugin-specific vs common

- Plugins ship **only their own behaviour** features/steps. Flag any copy of the common lifecycle
  (install/uninstall/boot/probe-enable) into a plugin — it ships from the devkit via `tests/_testkit`.

## Manifest & shipping

- `plugin.yaml` ↔ `<name>.meta.yaml` version match; declared `env[]` actually read in source; no UI
  prompts for secrets (operator provides via chart). To ship verified, the gate meta needs
  `source_repo` + `source_commit` with a green `plugin-e2e`.

## General

- No plaintext secrets. Idempotent lifecycle. Commit messages explain the *why*. Don't weaken a gate to
  make a red build green — fix the underlying issue (see `docs/BDD-GATES.md` for each gate's fix).
