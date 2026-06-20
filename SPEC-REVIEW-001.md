# SPEC-REVIEW-001 — Audit of `SPEC-plugin-quality-standard.md`

**Reviewer role:** IEEE 29148 specification reviewer (skeptical pass).
**Target:** `SPEC-plugin-quality-standard.md` — iteration 4, "all decision clusters closed."
**Date:** 2026-06-19.
**Method:** Audited against IEEE 29148 quality characteristics (Unambiguous, Complete, Consistent, Verifiable, Feasible, Necessary, Traceable, Modifiable, Bounded) plus the six high-risk areas called out by the author. Each finding has a stable ID; quotes are verbatim from the spec.

---

## Verdict

**Needs material revision.**

The decision log is unusually mature and the cluster discovery is thorough, but the spec is **not yet ready for implementation** because of a small number of true blockers, all concentrated in the seam contract and the lifecycle/config model. Specifically: (1) the **hook target ABI is entirely unspecified** — an implementer cannot write a single hook target because no exit-code semantics, file location, or passed context (base URL, credentials, plugin name, active case) is defined (Critical-1); (2) **post-install API config (DEC-012/REQ-LC-003) collides with A0's boot-time-only settings** and the spec does not acknowledge the class of config that cannot be tested in one boot (Critical-2); (3) the **`requirements.txt` import check is unimplementable as written** because pip-name ≠ import-name (Critical-3); and (4) the **devcontainer rootless-nested-podman contract is asserted but its feasibility on GH-hosted runners is deferred to Q-021 while REQ-DEV-003/REQ-CI-006 already mandate it as MUST** — a normative requirement resting on an unvalidated assumption (Critical-4). A material revision closing these, plus the Major-tier ambiguities, would move this to "Ready."

### Findings by severity

| Severity | Count |
|---|---|
| Critical | 5 |
| Major | 9 |
| Minor | 7 |
| Gap | 6 |
| XCut | 4 |
| **Total** | **31** |

---

## Critical findings (block implementation)

### Critical-1 — The hook-target ABI is completely unspecified

