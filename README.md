# agent-zero-plugin-development-testkit

**The devkit: the single source of truth for how Agent Zero plugins are built, tested, documented,
and shipped — and the shared machinery that enforces that standard across the whole plugin fleet.**

Every plugin repo vendors this devkit as a submodule (`tests/_testkit`). The devkit gives a plugin,
batteries-included: a reproducible dev container, three layers of automated tests, the reusable CI
workflow that runs them on the real image we deploy, the authoring skills, and the documentation
templates. A plugin author writes *their plugin's behaviour* — everything common comes from here.

> **Start here:** the authoritative design is [`SPEC.md`](SPEC.md) (the numbered REQ/DEC contract).
> This README is the readable map; the SPEC is the law.

---

## The two things this repo is

1. **The standard** — [`SPEC.md`](SPEC.md): a spec-driven contract (100+ requirements, 65+ decisions,
   two review rounds) describing everything a fleet plugin must satisfy: layout, CI, the Makefile
   contract, lifecycle, docs, licensing, behaviour verification, and the behaviour-first BDD e2e method.
   Authored via the `spec-driven-development` method; lives here so it's queryable, not in anyone's head.

2. **The machinery that delivers it** — the devcontainer, the reusable GitHub Actions workflows, the
   pytest assertion library, and the playwright e2e layers (lifecycle + BDD). Plugins consume these by
   reference; they never copy them.

---

## Repository map

