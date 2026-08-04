# SPEC — Agent Zero Plugin Quality & Structure Standard

**Status:** Reviewable (iteration 18 — **BDD mandatory** (DEC-069: bdd_lint hard-fails a plugin with no tests/e2e/features/ — no self-skip loophole; breaking → **v2.0.0**; rollout via a major-version channel so the fleet isn't force-jumped); iteration 17 — **skills distribution** (DEC-068: the devkit ships the plugin-facing skills, symlinked into .claude/skills/ via link-skills; v1.1.0); iteration 16 — **versioning** (DEC-067: SemVer release tags; consumers track the latest tag; first release **v1.0.0**; CHANGELOG.md); iteration 15 — **enforcement gates** (DEC-066: two-tier machine-checked — Tier-1 lint + seam-off red-proof, Tier-2 verified-publish, merge-guard for free private repos; docs/BDD-GATES.md); iteration 14 — **Cycle 3 PILOT MERGED + PROVEN**: DEC-065 BDD CI harness (`run-bdd.sh` + `plugin-e2e.yml` auto-branch + devcontainer `playwright-bdd`) + fork-robustness rules (real `chat_create` context, overlay-hide-then-real-click); ask-user-question 12/12 BDD scenarios green on the fork in the `plugin-e2e` gate, merged to main; iteration 13 — **Cycle 3: spec-driven BDD e2e** (§5.14 / DEC-059–064) — the per-repo 5-step pipeline, behaviour-first BDD, the 4-doc artifact model, plugin-specific/common split, playwright-bdd batteries-included from the devkit (linked not duplicated), deterministic behaviour-trigger seams; gold standard = ask-user-question; iteration 12 — DEC-058 behaviour groups on loggedInPage + fire-and-forget openModal (fixed a 300s fixture hang); iteration 11 — DEC-057 pod-env test-seam enablement + no-silent-swallow honesty rule, after the context-scoping pilot caught hollow coverage; iteration 10 — Cycle-1 SHIPPED, 19/19 fan-out done; Cycle-2 (§5.7–5.13 / DEC-045–054) drafted + post-SPEC-REVIEW-002 sweep; **theme-4 fork analysis resolved by a 19-subagent audit** — two-tier fork model (DEC-049/054), **18 `upstream` / 1 `fork-required`** (context-scoping), all high confidence, `docs/a0-compatibility.md`; **fork-first e2e** DEC-055 — default image = the fork, stock upstream added later as a 2nd target)

> **Cycle-2 (2026-06-20) — authoring & polish standard.** Cycle-1 proved the harness and
> standardized every repo's *CI interface*. Cycle-2 standardizes what an author and a user
> see: the SPEC + knowledge committed here (not in assistant memory) · vendored authoring
> skills + a shared `CLAUDE.md` block · per-repo `DEVELOPING.md` · a fixed README skeleton
> with harness-captured screenshots/GIFs, the *why*, inter-plugin deps, and declared
> upstream-vs-fork A0 compatibility · Apache-2.0 across first-party repos · real
> thumbnail+description · an in-A0 `doctor` script · and **behaviour-level** verify (not
> implementation tests) wired into the PR gate. Themes → §5.7–5.13, DEC-045–053, Q-025–028.

**Canonical home:** `agent-zero-plugins/agent-zero-plugin-development-testkit/SPEC.md` (per DEC-025; **now committed here** — DEC-045 retires the workshop copy as system-of-record).
**Review trail:** `SPEC-REVIEW-001.md` (31 findings; closures in DEC-026…DEC-037) · `SPEC-REVIEW-002.md` (25 findings; Cycle-2; closures in the "Cycle-2 review closures" block of Appendix A).

This specification defines a single, durable contract that every Agent Zero plugin
repository conforms to: a common build/test interface, a three-operation CI surface
(install / verify / uninstall), and a shared "devkit" that holds all reusable heavy
lifting so individual plugin repos carry only their plugin-specific differences.

The design intent is the **template-method pattern at the repository level**: the
skeleton of every operation (build, package, install, uninstall, and the harness that
runs them) lives once in the devkit; each plugin repo supplies only the variant
steps — initially just `verify` — through a fixed, well-known seam.

---

## Conformance keywords

The keywords **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be interpreted as
described in RFC 2119.

---

## 1. Scope

This spec covers the shared quality and structure standard applied across the
`agent-zero-plugins` GitHub organisation:

- The **devkit** — the shared component holding reusable test/build/CI heavy lifting
  (currently `agent-zero-plugin-development-testkit`).
- The **common Makefile interface** — the target vocabulary every plugin repo exposes.
- The **three-operation CI interface** — install, verify, uninstall — and the cleanup
  assertions that gate a green build.
- The **per-plugin seam(s)** — what an individual plugin repo is allowed/required to
  override, starting with `verify`.
- The **rollout** — how the standard reaches the ~20 existing plugin repos and the
  template, and how it stays in sync thereafter.

## 2. Goals / non-goals

### Goals
- G1. One plugin repo looks like every other plugin repo at the build/test/CI surface.
- G2. The expensive logic (docker startup, Playwright flows, versioning, reusable
  workflows) lives in exactly one place and is consumed, not copied.
- G3. Adding a new per-plugin behaviour (today: `verify`) is the *only* work an author
  does to get a fully-gated CI pipeline.
- G4. The CI interface is three legible operations whose pass/fail an operator can read
  without understanding the plugin: install succeeds, plugin verifies, uninstall leaves
  no residue.
- G5. The contract is mechanical to conform to and mechanical to check — a plugin either
  conforms or fails a gate.

### Non-goals
- NG1. Re-architecting the A0 plugin runtime API. The runtime install/uninstall
  endpoints are treated as a fixed dependency, not a thing this spec changes.
- NG2. Replacing the existing L0–L2 Python testkit assertions. They stay; this spec is
  about the L3 (e2e) interface and the repo-level structure around it.
- NG3. Changing the gate/OCI publish pipeline (`agent-zero-vendor-plugins`) beyond what
  the new CI interface requires.

## 3. Out of scope (with rationale)

- OOS1. **MCP servers** (`agent-zero-mcps`) — different conformity contract already
  exists (`mcp-image-conformity-contract`). This spec is plugins-only.
- OOS2. **The A0 runtime fork itself** — its plugin API is an upstream dependency here.
- OOS3. **Non-`agent-zero-plugins` plugin repos** (e.g. third-party `agkonnect/*`) —
  they MAY adopt the standard but are not bound by it.

## 4. Glossary

- **Devkit** — the shared component (`agent-zero-plugin-development-testkit`) that holds
  reusable heavy lifting consumed by every plugin repo.
- **Harness** — the docker + Playwright machinery that boots an A0 instance and drives
  plugin operations against it.
- **The three operations** — `install`, `verify`, `uninstall`, the CI-facing interface.
- **Seam** — the fixed extension point where a plugin repo supplies its variant logic
  (template-method "hook method").
- **Common Makefile** — the target set every plugin repo exposes identically.
- **Gate** — `agent-zero-vendor-plugins`, the curated repo whose merge-to-main publishes
  a plugin as an OCI artifact.
- **Cleanup verification** — the assertions proving uninstall left no residue on disk,
  in the API, or in the UI.
- **Doctor** — a per-plugin health script runnable inside a booted A0 that checks the
  plugin's dependencies, config, and extension-point mounting (DEC-052).
- **Behaviour verify** — a check that exercises the plugin's *running behaviour* against a
  live A0 instance (UI/API), as opposed to implementation/unit tests (DEC-053).
- **A0 compatibility** — a plugin's declared dependency on stock upstream A0 vs. the
  operator's A0 fork (`a0_compat: upstream | fork-required`, DEC-049).
- **Internal fork (NuevaNext)** — `NuevaNext/agent-zero` branch `nuevanext`: the fast-moving
  *internal* fork. Periodically fetched-from-upstream and its commits reorganised into
  upstreamable change-groups. Its image `ghcr.io/nuevanext/agent-zero` is the **currently**
  consumed/tested A0 image for `fork-required` plugins (DEC-049/DEC-054).
- **Public fork (operator)** — `agent-zero-operator/agent-zero`: the *visible upstreaming*
  fork that SHOULD carry one open PR to upstream per change-group. The **target** compat
  reference once maintained; plugins repoint to it later (DEC-054, Q-029).
- **Common CLAUDE block** — the marker-delimited, org-identical guidance block every
  plugin repo's `CLAUDE.md` carries, refreshed by sync (DEC-046).
- **Behaviour media** — harness-captured screenshot + GIF/video of the plugin installed
  and behaving in A0, committed as the README's visuals (DEC-051).

---

## 5. Requirements

_(REQs are added cluster-by-cluster as decisions are made.)_

### 5.1 Devkit & distribution (DEV)

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-DEV-001 | All reusable test/build/CI logic (harness boot, Playwright flows, lifecycle orchestration, residue scanning, versioning, the devcontainer definition) **MUST** live in the devkit. Plugin repos **MUST NOT** copy or reimplement it. | DEC-003, DEC-015 | Devkit |
| REQ-DEV-002 | Plugin repos **MUST** vendor **only the devkit** (git submodule), **MUST NOT** vendor the full skills library, and **MUST** keep the vendored surface minimal — preferring submodule references over copied files. | DEC-015 | Devkit, submodule |
| REQ-DEV-003 | The devkit **MUST** publish a **devcontainer image** carrying all execution tooling (Playwright, SSH, node, rootless podman + nesting tooling) that runs the A0 container **nested and unprivileged**. The same image **MUST** be usable as CI runner, developer dev container, and AI-agent local environment. | DEC-018 | Devkit, Image |
| REQ-DEV-004 | A plugin repo's tracked assets **MUST** be limited to: plugin source, the per-plugin seam files, the thin caller workflow, the shared AI-code-review guide, the minimal Claude integration, and the devkit submodule. | DEC-003, DEC-015 | Repo |
| REQ-DEV-005 | The bootstrap/sync mechanism **MUST** generate only **Claude** IDE integration. Antigravity and Copilot generation **MUST NOT** be produced for plugin repos. | DEC-016 | Devkit, Makefile |
| REQ-DEV-006 | A single shared **AI-code-review guide** **MUST** be vendored into every plugin repo so AI-driven review is consistent org-wide. | DEC-017 | Devkit, Repo |
| REQ-DEV-007 | The rootless-nested-podman model **MUST** pass a feasibility spike (Appendix E.6 acceptance) on the target CI runner **before** Phase-1 rollout; a self-hosted-runner fallback **MUST** be documented if GH-hosted runners cannot satisfy it. | DEC-031, DEC-032 | Process, Image |
| REQ-CONF-001 | The devkit **MUST** provide a `conformance` check (run in each repo's PR gate) asserting the repo exposes the frozen Appendix E.1 targets and matches the Appendix E.5 asset list. | DEC-037 | Devkit, Makefile |

### 5.2 CI interface (CI)

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-CI-001 | The devkit **MUST** publish a reusable **resync** workflow (`workflow_call`), runnable nightly and via `workflow_dispatch`, that updates the vendored submodule and opens an auto-merge PR. | DEC-002 | Workflow |
| REQ-CI-002 | The devkit **MUST** publish a reusable **branch/PR e2e** workflow (`workflow_call`) that runs the full plugin lifecycle self-contained against a booted A0 instance. | DEC-002, DEC-004 | Workflow |
| REQ-CI-003 | The e2e workflow **MUST** report `install`, `verify-installed`, `uninstall`, and `verify-uninstalled` as **individually-legible stages** per config-case within a single A0 boot. | DEC-004, DEC-033 | Workflow |
| REQ-CI-007 | The e2e workflow **MUST** trigger on PR → `main`, `workflow_dispatch`, and a nightly schedule (upstream `latest`); feature-branch pushes are not a default trigger. | DEC-021 | Workflow |
| REQ-CI-004 | The reusable e2e workflow body **MUST** live in the **devkit** repo; plugin repos carry only a thin caller (`uses: …@<ref>`) rendered by bootstrap and kept fresh by the resync mechanism. | DEC-002, DEC-020 | Workflow |
| REQ-CI-005 | The A0 image under test **MUST** be a parameter, defaulting to upstream `agent0ai/agent-zero` and overridable (per-plugin / workflow input) to the operator-fork image. | DEC-019 | Workflow, Devkit |
| REQ-CI-006 | CI **MUST** run the lifecycle **inside the devkit devcontainer**, booting A0 as a nested unprivileged container — no `--privileged`, no host Docker socket mount. | DEC-018 | Workflow, Image |

### 5.3 Common Makefile contract (MK)

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-MK-001 | Every plugin repo **MUST** expose the frozen common Make target set defined in Appendix E.1, with identical names and contracts across all repos. | DEC-005, DEC-006, DEC-008 | Makefile |
| REQ-MK-002 | The skeleton of every common target **MUST** be supplied by the devkit (via an included Makefile fragment); a plugin repo **MUST** override only the designated hook targets. | DEC-003, DEC-005 | Makefile |
| REQ-MK-003 | Hook targets **MUST** be language-agnostic: a plugin **MAY** implement them with Playwright, container exec/SSH, API calls, scripts, or any combination. | DEC-005 | Makefile |

### 5.4 Lifecycle & config-matrix (LC)

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-LC-001 | The harness **MUST** support a plugin-declared set of configurations exercised **serially** within one A0 boot, each via an `install(config) → verify-installed → uninstall → verify-uninstalled` cycle. | DEC-006, DEC-012 | Devkit |
| REQ-LC-002 | Configurations **MUST** be declared in a single declarative cases manifest (`tests/e2e/cases.yaml`, shape per Appendix E.2); the devkit **MUST** drive the loop. A plugin with no manifest is treated as one default case. | DEC-012 | Devkit |
| REQ-LC-003 | Per-case configuration **MUST** be applied after install via the A0 plugin config API (not via boot-time seeding), since all cases share one boot. | DEC-012 | Devkit |
| REQ-LC-004 | The common lifecycle interface targets `install`, `enable`, `disable`, `uninstall` (aliases `delete`/`remove`), `up`, `down` **MUST** be generic and supplied by the devkit; a plugin **MUST NOT** reimplement them. `enable`/`disable` are hook-callable primitives, not mandatory loop stages. | DEC-008, DEC-010, DEC-036 | Devkit, Makefile |
| REQ-LC-005 | On a stage failure mid-matrix, the harness **MUST** record which case+stage failed, attempt teardown toward baseline, and report it; remaining cases default to **fail-fast** (skipped) unless the run is configured to continue. | DEC-024 | Devkit |
| REQ-LC-006 | A case **MAY** declare `requires_reboot: true`; the harness **MUST** then restart the A0 container before applying that case's config (for boot-only settings — Appendix F.4). | DEC-028 | Devkit |

### 5.5 Assertion targets (VER) — verify-installed / verify-uninstalled

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-VER-001 | `verify-installed` **MUST** run, in series: (a) the **common** install-effectiveness checks, then (b) a **per-plugin hook**. A green `verify-installed` means both passed. | DEC-009, DEC-011 | Devkit + seam |
| REQ-VER-002 | The common checks of `verify-installed` **MUST** include: (1) every dependency the plugin **declares** (manifest shape mirrors the infra env-descriptor, Appendix E.3) is present in the running container, and (2) the plugin's files are unzipped/landed per its expected directory structure. This logic lives once in the devkit and **MUST NOT** be reimplemented per plugin. | DEC-011 | Devkit |
| REQ-VER-003 | The per-plugin hook of `verify-installed` **MUST** be language-agnostic (Playwright, container exec/SSH, API calls, scripts) and is the plugin's functional assertion for the active case. | DEC-005, DEC-009 | Seam |
| REQ-VER-006 | Hooks **MUST** conform to the ABI in Appendix E.4: fixed executable paths, pass/fail by exit code, and the fixed env-var context the devkit injects. A missing hook is a no-op pass. | DEC-026 | Devkit, Seam |
| REQ-VER-004 | `verify-uninstalled` **MUST** run, in series: (a) the **common** residue scan via snapshot+diff of all four layers — plugin-dir filesystem, `pip freeze`, settings.json keys, `plugins_list` API — against a pre-install baseline, then (b) an optional **per-plugin hook**. | DEC-009, DEC-022 | Devkit + seam |
| REQ-VER-005 | Any residue detected by `verify-uninstalled` **MUST** fail the build and be reported as a plugin **defect** — residue is a bug in the plugin's uninstall path, not a condition to silently clean. | DEC-007, DEC-009 | Devkit |

### 5.6 Rollout & governance (ROL)

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-ROL-001 | Rollout **MUST** proceed in phases — devkit, then template + a reference plugin, then fan-out — with each phase validated before the next. | DEC-024 | Process |
| REQ-ROL-002 | Conformance **MUST** be enforced by each plugin repo's PR gate. The `agent-zero-vendor-plugins` gate **MUST NOT** be extended with e2e and retains its existing static checks. | DEC-023 | Workflow, Gate |
| REQ-ROL-003 | During fan-out, each migrated repo **MUST** drop the full skills-lib vendoring in favour of the devkit-only surface (REQ-DEV-002). | DEC-015, DEC-024 | Repo |
| REQ-ROL-004 | The canonical SPEC **MUST** reside at `agent-zero-plugin-development-testkit/SPEC.md`. | DEC-025 | Doc |
| REQ-ROL-005 | Cycle-2 **MUST** roll out in the same phased shape as Cycle-1 — devkit (harness media/doctor/behaviour support + conformance checks + templates) → template repo + one reference plugin → fan-out across the standardized repos — each phase validated before the next; the new conformance checks **MUST** ship in `report-only` mode first, then become gating, so the 19-repo retrofit is not a flag-day. _Major-4 of SPEC-REVIEW-002._ | DEC-024, DEC-045 | Process, Devkit |

### 5.7 Knowledge capture & canonical home (GOV) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-GOV-001 | The SPEC and all its review documents **MUST** be committed at the devkit repo root (`SPEC.md`, `SPEC-REVIEW-NNN.md`); the workshop copy is non-canonical and **MUST NOT** be the system of record. | DEC-025, DEC-045 | Doc |
| REQ-GOV-002 | Durable operational knowledge an implementer needs (verified A0 runtime quirks, harness gotchas, fan-out classification) **MUST** be captured in committed devkit docs (Appendix F + `docs/`) and **MUST NOT** live only in assistant memory. | DEC-045 | Doc |
| REQ-GOV-003 | Every **structural/presence** standard in this SPEC (file/section/asset/marker/field presence, exit codes, gate steps) **MUST** be machine-checkable by `make conformance` or the e2e gate. **Semantic-quality** judgements (prose usefulness, thumbnail aesthetics, media non-triviality) are **SHOULD**s, may be human-reviewed, and are tracked as such — they are not held to the machine-check bar. _Scoped per SPEC-REVIEW-002 Major-6/XCut-1 (the original blanket rule was self-violated by its own siblings)._ | DEC-045 | Devkit |

### 5.8 Vendored authoring skills & Claude guidelines (SKL) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-SKL-001 | The devkit **MUST** vendor the curated plugin-authoring skill set (Appendix E.7) sourced from `agent-zero-plugins-skills`, and **MUST** keep it current via the sync mechanism. | DEC-046 | Devkit |
| REQ-SKL-002 | Every plugin repo's `CLAUDE.md` **MUST** contain the shared common-guidelines block (identical org-wide, marker-delimited so sync can replace it) and **MAY** add a repo-specific section outside the markers. | DEC-046 | Repo, Devkit |
| REQ-SKL-003 | The vendored skills and the common `CLAUDE.md` block **MUST** be distributed/refreshed by the devkit-sync mechanism, not hand-copied. | DEC-046, DEC-044 | Workflow |

### 5.9 Documentation: README & developer guide (DOC) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-DOC-001 | Every plugin repo **MUST** ship a `DEVELOPING.md` rendered from the devkit template, documenting the devcontainer and the standard local dev/test loop (`build → up → e2e → doctor → verify → down`). | DEC-047 | Repo, Devkit |
| REQ-DOC-002 | Every plugin repo's `README.md` **MUST** follow the standard skeleton (Appendix E.8): title + thumbnail, one-line description, **Why**, install/behaviour media, configuration, inter-plugin dependencies, A0 compatibility, doctor, license. Content is plugin-specific; the skeleton is fixed. | DEC-048 | Repo |
| REQ-DOC-003 | A plugin's README **MUST** embed the harness-captured install/behaviour media (§5.11) as its primary visual, referenced from the committed known path. | DEC-048, DEC-051 | Repo |
| REQ-DOC-004 | Every plugin **MUST** declare `a0_compat: upstream \| fork-required` in `.devkit.yml`, consistent with the A0 image its e2e passes against (REQ-CI-005). A `fork-required` plugin **MUST** set `a0_image` to the fork image (currently the internal `ghcr.io/nuevanext/agent-zero` — DEC-049/054), name the required fork change, and — once the public fork is maintained (Q-029) — link the public fork + the specific upstreaming PR in its README "Agent Zero compatibility" section. | DEC-049, DEC-054 | Repo, Doc |
| REQ-DOC-005 | Every plugin's `plugin.yaml` **MUST** carry a human-readable `description`, and the card **MUST** ship a real `webui/thumbnail.*`. The placeholder stubs generated during Cycle-1 standardization (solid-colour 16×16 PNGs) **MUST** be replaced; conformance rejects a thumbnail below a minimum dimension/byte threshold (Appendix E.8). _Gap-1 of SPEC-REVIEW-002._ | DEC-048, DEC-051 | Repo |
| REQ-DOC-006 | A plugin's inter-plugin dependencies **MUST** be declared in `.devkit.yml` as `depends_on: [<plugin-name>…]` (the checkable source); the README "Dependencies" section mirrors it. Absent/empty ⇒ no inter-plugin deps. _Gap-4 of SPEC-REVIEW-002._ | DEC-048 | Repo |

### 5.10 Licensing (LIC) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-LIC-001 | Every first-party plugin repo **MUST** contain a root `LICENSE` (Apache-2.0) and a matching `plugin.yaml` `license: Apache-2.0`. | DEC-050 | Repo |
| REQ-LIC-002 | A fork plugin **MUST** retain its upstream license and declare it in `plugin.yaml`; the Apache-2.0 mandate **MUST NOT** override an upstream license. | DEC-050, DEC-043 | Repo |

### 5.11 Behaviour media capture (MED) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-MED-001 | The devkit lifecycle harness **MUST** capture, on **every** run (not only on failure), a screenshot of the installed card/config screen and a video of the behaviour-verify flow, write them to the in-container report dir, and upload them as CI **artifacts** — it **MUST NOT** write into the read-only workspace mount. | DEC-051 | Devkit |
| REQ-MED-002 | Media **MUST** be landed at the committed path `docs/media/` by a defined publish mechanism — a local `make media` target (devcontainer holds the video→GIF tooling) and/or a devkit media-publish CI step that commits the downloaded artifact to the PR branch via the App token. The README embeds these paths; an author **MAY** re-run `make media` to override an asset. | DEC-051 | Repo, Devkit |
| REQ-MED-003 | The behaviour GIF/video **MUST** be produced by driving the plugin's behaviour verify (§5.13), so the documented behaviour is the verified behaviour. | DEC-051, DEC-053 | Devkit |

### 5.12 Doctor health command (DR) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-DR-001 | Every plugin **MUST** ship a doctor script at the known path `usr/plugins/<name>/scripts/doctor.py` (or the `plugin_dir` equivalent for forks/build-generated), exiting `0` iff healthy, that checks: declared dependencies importable, config present + schema-valid, and the plugin's extension points mounted. | DEC-052 | Repo |
| REQ-DR-002 | `doctor` **MUST** be runnable inside a booted A0 (`python /a0/usr/plugins/<name>/scripts/doctor.py`) and **MUST** print a per-check PASS/FAIL summary; soft warnings exit `0`, hard failures exit non-zero. | DEC-052 | Repo |
| REQ-DR-003 | The e2e **MUST** run `doctor` against the installed plugin and assert it reports healthy, wiring the doctor into the PR gate. | DEC-052 | Devkit, Workflow |

### 5.13 Behaviour-level verification (BEH) — Cycle 2

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-BEH-001 | Every plugin **MUST** carry ≥1 falsifiable behaviour assertion that drives the live A0 over the wire and asserts a plugin-specific observable effect — preferably `tests/e2e/behaviour.mjs` (in-browser seam, Appendix E.11), or the `verify-installed` hook making a Playwright/HTTP call. It **MUST NOT** be satisfied by `podman exec` file/dependency presence checks alone. | DEC-053, DEC-056 | Repo |
| REQ-BEH-002 | The behaviour verify **MUST** run in the branch/PR e2e gate (one nested-A0 boot) and gate merge; the generic install/uninstall lifecycle is necessary but **MUST NOT** be the only behavioural check. | DEC-053 | Workflow |
| REQ-BEH-003 | The behaviour verify **SHOULD** be the same flow the media capture (§5.11) records, so a green behaviour check and the README GIF are the same evidence. | DEC-053, DEC-051 | Repo, Devkit |

---

### 5.14 Spec-driven BDD e2e (SBE) — Cycle 3

_The Cycle-2 behaviour seam (§5.13) proved hollow-prone: a quick `behaviour.mjs` reverse-engineered
from code tends to test the implementation (selectors, store internals) and to pass without verifying.
Cycle 3 replaces the ad-hoc behaviour test with a **spec-driven, behaviour-first BDD** method whose
artifacts are durable, queryable, per-plugin documents, and whose common machinery ships from the
devkit. See DEC-059…064 and Appendix E.12._

| ID | Requirement | Trace | Impl |
|---|---|---|---|
| REQ-SBE-001 | Each plugin's e2e **MUST** be produced by the per-repo **spec-driven pipeline**: (1) reverse-engineer an after-the-fact **behaviour spec**; (2) an after-the-fact **implementation plan**; (3) a **BDD `.feature`** derived from the behaviour spec; (4) an **e2e steps spec** (test wiring). Each stage is authored + reviewed by a typed subagent (behaviour-spec author, impl-plan author, BDD author, QA-expert reviewer, BDD-expert reviewer). | DEC-059, DEC-060 | Doc, Process |
| REQ-SBE-002 | The four documents are **living, plugin-specific** artifacts committed under `docs/spec/` of each plugin (`behaviour-spec.md`, `implementation-plan.md`, `e2e.feature.md`, `e2e-steps-spec.md`). They **MUST** contain **only that plugin's concerns** — no common lifecycle content. Docs #1/#3 are the behaviour face; #2 locks product internals; #4 locks test wiring (same depth, different concern). | DEC-060 | Repo |
| REQ-SBE-003 | A `.feature` **MUST** assert **observable behaviour in domain language** and **MUST NOT** contain selectors, DOM ids, CSS classes, store/internal-API names, function-existence checks, or internal-state poking. The "how" (triggers, seams, selectors, probes) lives **only** in step definitions. Behaviours are provoked by **real actions**, not by setting internal flags. | DEC-061 | Repo |
| REQ-SBE-004 | The `.feature` **MUST** obey the honesty hard-rules: real falsifiable assertions, no silent swallow (failure ⇒ RED, per-group `[coverage]` tally), no fake green (a case is asserted or an explicit `@skip` with a tracked reason), UI-driven self-provisioning fixtures, hermetic/LLM-less determinism, ≤10 grouped features (one webm each). | DEC-061, DEC-057 | Repo, Devkit |
| REQ-SBE-005 | **Common lifecycle and BDD wiring are the devkit's responsibility, batteries-included** — the playwright-bdd runner/config, the shared step library, and the common lifecycle `.feature`(s)+steps (install / uninstall / boot / probe-enable / onboarding-suppression). Plugins **MUST** consume them by reference via the `tests/_testkit` submodule and **MUST NOT** copy them. A plugin's run **composes** devkit-common features+steps **+** the plugin's own behaviour `.feature` + plugin-specific steps. | DEC-062, DEC-063 | Devkit |
| REQ-SBE-006 | Agent-driven behaviours (e.g. "the agent asks…") **MUST** be triggered by a **deterministic seam** that invokes the real handler without an LLM, so behaviour-true scenarios stay hermetic — extending the `dump_live` philosophy (DEC-057) from observation to **triggering**. A real LLM turn is used only when a behaviour is genuinely un-seamable. | DEC-064, DEC-057 | Repo, Devkit |

---

## 6. Verification

_(One row per REQ, added in lockstep.)_

| ID | Method | Acceptance |
|---|---|---|
| REQ-DEV-001 | Inspection | No plugin repo contains harness/Playwright/orchestration code or a devcontainer def outside the vendored devkit; grep across repos returns none. |
| REQ-DEV-002 | Inspection | Each repo vendors only the devkit submodule; no `.skills` full-library submodule; tracked copied files are minimal vs submodule references. |
| REQ-DEV-003 | Demonstration | The published devcontainer image boots an A0 container nested + rootless (no `--privileged`); the same image runs a lifecycle in CI and on a developer/AI machine. |
| REQ-DEV-004 | Inspection | A repo's tracked files match the allowed-asset list; CI flags any out-of-contract tracked file. |
| REQ-DEV-005 | Inspection | Generated IDE integration is Claude-only; no `.antigravity`/Copilot artifacts are produced. |
| REQ-DEV-006 | Inspection | Every plugin repo contains the identical vendored AI-code-review guide. |
| REQ-DEV-007 | Demonstration | The Phase-0 spike boots A0 rootless+nested on the chosen runner and passes Appendix E.6's acceptance test; the fallback is documented. |
| REQ-CONF-001 | Demonstration | `make conformance` passes on a conforming repo and fails on a repo missing a target or carrying an out-of-list asset. |
| REQ-CI-001 | Demonstration | Triggering the resync mechanism updates the devkit submodule pin and opens an auto-merge PR. |
| REQ-CI-002 | Demonstration | A PR in a conforming repo runs the full lifecycle to green with no repo-local harness code. |
| REQ-CI-003 | Inspection | CI run shows install / verify-installed / uninstall / verify-uninstalled as separate, named, individually pass/fail steps under one boot. |
| REQ-CI-007 | Inspection | The workflow's `on:` block lists pull_request→main, workflow_dispatch, and schedule; no feature-branch push trigger. |
| REQ-CI-004 | Inspection | The e2e workflow body exists only in the devkit; plugin repos hold a thin `uses:@<ref>` caller. |
| REQ-CI-005 | Demonstration | The same plugin's e2e runs against both the default upstream image and an overridden fork image via parameter. |
| REQ-CI-006 | Inspection | The CI job runs inside the devcontainer and boots A0 nested with no privileged flag / no docker.sock mount. |
| REQ-MK-001 | Inspection | `make help` in every repo lists the identical common target set with identical contracts. |
| REQ-MK-002 | Inspection | Removing the included devkit fragment breaks the common targets; only hook targets differ between repos. |
| REQ-MK-003 | Demonstration | A reference plugin implements a hook target via container-exec (non-Playwright) and passes CI. |
| REQ-LC-001 | Demonstration | A plugin declaring ≥2 cases runs N serial install→verify-installed→uninstall→verify-uninstalled cycles in one boot; CI shows each cycle. |
| REQ-LC-002 | Inspection | `cases.yaml` drives the loop; a plugin without one runs exactly one default case. |
| REQ-LC-003 | Demonstration | Two cases producing observably different installed state both verify correctly within one boot. |
| REQ-LC-004 | Inspection | `install/enable/disable/uninstall/up/down` are identical across repos and sourced from the devkit fragment. |
| REQ-LC-005 | Demonstration | A deliberately-failing case reports its case+stage, tears down, and (default) skips remaining cases. |
| REQ-LC-006 | Demonstration | A `requires_reboot: true` case restarts the A0 container and verifies a boot-only setting takes effect. |
| REQ-VER-001 | Demonstration | Breaking only the per-plugin hook fails verify-installed at stage (b); breaking a declared dep fails at stage (a). |
| REQ-VER-002 | Demonstration | After the hook exercises the plugin, each declared distribution resolves via importlib.metadata; a removed/misnamed declared dist fails with a specific message. Pip-name≠import-name cases (e.g. PyYAML→yaml) pass. |
| REQ-VER-003 | Demonstration | A reference plugin implements its verify-installed hook via container-exec (non-Playwright) and passes. |
| REQ-VER-006 | Inspection/Demonstration | A hook returning non-zero fails its stage; a hook receives the documented env-var context; an absent hook is a no-op pass. |
| REQ-VER-004 | Demonstration | After uninstall, an injected residue in any layer is caught; the plugin's OWN declared deps persisting (expected per F.1) do NOT trip the scan; ambient A0 drift does not false-fail. |
| REQ-VER-005 | Demonstration | A plugin whose uninstall hook leaves residue fails CI with a defect-labelled verify-uninstalled report. |
| REQ-ROL-001 | Inspection | Rollout history shows devkit → template+livekit → fan-out ordering; no batch migration precedes a green reference. |
| REQ-ROL-002 | Inspection | Each plugin repo has the e2e PR gate; the vendor-plugins publish workflow is unchanged (no e2e step added). |
| REQ-ROL-003 | Inspection | A migrated repo no longer vendors the full skills lib; only the devkit submodule remains. |
| REQ-ROL-004 | Inspection | `SPEC.md` exists at the devkit repo root. |
| REQ-ROL-005 | Demonstration | Cycle-2 lands devkit→template→reference→fan-out; new conformance checks run report-only before gating; no single PR flips all 19 repos. |
| REQ-GOV-001 | Inspection | `SPEC.md` + `SPEC-REVIEW-*.md` exist at the devkit root; no canonical copy remains only in the workshop. |
| REQ-GOV-002 | Inspection | Appendix F + `docs/` capture the A0 quirks/gotchas an implementer needs; none are flagged "memory-only". |
| REQ-GOV-003 | Demonstration | Each new binding REQ maps to a `make conformance` assertion or an e2e gate step. |
| REQ-SKL-001 | Inspection | The devkit `skills/` tree contains the Appendix E.7 set; sync refreshes them. |
| REQ-SKL-002 | Inspection | Every repo's `CLAUDE.md` carries the marker-delimited common block byte-identical org-wide; repo-specific content sits outside the markers. |
| REQ-SKL-003 | Demonstration | Running devkit-sync updates the vendored skills + the common CLAUDE block in a consumer via PR. |
| REQ-DOC-001 | Inspection | Every repo has `DEVELOPING.md` matching the devkit template's common sections. |
| REQ-DOC-002 | Inspection | Every README contains the Appendix E.8 headings in order; `make conformance` flags a missing section. |
| REQ-DOC-003 | Inspection | The README references the committed media at the known path; the asset exists. |
| REQ-DOC-004 | Inspection | Every plugin declares `a0_compat`; `fork-required` entries link the fork repo and name the change; value matches the e2e image. |
| REQ-DOC-005 | Inspection | `plugin.yaml` has a non-empty `description`; the thumbnail is not the placeholder stub (size/dimension check). |
| REQ-DOC-006 | Inspection | `.devkit.yml depends_on` (if any) lists existing plugins; the README "Dependencies" section matches it. |
| REQ-LIC-001 | Inspection | Every first-party repo has Apache-2.0 `LICENSE` + matching `plugin.yaml license`. |
| REQ-LIC-002 | Inspection | Fork repos retain + declare their upstream license; none are force-relicensed. |
| REQ-MED-001 | Demonstration | An e2e run emits the screenshot + behaviour GIF/video artifacts. |
| REQ-MED-002 | Inspection | The README media path holds the harness-captured assets; overrides are explicit. |
| REQ-MED-003 | Demonstration | The captured GIF is produced by running the behaviour verify; disabling the verify removes the GIF. |
| REQ-DR-001 | Demonstration | `doctor.py` exists at the known path; it fails when a declared dep is removed or config is invalid, and passes when healthy. |
| REQ-DR-002 | Demonstration | Running `doctor.py` inside booted A0 prints per-check PASS/FAIL with the documented exit codes. |
| REQ-DR-003 | Demonstration | The e2e runs doctor post-install and fails the gate when doctor reports unhealthy. |
| REQ-BEH-001 | Demonstration | The `verify-installed` hook drives real plugin behaviour in nested A0; stubbing the behaviour (not the files) fails it. |
| REQ-BEH-002 | Inspection | The PR e2e includes the behaviour verify as a gating step. |
| REQ-BEH-003 | Inspection | The media-capture flow and the behaviour verify reference the same scripted flow. |
| REQ-SBE-001 | Inspection | The plugin's `docs/spec/` holds the four pipeline artifacts; commit history / authorship shows the staged subagent reviews (QA + BDD). |
| REQ-SBE-002 | Inspection | The four docs exist under `docs/spec/`, are plugin-specific, and contain no common-lifecycle content (no install/uninstall scenarios). |
| REQ-SBE-003 | Demonstration | A `.feature` grep finds no selectors/DOM-ids/CSS-classes/store-names/`showModal`-style flags in `Given/When/Then`; a BDD-expert review confirms declarative behaviour. |
| REQ-SBE-004 | Demonstration | The run emits per-group `[coverage]` tallies; a deliberately-broken assertion turns the group RED; no `@skip` lacks a tracked reason. |
| REQ-SBE-005 | Inspection | The plugin repo contains no copy of the common lifecycle features/steps or the runner config; they resolve from `tests/_testkit`; the run executes both common + plugin-specific groups. |
| REQ-SBE-006 | Demonstration | The behaviour trigger runs with no LLM configured; disabling the seam (probe off) makes the triggered scenarios RED, not silently green. |

---

## Appendix A — Decisions log

_(DEC-NNN entries written immediately as each decision is made.)_

**DEC-001 — Devkit is a vendored library, not a container image.**
⚠️ **SUPERSEDED by DEC-018.** _Original: the devkit stays a vendored submodule and there
is no bespoke devkit image, only the A0 image under compose. Rationale at the time: an
image adds maintenance for no capability the compose+library model lacks. DEC-018 reverses
the conclusion — a devcontainer image provides a capability the host-compose model lacks:
one portable execution environment shared by CI, developers, and AI agents, with rootless
nested containers. The submodule-vendoring half of DEC-001 survives (see DEC-015)._
_Closed Q-001._

**DEC-002 — Two reusable workflow families.** The devkit publishes (a) a **resync**
workflow that keeps the vendored submodule current (nightly + on-demand) and opens an
auto-merge PR, and (b) a **branch/PR e2e** workflow that runs the full lifecycle
self-contained. Both are distributed by the same mechanism the org already uses for
shared workflows (caller-template copy + `make link-workflows`), mirroring the **skills
vendoring system**. _Augments DEC-001._

**DEC-003 — Repos hold only the absolute minimum.** Everything common lives in the
devkit. A plugin repo tracks only: plugin source, its seam files, thin caller workflows,
and the vendoring submodule + generated symlinks. _Refines DEC-002._

**DEC-004 — CI granularity: distinct stages, one boot.** install / effectiveness-check /
verify / remove / purge run as separate, individually-reported stages against a single
booted A0 instance. _Closes Q-002._

**DEC-005 — Seams are language-agnostic Make targets (template-method hook methods).**
The plugin overrides hook targets (`verify`, and others per DEC-006); each may be
implemented with Playwright, container exec/SSH, API calls, or scripts. The devkit owns
the skeleton (boot, login, generic install/uninstall mechanics, orchestration, residue
scan). _Closes Q-003. Supersedes the earlier "verify-only seam" framing — there are
several hook methods._

**DEC-006 — The lifecycle is a serial config-matrix, richer than three operations.**
A plugin declares ≥1 configuration. For each configuration the harness runs
`install(config) → effectiveness-check → verify → remove`, serially, within one boot.
After the last configuration, a final cleanup pass runs `purge`. The operations:
- `install(config)` — generic zip install + plugin-supplied per-config settings.
- **effectiveness-check** — confirms the install materially took effect (packages
  present, config landed, routes/extensions registered). _Provisional name; the user
  referred to it as `docker` — final name pending Q-012._
- `verify` — plugin-specific functional assertion for the active config.
- `remove` — uninstall, enabling reinstall with the next config.
- `purge` — final residue assertion (see DEC-007).
_Augments DEC-005._

**DEC-007 — Residue is a flagged defect, not silent cleanup.** `purge` exists to prove
a clean uninstall. If it finds any leftover (disk / API / UI / pip deps / settings), it
fails the build and reports the leftover as a plugin defect — because a conforming
plugin's uninstall path should have removed it. _Augments DEC-006. Realised by
`verify-uninstalled` per DEC-009._

**DEC-008 — Frozen common target vocabulary.** The target set is frozen as Appendix E.1:
artifact (`build`, `package`); generic lifecycle interface (`up`, `down`,
`install`, `enable`, `disable`, `uninstall` — aliases `delete`/`remove`, `e2e`/`ci`);
assertions (`verify-installed`, `verify-uninstalled`); plus the unchanged skills-linking
targets. `uninstall`, `delete`, `remove` are one operation. _Refines DEC-005._

**DEC-009 — No standalone `purge` / `verify`; two assertion targets instead.** The
effectiveness check, the functional verify, and the residue check collapse into two
targets, each `common-checks → per-plugin-hook` run in series:
- `verify-installed` — common install-effectiveness + per-plugin functional hook.
- `verify-uninstalled` — common residue scan + optional per-plugin residue hook.
The user's "doctor" diagnostic is realised as the common stage of `verify-installed`.
_Supersedes the standalone `purge` and standalone functional `verify` from DEC-006._

**DEC-010 — `enable` / `disable` are first-class lifecycle targets.** They are part of
A0's common plugin interface (toggle), so the devkit exposes them generically. The
default lifecycle installs enabled; plugins that need to exercise enable/disable
transitions do so from their `verify-installed` hook. _Augments DEC-008._

**DEC-011 — `verify-installed` common stage = declared-deps check + unzip-structure
check.** Two deterministic, devkit-owned checks run before the per-plugin hook:
1. **Declared dependencies present** — the plugin declares its dependencies in its
   manifest using the *same shape/options as the infra env-descriptor* (Appendix E.3);
   the devkit checks each is actually installed in the running container.
2. **Unzip/structure landed** — the plugin's files are present at their expected paths
   after install. Common logic; never reimplemented per plugin.
_Augments DEC-009._

**DEC-012 — Config-matrix via declarative `cases.yaml`.** A plugin declares its serial
configuration cases in `tests/e2e/cases.yaml` (Appendix E.2): a list of `{name, config}`
entries. The devkit loops over them in one boot, applying each case's `config` after
install via the A0 plugin config API. No `cases.yaml` ⇒ one default (empty-config) case.
_Closes Q-013, Q-014._

**DEC-013 — `verify-installed` common checks reuse existing declarations; no new
dependency schema.** The two common checks read what plugins already ship:
1. **Deps present** — every package in the plugin's `requirements.txt` is importable in
   the running container (this is the canonical pip declaration; A0's `hooks.py` installs
   it on enable). Each operator-config/secret env var declared in `meta.yaml` `env[]`
   (`kind: config|secret`) is present in the container environment.
2. **Structure landed** — the file set is derived **automatically from the packaged
   zip**; the devkit asserts those paths exist under `/a0/usr/plugins/<name>/`. No
   plugin-authored structure manifest.
_Closes Q-016, Q-018. Refines DEC-011 (supersedes the placeholder `dependencies:` block
in Appendix E.3 — reuse `requirements.txt` + `meta.yaml` instead)._

**DEC-014 — `verify-uninstalled` cadence + baseline.** `verify-uninstalled` runs after
**every** `uninstall` in the matrix loop (cheap per-case residue insurance) and is the
final action. The residue baseline is a **pre-install snapshot** of the relevant surfaces
(plugin dir, pip freeze, settings keys, plugin API list); after uninstall the harness
asserts return-to-baseline. `cases.yaml` MAY override expectations per case. Exact
per-surface snapshot/diff mechanism is Cluster 4. _Closes Q-017._

**DEC-015 — Vendor ONLY the devkit, minimally; reuse the skills bootstrap mechanism.**
Plugin repos stop vendoring the full skills library (too broad a context for plugin work).
They vendor **only the devkit** as a git submodule. The skills repo's bootstrap + sync
*mechanism* is **ported into the devkit** so the devkit can (a) bootstrap itself into a
new plugin repo and (b) render the first version of the pipelines — but the vendored
surface is kept to the **minimum**, preferring **submodule references over copied files**.
_Refines DEC-002, DEC-003; keeps the submodule half of DEC-001._

**DEC-016 — Claude-only IDE integration.** The ported mechanism drops Antigravity and
Copilot generation (they add noise). Only Claude integration is actively supported and
kept minimal. Other link targets MAY remain wired but unused. _Augments DEC-015._

**DEC-017 — Vendor a shared AI-code-review setup (Claude-native).** Every plugin repo
gets a thin `claude-code-review.yml` workflow using `anthropics/claude-code-action@beta`
routed to the `/code-review` plugin (`code-review@claude-code-plugins`), fork-safe via
`pull_request_target`, authed with the org `CLAUDE_CODE_OAUTH_TOKEN` secret — the existing
ecosystem standard (canonical: gitnexus). A shared review rubric is vendored alongside so
local (agent-driven) and CI reviews share one standard. No CodeRabbit; Gemini is legacy.
_Closes Q-022. Augments DEC-015._

**DEC-021 — e2e triggers.** The e2e workflow runs on: PR → `main` (the merge gate),
`workflow_dispatch` (manual re-runs, e.g. against a new A0 image), and a nightly schedule
against upstream `latest` (drift-catch). Pushes to feature branches are NOT a default
trigger (developers/AI run the lifecycle locally in the devcontainer instead — DEC-018).
_Closes Q-020._

**DEC-022 — Residue detection is snapshot + diff across all four layers.**
`verify-uninstalled`'s common stage snapshots, before install: (1) the plugin-dir
filesystem listing, (2) `pip freeze`, (3) settings.json keys, (4) the `plugins_list` API.
After each uninstall it asserts exact return-to-baseline on all four; any delta is residue
⇒ fail-as-defect (DEC-007). The per-plugin residue hook (DEC-009 stage b) remains
**optional**. _Closes Q-009. Refines DEC-014._

**DEC-023 — Conformance is enforced per-repo only; the gate is unchanged.** Each plugin
repo's PR gate runs the full e2e and is the enforcement point. The
`agent-zero-vendor-plugins` gate keeps its current static checks (zip sanity, secrets
hygiene, meta sync) and is **not** extended with e2e. _Closes Q-010._

**DEC-024 — Phased rollout: devkit → reference → fan-out.** (1) Build the devkit
(devcontainer image + reusable e2e workflow + ported Claude-only bootstrap). (2) Prove
it end-to-end on the template + `livekit` (existing adopter). (3) Fan out to the other
~18 repos via the bootstrap/resync mechanism, de-vendoring the full skills lib down to
the devkit-only surface per repo, adding `cases.yaml` + verify hooks. Each phase validates
before the next. _Closes Q-024._

**DEC-025 — SPEC canonical home is the devkit repo.** This SPEC lives at
`agent-zero-plugin-development-testkit/SPEC.md` — with the component that implements the
contract. _Closes Q-011._

---

### Post-review closures (SPEC-REVIEW-001)

**DEC-026 — Hook-target ABI is pinned (Appendix E.4).** A per-plugin hook is an
executable at a fixed path (`tests/e2e/hooks/verify-installed`,
`tests/e2e/hooks/verify-uninstalled`); the common target invokes it. **Pass/fail = exit
code** (0 = pass). The devkit passes a **fixed env-var context** (`A0_BASE_URL`,
`A0_USERNAME`, `A0_PASSWORD`, `A0_CONTAINER`, `PLUGIN_NAME`, `CASE_NAME`,
`CASE_CONFIG_JSON`, `A0_REPORT_DIR`). A missing hook ⇒ that stage is a no-op pass.
_Closes Critical-1. Augments DEC-005/009._

**DEC-027 — Dep check matches A0's lazy-install reality (Appendix F.2).** A0 installs
plugin deps **lazily at first use**, not on install, and never uninstalls them. So the
common dep check (a) parses `requirements.txt` to **distribution** names (handling
specifiers/extras/markers/URL/`-r` includes), and (b) asserts each declared distribution
**resolves via `importlib.metadata` after the verify-installed hook has exercised the
plugin** (which triggers lazy install). Functional `import` correctness stays in the
per-plugin hook. _Closes Critical-3._

**DEC-028 — Single-boot config-matrix is valid for `config.json`; boot-only config uses
a restart flag.** A0 reads `config.json` **live per-operation** (Appendix F.3), so
post-install API config application within one boot is correct for the common case. For
the narrow **boot-only** class (env-var-derived settings, MCP settings — Appendix F.4), a
case MAY set `requires_reboot: true` (Appendix E.2), instructing the harness to restart
the A0 container for that case. _Closes Critical-2. Refines DEC-012._

**DEC-029 — Residue scan is scoped to plugin-attributable, undeclared deltas.** Because
A0 does not uninstall deps (Appendix F.1), the `pip freeze` layer asserts **no
*undeclared* package leaked** and **excludes the plugin's own `requirements.txt`
distributions** (their persistence is expected A0 behaviour, not a plugin defect). The
fs/settings/API layers diff only **plugin-attributable** keys/paths/entries, not ambient
A0 drift. _Closes Major-4. Refines DEC-022._

**DEC-030 — `meta.yaml env[]` presence check splits by kind.** `kind: config` ⇒ env var
MUST be **set and non-empty**. `kind: secret` ⇒ only **declaration-wiring** is checked
(the var is wired into the container env; a placeholder value is acceptable), since real
secrets are absent in e2e. The devkit provides a **secret-stub injection** path for CI.
_Closes Critical-5. Refines DEC-013._

**DEC-031 — Devcontainer feasibility is a Phase-0 gate.** The rootless-nested-podman
model (DEC-018) MUST be proven by a feasibility spike (Q-021) **before Phase 1 of rollout**
(DEC-024): boot an A0 container rootless+unprivileged inside the devcontainer on
GH-hosted `ubuntu-latest`, with an explicit acceptance test. If GH-hosted runners can't
do it (e.g. missing `/dev/fuse`, subuid/subgid), a **self-hosted-runner fallback** is the
documented alternative. The contract clauses stay normative MUST; the *mechanism* is
proven first. _Closes Critical-4._

> **✅ PHASE-0 PASSED on GH-hosted `ubuntu-latest` (2026-06-20, run `ee1a4fb`).** The
> `devcontainer-spike` workflow built the devcontainer, ran a nested rootless container,
> **booted the real `agent0ai/agent-zero:latest` image nested + unprivileged**, hit
> `/login` healthy, and established an authenticated session — `PHASE-0 ACCEPTANCE PASSED`.
> The DEC-018 devcontainer model is no longer an assumption. Findings hardened along the
> way: DEC-039 (base image), DEC-040 (sshd self-destruct), DEC-041 (port-80 bind). The
> self-hosted-runner fallback is therefore **not needed**. Phase 1 is unblocked.
>
> **Empirical update (2026-06-19):** the core mechanism is **proven on a real Linux host**.
> Rootless podman-in-podman ran with **no `--privileged`** — flags
> `--device /dev/fuse --security-opt label=disable`, nested container pulled+ran. Prereqs
> present: `/dev/fuse`, subuid/subgid for the run user, `fuse-overlayfs`, `newuidmap`,
> userns enabled. **Spike finding → DEC-039.** Remaining Phase-0 work is the **full**
> Appendix E.6 acceptance (boot the actual A0 image nested) on **GH-hosted `ubuntu-latest`**
> — authored as the `devcontainer-spike` workflow (PR #8) so the real runner is the proof.

**DEC-044 — Devkit is the SOLE vendored submodule in plugin repos; the skills-sync
*mechanism* is copied into the devkit. (Supersedes the `.skills`-mediated vendoring in
DEC-015/DEC-002.)** Plugin repos vendor **only** the devkit
(`agent-zero-plugin-development-testkit`), as a **direct** submodule at `tests/_testkit` —
NOT transitively via a `.skills` submodule. The full skills library is too wide/specific
for plugin work, and the devkit is self-contained (intended to open-source alongside the
plugins). Plugin repos therefore **remove `.skills` and the `skills-sync` workflow**.
The skills-sync *distribution mechanism* (genuinely useful) is **ported into the devkit**
as **`devkit-sync`**: a reusable `workflow_call` sync workflow + a caller-template + `link-*`
Makefile targets + GitHub-App auth (the same App, already installed on the devkit repo). It
keeps each consumer's devkit submodule current and renders the e2e caller workflow, opening
auto-merge PRs — exactly like skills-sync, but devkit-scoped. _Earlier PR #15 (bumping the
devkit *inside* `.skills`) was closed as the abandoned path._

**DEC-042 — Canonical plugin-repo layout.** A standardized plugin repo places the plugin
source — the exact install payload — at **`usr/plugins/<name>/`** (mirrors the A0 runtime
path `/a0/usr/plugins/<name>/`, so repo layout == deployed layout and packaging is "zip the
contents of `usr/plugins/<name>/`"). Plus the standardization wrapper: `tests/e2e/hooks/`
(the seam), `tests/_testkit` (symlink → vendored devkit), `.skills` (submodule),
`.github/workflows/` (caller workflows), `Makefile` (`-include` the devkit fragment).
First-party plugins migrate to this; the template (`agent-zero-new-plugin-template`) moves
`my_plugin/` → `usr/plugins/<name>/`. _Resolves the divergent-layout problem (livekit
`usr/plugins/livekit/`, gitnexus `dist/gitnexus/`, mermaid `mermaid_diagrams/`, root, …)._

**DEC-043 — Forked plugins keep upstream layout via a declared `.devkit.yml`.** A plugin
that is a fork the operator keeps **upstreaming changes to** MUST NOT be forced to DEC-042's
layout (it would diverge from upstream and break PR round-tripping). Instead the fork adds a
repo-local `.devkit.yml` declaring `plugin_dir:` (where upstream keeps the source) and
optional `display_name:`. The plugin source stays put; the fork only *adds* the
standardization wrapper (which doesn't collide with upstream merges). **plugin_dir resolution
(harness + Makefile + reusable workflow):** `.devkit.yml` `plugin_dir` → else canonical
`usr/plugins/<name>`. This is a first-class escape hatch, not a workaround. The SAME escape
hatch serves **build-generated** plugins whose manifest is produced into a build dir (e.g.
gitnexus → `dist/gitnexus/`), even when first-party. _Fan-out has two tracks: **reshape**
(first-party → DEC-042) and **declare** (forks + build-generated → `.devkit.yml`)._

> **Classification (confirmed by operator 2026-06-20):**
> - **Declare `.devkit.yml`** (keep layout): forks `commands`, `phantom-bridge`,
>   `ask-user-question`; build-generated `gitnexus` (`dist/gitnexus`).
> - **Reshape → `usr/plugins/<name>/`** (first-party): `livekit` (already there),
>   `mermaid-diagrams`, `browser-interactive`, `context-scoping`, `conversational-mode`,
>   `claude-code-profile`, `mcp-tool-filter`, `intent-graph`, `detailed-prompts`,
>   `fullscreen-toggle`, `task-controls`, `share-chat`, `chat-comments`, `chat-goals`,
>   `diff-visualizer`.
> - **Out of scope** (archived, though also forks): `chat-reorder`, `archive-chats`,
>   `project-folders`.

**DEC-041 — Nested A0 reaches the harness via outer-sysctl + host-net, not `-p`.**
Spike finding (CI run 23ae917): A0's UI binds `0.0.0.0:80`, a privileged port; under
nested rootless podman the inner container's mapped-root can't bind it
(`PermissionError [Errno 13]`). Also the inner container defaults to **host netns**, so a
`--sysctl` on the *inner* run is rejected (`Network Namespace set to host`). Verified-working
model: run the **devcontainer (outer)** with `--sysctl net.ipv4.ip_unprivileged_port_start=0`
and the **A0 (inner)** container with `--network=host`; A0 then binds 80 on the shared
devcontainer netns and the harness reaches it at `localhost:80`. Confirmed locally
(`REACHED_80_OK`). _Refines DEC-032 (the nested boot/network contract). Alternative for
production: configure A0 to serve a high (≥1024) port and use a normal rootless netns + `-p`._

**DEC-040 — The rootless e2e harness MUST neutralize A0's `sshd` (or make it
non-fatal).** Spike finding (CI run 156e82a): A0's `[program:run_sshd]` (`/usr/sbin/sshd
-D`) **exits 255 under rootless podman** (privilege separation needs caps a mapped-root
lacks); A0's `[eventlistener:the_listener]` runs with **no args**, so its
`if not args or ...` kills the **entire instance** on *any* process `PROCESS_STATE_FATAL`
— so a flapping sshd tears A0 down ~8s after boot. (The current harness never saw this:
it runs under docker/rootful, where sshd starts.) SSH is irrelevant to HTTP e2e, so the
harness replaces `/usr/sbin/sshd` with a no-op before `initialize.sh` (keeps the watchdog
armed for genuinely-critical procs like `run_ui`). _Long-term: upstream A0 should scope
`the_listener` to critical processes only, or make sshd optional. Appendix F.6._
_Refines DEC-018/032._

**DEC-039 — Devcontainer base MUST ship a modern podman; not Playwright+apt-podman.**
Spike finding: basing on the official Playwright image (Ubuntu jammy) + apt `podman`
(3.4.4) **fails** to nest rootlessly (`cannot setup namespace using newuidmap`). Basing on
`quay.io/podman/stable` (podman 5.8.2, pre-configured `podman` user with working
subuid/subgid + newuidmap caps) **nests cleanly** (verified locally: `NESTED_IN_DEVKIT_OK`,
unprivileged). Therefore the devcontainer bases on a modern-podman image; **Playwright
browser deps become a Phase-1 Fedora addition** (Playwright's `--with-deps` is
Debian/Ubuntu-only). The Phase-0 gate needs no browser, so the spike image carries only
podman + curl. _Refines DEC-018/031; resolves part of Q-021._
> **Phase-1 update (2026-06-20):** Playwright-on-Fedora **resolved** — Node v22 (dnf) +
> `playwright@1.48.0` + `chromium` with an explicit Fedora lib set; headless Chromium
> launches inside the nested rootless devcontainer (`CHROMIUM_OK 130.0.6723.31`). DEC-039's
> "Fedora browser deps" concern is closed.

**DEC-032 — Nested boot/network contract (output of the Q-021 spike).** Inside the
devcontainer, A0 is booted via rootless podman (or `podman compose`); the harness reaches
it at `A0_BASE_URL` over a pinned network/port mapping. The spike MUST pin: the compose
engine, the network mode, the port contract, and required volumes. `up`/`down` (E.1) are
redefined to drive this nested boot, superseding the host-compose phrasing inherited from
the pre-DEC-018 era. _Closes Major-8._

**DEC-033 — Canonical terminology cleanup.** One term per concept: the post-install
diagnostic is the **common stage of `verify-installed`** — the names
`effectiveness-check`, `doctor`, `docker`, standalone `verify`, and `purge` are
**non-normative/historical** and MUST NOT appear in REQs. REQ-CI-003's stage list is
corrected to `install / verify-installed / uninstall / verify-uninstalled`. _Closes
Major-2, Major-3._

**DEC-034 — One canonical allowed-asset list (Appendix E.5).** A single list supersedes
the divergent enumerations in REQ-DEV-002/004 and DEC-003/016/017. It includes plugin
source, `plugin.yaml`/`meta.yaml`/`default_config.yaml`/`requirements.txt`,
`tests/e2e/cases.yaml`, the `tests/e2e/hooks/*` scripts, the thin caller workflow, the
AI-review workflow + rubric, the minimal Claude surface, the devkit submodule, and
generated symlinks. _Closes Major-6._

**DEC-035 — Snapshot baseline is captured once, pre-case-1.** The residue baseline is
taken **once** before the first install; every `verify-uninstalled` diffs against that
single baseline, so cross-case leakage (case 1 leaves residue surviving case 2's cycle)
is caught. _Closes Major-5. Refines DEC-014._

**DEC-036 — `enable`/`disable` are devkit primitives, hook-callable, not mandatory loop
stages.** Given deferred-unload semantics (Appendix F.5), the standard loop does not force
a toggle stage; `enable`/`disable` are primitives the `verify-installed` hook MAY invoke
to assert enabled/disabled behaviour. A reference plugin MUST exercise them (verification).
_Closes Major-1. Refines DEC-010._

**DEC-037 — A devkit-provided `conformance` check enforces structural conformance.**
`make conformance` (run in each repo's PR gate, per DEC-023) asserts the repo exposes the
frozen E.1 target set and matches the E.5 asset list — this is how G5 "mechanical
conformance" is enforced without touching the gate. _Closes Major-9._

**DEC-038 — Structure check asserts manifest + entrypoints, not zip-path identity.** The
unzip check asserts the install dir contains `plugin.yaml` and the plugin's declared
entrypoints/extension folders; it does **not** assert a 1:1 zip↔install path identity
(A0's installer may transform/skip), and **excludes dev-only files** (`tests/`, `.github/`,
`.skills`-era cruft). _Closes Major-7. Refines DEC-013._

**DEC-018 — The devkit ships a devcontainer image (reverses DEC-001).** The devkit
publishes a single container definition carrying all execution tooling — Playwright,
SSH, node, and **rootless podman** plus nesting tooling (e.g. fuse-overlayfs) — that runs
the A0 container **nested inside it without privilege** (no `--privileged`, no host Docker
socket). The same image is the execution surface in **all three** contexts:
1. GitHub Actions CI runs the lifecycle inside it.
2. A developer uses it as a dev container.
3. An AI agent runs it (via docker or podman) to develop + test locally before pushing.
_Supersedes DEC-001. Nesting is podman-in-podman / podman-in-docker / docker-in-docker,
always rootless._

**DEC-019 — The A0 image under test is a parameter.** Defaults to upstream
`agent0ai/agent-zero` (tag policy per Q-008-followup); plugins that depend on operator-fork
changes override it to the fork image. Declared per-plugin and overridable at the
workflow/Make level. The A0 image runs as the nested container inside the devcontainer.
_Closes Q-008._

**DEC-020 — Reusable e2e workflow body lives in the devkit repo.** Referenced via
`uses: agent-zero-plugins/agent-zero-plugin-development-testkit/.github/workflows/plugin-e2e.yml@<ref>`.
The job runs the devcontainer image and invokes the lifecycle (`make e2e`) inside it. The
thin caller workflow is rendered into the plugin repo by the ported bootstrap mechanism
and kept current by the resync mechanism. _Closes Q-006; augments DEC-015, DEC-018._

### Cycle-2 decisions (authoring & polish standard, 2026-06-20)

**DEC-045 — The SPEC and acquired knowledge live in the devkit, never in assistant memory.**
`SPEC.md`, every `SPEC-REVIEW-NNN.md`, and the durable operational knowledge an implementer
needs (verified A0 runtime quirks → Appendix F; harness gotchas, fan-out classification,
runbooks → `docs/`) are committed in the devkit repo and are the **system of record**.
Assistant memory is a convenience cache only — it MUST be reconstructable from committed
artifacts. Every Cycle-2 standard MUST be machine-checkable (conformance or e2e), so the
contract is enforced, not remembered. _Opens Cycle 2; closes the operator ask "keep all
acquired knowledge in a form we can retrieve and query."_

**DEC-046 — Authoring skills + a shared CLAUDE block are vendored through the devkit.** The
devkit vendors a curated **plugin-authoring skill set** (Appendix E.7 — the subset useful
for building A0 plugins in general and ours in particular), sourced from
`agent-zero-plugins-skills` and kept fresh by the sync mechanism. Separately, every plugin
repo's `CLAUDE.md` carries a **common-guidelines block** (org-identical, delimited by
`<!-- a0:common:start -->`/`<!-- a0:common:end -->` markers so sync can replace it
in-place) plus a repo-specific section outside the markers. Plugin repos still do NOT
vendor the full skills library (consistent with DEC-015/DEC-044) — only the curated set
lives in the devkit, reachable via the submodule. **Sync hazard handling (Major-3 of
SPEC-REVIEW-002):** `CLAUDE.md` is NOT under `.github/workflows/`, so `GITHUB_TOKEN`/the App
token may write it (unlike workflow files — the DEC-044 constraint does not apply here). If
a repo's markers are missing or malformed, sync **MUST fail closed** for that repo (leave
`CLAUDE.md` untouched) and surface it (PR comment / issue), never blind-append a second
block. _Theme 2. Augments DEC-044._

**DEC-047 — Per-repo `DEVELOPING.md` from a devkit template.** Every plugin repo ships a
`DEVELOPING.md` rendered from a devkit template that explains the devcontainer and the
standard local dev/test loop using the real frozen targets (Appendix E.1): `make build →
make e2e` (which does `up → ∀case {install → verify-installed [+ behaviour + doctor] →
uninstall → verify-uninstalled} → down`), plus `make media` to refresh docs assets — so any
developer or agent reproduces CI locally. _Minor-3 of SPEC-REVIEW-002 corrected the loop to
real targets._ Common body from the devkit; a thin per-repo header names the plugin. _Theme 3._

**DEC-048 — A fixed README skeleton, plugin-specific content.** Every plugin README follows
the Appendix E.8 skeleton (fixed section set + order): title + thumbnail, one-line
description, **Why** (the rationale/problem it solves), install + behaviour media, inter-
plugin dependencies, A0 compatibility, configuration, doctor, license. Distinct prose per
plugin; identical structure so the fleet reads consistently and `make conformance` can
check section presence. _Themes 4, 6, 7._

**DEC-049 — A0 compatibility is a declared field with an *e2e-matrix* proof.** Each plugin
declares `a0_compat: upstream | fork-required` in `.devkit.yml`. _Reframed by SPEC-REVIEW-002
Critical-2: a single-image e2e cannot discriminate the two, so the value would be an
unproven assertion._ The mechanical proof:
- **`upstream`** — the plugin's e2e (behaviour verify included) MUST pass against **stock
  `agent0ai/agent-zero:latest`** (the current default). That green run *is* the proof.
- **`fork-required`** — the plugin's e2e MUST pass against the **fork image** (declared
  `a0_image`) AND the repo MUST commit the **git-history evidence**: the specific A0 fork
  change it needs, a link to the fork repo + commit/PR, and (SHOULD) a recorded run on stock
  upstream demonstrating the dependent behaviour fails or is absent. So `fork-required` is
  backed by *two* observations (passes-on-fork, and the named upstream gap), not a label.

The classification is seeded by a per-plugin **git-history analysis** (the why, the extension
points, when fork support landed) and then frozen by the matrix result.

**Fork topology (resolved from the theme-4 analysis, 2026-06-20 — Q-025 closed).** There are
**two** forks, and they play different roles:
- **Internal fork** `NuevaNext/agent-zero@nuevanext` (image `ghcr.io/nuevanext/agent-zero`) —
  fast-moving, where fork features actually land. **For now** this is the image
  `fork-required` plugins set as `a0_image` and test against (the public fork's maintenance
  has lapsed and no plugin is open-source yet, so pointing at the internal image is acceptable
  interim).
- **Public fork** `agent-zero-operator/agent-zero` — the visible upstreaming fork; the
  **target** reference (DEC-054). `agent-zero-operator/agent-zero` carries only infra changes
  today and **none** of the plugin `@extensible` seams, so it is NOT yet a valid test target.

**Theme-4 result (rigorous 19-subagent audit, all high confidence):** **18 `upstream` / 1
`fork-required`** — `context-scoping` (7 fork-only `@extensible` memory/skills/subagent seams).
**Reconciliation:** the fork made *many* plugin-supporting changes historically (27 `@extensible`
seams, ~200 commits), but the audit shows the great majority were **upstreamed** into stock
`agent0ai/agent-zero` (the whole webui `<x-extension>` framework, `init_a0` `@extensible`,
`usr/plugins` discovery, the `api/` area, notifications, `get_api_key`, …) — so *historical fork
contribution ≠ current fork dependency*; only context-scoping's 7 seams remain un-upstreamed.
**context-scoping is the proof case for DEC-053:** it ships *no* behaviour hook and *no* `a0_image`
override, so its e2e is green on stock upstream **where its scoping is inert** — a presence-only
test masking a real regression. _This static audit is the current best evidence; the durable proof
is the DEC-049 e2e behaviour matrix once behaviour hooks exist (18/19 lack them)._ The full
per-plugin classification +
evidence is committed at `docs/a0-compatibility.md`. _Theme 4; Q-025 closed; repoint-to-public
timing = Q-029._

**DEC-050 — Apache-2.0 for first-party; forks keep upstream.** Every first-party plugin
repo carries a root `LICENSE` = Apache-2.0 and `plugin.yaml license: Apache-2.0` (operator
choice 2026-06-20; matches existing author metadata). Fork plugins retain and declare their
upstream license — the Apache mandate never force-relicenses a fork. **Vendored-upstream
carve-out (Gap-5 of SPEC-REVIEW-002):** a first-party repo that vendors a third-party
upstream (e.g. gitnexus's `upstream/` submodule) applies Apache-2.0 to **its own authored
code only**; the vendored upstream keeps its own `LICENSE`, which MUST be preserved (and is
copied into the build, as gitnexus already does). _Theme 5. Augments DEC-043._

**DEC-051 — The harness *produces* README media; commit-back is an explicit, separate
mechanism.** _Reframed by SPEC-REVIEW-002 Critical-1 (the harness mounts the workspace
read-only, captures only on failure, and has no GIF tooling or commit-back — so "auto-commit
during e2e" was infeasible)._ Split into two feasible halves:
1. **Capture (MUST, in-harness):** the devkit lifecycle captures, on **every** run (not only
   on failure), a screenshot of the installed card/config screen and a short video of the
   behaviour-verify flow (DEC-053), written to the in-container report dir and uploaded as a
   **CI artifact** (`actions/upload-artifact`). The container does NOT write back into the
   read-only workspace.
2. **Publish (MUST, separate step):** media is landed at the committed path `docs/media/`
   either by (a) a developer running `make media` locally (devcontainer has the GIF tooling —
   ffmpeg/`playwright` video→GIF, pinned in Q-026) and committing the result, or (b) a devkit
   **media-publish** workflow step that downloads the artifact and commits `docs/media/` to
   the PR branch using the App token (CLAUDE.md/docs are not under `.github/workflows/`, so
   this is permitted — unlike workflow files). The behaviour clip is driven by the behaviour
   verify (DEC-053), so docs show *verified* behaviour. Authors MAY override a specific asset
   via `make media` re-runs. _Themes 4, 6 (operator chose harness auto-capture)._

**DEC-052 — `doctor` is a script at a known path (for now).** Every plugin ships
`usr/plugins/<name>/scripts/doctor.py` (or the `plugin_dir` equivalent), runnable inside a
booted A0 (`python …/doctor.py`), exit `0` iff healthy, checking: (a) each declared
dependency importable; (b) **config keys** — every key present in the plugin's
`default_config.yaml` resolves in the live config with a type-compatible value (a key/type
check, _not_ a formal JSON-schema — clarified per SPEC-REVIEW-002 Major-1); (c) the plugin's
declared **extension files** exist under the live A0 plugin dir and import without error
(clarified per Major-2 — A0 exposes no "is-mounted" introspection API, so presence +
import-clean is the feasible proxy). The e2e runs it post-install and asserts healthy. A
shared in-product command that enumerates installed plugins and runs each doctor MAY wrap
this later — deferred per operator ("just a script at a known location, for now"). _Theme 8._

**DEC-053 — Behaviour-level verify is mandatory and gating, defined by a *falsifiable*
signal.** _Reframed by SPEC-REVIEW-002 Critical-3: "real behaviour vs implementation" is not
mechanically checkable and GOV-003 forbids un-checkable MUSTs._ The enforceable definition:
the plugin's `verify-installed` hook (the frozen DEC-026 ABI — this **augments**, does not
redefine, it) MUST include at least one assertion that **drives the live A0 instance over
the wire** — a Playwright interaction against `A0_BASE_URL` or an HTTP call to an A0/plugin
API endpoint — and asserts a **plugin-specific observable effect** of that interaction.
Mechanically checkable proxy (conformance): the hook MUST reference `A0_BASE_URL` / use the
browser or HTTP client, i.e. it cannot consist solely of `podman exec` file/dep presence
checks (those remain the *common* stage's job, not the plugin behaviour stage). It runs in
the branch/PR e2e (one boot) and gates merge; the generic install→uninstall lifecycle stays
necessary but insufficient. The same scripted interaction feeds the media capture (DEC-051).
_Theme 9. Augments DEC-026._

**DEC-054 — Two-tier fork model: the public fork is the upstreaming surface; plugins repoint
to it once it's maintained.** _Added 2026-06-20 from the operator's fork-topology explanation;
closes Q-025._ The model: the **internal fork** (`NuevaNext/agent-zero@nuevanext`) is where
features land fast and is rebased into upstreamable change-groups; the **public fork**
(`agent-zero-operator/agent-zero`) is the visible surface that should carry one open PR to
upstream per change-group. Target end-state:
- **The public fork MUST carry a fork-declaration README**: a clear "this is a fork" notice,
  the *reason* for forking, a **table of open upstreaming PRs** (one row per change-group,
  each linking the PR against upstream so consumers can 👍/+1 it), and a reference to the
  **consumable fork image**.
- **Repoint plan (gated on the public fork being maintained — Q-029):** once the change-groups
  have open PRs on the public fork, every `fork-required` plugin MUST repoint `a0_image` from
  the internal `ghcr.io/nuevanext/agent-zero` to the **public** fork image, AND its README
  "Agent Zero compatibility" section MUST link the public fork (short intro: what it adds +
  why) and the specific upstreaming PR it depends on. **Until then**, the internal image is
  the accepted interim target (DEC-049) and `agent-zero-operator/agent-zero` — which today
  carries only infra changes, none of the plugin seams — is NOT a valid test target.
_Theme 4. Augments DEC-049; repoint timing = Q-029._

**DEC-055 — Fork-first e2e: the default image is the operator fork; stock upstream is added
later as a second target.** _Operator decision 2026-06-20; **supersedes** the "stock-upstream
default + fork-required override" stance of DEC-019/DEC-049._ The e2e default `a0_image` is the
**latest operator fork image** `ghcr.io/nuevanext/agent-zero:latest-nonroot` — the real
deployment target, so we test what we actually ship. Every plugin's e2e runs against it (a
single-target matrix) and MUST pass. **Then**, once behaviour hooks (DEC-053) exist and the
fork-target matrix is green on GitHub, add **stock upstream** (`agent0ai/agent-zero:latest`) as
a *second* image via a one-line `.devkit.yml`/matrix entry; the behaviour tests that **fail** on
stock upstream then (a) empirically identify the genuinely `fork-required` plugins and (b)
validate that the behaviour tests are correctly written (a fork-dependent feature's test MUST
fail on stock). So `a0_compat` becomes an **output of the two-image observation**, not a
hand-asserted label — the durable form of DEC-049's matrix. The fork image is **private** (ghcr),
so the e2e MUST authenticate to pull it; auth mechanism = Q-030. _Reframes DEC-049 to fork-first;
context-scoping no longer needs a per-repo `a0_image` override (the default is already the fork)._

**DEC-056 — In-browser behaviour seam (`tests/e2e/behaviour.mjs`).** _Refines DEC-053; added +
implemented 2026-06-21._ Because most plugins are UI injections, the falsifiable behaviour check
is expressed (preferably) as an **in-browser seam**: a plugin ships `tests/e2e/behaviour.mjs`
default-exporting `async ({ page, expect, pluginName, displayName, baseURL }) => {…}`, which the
devkit lifecycle runs against the **live authenticated A0 page** right after install. It MUST
assert a plugin-specific observable effect over the wire (e.g. its injected element is visible),
and the screenshot it produces (`behaviour.png`) is the DEC-051 media source. The bash
`verify-installed` hook (DEC-026/Appendix E.4) remains for container/API checks; a plugin uses
whichever fits (UI → `behaviour.mjs`; backend/API → hook), and **at least one** MUST carry a
falsifiable behaviour assertion (REQ-BEH-001). Absent both, the lifecycle logs the gap (a future
conformance check can require ≥1). The lifecycle re-opens the Plugins modal after the seam so a
behaviour that navigates can't break uninstall. _Implemented: devkit `6da09130`; validated on the
sample-e2e self-test. Contract in Appendix E.11._

**DEC-057 — Plugin-declared nested-A0 env (`e2e_pod_env`) + no-silent-swallow honesty rule.**
_Refines DEC-053/056; added 2026-06-21 after the context-scoping pilot exposed hollow coverage._
A plugin whose behaviour sits behind an **env-gated test seam** (a deterministic in-pod probe kept
OFF in production, e.g. gated by `A0_<PLUGIN>_TEST_PROBE=1`) declares the enabling env in
`.devkit.yml` `e2e_pod_env:` (a YAML map, or inline `"K=V K2=V2"`). The reusable workflow flattens
it to `A0_POD_ENV` and the harness (`a0-up.sh`) forwards each entry as `-e KEY=VAL` into the nested
A0 pod — so the seam is live for e2e **only**. This closes the trap the pilot hit: 34/65 behaviour
cases were calling a disabled probe, erroring, and being **swallowed by best-effort `try/catch`** →
the gate was green but verified nothing. Two coupled honesty requirements (REQ-BEH-002):
(a) **best-effort `try/catch` is reserved for genuinely un-enableable env** (a real LLM agent turn,
OS clipboard) — anything reachable via a declared `e2e_pod_env` seam MUST **hard-assert** so a
disabled/broken seam goes RED; (b) **no fake green** — a behaviour case is either genuinely asserted
(logs `✓`) or explicitly `SKIP(reason)` (visibly not-covered + tracked), never a bare `✓` for an
untested case. A run is reviewed by its **log body**, not just its conclusion: the harness fails if
`probe disabled` appears, and each group logs a `[coverage] <group>: asserted=N skipped=M` tally.
_Implemented: devkit `a0-up.sh`/`run-lifecycle.sh`/`plugin-e2e.yml`; validated on context-scoping
(probe ON → backend layer asserts for real)._

**DEC-058 — Behaviour groups run on `loggedInPage`, not `pluginsPage`; `openModal` is
fire-and-forget.** _Refines DEC-056; added 2026-06-21 after a behaviour group hung 300s in
fixture setup._ With no LLM key configured (the LLM-less e2e posture), A0's `_onboarding` modal
re-opens on every page load. The `pluginsPage` fixture eagerly `open()`s the Plugins panel, and
that `openModal()` fallback — being `await`ed — can hang for the whole test timeout when the
onboarding modal interferes. Two fixes: (a) per-group behaviour tests take the `loggedInPage`
fixture (they each `page.goto("/")` and never use the Plugins panel — opening it was wasted work;
the plugin stays installed as backend state regardless); (b) `PluginsPage.open()`'s `openModal`
fallback is **fire-and-forget** (invoke, don't await its promise) and gates on the panel's tab
becoming visible. Only the install/uninstall lifecycle tests still take `pluginsPage`. _Implemented:
devkit `lifecycle.spec.ts` + `PluginsPage.ts`._

### Cycle-2 review closures (SPEC-REVIEW-002, 2026-06-20)

25 findings (3 Critical · 7 Major · 5 Minor · 6 Gap · 4 XCut). Disposition:

- **Critical-1** (media infeasible) → **closed**: DEC-051 split into capture-as-artifact (MUST,
  every run) + separate publish (`make media` / App-token commit step); REQ-MED-001/002 rewritten.
- **Critical-2** (a0_compat unproven) → **closed**: DEC-049 reframed to an e2e image-matrix proof
  (`upstream` passes on stock; `fork-required` passes on fork image + committed history evidence).
- **Critical-3** (behaviour-verify unfalsifiable, redefines DEC-026) → **closed**: DEC-053 now
  *augments* DEC-026 with a mechanical proxy (hook must drive A0 over the wire via
  `A0_BASE_URL`/HTTP, not only `podman exec`); REQ-BEH-001 rewritten.
- **Major-1** (config "schema") → **closed**: DEC-052/E.9 = key/type check vs `default_config.yaml`.
- **Major-2** (extension "mounted") → **closed**: DEC-052/E.9 = declared extension files present +
  import-clean (A0 has no is-mounted API).
- **Major-3** (CLAUDE-sync hazard) → **closed**: DEC-046 fail-closed on bad markers; token may write
  `CLAUDE.md` (not a workflow file).
- **Major-4** (no Cycle-2 rollout) → **closed**: REQ-ROL-005 (phased; report-only → gating).
- **Major-5** (E.5 omits new assets) → **closed**: E.5 extended (README, DEVELOPING, LICENSE,
  .devkit.yml, docs/media, scripts/doctor.py).
- **Major-6 / XCut-1** (GOV-003 self-violation) → **closed**: REQ-GOV-003 scoped to structural
  checks (MUST/mechanical) vs semantic quality (SHOULD/human).
- **Major-7** (doctor path for fork/build-gen) → **deferred → Q-028** (DEC-052 resolves via
  `plugin_dir`; build-generated edge under Q-028).
- **Minor-2** (stale "compose harness") → **closed** (E.1). **Minor-3** (bad loop targets) →
  **closed** (DEC-047). **Minor-4** (override mechanism) → **closed** (REQ-MED-002 `make media`).
- **Minor-1** (status vs open Qs) → **accepted**: Cycle-2 design is complete; Q-025–028 are
  implementation-detail/data, not open design (mirrors Cycle-1's Q-021/023 posture).
- **Minor-5** (`skill/` vs `skills/`) → **closed**: see E.7 note (the singular `skill/` testkit
  folds into the `skills/` vendored tree).
- **Gap-1** (replace placeholder thumbnails) → **closed** (REQ-DOC-005). **Gap-4** (deps source) →
  **closed** (REQ-DOC-006 `depends_on`). **Gap-5** (vendored-upstream license) → **closed** (DEC-050).
- **Gap-2** (media size budget) → **deferred → Q-026**. **Gap-3** (non-blank media) → **accepted**
  as a SHOULD under the GOV-003 semantic-quality bucket. **Gap-6** (Cycle-2 vs gate) → **closed by
  reference**: DEC-023 stands — Cycle-2 conformance is the *per-repo* PR gate; the vendor-plugins
  gate is unchanged.
- **XCut-2** (distribution-auth hazard) → addressed wherever it appears (DEC-046 markers, DEC-051
  publish step — `CLAUDE.md`/`docs/` are writable; workflows are not, per DEC-044). **XCut-3**
  (re-opened Cycle-1 closures) → closed via E.5 + E.1/DEC-047 corrections. **XCut-4** (vacuous
  acceptances) → addressed by the Critical/Major rewrites above.

### Cycle-3 decisions (spec-driven BDD e2e, 2026-06-22)

_Cycle 3 was driven from the context-scoping pilot (DEC-057/058) + the ask-user-question BDD review.
It supersedes the ad-hoc `behaviour.mjs` (DEC-056) as the **authoring method** while keeping that
seam as a low-effort fallback._

**DEC-059 — Per-repo spec-driven e2e pipeline (multi-agent).** Each plugin's e2e is produced by a
five-step pipeline, each step authored/reviewed by a **typed subagent** (the orchestration is the
deliverable, not a one-shot): (1) reverse-engineer an after-the-fact **behaviour spec** + self-review
(IEEE-29148); (2) an after-the-fact **implementation plan**; (3) a **BDD `.feature`** derived from the
*behaviour* spec; (4) an **e2e steps spec** (test wiring); with a **QA-expert** review of coverage and
a **BDD-expert** review of Gherkin craft folded in. _Validated: the context-scoping pilot caught real
defects (hollow coverage, the zero-global migrate latch #21); the ask-user-question BDD-expert pass
caught a hidden two-in-one scenario + Then/When inversion._ Skills project FROM this (the canonical
subagent set, prompts, expected outputs, example findings) — see SKL.

**DEC-060 — The 4-doc artifact model (living, per-plugin).** Each plugin commits four documents under
`docs/spec/`: **behaviour-spec.md** (what it does — behaviour-first, reads like the BDD, not an impl
plan), **implementation-plan.md** (how it's built — locks the *product's* low-level internals),
**e2e.feature.md** (behaviour as executable spec), **e2e-steps-spec.md** (how the *tests* bind to the
product — low-level: selectors, seams, probes). #2 and #4 are the **same depth, different concern**
(product internals vs test wiring). All four are **plugin-specific** (DEC-062).

**DEC-061 — Behaviour-first BDD + honesty hard-rules.** A `.feature` asserts **observable behaviour in
domain language**; it MUST NOT contain selectors, DOM ids, CSS classes, store/internal-API names,
function-existence checks, or internal-state poking — the "how" lives only in step definitions, and
behaviours are provoked by **real actions** not internal flags. Plus the honesty rules (from DEC-057):
no silent swallow (failure ⇒ RED + `[coverage]` tally), no fake green (assert or explicit tracked
`@skip`), UI-driven self-provisioning fixtures, hermetic/LLM-less determinism, ≤10 grouped features
(one webm each), best-effort `try/catch` reserved for genuinely un-enableable env. _Reverse-engineering
from code biases toward implementation tests; sourcing the `.feature` from the behaviour spec (not the
e2e/Playwright spec) is what keeps it behaviour-first._

**DEC-062 — Plugin-specific vs common split.** Plugin repos hold **only their own behaviours** (the
four docs, scoped to that plugin). **Common lifecycle is the devkit's responsibility** and is
**linked, never duplicated** — no plugin re-states an install/uninstall/boot scenario or a common step.

**DEC-063 — playwright-bdd execution layer, batteries-included from the devkit.** The devkit ships the
playwright-bdd runner/config, the **shared step library**, and the **common lifecycle `.feature`(s) +
steps** (install / uninstall / boot / probe-enable / onboarding-suppression). A plugin's run
**composes** devkit-common features+steps **+** the plugin's own behaviour `.feature` + plugin-specific
steps, consumed by reference through the `tests/_testkit` submodule. One nested-A0 boot; one webm per
group; honest `[coverage]` tally. _Replaces the bespoke `lifecycle.spec.ts` multi-spec runner for
Cycle-3 plugins; the DEC-056 `.mjs` seam remains a fallback for plugins not yet migrated._

**DEC-064 — Deterministic behaviour triggers (seams).** Agent-driven behaviours ("the agent asks…")
are triggered by a **deterministic seam** that invokes the real handler without an LLM — extending the
`dump_live` philosophy (DEC-057) from *observation* to *triggering*. The seam is enabled for e2e only
(`.devkit.yml e2e_pod_env`); a real LLM turn (deterministic stub) is used only when a behaviour is
genuinely un-seamable. Keeps behaviour-true scenarios hermetic.

**DEC-065 — BDD CI execution harness + fork-robustness (proven by the ask-user-question pilot).**
*Augments DEC-063.* The batteries-included BDD layer is executed in CI by `e2e/harness/run-bdd.sh`
(boots A0 via `a0-up`, copies the plugin tree to a writable workspace, symlinks the devcontainer's
global `node_modules`, runs `bddgen` + `playwright test` from the **submodule's** `e2e/bdd` config with
`PLUGIN_BDD_DIR` → the plugin's `tests/e2e`, collects one webm per scenario). The reusable
`plugin-e2e.yml` **auto-branches**: it runs `run-bdd.sh` when the plugin ships `tests/e2e/features/`,
else the classic `run-lifecycle.sh` (backward-compatible for un-migrated plugins). The devcontainer
installs `playwright-bdd`. **Operational fork-robustness requirements the steps MUST observe** (the
fork image diverges from stock): (a) provision a **real persisted chat context** (`chat_create`), never
a synthetic `newContext()` — the fork's chat-restore deselects the latter, starving context-scoped
polls; (b) **hide unrelated overlays** (e.g. the no-LLM `composer-banner`) before clicking an
underlying control — and use a **real click on a clear target**, since a dispatched event bypasses the
overlay but does not trigger the framework handler. Verified: ask-user-question 12/12 BDD scenarios
green on the fork image in the `plugin-e2e` gate (+ 2 tracked `@skip` for tool-only behaviours).

**DEC-066 — Two-tier machine-checked enforcement of the BDD standard.** The standard (DEC-059–065) was
advisory; make it enforced, because humans and AI agents both cut corners. **Tier-1 (repo, hard-fail in
`plugin-e2e`, where the test files live):** a linter (`e2e/lint/bdd_lint.py`) runs three static gates —
**feature-purity** (no selectors/DOM-ids/store-names/internal-API in `Given/When/Then`), **honesty**
(every `@skip` has a tracked reason; no swallowed `catch`/`.catch`; the four `docs/spec` docs exist), and
**traceability** (every `BEH-n` in `behaviour-spec.md` is covered in `e2e.feature.md` or tracked-skipped);
plus the **seam-off red-proof** in `run-bdd.sh` — run the suite once with the plugin NOT installed and
assert **0** pass (any pass plugin-less is fake-green). **BDD behaviour tests are REQUIRED** — a plugin
with no `tests/e2e/features/` hard-fails (no exceptions, DEC-069); "installs + uninstalls" is not a
behaviour assertion. **Tier-2 (gate,
`agent-zero-vendor-plugins` publish):** **verified-publish** — optional `meta.yaml` `source_repo` +
`source_commit`; when present, publish hard-fails unless the `plugin-e2e` check was green on that commit
(the gate holds only zips, so it asks GitHub "was the upstream check green?"). **Private-repo merge:**
free private repos cannot use required status checks (paid), so a `merge-guard` job converts a red PR to
draft (deterrent, not a lock); the verified-publish gate is the hard block on *shipping* (a red plugin can
be merged but never ships). Known gap: zip↔`source_commit` trust (future content-hash). **Adoption is
per-repo on devkit-submodule bump** — hard the instant a repo is on the new devkit, no fleet breakage.
Reference + every error→fix: `docs/BDD-GATES.md`. Threat model = laziness, human and AI alike. Verified:
ask-user-question lint + red-proof (`0 passed`) + e2e 12/12 green on the fork.

**DEC-067 — Versioning: SemVer release tags, consumers track the latest tag.** The devkit moves from
pure commit-pin/track-`main` to **tagged SemVer releases** (`vMAJOR.MINOR.PATCH`), starting at **v1.0.0**.
Rationale: once the enforcement gates exist, a broken `main` reaching the fleet via nightly sync is a real
hazard; a vetted tag is the safe unit of consumption. **MAJOR** = a change that could fail a
previously-green consumer (the frozen Make target contract / Appendix E.1, reusable-workflow
inputs/behaviour, the `Makefile.devkit`/`.devkit.yml` interface, or a tightening of the gates); **MINOR** =
backward-compatible new targets/checks/assets; **PATCH** = non-contract fixes. **Consumption:** the
`devkit-sync` workflow bumps a consumer's `tests/_testkit` pin to the **latest release tag** (not `main`),
and `make update-devkit` defaults to the latest tag (override `DEVKIT_REF=vX.Y.Z`/`main`). `main` stays the
integration branch; releases are cut from it. History + policy live in `CHANGELOG.md`.

**DEC-068 — The devkit distributes the plugin-facing skills.** Problem: the devkit machinery is vendored
into every plugin (the `tests/_testkit` submodule), but the *skills that document how to use it*
(`a0-plugin-e2e-bdd`, `a0-plugin-architecture`, …) were only available via the operator's global install —
a developer/agent in a bare plugin clone didn't get them. Fix: the devkit ships a curated **`skills/`**
set, and `make link-skills` (folded into `link-devkit`, run by `init.sh`) **symlinks** them into the
plugin's `.claude/skills/`. Symlinks (not copies) so they auto-refresh when the devkit pin bumps.
**Provenance / anti-drift:** `skills/` is a *distribution snapshot*; the canonical homes are split across
skill repos (`a0-plugin-e2e-bdd` → `agent-zero-operator-skills`; most others → `agent-zero-plugins-skills`;
`a0-plugin-testkit` vendored). A maintainer **manually copies** the changed skill from the right repo into
`skills/` before a release (no automated sync target — the split sources would make a one-source helper
misleading). Shipped in devkit **v1.1.0**; the misleading `sync-skills` target was dropped in **v1.1.1**.

**DEC-069 — BDD behaviour tests are mandatory (hard-require), rolled out via a major-version channel.**
Corrects DEC-066's original "self-skip non-BDD plugins" — that was a silent loophole (no tests ⇒ no gate
⇒ green), exactly the laziness the gates exist to close. Now: **`bdd_lint` hard-fails a plugin with no
`tests/e2e/features/`** — every plugin on the devkit MUST ship behaviour tests; there is no
lifecycle-only escape (the classic install/uninstall check is not behaviour verification). Because this
would fail every currently-green non-BDD consumer, it is a **breaking change → v2.0.0**, and rollout is
**opt-in per repo via a major-version channel**: `devkit-sync` and `make update-devkit` bump only within
the consumer's major (`.devkit.yml devkit_major`, default **1**), so the nightly sync never force-jumps a
repo to v2. A plugin adopts the mandate deliberately when it's ready — `make update-devkit DEVKIT_REF=v2.0.0`
(and sets `devkit_major: 2`). Non-breaking releases (MINOR/PATCH) still auto-flow within the channel.

**DEC-073 — e2e traces are captured on every run, not just failures.**
`trace: "retain-on-failure"` meant a **passing** run produced no trace at all, so there was no ground
truth to diff a later regression against and a scenario could only be diagnosed *after* it had already
broken. Traces are now **always on**; the storage cost is bounded by the uploader's retention (and by
DEC-074's count policy), not by discarding green runs. Overridable per-run via `BDD_TRACE`.
Corollary — the **collectors must ship what Playwright writes**: `screenshot: "on"` and `video: "on"`
were already capturing `.png`/`.webm` next to each `trace.zip`, but both harnesses (`run-bdd.sh` and
`run-lifecycle.sh`) copied *only* `trace.zip`, so those files were silently dropped and the downstream
"video → GIF" step had never produced anything. Both now collect traces + screenshots + videos,
scenario-prefixed for attributability.

**DEC-074 — Artifact retention is count-based ("keep the last N runs"), enforced, not configured.**
GitHub has **no native keep-last-N setting** — `retention-days` is the only built-in control and it is
purely time-based, so under a variable CI cadence it cannot express "the last N executions". The policy
is therefore enforced explicitly: after upload, a prune step lists the live artifacts of that name
newest-first and deletes everything past `artifact-keep` (**default 5**). `retention-days` is raised to
**90** as a pure backstop so the *prune*, not expiry, decides what disappears — a short retention would
otherwise race the policy and delete one of the N first.
Constraints that shape the implementation: (a) it needs `actions: write`, and a reusable workflow's job
permissions are **capped by the caller's grant**, so the caller template must grant it too or the prune
silently degrades to a warning; (b) fork PRs get a read-only token, so the prune is skipped there
(their artifacts belong to the fork anyway); (c) the step is `continue-on-error` — retention
housekeeping must never turn a green e2e red. Applied to both the reusable `plugin-e2e.yml` and the
devkit's own `sample-plugin-e2e.yml` self-test.
**Propagation debt:** consumers hold a *copy* of the caller template and `devkit-sync` deliberately
never writes `.github/workflows/` (its `GITHUB_TOKEN` cannot), so existing consumers keep the old
caller until `make link-workflows` is re-run. Until then their prune warns rather than prunes —
visible and non-fatal by design.

**DEC-075 — CI must be runnable with no secrets at all.**
Every secret the e2e needs is now **optional**, and each step that consumes one is guarded on its
presence. The App-token dance existed because the devkit was a *private* repo whose submodule could
only be cloned with a token; the devkit is public now (verified by an anonymous clone), so the token
buys nothing on the default path. Leaving the secrets `required: true` had a cost that was invisible
until it was looked for: **Dependabot runs never receive repo secrets**, so all five open dependency
PRs across the fleet failed with `Input required and not supplied: app-id` — a failure that had
nothing to do with the dependency being bumped, and which made every bump unverifiable. The same
property is what lets an outside contributor's fork PR run the suite at all, which is a precondition
for open-sourcing. A consumer that keeps its devkit private is unaffected: when the App credentials
are present they are still used.

**DEC-076 — Shared logic lives in one file, not in two workflows.**
The artifact collector was duplicated across `run-bdd.sh` and `run-lifecycle.sh`, and the retention
prune across `plugin-e2e.yml` and `sample-plugin-e2e.yml`. This is not a style preference: the
collector copies had silently **drifted** (only one sanitised non-alphanumerics in scenario names,
so artifacts from the other carried raw `→` in their filenames), and when the "green runs upload an
empty artifact" defect was fixed in one copy the other kept it — the fix was reported as complete
while half the fleet was still broken. Collector → `e2e/harness/_artifacts.sh`, sourced by both
harnesses; prune → `e2e/ci/prune-artifacts.sh`, invoked by both workflows. A reusable workflow can
call the script from the consumer's vendored devkit path, so there is still exactly one definition.

> **Numbering note:** DEC-070–072 were introduced as code comments only and were never written up
> here. This section documents 073–076; backfilling 070–072 is tracked separately.

---

## Appendix B — Open questions

These are the decision clusters to work through, one at a time. Each closes into one or
more DECs.

### Cluster 1 — Devkit packaging, granularity, seam & lifecycle — **CLOSED**
- ~~Q-001~~ → DEC-001. ~~Q-002~~ → DEC-004. ~~Q-003~~ → DEC-005/006.

### Cluster 2 — Target vocabulary & seam mechanisms — **CLOSED**
- ~~Q-004~~ → DEC-008 (Appendix E.1). ~~Q-012~~ → DEC-009 ("doctor" folded into
  `verify-installed`). ~~Q-013/Q-014~~ → DEC-012. ~~Q-015~~ → DEC-011 (hybrid:
  declarative common + per-plugin hook).

#### Cluster 2 follow-ups — **CLOSED by code inspection**
- ~~Q-016~~ → DEC-013 (reuse `requirements.txt` + `meta.yaml`; no new schema).
  ~~Q-017~~ → DEC-014 (runs every cycle + final; pre-install snapshot baseline).
  ~~Q-018~~ → DEC-013 (structure derived from the zip).

### Cluster 3 — Reusable CI workflows + devcontainer — **CLOSED (decisions)**
- ~~Q-006~~ → DEC-020 (e2e body in devkit). ~~Q-008~~ → DEC-019 (A0 image is a param).
  ~~Q-019~~ → DEC-015 (reuse ported skills mechanism, devkit-scoped). The architecture
  pivoted to a **devcontainer** (DEC-018) — follow-ups below.

#### Cluster 3 follow-ups
- ~~Q-020~~ → DEC-021 (triggers). ~~Q-022~~ → DEC-017 (claude-code-action + `/code-review`).
- **Q-021.** Devcontainer design: base image, rootless-podman-nesting approach (confirm it
  works on GH-hosted `ubuntu-latest` without privilege), publish location
  (`ghcr.io/agent-zero-plugins/plugin-devkit`?) + versioning/tagging. _Mostly
  implementation; the SPEC pins the contract (no privilege). Revisit at impl time._
- **Q-023.** Exact minimal Claude vendored surface (CLAUDE.md for plugin dev? `.claude/`
  rules? which?). _Minor; fold into rollout._

### Cluster 4 — Cleanup / residue mechanism — **CLOSED**
- ~~Q-009~~ → DEC-022 (snapshot+diff, all four layers).

### Cluster 5 — Rollout & sync — **CLOSED**
- ~~Q-010~~ → DEC-023 (per-repo gate only). ~~Q-011~~ → DEC-025 (devkit repo).
  ~~Q-024~~ → DEC-024 (phased fan-out de-vendors per repo).

### Cluster 6 — Authoring & polish (Cycle 2) — **OPEN**
- ~~**Q-025**~~ → **CLOSED** (2026-06-20) by the theme-4 analysis + operator's fork-topology
  explanation → DEC-049 + DEC-054. Two-tier fork model (internal `NuevaNext/agent-zero` vs
  public `agent-zero-operator/agent-zero`); 18 `upstream` / 1 `fork-required` (context-scoping);
  `docs/a0-compatibility.md`.
- **Q-030.** ghcr pull auth for the private fork image (DEC-055): the e2e must `podman login
  ghcr.io` to pull `ghcr.io/nuevanext/agent-zero:latest-nonroot`. Mechanism options: (a) extend
  the existing sync App with `packages:read` + install on `NuevaNext` → the already-minted App
  token pulls it (no new secret — fits batteries-included); (b) a new `GHCR_PULL_TOKEN` PAT
  secret (read:packages) per repo/org; (c) grant the package read-access to the
  `agent-zero-plugins` org so each repo's `GITHUB_TOKEN` pulls it. Blocks flipping the default
  image live (a private pull without auth fails every repo's e2e).
- **Q-029.** Timing of the **repoint to the public fork**: when the internal change-groups have
  open upstreaming PRs on `agent-zero-operator/agent-zero` (and it carries the seams + a
  fork-declaration README), `fork-required` plugins flip `a0_image` to the public image and add
  the fork+PR README links (DEC-054). Gated on the public-fork maintenance pass, which is not yet
  scheduled. → resolves into the repoint PRs.
- **Q-026.** GIF/video tooling in the devcontainer (ffmpeg? Playwright video→GIF?), the
  size/length budget, and where format is pinned. → refines DEC-051 / Appendix E.10.
- **Q-027.** "Nice" thumbnail sourcing: the harness screenshot ≠ a designed card thumbnail.
  Who/what produces the branded `webui/thumbnail.*` (design tool, author, generator)? →
  refines DEC-048/DEC-051, REQ-DOC-005.
- **Q-028.** Doctor config-validation depth: is `default_config.yaml` the schema source, and
  how does doctor resolve `plugin_dir` for forks/build-generated plugins? → refines DEC-052.
- **Q-026.** GIF/video tooling in the devcontainer (ffmpeg? Playwright video→GIF?), the
  size/length budget, and where format is pinned. → refines DEC-051 / Appendix E.10.
- **Q-027.** "Nice" thumbnail sourcing: the harness screenshot ≠ a designed card thumbnail.
  Who/what produces the branded `webui/thumbnail.*` (design tool, author, generator)? →
  refines DEC-048/DEC-051, REQ-DOC-005.
- **Q-028.** Doctor config-validation depth: is `default_config.yaml` the schema source, and
  how does doctor resolve `plugin_dir` for forks/build-generated plugins? → refines DEC-052.

### Remaining (implementation-time, non-blocking)
- **Q-021.** Devcontainer base + rootless-podman-nesting specifics + image publish/version.
- **Q-023.** Exact minimal Claude vendored surface.
_Both are implementation details; the SPEC pins their contracts. No open design decisions
block a first implementation._

---

## Appendix E — Resource / field reference

### E.1 — Frozen common Make targets (per DEC-008)

| Target | Kind | Owner | Contract |
|---|---|---|---|
| `build` | artifact | devkit | Assemble the plugin directory (no-op for simple source-only plugins). |
| `package` | artifact | devkit | Produce the versioned plugin zip from `plugin.yaml` version. |
| `up` / `down` | lifecycle | devkit | Boot / teardown the **nested rootless A0 container** (Cycle-1 replaced the compose harness with nested podman per DEC-018/039–041; _Minor-2 of SPEC-REVIEW-002_). |
| `doctor` | health | devkit + **plugin script** | Run the plugin's `scripts/doctor.py` against the running instance (DEC-052); part of `e2e` post-install. |
| `media` | media | devkit | Produce `docs/media/` assets from the captured artifacts (DEC-051); run locally or in the publish step. |
| `install` | lifecycle | devkit | Install the packaged zip into the running instance for the active case. |
| `enable` / `disable` | lifecycle | devkit | Toggle the installed plugin via the A0 plugin API. |
| `uninstall` (`delete`, `remove`) | lifecycle | devkit | Uninstall the plugin (one op, three names). |
| `e2e` / `ci` | orchestrator | devkit | Run the full serial config-matrix: `up` → ∀ case `{install → verify-installed → uninstall → verify-uninstalled}` → `down`. |
| `verify-installed` | assertion | devkit + **plugin hook** | (a) common effectiveness checks (E.3 deps + unzip structure), then (b) per-plugin hook, in series. |
| `verify-uninstalled` | assertion | devkit + **plugin hook (opt)** | (a) common residue scan, then (b) optional per-plugin residue hook, in series. |
| `link-*`, `update-skills` | vendoring | devkit/skills | Unchanged from current org Makefile. |

_Hook targets are the only ones a plugin repo overrides._

### E.2 — `tests/e2e/cases.yaml` (per DEC-012)

```yaml
# Absent file ⇒ a single implicit case: { name: default, config: {} }
- name: default
  config: {}
- name: custom-backend
  config: { backend: "remote", polling_interval_seconds: 5 }
- name: debug-on
  config: { debug: true }
- name: boot-only-env          # needs a restart (env/MCP settings, Appendix F.4)
  config: { ... }
  requires_reboot: true        # per DEC-028 / REQ-LC-006
```
_`config` is applied post-install via the A0 plugin config API (read live — Appendix F.3),
except `requires_reboot` cases which restart the A0 container first._

### E.3 — `verify-installed` common-check sources (per DEC-013)

No new manifest. The common stage reads existing declarations:

| Check | Source of truth | Assertion in container |
|---|---|---|
| Pip deps installed | `requirements.txt` (canonical; installed by A0 `hooks.py` on enable) | each package importable in the A0 runtime venv |
| Config/secret env present | `meta.yaml` `env[]` (`kind: config\|secret`) | each declared env var set in the container env |
| Files landed | the packaged zip's file list (derived automatically) | each path exists under `/a0/usr/plugins/<name>/` |
| Routes/extensions registered | (optional, per-plugin hook in stage (b)) | plugin-specific |

Dep check semantics (per DEC-027): `requirements.txt` lines are parsed to **distribution
names** (specifiers/extras/markers stripped; `-r`/URL/VCS lines resolved or flagged);
presence is asserted via `importlib.metadata` **after** the verify-installed hook has
exercised the plugin (A0 installs deps lazily — Appendix F.2), never by `import <pkgname>`.

`meta.yaml env[]` presence (per DEC-030): `kind: config` ⇒ set-and-non-empty; `kind:
secret` ⇒ declaration-wired only (placeholder allowed; real value absent in CI).

### E.4 — Hook ABI (per DEC-026)

| Aspect | Contract |
|---|---|
| Location | `tests/e2e/hooks/verify-installed`, `tests/e2e/hooks/verify-uninstalled` (executable; any language). Absent ⇒ no-op pass. |
| Result | Exit code `0` = pass; non-zero = fail (that stage, with the script's stderr captured). |
| Context (env) | `A0_BASE_URL`, `A0_USERNAME`, `A0_PASSWORD`, `A0_CONTAINER` (name/id for exec), `PLUGIN_NAME`, `CASE_NAME`, `CASE_CONFIG_JSON`, `A0_REPORT_DIR` (write artifacts here). |
| Invocation | Called by the common target after its devkit-owned stage (a); cwd = repo root. |

### E.5 — Canonical allowed-asset list (per DEC-034)

A conforming plugin repo tracks **only**:
- Plugin source: `plugin.yaml`, `meta.yaml`, `default_config.yaml`, `requirements.txt`,
  `__init__.py`, `webui/` (incl. `thumbnail.*`), `api/`, `extensions/`, `hooks.py`,
  `scripts/` (incl. `scripts/doctor.py`) (as applicable).
- `tests/e2e/cases.yaml` and `tests/e2e/hooks/*`.
- The thin caller workflows (`.github/workflows/plugin-e2e.yml`, `devkit-sync.yml`).
- The AI-review workflow (`.github/workflows/claude-code-review.yml`) + vendored rubric.
- The minimal Claude surface (Q-023): `CLAUDE.md` (common block + repo section).
- **Cycle-2 assets (per SPEC-REVIEW-002 Major-5):** `README.md`, `DEVELOPING.md`, `LICENSE`,
  `.devkit.yml`, `docs/media/*`.
- The devkit submodule + generated symlinks.

`make conformance` (REQ-CONF-001) flags any tracked file outside this list. _The build-
generated/fork tracks (DEC-043) carry their own upstream files; conformance reads the list
relative to the declared `plugin_dir`._

### E.6 — Phase-0 feasibility-spike acceptance (per DEC-031)

The spike PASSES iff, on the target runner with **no `--privileged` and no host
docker.sock mount**: the devcontainer starts; rootless podman inside it pulls and runs the
A0 image; the harness reaches A0 at `A0_BASE_URL` and logs in; one full
`install → verify-installed → uninstall → verify-uninstalled` cycle completes green. A
documented self-hosted-runner fallback is produced if GH-hosted `ubuntu-latest` fails.

---

### E.7 — Curated authoring skill set vendored in the devkit (per DEC-046)

Sourced from `agent-zero-plugins-skills`, kept fresh by sync. The set is "what helps build
A0 plugins" — architecture, scaffolding, the manifest contract, testkit, troubleshooting —
not the full org/meta library:

| Skill | Why it's in the set |
|---|---|
| `a0-plugin-architecture` | Canonical plugin architecture (extension points, lifecycle). |
| `a0-bootstrap-plugin` | Stand up a new plugin repo to the standard. |
| `author-plugin-from-template` | Generate a plugin from `agent-zero-new-plugin-template`. |
| `plugin-manifest-contract` | `plugin.yaml`/`meta.yaml` field contract. |
| `a0-plugin-testkit` | Shared pytest scaffolding (already in the devkit `skill/`). |
| `troubleshoot-plugin-deployment` | Diagnose install/deploy failures. |
| `rotate-plugin-credentials` | Secret rotation for plugins that need it. |

_Candidates deferred to Q-023/Q-025 review: the `manage-*` meta-skills (distribution-time,
not authoring-time) and `contribute-plugin-to-gate` / `curate-vendor-plugins-gate` (gate
workflow, not plugin authoring)._

_Naming (Minor-5 of SPEC-REVIEW-002): the vendored set lives under `skills/<name>/SKILL.md`;
the devkit's existing singular `skill/` (the `a0-plugin-testkit` skill) folds into that
`skills/` tree so there is one location._

### E.8 — README skeleton (per DEC-048)

Fixed headings, in order; prose is plugin-specific. `make conformance` checks presence.

```
# <Title>                         ← + card thumbnail image
<one-line description>            ← matches plugin.yaml description
## Why                           ← the problem it solves / rationale
## See it                        ← harness-captured screenshot + behaviour GIF (docs/media/)
## Install                       ← how to install in A0 (+ gate/OCI ref if applicable)
## Configuration                 ← config keys (mirror default_config.yaml), or "none"
## Dependencies                  ← inter-plugin deps (other A0 plugins) + external deps
## Agent Zero compatibility      ← `upstream` | `fork-required` (+ fork repo link & the change)
## Health (doctor)               ← how to run scripts/doctor.py inside A0
## License                       ← Apache-2.0 (first-party) / upstream (forks)
```

### E.9 — Doctor contract (per DEC-052)

- **Path:** `usr/plugins/<name>/scripts/doctor.py` (or `plugin_dir`/`scripts/doctor.py`).
- **Run:** `python /a0/usr/plugins/<name>/scripts/doctor.py` inside a booted A0.
- **Exit:** `0` healthy (incl. soft warnings), non-zero on any hard failure.
- **Checks (minimum):** (a) each declared dependency importable; (b) every key in the
  plugin's `default_config.yaml` resolves in the live config with a type-compatible value
  (key/type check, not a formal schema); (c) the plugin's declared extension files exist
  under the live A0 plugin dir and import without error. Output is a per-check
  `PASS`/`WARN`/`FAIL` summary.
- **CI:** the e2e runs doctor post-install and fails the gate on non-zero (REQ-DR-003).

### E.10 — Behaviour media (per DEC-051)

- **Committed path:** `docs/media/` — `installed.png` (card/config screenshot),
  `behaviour.gif` (or `.webm`) of the documented flow.
- **Producer:** the devkit lifecycle, driving the behaviour verify (DEC-053); emitted as CI
  artifacts and committed/refreshed at the known path.
- **README embed:** the §E.8 "See it" section references these paths.
- _Tooling/format/size budget: Q-026._

### E.11 — Behaviour seam contract (per DEC-056)

- **File:** `tests/e2e/behaviour.mjs` (consumer repo root). Absent ⇒ lifecycle logs the
  missing-behaviour gap and continues.
- **Shape:** `export default async function ({ page, expect, pluginName, displayName, baseURL }) {…}`.
  Throw to fail the gate. Do **not** `import "@playwright/test"` inside the file — `page`/`expect`
  are injected (the consumer path can't resolve it from the bind mount).
- **Context:** `page` is the live, authenticated A0 Playwright page (the plugin is installed);
  `baseURL` e.g. `http://localhost:80`. The seam runs right after install; the lifecycle re-opens
  the Plugins modal afterwards, so the function MAY navigate/interact freely.
- **Must:** assert ≥1 plugin-specific observable effect over the wire (e.g.
  `await page.goto(baseURL + "/"); await expect(page.locator("#injected")).toBeVisible()`).
- **Media:** the lifecycle screenshots the post-seam page to `A0_REPORT_DIR/behaviour.png`
  (DEC-051 source).

---

## Appendix F — Assumed A0 runtime behaviour (grounds NG1; per XCut-1)

These are **verified** against the A0 source (`agent-zero-operator/agent-zero`); if A0
changes them, the cited REQs must be revisited.

- **F.1 — Uninstall does NOT remove pip deps.** `delete_plugin()` (helpers/plugins.py)
  deletes the plugin dir + clears caches + purges `sys.modules`; there is no `pip
  uninstall`. ⇒ DEC-029 excludes declared deps from residue.
- **F.2 — Deps install lazily at first use, not on install.** No centralized installer;
  plugins self-install on first use. ⇒ DEC-027 checks dist-presence after the hook runs.
- **F.3 — `config.json` is read live, per-operation.** `get_plugin_config()` reads disk
  each call; config saves don't invalidate caches. ⇒ DEC-028 single-boot matrix valid.
- **F.4 — Boot-only classes:** env-var-derived settings (read once at boot) and MCP
  settings. ⇒ DEC-028 `requires_reboot` escape hatch.
- **F.5 — Toggle is filesystem state with deferred unload.** `toggle_plugin()` writes
  `.toggle-{0,1}` + `after_plugin_change()`; loaded Python unloads only if python files
  changed. ⇒ DEC-036 treats enable/disable as primitives, not assumed-live transitions.
- **F.6 — A0 self-destructs on any supervised-process FATAL.**
  `docker/run/fs/etc/supervisor/conf.d/supervisord.conf` registers `the_listener`
  (`supervisor_event_listener.py`) on `PROCESS_STATE_FATAL` with **no args**; the listener
  `kill -15 1` (then `kill -9 -1`) the whole instance on any FATAL. `run_sshd` exits 255
  under rootless podman → FATAL → instance dies. ⇒ DEC-040 neutralizes sshd in the rootless
  harness. (Note: a `DEBUG` env var makes the listener a no-op — useful but broader.)