**Symptom.** The seam is the entire point of the spec ("Adding a new per-plugin behaviour … is the *only* work an author does", G3), yet no contract for a hook target exists. REQ-MK-002: *"a plugin repo **MUST** override only the designated hook targets."* REQ-MK-003 / REQ-VER-003: *"Hook targets **MUST** be language-agnostic: a plugin **MAY** implement them with Playwright, container exec/SSH, API calls, scripts, or any combination."* DEC-005 says the devkit "owns the skeleton." But nowhere is the hook ABI defined:
- **What signals pass/fail?** (Exit code 0/non-zero? A Make target's exit status? A produced report file?)
- **Where does the hook live?** (A Make target named what, in which file? A script at a fixed path like `tests/e2e/verify_installed_hook.sh`? Appendix E.1 lists `verify-installed` as `devkit + plugin hook` but never says how the plugin supplies the hook half.)
- **What context does the devkit pass in?** The high-risk brief names the exact gap: base URL of the booted A0, credentials/login token, plugin name, **active case name + its config**. None is specified. A Playwright hook needs the base URL and auth; a container-exec hook needs the container name/exec handle; all of them need to know *which case is active*.

**Why critical.** Two implementers will produce incompatible hook conventions; no plugin author can write a hook against this spec. This is the single most load-bearing contract in the document and it is empty.

**Proposed fix.** Add a new requirement cluster **REQ-SEAM-00x** + an Appendix (E.4 "Hook ABI") pinning:
- The hook surface: each hook is a Make target with a fixed name (e.g. `verify-installed-hook`, `verify-uninstalled-hook`) that the devkit fragment invokes; the plugin defines it in its own `Makefile` (overriding an empty default in the fragment). State that an undefined optional hook is a no-op pass.
- Pass/fail = target exit code (0 = pass, non-zero = fail); stdout/stderr captured into the stage report.
- The context contract: the devkit exports a fixed set of environment variables before invoking any hook — at minimum `A0_BASE_URL`, `A0_AUTH_TOKEN` (or login mechanism), `A0_CONTAINER` (name/id for exec), `PLUGIN_NAME`, `CASE_NAME`, `CASE_CONFIG` (path to the resolved per-case config). Enumerate them in a table.
- A DEC (e.g. DEC-026) recording this ABI choice and closing the implicit gap left by DEC-005.

---

### Critical-2 — Post-install API config (REQ-LC-003) collides with A0 boot-time-only settings; the "can't-test-in-one-boot" class is unacknowledged

**Symptom.** REQ-LC-003: *"Per-case configuration **MUST** be applied after install via the A0 plugin config API (not via boot-time seeding), since all cases share one boot."* DEC-012 makes this absolute: every case's config is applied post-install via the API. But the high-risk brief is correct that **A0 reads some settings only at boot** (e.g. settings consumed by `hooks.py` at enable/import time, or runtime config read once at process/extension registration). For such settings, applying config via the API *after* install will not change observable behaviour within the same boot — so a case that flips a boot-only setting cannot be verified, yet REQ-LC-001 demands every case run a full `install → verify-installed → uninstall → verify-uninstalled` cycle and REQ-LC-003 forbids boot-time seeding.

**Why critical.** This is a latent contradiction between the single-boot constraint (DEC-006: "within one boot") and the universe of plugin config. An implementer following the spec literally will ship a harness that silently mis-verifies boot-only-config cases (the verify passes against stale behaviour), which is worse than failing. The spec does not even acknowledge the class exists.

**Proposed fix.** Either (a) add a per-case escape hatch — `cases.yaml` entry MAY declare `requires_reboot: true`, and the devkit MUST restart the A0 container (or re-enable the plugin) for that case, accepting the cost; or (b) explicitly scope the standard to runtime-applicable config and add a non-goal/limitation stating boot-only-config cases are **out of scope for single-boot verification** and MUST be tested by a dedicated reboot case. Record as a new DEC refining DEC-012, and add a verification row demonstrating a reboot-requiring case. Also reconcile the wording of DEC-006 ("within one boot") with whichever path is chosen.

---

### Critical-3 — "Each requirements.txt package is importable" is unimplementable as written (pip name ≠ import name)

**Symptom.** DEC-013 / Appendix E.3: *"every package in the plugin's `requirements.txt` is importable in the running container"* with assertion *"each package importable in the A0 runtime venv."* This is not mechanically computable: the distribution name in `requirements.txt` is frequently not the importable module name (`PyYAML`→`yaml`, `Pillow`→`PIL`, `beautifulsoup4`→`bs4`, `python-dateutil`→`dateutil`, `scikit-learn`→`sklearn`). A naive `import <pkgname>` check will produce false failures for a large fraction of real plugins. Also unaddressed: version specifiers/extras/markers in requirements lines (`foo>=1.2,<2`, `foo[extra]`, `foo; sys_platform=='linux'`), VCS/URL requirements, and `-r nested.txt` includes.

**Why critical.** REQ-VER-002 makes this a build-gating common check that "**MUST NOT** be reimplemented per plugin." As specified it will fail conforming plugins, so no implementer can build the check correctly from the text.

**Proposed fix.** Change the assertion from "importable" to a presence check against installed distributions: parse each requirement to its **distribution name** (strip specifiers/extras/markers) and assert it appears in `pip freeze` / `importlib.metadata.distribution(name)` — i.e. assert *installed*, not *importable*. If functional import is wanted, make it the plugin's `verify-installed` hook job (stage b), not the common stage. Define handling for VCS/URL/`-r` lines (resolve includes; for URL/VCS, assert the resolved project name is present). Record as a DEC refining DEC-013 and update E.3's assertion column.

---

### Critical-4 — Rootless-nested-podman feasibility is mandated as MUST while its validation is deferred to an open question

**Symptom.** REQ-DEV-003 (MUST): *"publish a **devcontainer image** … (Playwright, SSH, node, rootless podman + nesting tooling) that runs the A0 container **nested and unprivileged**."* REQ-CI-006 (MUST): *"CI **MUST** run the lifecycle **inside the devkit devcontainer** … no `--privileged`, no host Docker socket mount."* But the load-bearing feasibility question is still **open**: Q-021 *"rootless-podman-nesting approach (confirm it works on GH-hosted `ubuntu-latest` without privilege)"* and the spec files it under "Remaining (implementation-time, non-blocking)." A normative MUST cannot rest on an unconfirmed feasibility assumption; if rootless nesting *needs* `--privileged` or specific runner kernel/`/dev/fuse`/`newuidmap` setup on GH-hosted runners, REQ-CI-006 is unsatisfiable and the whole CI model (and DEC-018's reversal of DEC-001) collapses.

**Why critical.** Feasibility (IEEE 29148) is in doubt for the spec's central architectural pivot. Rootless podman-in-X commonly requires `--device /dev/fuse`, configured `subuid`/`subgid` ranges, and `fuse-overlayfs`; whether all of that is available on `ubuntu-latest` GitHub-hosted runners *without* a privileged container is exactly the unanswered question — and the answer determines whether the spec is buildable at all.

**Proposed fix.** Demote REQ-DEV-003/REQ-CI-006 to depend on a **feasibility spike that MUST complete before Phase 1 of rollout** (tie to REQ-ROL-001), or add a documented fallback contract (e.g. "if rootless nesting is infeasible on GH-hosted runners, the devcontainer MAY run on a self-hosted runner with `/dev/fuse`, still without `--privileged`/docker.sock"). Convert Q-021's feasibility half from "non-blocking" to a **gating pre-condition** with an explicit acceptance test, and reference it from REQ-DEV-003. The contract clauses (no `--privileged`, no docker.sock) can stay MUST; the *mechanism* must be proven before the MUST is binding.

---

### Critical-5 — `env[]` `kind: secret` presence check is undefined in CI where the secret is intentionally absent

**Symptom.** DEC-013 / E.3: *"Each operator-config/secret env var declared in `meta.yaml` `env[]` (`kind: config|secret`) is present in the container environment"* — assertion *"each declared env var set in the container env."* The high-risk brief flags it: for `kind: secret`, the value is frequently **intentionally absent in CI** (no real credential is provisioned for an e2e run). The common check would then fail every secret-bearing plugin, or — if it doesn't — the spec needs to say a secret may be present-but-empty, or supplied by a CI dummy, and "present" must be defined (key exists vs. key non-empty).

**Why critical.** REQ-VER-002 gates the build on this common check. As written it either blocks all secret-using plugins or has undefined semantics, and the spec does not say how CI provisions (or stubs) secrets for the booted A0.

**Proposed fix.** Split the rule by `kind`: for `kind: config`, assert the env var is **set and non-empty**; for `kind: secret`, assert only that the **declaration is wired** (the container has the env key present, value MAY be a CI-provided placeholder) — or exclude `secret` from the common presence check entirely and push real-credential validation into the per-plugin hook of cases that need it. Add to `cases.yaml`/the harness a defined way to inject CI secret stubs. Record as a DEC refining DEC-013; clarify "present" = key-exists vs non-empty in E.3.

---

## Major findings (will cause contested code review)

### Major-1 — `enable`/`disable` are first-class lifecycle targets but never appear in the per-case loop

**Symptom.** DEC-010: *"`enable` / `disable` are first-class lifecycle targets … the devkit exposes them generically. The default lifecycle installs enabled; plugins that need to exercise enable/disable transitions do so from their `verify-installed` hook."* REQ-LC-004 lists them as MUST-be-generic targets. But the canonical loop in REQ-LC-001 and Appendix E.1 `e2e` is `install → verify-installed → uninstall → verify-uninstalled` — `enable`/`disable` appear nowhere in it. So the only place they're exercised is "from the verify-installed hook," i.e. at the plugin's discretion, via targets whose ABI is also unspecified (see Critical-1).

**Why major.** The spec elevates enable/disable to first-class then orphans them from the orchestration. Reviewers will dispute whether a plugin is *required* to test the toggle, when "install enabled" happens relative to `install`, and whether `disable` residue is in scope for `verify-uninstalled`. It's a half-specified surface.

**Proposed fix.** Decide and state: is enable/disable part of the standard loop (e.g. an optional `enable → verify → disable → verify` sub-cycle the harness can run per case) or purely a hook-callable primitive? If the latter, say so explicitly in REQ-LC-001 ("the loop does not invoke enable/disable; plugins MAY call them from hooks") and note that disable-state residue is not separately gated. Add a verification row either way (currently REQ-LC-004's row only checks the targets exist/are identical, not that they work).

### Major-2 — "effectiveness-check" naming and identity is left provisional inside a "closed" spec

**Symptom.** DEC-006: *"**effectiveness-check** … _Provisional name; the user referred to it as `docker` — final name pending Q-012._"* But Q-012 is marked closed by DEC-009 ("doctor folded into verify-installed"), and REQ-CI-003 names the stage *"the effectiveness check"* while Appendix E.1's `e2e` contract and REQ-LC-001 use *"verify-installed"*. So the document carries three names (`effectiveness-check`, `docker`, the common stage of `verify-installed`) for one thing, with a dangling "pending Q-012" on a closed question.

**Why major.** A reader cannot tell whether "effectiveness check" is a separate stage (REQ-CI-003 lists it alongside verify) or stage (a) of verify-installed (DEC-009/E.1). This is a genuine consistency ambiguity in the stage model, not just wording.

**Proposed fix.** Pick one canonical term ("verify-installed common stage / install-effectiveness checks"), purge `effectiveness-check` and `docker` as stage names, fix REQ-CI-003 to enumerate the actual stages (`install`, `verify-installed`, `uninstall`, `verify-uninstalled`) rather than introducing "the effectiveness check" as a peer, and strike "pending Q-012."

### Major-3 — REQ-CI-003 stage list contradicts the canonical loop

**Symptom.** REQ-CI-003: *"The e2e workflow **MUST** report `install`, the effectiveness check, `verify`, `remove`, and `purge` as **individually-legible stages**."* This uses the *old* DEC-006 vocabulary (`verify`, `remove`, `purge`), all of which DEC-009 superseded (`purge`/standalone `verify` removed; `remove` is an alias of `uninstall`; two assertion targets replace them). Its own verification row (line 166) then lists the *new* names: *"install / verify-installed / uninstall / verify-uninstalled."*

**Why major.** The requirement and its acceptance criterion describe different stage sets. Implementers will not know which five (or four) stages the workflow must surface.

**Proposed fix.** Rewrite REQ-CI-003 to the post-DEC-009 stage set: `install`, `verify-installed`, `uninstall`, `verify-uninstalled` (per case), reported individually within one boot. Align with E.1's `e2e` contract.

### Major-4 — "All four layers" residue scan: settings.json keys and plugins_list semantics are underspecified

**Symptom.** REQ-VER-004 / DEC-022: snapshot+diff of *"plugin-dir filesystem, `pip freeze`, settings.json keys, `plugins_list` API … asserts exact return-to-baseline on all four; any delta is residue."* Two problems: (1) **`pip freeze` baseline is wrong for the matrix loop** — A0's `hooks.py` installs `requirements.txt` on enable; a *pre-install* `pip freeze` baseline will differ from post-uninstall *if A0 does not uninstall the deps on plugin removal* (a very common reality), so every plugin with deps would be flagged as residue-defective even when behaving exactly as A0 intends. (2) **"settings.json keys" and "exact return-to-baseline"** is brittle: unrelated A0 background activity (telemetry, last-login, cache counters) can mutate settings.json or installed-package set during the boot, producing false residue deltas independent of the plugin.

**Why major.** REQ-VER-005 turns any delta into a build-failing "defect." A scan this literal will produce false defects, and reviewers will fight over what counts as plugin residue vs. ambient drift. The spec asserts "exact" without scoping the diff to plugin-attributable changes.

**Proposed fix.** Scope each layer's diff to plugin-attributable deltas: filesystem → only under `/a0/usr/plugins/<name>/` (and any declared external paths); settings → only keys namespaced to the plugin; `plugins_list` → only the plugin's own entry; pip → **explicitly decide** whether dep-uninstall is in A0's contract — if A0 intentionally retains deps, exclude `requirements.txt`-declared packages from the residue baseline (only flag *unexpected* new packages). Record as a DEC refining DEC-022. This interacts with NG1 (A0 runtime behaviour is fixed) — call that out (see XCut-1).

### Major-5 — Snapshot baseline timing is contradictory between per-case and matrix

**Symptom.** DEC-014: *"The residue baseline is a **pre-install snapshot**"* and `verify-uninstalled` *"runs after **every** `uninstall` in the matrix loop."* But there is one boot and N serial cases. Is the baseline captured **once** (before case-1 install) and reused for all N `verify-uninstalled` checks, or **re-captured before each case's install**? These differ materially: if A0 retains anything case-1 created, a single shared baseline flags it for case-2..N; a per-case baseline hides cross-case leakage that the standard arguably wants to catch.

**Why major.** Determines whether cross-case residue is detected. The spec says "pre-install snapshot" (singular) but "after every uninstall" (plural) without binding them.

**Proposed fix.** State explicitly: baseline captured once before the first case's install; every `verify-uninstalled` diffs against that single baseline (catches cumulative leakage). If per-case baselines are intended, say so and accept that cross-case residue is invisible. Add a verification row covering the 2-case cross-leak scenario.

### Major-6 — REQ-DEV-004 / REQ-DEV-002 allowed-asset lists disagree

**Symptom.** REQ-DEV-002: vendor *"**only the devkit** (git submodule)"* and keep tracked surface minimal. REQ-DEV-004 enumerates allowed tracked assets: *"plugin source, the per-plugin seam files, the thin caller workflow, the shared AI-code-review guide, the minimal Claude integration, and the devkit submodule."* DEC-003 gives yet a third list: *"plugin source, its seam files, thin caller workflows, and the vendoring submodule + generated symlinks."* DEC-017 adds the `claude-code-review.yml` workflow + rubric; DEC-016 adds Claude integration + "other link targets MAY remain wired." `cases.yaml` (a tracked seam file) and `meta.yaml`/`requirements.txt` (read by the common checks, so tracked) appear in none of the three asset lists.

**Why major.** REQ-DEV-004's verification row says *"CI flags any out-of-contract tracked file."* If the canonical allowed-list is itself inconsistent and incomplete, that CI gate will flag legitimate files (`cases.yaml`, `meta.yaml`, `requirements.txt`, generated symlinks) as violations.

**Proposed fix.** Produce one canonical allowed-asset list (in REQ-DEV-004 or a dedicated appendix) and make DEC-003/DEC-017/REQ-DEV-002 reference it rather than re-enumerate. Ensure it includes: plugin source, `plugin.yaml`, `meta.yaml`, `requirements.txt`, `tests/e2e/cases.yaml` + hook scripts, thin caller workflow(s), `claude-code-review.yml` + review rubric, minimal Claude integration, devkit submodule + generated symlinks.

### Major-7 — "Unzip structure derived automatically from the zip" begs the question

**Symptom.** DEC-013 / E.3: *"the file set is derived **automatically from the packaged zip**; the devkit asserts those paths exist under `/a0/usr/plugins/<name>/`. No plugin-authored structure manifest."* But the zip is produced by the same `package` step (E.1) the devkit owns, and A0's installer may rewrite, filter, or relocate entries on unzip (ignoring dotfiles, stripping a top-level dir, not installing `tests/`). Asserting "every zip path exists under the install dir" assumes a 1:1 identity between zip layout and installed layout that A0's installer does not guarantee.

**Why major.** If A0's unzip transforms paths, this common check produces false failures; if it doesn't, the check is near-tautological (the devkit unzipped what it zipped). Either way the semantics depend on undocumented A0 installer behaviour — which NG1 says is fixed but unspecified here.

**Proposed fix.** Define the expected mapping: assert presence of the **plugin manifest + declared entrypoints** (from `plugin.yaml`) under the install dir, not raw zip-path identity; or document the exact zip→install transform A0 applies and assert against the transformed set. Exclude `tests/`, dotfiles, and dev-only files from the expected installed set. Record as a DEC.

### Major-8 — Compose harness (`up`/`down`) vs. nested-container model is unreconciled

**Symptom.** Appendix E.1: `up`/`down` = *"Boot / teardown the A0 compose harness."* Glossary "Harness" = *"the docker + Playwright machinery."* But DEC-018/REQ-CI-006 move execution *inside* a devcontainer running A0 as a **nested rootless** container. The high-risk brief names this exactly: A0's compose harness "today runs on the host" — how does `docker compose up` behave *inside* a rootless-podman devcontainer? Is it `podman compose`? Does the compose file change? Where does Playwright reach the nested A0 (network namespace, port mapping, `A0_BASE_URL` from Critical-1)? None specified.

**Why major.** The pivot from host-compose (DEC-001) to nested-devcontainer (DEC-018) leaves the most operationally complex layer — how `up`/`down`/compose work nested and rootless, and how Playwright reaches the nested instance — entirely undefined. This is where implementation will actually break.

**Proposed fix.** Add requirements pinning: (1) whether `up`/`down` use docker-compose or podman-compose inside the devcontainer and whether the same compose file serves host-dev and nested-CI; (2) the network/port contract by which the harness (Playwright/API) reaches the nested A0 (the `A0_BASE_URL` resolution); (3) data/volume handling for the nested container. Tie to DEC-018. This is the concrete content Q-021 must produce before Phase 1.

### Major-9 — "Conformance is mechanical to check" (G5, REQ-MK-001) lacks the conformance checker

**Symptom.** G5: *"a plugin either conforms or fails a gate."* REQ-MK-001 verification: *"`make help` in every repo lists the identical common target set with identical contracts."* REQ-DEV-004: *"CI flags any out-of-contract tracked file."* But no requirement defines the **conformance checker** that performs these structural assertions (target-set identity, allowed-asset enforcement, presence of `cases.yaml`/hooks). `make help` listing names does not prove "identical contracts," and "CI flags out-of-contract files" names no mechanism or owner.

**Why major.** A central goal (mechanical conformance) has no specified enforcing component. Reviewers will dispute where this lives (devkit fragment? caller workflow? gate — but DEC-023 says the gate is unchanged) and what exactly it asserts.

**Proposed fix.** Add REQ-CONF-00x: the devkit MUST provide a conformance check (e.g. `make conform` or a CI step) asserting target-set identity, required-file presence, and allowed-asset compliance; it runs in each repo's PR gate (consistent with DEC-023). Define its pass/fail and what "identical contracts" is checked against (the frozen E.1 table).

---

## Minor findings (mechanical fixes)

### Minor-1 — DEC ordering is non-monotonic
DEC-021–DEC-025 are written *before* DEC-018–DEC-020 in Appendix A (DEC-018 appears at line 345, after DEC-025 at 341). Renumber or reorder so the log reads in DEC order; aids Modifiability.

### Minor-2 — "iteration 4 … all decision clusters closed" vs. open Q-021/Q-023
The status line claims all clusters closed, but Appendix B keeps Q-021 and Q-023 open (even if "non-blocking"). Reword status to "all *blocking* decisions closed; two implementation-time questions deferred."

### Minor-3 — DEC-001 still cited as live trace context
REQ-DEV-002 traces only DEC-015, good — but DEC-001 is SUPERSEDED yet still referenced as surviving-in-part via DEC-015. No live REQ traces DEC-001 directly (verified: it appears in no Trace cell). Confirm and add a one-line note in DEC-001 that no REQ traces it directly; its surviving half is carried by DEC-015. (See XCut-3.)

### Minor-4 — `livekit` vs `livkit` typo
DEC-024 line 337: *"prove it end-to-end on the template + `livekit`"*; REQ-ROL-001 verification row 182: *"devkit → template+livekit → fan-out"* — but line 182 reads "template+livekit" while the reference plugin is named `livekit`. Also REQ-ROL-001's row says "livekit" — confirm the plugin name spelling is consistent (it is `livekit` in DEC-024). Fix any `livkit`/`livekit` drift.

### Minor-5 — "~20" vs "~18" plugin repo count
Scope §1 says *"~20 existing plugin repos"*; DEC-024 says fan out to *"the other ~18 repos"*. Reconcile (18 + template + reference ≈ 20?) and state the arithmetic.

### Minor-6 — Q-008-followup referenced but never defined
DEC-019: *"tag policy per Q-008-followup"* — there is no Q-008-followup entry in Appendix B (Q-008 is closed by DEC-019 itself). Add the follow-up question explicitly or fold the tag policy into Q-021.

### Minor-7 — E.2 `cases.yaml` example references TBD Q-017, which is closed
E.2 caption: *"(Per-case override of verify expectations — TBD Q-017.)"* — but Q-017 is marked closed by DEC-014. DEC-014 itself says "`cases.yaml` MAY override expectations per case" but the *shape* of that override is undefined. Either close the E.2 TBD with the override schema or open a fresh implementation-time Q; don't point a "TBD" at a closed Q.

---

## Gap findings (behaviour that should be specified but isn't)

### Gap-1 — Failure/abort semantics of the serial matrix loop
If case-2's `install` or `verify-installed` fails mid-loop, does the harness still attempt `uninstall`/`verify-uninstalled` for that case and continue to case-3, or abort? Unspecified. Without this, a failure leaves the booted A0 in an unknown state and subsequent cases' baselines are meaningless. Add a REQ: on any stage failure, the harness MUST attempt teardown of the active case and MUST mark the run failed; whether it proceeds to remaining cases MUST be defined (recommend: abort, report).

### Gap-2 — Timeouts / flake policy for the e2e lifecycle
No requirement bounds how long `up`, install, verify, or the whole `e2e` may take, nor a retry/flake policy for Playwright/network steps. e2e harnesses are flake-prone; the gate's reliability depends on this. Add a SHOULD/MUST on per-stage timeouts and a defined (or explicitly forbidden) retry policy.

### Gap-3 — Devcontainer image versioning/pinning contract
REQ-DEV-003 mandates publishing the image but nothing pins *which tag* CI/devs use or how it's kept in sync (the resync mechanism syncs the *submodule*, REQ-CI-001 — does it also bump the devcontainer image tag?). Q-021 defers versioning. Add a REQ that the caller workflow pins the devcontainer image by digest/tag and that resync updates it, mirroring the submodule pin.

### Gap-4 — What `verify-installed` asserts for the *default empty-config* case
A plugin with no `cases.yaml` runs "one default (empty-config) case" (REQ-LC-002). Its `verify-installed` common stage still runs deps+structure checks, but the per-plugin functional hook may be empty. Is a plugin *required* to supply a functional hook, or is deps+structure-only conformant? G3 implies the hook is the author's one job; REQ-VER-003 says the hook "is the plugin's functional assertion" (implying mandatory) while E.1 marks `verify-uninstalled`'s hook "(opt)" but `verify-installed`'s simply "plugin hook." Specify whether the `verify-installed` functional hook is mandatory or MAY be empty.

### Gap-5 — Credential/login mechanism for the booted A0
The harness must authenticate to A0 (UI login for Playwright, bearer for API). Nothing specifies how credentials are established for the booted instance (default admin? injected env? generated?). This is also a Critical-1 dependency (the hook needs `A0_AUTH_TOKEN`). Add a REQ pinning how the harness provisions and exposes A0 auth.

### Gap-6 — Plugin install *source* in CI (zip path vs OCI vs Git)
`install` (E.1) installs "the packaged zip," but A0 supports install-from-Git/ZIP/OCI. The spec never says the e2e exercises the zip path specifically (and whether that matches how the plugin is actually published via the gate's OCI artifact). If the gate publishes OCI but e2e tests zip-install, the tested install path differs from production. State which install source the lifecycle exercises and why.

---

## Cross-cutting findings

### XCut-1 — Multiple residue/dep requirements depend on undocumented A0 runtime behaviour, which NG1 declares fixed-but-doesn't-pin
NG1: *"The runtime install/uninstall endpoints are treated as a fixed dependency, not a thing this spec changes."* Yet Critical-3, Major-4, Major-7 all hinge on *what A0 actually does* on install/enable/uninstall (does it uninstall deps? does it transform zip paths? does it namespace settings?). The spec treats A0 behaviour as fixed but never **documents the assumed contract**. Add an appendix "Assumed A0 runtime behaviour" enumerating the install/enable/uninstall/config-API behaviours the standard relies on, so that if A0 differs, the mismatch is visible. Touches NG1, DEC-011, DEC-013, DEC-022, REQ-LC-003, REQ-VER-002/004.

### XCut-2 — The language-agnostic-hook promise is repeated but the ABI that makes it real is absent everywhere
REQ-MK-003, REQ-VER-003, DEC-005 all assert hooks are language-agnostic (Playwright/exec/SSH/API/script). Language-agnosticism is *only meaningful if the invocation/context/exit contract is defined* (Critical-1). Every "language-agnostic" claim is currently unbacked. Resolving Critical-1 retroactively grounds REQ-MK-002, REQ-MK-003, REQ-VER-001, REQ-VER-003, REQ-VER-004, DEC-005, DEC-009, DEC-010.

### XCut-3 — Traceability hygiene: DECs that close nothing, REQs vs DEC coverage
Audit results: every REQ traces to ≥1 DEC (good) and every REQ has exactly one verification row (good — 30 REQs, 30 rows). But: **DEC-016** (Claude-only IDE) is traced by REQ-DEV-005 (good); **DEC-021** (triggers) is closed and referenced by no REQ — the trigger set (PR→main, dispatch, nightly) is a normative behaviour with **no REQ and no verification row** (promote to a REQ-CI-00x). **DEC-007** is traced by REQ-VER-005 (good). **DEC-010** is traced by REQ-LC-004 (good) but see Major-1. Add a REQ for DEC-021's triggers so the trigger contract is verifiable.

### XCut-4 — Two superseding chains leave stale vocabulary scattered through normative text
DEC-009 supersedes the `purge`/standalone-`verify` model of DEC-006, and DEC-018 supersedes DEC-001. The superseded vocabulary still leaks into *normative* clauses: REQ-CI-003 (`verify`/`remove`/`purge` — Major-3), DEC-006's body still describes `purge` as a live final pass (line 227, 234) though DEC-009 removed it, and the Glossary "The three operations — install, verify, uninstall" (line 77) predates the two-assertion-target model. Sweep all normative text and the glossary to the post-DEC-009 / post-DEC-018 vocabulary; keep superseded terms only inside the superseded DEC bodies with explicit "(superseded)" markers.

---

## Appendix — traceability spot-check table

| Check | Result |
|---|---|
| Every REQ traces ≥1 DEC | PASS (all 30 REQs have a Trace cell) |
| Every REQ has exactly one verification row | PASS (30 REQs ↔ 30 rows) |
| Superseded DEC-001 traced by a live REQ | PASS (not directly traced; see Minor-3) |
| DECs closing no REQ | DEC-021 (triggers) — no REQ; behaviour unverifiable (XCut-3) |
| Dangling Q references | Q-008-followup undefined (Minor-6); E.2 points "TBD" at closed Q-017 (Minor-7); "pending Q-012" on closed Q-012 (Major-2) |
| Stage-vocabulary consistency | FAIL — `effectiveness-check`/`docker`/`verify`/`remove`/`purge` vs `verify-installed`/`verify-uninstalled` (Major-2, Major-3, XCut-4) |