| Path | What it is |
|---|---|
| `SPEC.md`, `SPEC-REVIEW-00*.md` | The standard + its two expert-review rounds. The canonical artifact. |
| `devcontainer/` | The `Containerfile` for the reproducible build/test environment (Node + Playwright + playwright-bdd + podman-in-podman, used by CI and local dev). |
| `.github/workflows/plugin-e2e.yml` | **The reusable e2e workflow** every plugin calls. Boots A0 nested + rootless, installs the plugin, runs the lifecycle **or** BDD suite on the fork image. |
| `.github/workflows/devkit-sync.yml` | Nightly sync that keeps consumer repos' vendored copies current. |
| `e2e/harness/` | Shell entrypoints run *inside* the devcontainer: `a0-up.sh`/`a0-down.sh` (boot/teardown a disposable nested A0), `run-lifecycle.sh` (classic lifecycle), **`run-bdd.sh`** (the playwright-bdd runner). |
| `e2e/bdd/` | **Batteries-included BDD layer:** `playwright.config.ts` (composes devkit-common + the plugin's features/steps), `bdd-fixtures.ts` (the `playwright-bdd` base test + install/uninstall as an auto worker fixture), `features/` + `steps/` (the **common lifecycle** feature + steps). |
| `e2e/lifecycle/` | The classic non-BDD lifecycle spec (install → verify → uninstall) for plugins that haven't adopted BDD yet. |
| `e2e/fixtures/`, `e2e/pages/` | Shared Playwright fixtures (authenticated page, A0 login) and page objects (Login, Plugins panel). |
| `src/a0_plugin_testkit/` | **The pytest assertion library** — fast static checks (extension-point names, hooks, declared deps, real-A0-API usage, manifest/security validation). Catches the "installs but does nothing / crashes on first hit / calls a non-existent A0 API" bug class at PR time. |
| `docs/` | `a0-compatibility.md` (the upstream-vs-fork analysis), `ADOPTING.md` (consumer onboarding). |
| `skills/` | The vendored authoring skills + common Claude/Copilot guidelines distributed to plugin repos. |
| `templates/`, `examples/` | README/CLAUDE templates and a worked sample. |

---

## The three test layers

A fleet plugin is gated by three complementary layers, fastest-first:

1. **Static pytest assertions** (`src/a0_plugin_testkit`, ~1s, no A0 boot).
   Scrapes A0's *own source* for the canonical names a plugin may hook into and asserts the plugin
   only uses real ones — invalid extension surface, undeclared third-party import, dead lifecycle hook,
   fabricated A0 API call, blank thumbnail, manifest/security issues. Red-first: every assertion was
   written against a real shipped bug.

2. **Lifecycle e2e** (`e2e/lifecycle` via `run-lifecycle.sh`).
   Boots a real nested A0, installs the plugin from its zip, asserts it's installed + listed, then
   uninstalls and asserts no residue. Plus an in-browser **behaviour hook** (`tests/e2e/behaviour.mjs`)
   that drives the live UI right after install.

3. **Behaviour-first BDD e2e** (`e2e/bdd` via `run-bdd.sh`) — **the current standard (Cycle 3).**
   Plain-language `.feature` scenarios executed by `playwright-bdd` against a live nested A0. This is
   what the rest of this README focuses on.

The reusable workflow **auto-selects** layer 2 vs 3: if a plugin ships `tests/e2e/features/`, CI runs
`run-bdd.sh`; otherwise it runs the classic `run-lifecycle.sh`. No per-plugin wiring beyond that.

---

## The behaviour-first BDD method (Cycle 3)

The goal: **test what the plugin promises a user, in language a human can read, against the real
deployed image — with no fake passes.** (SPEC §5.14, DEC-059–065; method skill: `a0-plugin-e2e-bdd`.)

### Four living documents per plugin (`docs/spec/`)

| Doc | Concern |
|---|---|
| `behaviour-spec.md` | What the plugin does, behaviour-first (reads like the BDD). |
| `implementation-plan.md` | How the product is built internally (components, fork seams, config). |
| `e2e.feature.md` | The BDD behaviour contract (the source the `.feature` files mirror). |
| `e2e-steps-spec.md` | How the tests bind to the product (selectors, seams, probes). |

Docs 2 and 4 are the same depth, different concern: product internals vs test wiring.

### The hard rules (binding on every `.feature`)

1. **Behaviour, not implementation.** No selectors, DOM ids, CSS classes, store/internal-API names, or
   state-poking in `Given/When/Then`. The "how" lives only in the step layer.
2. **Real triggers.** A behaviour is provoked by a real action, never by setting an internal flag.
3. **No silent swallow.** Every scenario is a real, falsifiable assertion; a failure turns the group RED.
4. **No fake green.** A case is genuinely asserted, or an explicit `@skip` with a tracked reason — never
   a bare pass.
5. **Self-provisioning fixtures, through the UI.** State is created by driving the real product.
6. **Hermetic & LLM-less.** Seams make agent-driven behaviour deterministic; no API keys, no live MCP.
7. **≤10 grouped features, one webm video each.**

### Plugin-specific vs common (don't rebuild — link)

The devkit owns the runner, the shared step library, and the **common lifecycle** feature+steps
(install/uninstall/boot/probe-enable/onboarding-suppression). A plugin ships **only its own behaviour**
features + steps, and its run *composes* devkit-common + plugin-specific via the `tests/_testkit`
submodule. Never copy a lifecycle scenario or a common step into a plugin.

### Triggering agent behaviour without an LLM (the seam — DEC-064)

"The agent asks me a question" normally needs a live LLM. Instead the plugin ships a **deterministic
seam** — a small test-only API handler that invokes the *real* code path (creating genuine state the
user then sees), gated on for e2e only via `.devkit.yml e2e_pod_env` (e.g. `A0_<PLUGIN>_TEST_PROBE=1`).
This extends the `dump_live` philosophy from *observing* state to *triggering* it. A real (stubbed) LLM
turn is used only when a behaviour is genuinely un-seamable. The seam lives in the step/plugin test
surface — never in the `.feature`.

### Fork-robustness gotchas (learned from the ask-user-question pilot — DEC-065)

The tests run on the **fork** image we deploy, which differs from stock A0 in ways that bit us — encode
these so the next plugin doesn't rediscover them:

- **Use a real chat context, not a synthetic one.** A client-side `newContext()` with no backing chat
  is *deselected by the fork's chat-restore* on load → any context-scoped poll skips. Create a **real
  persisted chat** (`callJsonApi("/chat_create", {})` — the UI's New-Chat path) and select that; the
  restore keeps it.
- **Hide unrelated overlays before clicking.** With no LLM configured, A0 shows a `composer-banner`
  that overlays part of the chat UI and **intercepts clicks**. Hide it (`display:none`) before clicking
  an underlying button. `dispatchEvent("click")` is *not* a substitute — it bypasses the overlay but
  does **not** trigger the framework's `@click` handler; you need a real click on a clear target.
- **Suppress onboarding.** The onboarding modal auto-opens with no LLM key — suppress it via
  `addInitScript` (hide `[data-modal-path*=_onboarding]` + neutralize the backdrop).
- **Never `await` `openModal`/`openPluginConfig`** inside `page.evaluate` — they return non-resolving
  promises that hang to the test timeout. Fire-and-forget + a bounded `toBeVisible`.

---

## How a plugin consumes the devkit

Two commands (details + agent guidance in [`CLAUDE.md`](CLAUDE.md)):

```bash
git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit tests/_testkit
bash tests/_testkit/init.sh   # writes the root Makefile + .devkit.yml, copies workflows + .gemini, installs the hook
```

`init.sh` infers `plugin_dir`/`display_name` from your `plugin.yaml`, is idempotent (re-run after a devkit
bump), and leaves you with `make verify` / `make e2e` and the caller workflows in place. Then **ship the
tests** — for BDD: `docs/spec/` (the 4 docs), `tests/e2e/features/*.feature`, `tests/e2e/steps/*.ts`
(importing the devkit base via `../../_testkit/e2e/bdd/bdd-fixtures`), and the seam handler if needed;
CI auto-runs `run-bdd.sh`.

Gold-standard worked example: **[`agent-zero-plugin-ask-user-question`](https://github.com/agent-zero-plugins/agent-zero-plugin-ask-user-question)**
(`docs/spec/` + `tests/e2e/` + `api/ask_probe.py` seam; 12 behaviour scenarios green on the fork).

---

## CI: what runs, and on what image

The reusable `plugin-e2e.yml` (called on every PR + `workflow_dispatch`):

1. mints a token + checks out the plugin and its `tests/_testkit` submodule;
2. resolves the plugin (`.devkit.yml` → else `usr/plugins/<name>`);
3. builds the devcontainer and packages the plugin zip;
4. boots A0 **nested + rootless** and runs `run-bdd.sh` (or `run-lifecycle.sh`), forwarding
   `e2e_pod_env` seam vars into the nested A0;
5. uploads one webm per scenario as an artifact.

**Fork-first (DEC-055):** the default image is the fork we actually deploy
(`ghcr.io/nuevanext/agent-zero:latest-nonroot`, private — `secrets: inherit` forwards the
`GHCR_PULL_TOKEN`). We test what we ship.

---

## Local dev loop

Iterate against a **disposable** A0 — the devcontainer or a host-podman A0 on a non-80 port — and
**never the operator's live instance** (see the `no-live-a0-for-testing` skill). Drive it with local
Playwright, screenshot/trace each step to learn the real selectors, get the groups green locally, then
push and confirm the same green in the `plugin-e2e` gate. (The same `run-bdd.sh` config runs locally
from the submodule's `e2e/bdd` dir with `PLUGIN_BDD_DIR` set to the plugin's `tests/e2e`.)

The static pytest layer needs no A0 boot:
```bash
git clone --recurse-submodules <this-repo> && cd agent-zero-plugin-development-testkit
python -m pip install -e ".[fasta2a]" pytest pytest-asyncio
pytest                                  # fast smoke tests
```

---

## Design principles

- **Scrape, don't hard-code.** Canonical name lists (extension points, hooks, API attrs) are derived
  from the live A0 source the devkit is loaded against — upgrading A0 adjusts them automatically.
- **Never teach a fake an API the real thing doesn't have.** A fake wider than reality masks prod bugs.
- **Batteries-included, linked not copied.** Common machinery lives here once; plugins reference it.
- **No fake green.** Honesty rules forbid silent swallow and untracked skips — a green check means the
  behaviour was actually exercised against a live instance.
- **No PyPI.** Submodule distribution, commit-pin versioning — same model as the operator-skills library.

---

## Pointers

- The standard: [`SPEC.md`](SPEC.md) (§5.14 + DEC-059–065 for the BDD method).
- The method skill (for agents): `a0-plugin-e2e-bdd` in the operator-skills library.
- Consumer onboarding: [`docs/ADOPTING.md`](docs/ADOPTING.md).
- Upstream-vs-fork compatibility: [`docs/a0-compatibility.md`](docs/a0-compatibility.md).

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
