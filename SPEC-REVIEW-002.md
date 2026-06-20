# SPEC-REVIEW-002 — Cycle-2 audit (authoring & polish standard)

**Reviewer role:** IEEE 29148 specification reviewer (skeptical pass).
**Target:** `SPEC.md` iteration 8 — **Cycle-2 additions only**: §5.7–5.13 (GOV, SKL, DOC,
LIC, MED, DR, BEH), DEC-045–DEC-053, Appendix E.7–E.10, open questions Q-025–Q-028, and
their consistency with the shipped Cycle-1 spec.
**Date:** 2026-06-20.
**Method:** Audited against the IEEE 29148 quality characteristics (Unambiguous, Complete,
Consistent, Verifiable, Feasible, Necessary, Traceable, Modifiable, Bounded). Cycle-1
internals are out of scope except where Cycle-2 contradicts them. Claims about the harness
were checked against the live `.github/workflows/plugin-e2e.yml` and `e2e/` tree, not just
the prose. Quotes are verbatim.

---

## Verdict

**Needs material revision.**

The Cycle-2 decision log is coherent at the prose level, but three of its central new
mechanisms are **specified as MUST while resting on capabilities the current harness
provably does not have**, and one new MUST is **logically unverifiable as written**.
Concretely: (1) **media auto-capture + commit-back** (DEC-051 / REQ-MED-001/002 / E.10) is
mandated, but the e2e job mounts the workspace **read-only**, has **no commit-back step**,
captures Playwright media **only on failure**, and has **no GIF tooling** — every clause is
contradicted by the running workflow (Critical-1). (2) **a0_compat** (DEC-049 / REQ-DOC-004)
demands the declared value "be consistent with the A0 image its e2e passes against," but
each e2e run tests exactly **one** image, so `fork-required` is asserted, never proven —
the e2e can't distinguish "needs the fork" from "happens to pass on whatever single image
was chosen" (Critical-2). (3) **doctor's** "config schema-valid against `default_config.yaml`"
and "extension points mounted" checks (DEC-052 / E.9) are under-defined to the point of
being unimplementable: `default_config.yaml` is a values file, not a schema, and "extension
points mounted in the live A0" has no defined introspection surface (Major-1, Major-2).
(4) **behaviour-verify** (DEC-053) re-defines the *same* `verify-installed` hook that
Cycle-1's DEC-026 already froze, but the distinction "real behaviour vs implementation" is
given **no machine-checkable criterion**, colliding head-on with GOV-003's own
"machine-checkable or non-normative" rule (Critical-3). Beyond those, the **Cycle-2 fan-out
to 19 repos is entirely unspecified** (no ROL-equivalent), several Cycle-2 assets are
**absent from the frozen E.5 allowed-asset list** (so `make conformance` would reject them),
and the GOV "machine-checkable" mandate is **self-violated** by DOC/LIC/MED REQs whose
acceptances are eyeball inspections. These are closable, but they block a first
implementation of the Cycle-2 surface.

### Findings by severity

| Severity | Count |
|---|---|
| Critical | 3 |
| Major | 7 |
| Minor | 5 |
| Gap | 6 |
| XCut | 4 |
| **Total** | **25** |

---

## Critical findings (block implementation)

### Critical-1 — Media auto-capture/commit-back is mandated but the harness physically cannot do any of it

**Symptom.** REQ-MED-001 (MUST): the harness *"**MUST** capture media during the e2e run —
… screenshot … and a short GIF (or video) … emitted as CI artifacts."* REQ-MED-002 (MUST):
*"**MUST** be written to a known committed path (`docs/media/`) and be the assets the README
embeds."* DEC-051: *"emits them as CI artifacts and **commits them** to a known path."*
Every clause is contradicted by the actual `plugin-e2e.yml`:
- The workspace is mounted **read-only** into the harness container: `-v "$GITHUB_WORKSPACE":/workspace:ro`. The harness *cannot write* `docs/media/` at all, let alone commit it.
- There is **no commit-back step** in the workflow — no `git add docs/media`, no push, no PR. "Committed to a known path" has no implementing actor. (And the e2e runs on `pull_request → main` from a token that, like `GITHUB_TOKEN`, cannot push to a contributor fork's PR branch — the same class of distribution hazard the brief flags, see XCut-2.)
- Playwright is configured `screenshot: "only-on-failure"`, `video: "retain-on-failure"` (`e2e/playwright-base.config.ts`) — i.e. media is produced **only when the run fails**, the exact opposite of "screenshot of the installed plugin behaving" (a green-run artifact).
- There is **no GIF tooling** anywhere in the devcontainer or e2e tree (no ffmpeg, no video→gif step); Q-026 admits the tooling is unchosen, yet REQ-MED-001/003 are already MUST.

**Why critical.** REQ-MED-001/002/003 and REQ-DOC-003 ("README **MUST** embed the
harness-captured … media … from the committed known path") form a chain that gates README
conformance on an artifact the pipeline cannot produce or commit. An implementer following
the SPEC literally builds a `make conformance` that fails every repo (no `docs/media/`
assets) while the harness that is supposed to fill `docs/media/` can't write to disk.

**Fix.** (a) Add a **media-capture stage** to the harness contract that runs on the
*success* path (a deliberate screenshot + a recorded clip of the behaviour-verify flow),
distinct from Playwright's failure-only artifacts — pin it in E.10 and in a new
`REQ-MED-00x` ("capture runs on the green behaviour-verify path; failure-only Playwright
media does NOT satisfy it"). (b) Resolve the read-only-mount contradiction: either drop the
"committed" requirement and make media a **downloadable CI artifact the author commits
manually** (Inspection-checkable: artifact exists), or specify a dedicated **commit-back
job** with an auth principal that can push to the PR head, mounted read-write into a media
scratch dir — and state how fork PRs are handled (they can't push back; see XCut-2). (c)
Demote REQ-MED-001's GIF clause to depend on Q-026's tooling decision (mirror how Cycle-1
demoted REQ-DEV-003 behind the Phase-0 spike), or pick the tool now. Record as a DEC
refining DEC-051.

### Critical-2 — `a0_compat: fork-required` is asserted, never proven, because the e2e tests exactly one image

**Symptom.** REQ-DOC-004 (MUST): *"`fork-required` **MUST** name the required fork change
and link the fork repo, and **MUST** be consistent with the A0 image its e2e passes
against."* DEC-049: *"MUST be consistent with the A0 image the plugin's e2e passes against
(the e2e base image is the mechanical check …)."* But `plugin-e2e.yml` resolves a **single**
`a0_image` per run (`.devkit.yml a0_image` → else the one workflow default
`docker.io/agent0ai/agent-zero:latest`) and boots exactly that one image. A single
green run against one image proves only "passes on *this* image" — it cannot distinguish:
- `upstream` (passes on stock) — would also pass on the fork, so a green upstream run is consistent with `upstream` **and** with a mis-declared `fork-required`;
- `fork-required` (genuinely needs a fork change) — a green run on the fork image is **equally** consistent with a plugin that didn't need the fork at all.

The "mechanical check" therefore has **no discriminating power**: there is no run against
the *other* image to falsify the declaration. `fork-required` reduces to an unverifiable
assertion (DEC-049's own git-history "human explanation" is acknowledged as non-mechanical),
and `upstream` is only weakly evidenced (it could silently depend on a fork feature present
in the tested image).

**Why critical.** REQ-DOC-004's acceptance row claims *"value matches the e2e image"* as if
mechanical, but the SPEC's own single-image harness makes the match vacuous. This is a
Verifiable failure on a MUST that the SPEC presents as machine-checked (and GOV-003 forbids
non-machine-checkable binding standards).

**Fix.** Make compatibility *falsifiable*: require a plugin that declares `fork-required` to
run e2e against **both** images and demonstrate **green-on-fork + red-on-upstream** (the red
run on upstream is the proof the fork change is actually needed); a plugin declaring
`upstream` runs against **stock upstream** specifically (not the fork) so a stock-green is
real evidence. Add a `REQ-DOC-00x` + verification row encoding the two-image contract, and
extend the e2e workflow to accept a compat-matrix (the SPEC already parameterizes the image
— the missing piece is *running both and asserting the expected pass/fail per declaration*).
Record as a DEC refining DEC-049. Absent that, downgrade REQ-DOC-004's `a0_compat` from a
mechanically-verified MUST to a **declared-and-human-reviewed** field and stop claiming
"value matches the e2e image" as the acceptance.

### Critical-3 — Behaviour-verify (DEC-053) re-defines the frozen DEC-026 hook with an unfalsifiable "behaviour vs implementation" criterion that GOV-003 forbids

**Symptom.** DEC-053 / REQ-BEH-001 (MUST): the `verify-installed` hook *"**MUST** assert
the plugin's **running behaviour** … not its implementation — unit/implementation tests do
not satisfy this … not mere file/dep presence."* But the hook ABI is already frozen by
Cycle-1's DEC-026 / Appendix E.4 as *"an executable … pass/fail = exit code,"* black-box.
The devkit invokes the hook and reads its exit code; it has **no visibility** into whether
the hook drove the live UI/API or just asserted file presence (or did nothing and returned
0). So "real behaviour, not implementation" is:
- **Unverifiable mechanically** — the acceptance row for REQ-BEH-001 says *"stubbing the behaviour (not the files) fails it,"* which tests the *plugin author's own hook*, not the standard; a hook that `exit 0`s without touching A0 passes the gate identically to a genuine behavioural hook. The devkit cannot tell them apart.
- **Self-contradictory with GOV-003** (MUST): *"a standard that can only be eyeballed is non-normative."* "Behaviour, not implementation" can only be eyeballed (a human reads the hook and judges it behavioural). By the SPEC's own rule it is therefore non-normative — yet DEC-053 makes it a gating MUST.

REQ-BEH-002's "the behaviour verify MUST … gate merge; the generic lifecycle … MUST NOT be
the only behavioural check" is real and enforceable (you can check a non-empty hook exists
and runs). The *behavioural-ness* of its content is the unfalsifiable part.

**Why critical.** The headline Cycle-2 quality bar ("verify real behaviour") is stated as a
binding, gating MUST with no mechanical discriminator, in direct tension with GOV-003. An
implementer cannot write a conformance check that enforces it; reviewers will endlessly
dispute whether a given hook is "behavioural enough."

**Fix.** Replace the unfalsifiable predicate with **mechanical proxies** that approximate
"touched the live instance": e.g. require the behaviour hook to (i) be present and non-empty
(REQ-BEH-002 — keep), and (ii) produce **evidence of live interaction** the devkit can
observe — at minimum the captured behaviour media (DEC-051) as a *byproduct* of the hook
(if the GIF is empty/identical-frames, fail), and/or require the hook to hit
`A0_BASE_URL`/the API and emit a structured assertion log into `A0_REPORT_DIR` that the
devkit validates is non-trivial. Recast REQ-BEH-001 as "the hook MUST exercise A0 over
`A0_BASE_URL` (HTTP/UI) and record ≥1 behavioural assertion to `A0_REPORT_DIR`; a hook that
performs no live request is non-conformant," which *is* checkable (the devkit can observe
that requests were made). Reconcile DEC-053 with DEC-026 explicitly (it "refines" it, but
the refinement narrows the ABI's semantics and must say how the narrowing is enforced).
Record as a DEC and add a real verification row.

---

## Major findings (substantive ambiguity / hole)

### Major-1 — "schema-valid against `default_config.yaml`" is undefined: `default_config.yaml` is values, not a schema

**Symptom.** DEC-052 / E.9: doctor checks *"config present and schema-valid against
`default_config.yaml` (default_config.yaml as the schema baseline)."* `default_config.yaml`
in the A0 plugin contract is a **default values file** (key → default value), not a schema —
it has no types, no required/optional markers, no constraints. "Schema-valid against a values
file" has no defined meaning. Plausible intents — "every key in the live config also appears
in `default_config.yaml`" (key-set conformance), or "live values are type-compatible with
the default's value types" (weak type inference), or "all default keys are present" — are
materially different checks, and none is a *schema* validation. Q-028 even asks "is
`default_config.yaml` the schema source?" — i.e. the SPEC ships the MUST while still asking
whether its premise holds.

**Why critical-adjacent (Major).** REQ-DR-001 makes this a gating doctor check; two
implementers will build incompatible validators, and "schema-valid" against a non-schema is
not Verifiable. The acceptance row (*"fails when … config is invalid"*) doesn't define
"invalid."

**Fix.** Pin the actual check in E.9: define it as **key-set + type conformance** — every key
present in live `config.json` is declared in `default_config.yaml`, and each value's Python
type matches the default's type (with null/optional rules stated); missing-but-defaulted keys
are a WARN not FAIL. If a true schema is wanted, mandate a real schema artifact (e.g.
`config.schema.json` / pydantic model) and make *that* the baseline — but then it's a new
required asset (see Major-5). Resolve Q-028 before REQ-DR-001 stays MUST. Record as a DEC
refining DEC-052.

### Major-2 — Doctor's "extension points mounted in the live A0" check has no defined introspection surface (feasibility)

**Symptom.** DEC-052 / E.9: doctor checks *"the plugin's declared extension points are
mounted in the live A0."* Nothing defines **how** a script running inside the booted A0
determines that *this plugin's* extension points are registered: there is no cited A0 API
that enumerates mounted extension points by plugin, no "declared extension points" manifest
field named (where does doctor read the *expected* set from — `plugin.yaml`? the
`extensions/` dir listing? the `@extensible`/`_functions` hook registry?), and no contract
for what "mounted" means at runtime (file present ≠ extension actually wired; the brief's own
memory notes a real "basename-path gotcha that silently broke context_scoping" — exactly the
class of bug a file-presence check misses). REQ-DR-001 already overlaps the Cycle-1 common
`verify-installed` structure check (DEC-038, "asserts manifest + entrypoints"); the SPEC
doesn't say how doctor's extension-point check differs from or duplicates it.

**Why major.** This is the one doctor check with genuine diagnostic value (it's the one that
catches the silent-unmount failure mode), and it's the least specified — no API, no expected
source, no runtime definition of "mounted." Feasibility is unproven; it may require A0
runtime introspection that doesn't exist.

**Fix.** Specify the introspection surface: name the A0 runtime call or registry doctor reads
to list active extension points (and if none exists, that's an upstream dependency to add —
flag it like F.6 flags the sshd issue, or scope the check to what *is* observable, e.g. an
HTTP probe of the plugin's registered routes / a tool-list query). Name where doctor reads
the *expected* extension-point set. State the relationship to DEC-038's structure check
(doctor = live-wiring; DEC-038 = files-landed). Resolve under Q-028. Record as a DEC.

### Major-3 — The shared CLAUDE common block (DEC-046) has a real distribution hazard analogous to GITHUB_TOKEN-can't-write-workflows, unaddressed

**Symptom.** REQ-SKL-002/003: every repo's `CLAUDE.md` carries a marker-delimited
(`<!-- a0:common:start -->`/`end -->`) org-identical block, *"distributed/refreshed by the
devkit-sync mechanism, not hand-copied."* The brief asks the right question: does sync own
`CLAUDE.md` edits cleanly, and is there a write-permission hazard like GITHUB_TOKEN's
inability to create/modify workflow files? Two real hazards the SPEC doesn't address:
1. **The sync App's write scope.** `devkit-sync` (DEC-044) opens auto-merge PRs via the GitHub App. If that App's token lacks the `workflows` permission it cannot modify `.github/workflows/*` — and devkit-sync *also* renders the e2e caller workflow (DEC-044) and the `claude-code-review.yml` (DEC-017). `CLAUDE.md` itself is a normal file (writable), but the same sync mechanism that touches it touches workflow files; the SPEC never states the App's required permission set, so a sync that updates the CLAUDE block but silently fails to update the caller workflow is possible (partial sync). The marker-replacement of `CLAUDE.md` is fine; the **co-distributed workflow edits are the hazard**.
2. **Marker-replacement robustness.** If a repo's `CLAUDE.md` has its markers deleted, edited, or duplicated (a contributor edits inside the block), the in-place replacement is undefined — does sync fail, re-insert, or clobber the repo-specific section? "MAY add a repo-specific section outside the markers" gives no rule for a malformed-marker repo.

**Why major.** Cycle-1 already learned (the workshop memory + the SPEC's own DEC-044 App
note) that distribution auth is load-bearing. A new sync payload (skills + CLAUDE block) is
added without re-stating the auth contract, and the marker-collision case is unspecified.

**Fix.** State the devkit-sync App's required permission set explicitly (contents:write, and
**workflows:write** if it renders caller/review workflows — call out that `GITHUB_TOKEN`
cannot and the App must), in a DEC refining DEC-044/DEC-046. Specify marker-failure behaviour:
sync MUST fail loudly (not clobber) on missing/duplicate markers, and MUST preserve content
outside the markers byte-for-byte. Add a verification row that a malformed-marker repo is
rejected, not silently overwritten.

### Major-4 — No Cycle-2 rollout/fan-out PROCESS requirement (Cycle-1 had ROL; Cycle-2 retrofit of 19 repos is unspecified)

**Symptom.** Cycle-1 specified rollout as first-class: §5.6 ROL (REQ-ROL-001..004), DEC-024
phased fan-out, with the 19-repo classification table. Cycle-2 adds **seven new per-repo
obligations** (DEVELOPING.md, README skeleton, `a0_compat`, LICENSE, `docs/media/`,
`doctor.py`, behaviour hook) that every one of those 19 already-standardized repos must now
acquire — but there is **no REQ-ROL/PROCESS for the Cycle-2 retrofit**: no phasing, no
ordering, no "reference plugin proves the Cycle-2 surface before fan-out," no statement of
who authors the per-repo prose (README "Why", behaviour hooks, real thumbnails) that cannot
be mechanically generated. Cycle-1's lesson (validate on a reference before batch) is not
re-applied. The status line says Cycle-2 is "drafted" but the spec is silent on *how it
reaches the fleet*.

**Why major.** Completeness gap mirroring Cycle-1's own structure. Without it the Cycle-2
standard is a set of conformance checks that would **red every existing repo simultaneously**
the moment `make conformance` learns the new rules, with no migration path — a flag-day.

**Fix.** Add §5.x **ROL-Cycle2** REQs (or extend §5.6): phase the retrofit (devkit ships the
templates/checks → one reference plugin acquires the full Cycle-2 surface and goes green →
fan-out), state that the new conformance checks are **introduced gated/soft** until a repo is
migrated (so they don't flag-day the fleet), and assign authorship for the irreducibly-human
content (README prose, thumbnail, behaviour assertions). Tie to DEC-024's existing
classification. Record as a DEC.

### Major-5 — Cycle-2 adds tracked assets the frozen E.5 allowed-asset list does not include, so `make conformance` would reject them

**Symptom.** DEC-034 / E.5 is the **single canonical allowed-asset list**, and REQ-CONF-001
+ REQ-DEV-004 make `make conformance` *"flag any tracked file outside this list."* Cycle-2
mandates new tracked files that **do not appear in E.5**: `DEVELOPING.md` (REQ-DOC-001),
`README.md`'s required state, `LICENSE` (REQ-LIC-001), `.devkit.yml` carrying `a0_compat`
(REQ-DOC-004 — and the e2e zip step `-x '.devkit.yml'` excludes it from the package but it's
still tracked), `docs/media/installed.png` + `behaviour.gif` (REQ-MED-002),
`usr/plugins/<name>/scripts/doctor.py` (REQ-DR-001), and the vendored authoring-skills tree +
common CLAUDE block (REQ-SKL-001/002). E.5 lists none of `DEVELOPING.md`, `README.md`,
`LICENSE`, `docs/media/`, `scripts/doctor.py`, `.devkit.yml`, or the `skills/` tree.

**Why major.** The Cycle-1 review's Major-6 was *exactly* this failure (divergent
allowed-asset lists) and was closed by freezing E.5 as canonical. Cycle-2 re-opens it by
adding assets without amending E.5 — so a conforming Cycle-2 repo fails `make conformance`,
or the check silently isn't updated and the GOV-003 "machine-checkable" promise is hollow.

**Fix.** Amend E.5 to add every Cycle-2 tracked asset (`LICENSE`, `README.md`,
`DEVELOPING.md`, `.devkit.yml`, `docs/media/*`, `usr/plugins/<name>/scripts/doctor.py`, the
vendored authoring-skills path, and confirm `CLAUDE.md` is listed). Add a verification row
that the E.5 list is the *exhaustive* superset of all REQ-mandated tracked files (a
cross-check that no REQ mandates a file absent from E.5). Record as a DEC refining DEC-034.

### Major-6 — GOV-003 ("machine-checkable or non-normative") is self-violated by DOC/LIC/MED/DR acceptances that are Inspection-only

**Symptom.** REQ-GOV-003 (MUST): *"Every binding standard introduced by this SPEC **MUST**
be machine-checkable by `make conformance` or the e2e gate; a standard that can only be
eyeballed is non-normative."* Yet several Cycle-2 acceptances are human inspections of
*content quality*, not mechanical checks:
- REQ-DOC-002 "README **MUST** follow the standard skeleton" — `make conformance` can check **heading presence** (E.8), but the brief's point stands: section-presence ≠ the section being *meaningful* (a "## Why" with one filler word passes).
- REQ-DOC-005 "the card **MUST** ship a **real (non-placeholder)** thumbnail" — acceptance is a *"size/dimension check,"* which a non-placeholder-sized blank PNG passes; "real/nice" is Q-027 and explicitly not mechanical.
- REQ-DOC-004 `a0_compat` "value matches the e2e image" — shown vacuous in Critical-2.
- REQ-BEH-001 "real behaviour not implementation" — shown unfalsifiable in Critical-3.

So GOV-003's own bar is failed by sibling Cycle-2 REQs. Either those REQs are non-normative
(contradicting their MUSTs) or GOV-003 is aspirational (contradicting its MUST).

**Why major.** A normative consistency defect: the SPEC asserts a meta-rule it
simultaneously breaks. Reviewers will weaponize GOV-003 against half of Cycle-2.

**Fix.** For each non-mechanical Cycle-2 standard, either (a) add the strongest *available*
mechanical proxy and explicitly mark the residual quality bar as **SHOULD / human-review,
not gating** (e.g. thumbnail: mechanically reject the byte-identical placeholder stub by
hash, leave "nice" to review), or (b) carve GOV-003 to "every binding standard is *gated by
the strongest available mechanical proxy*; content quality is SHOULD." Record as a DEC.
This also resolves Q-027's "who makes it nice" by separating the mechanical floor from the
quality ceiling.

### Major-7 — Doctor path collides with the e2e packaging exclusion and the `tests/` ABI; fork/build-generated path resolution is open

**Symptom.** REQ-DR-001 puts doctor at `usr/plugins/<name>/scripts/doctor.py` *"(or the
`plugin_dir` equivalent for forks/build-generated)."* Two problems:
1. **Path resolution for forks/build-generated is unresolved** — Q-028 explicitly asks "how does doctor resolve `plugin_dir` for forks/build-generated plugins?" while REQ-DR-001/002 already hard-code the literal `python /a0/usr/plugins/<name>/scripts/doctor.py` invocation (REQ-DR-002) that is *wrong* for a fork whose `plugin_dir` is e.g. `dist/gitnexus` or an upstream layout. The MUST and its open question contradict.
2. **doctor must ship in the install payload, but the e2e excludes wrappers.** The packaging step zips `usr/plugins/<name>/` and `-x 'tests/*' '.github/*'` etc. `scripts/doctor.py` *inside* the plugin dir does ship (good) — but the SPEC never states that doctor MUST be inside the packaged payload (vs. a dev-only file), and for `plugin_dir: .` (root-layout forks) the exclusion list could strip a top-level `scripts/` if it ever collided. The "ships in the zip vs dev-only" status of doctor is unstated.

**Why major.** REQ-DR-002's concrete invocation path is non-portable across the two fan-out
tracks (reshape vs declare) the SPEC itself defined (DEC-042/043), and Q-028 is unclosed
under a MUST.

**Fix.** Make REQ-DR-002's invocation `plugin_dir`-relative
(`python <resolved_plugin_dir>/scripts/doctor.py`, resolving via the same `.devkit.yml`
`plugin_dir` → else `usr/plugins/<name>` rule as DEC-043), not a hard-coded
`usr/plugins/<name>`. State that doctor is part of the **installed payload** (it must run
inside booted A0, so it must be installed) and is therefore in-scope for the packaged zip.
Close Q-028 before REQ-DR-001/002 stay MUST. Record as a DEC.

---

## Minor findings (mechanical)

### Minor-1 — Status line claims Cluster 6 work is done while Q-025–Q-028 are open
The header says Cycle-2 *"drafted; pre-SPEC-REVIEW-002"* but §5.7–5.13 are full MUST REQs
while Cluster 6 (Q-025–028) is marked **OPEN** and four of those questions block the *data*
or *premise* behind DOC-004, MED, DR. Reword the DOC/DR/MED REQ statuses to "provisional
pending Q-025–028" or close the questions; don't ship MUSTs whose premises are open Qs (see
Critical-2, Major-1, Major-2, Major-7).

### Minor-2 — E.1 still says `up`/`down` "boot the A0 **compose** harness"; Cycle-1 DEC-032 already moved to nested podman
Appendix E.1 row: *"Boot / teardown the A0 compose harness."* DEC-032/DEC-041 (Cycle-1
closures) redefined `up`/`down` as nested rootless podman; the live harness is
`podman run … --network=host`. Cycle-2's DEC-047 `DEVELOPING.md` loop quotes
`make build → up → e2e → doctor → verify → down` — propagating the stale "compose" framing
into a new Cycle-2 artifact. Update E.1's `up`/`down` contract text to the nested-podman
model (carry-over from Cycle-1, now re-exposed by DEC-047).

### Minor-3 — DEC-047's documented loop names `doctor` and `verify` as if they were targets
DEC-047: *"`make build → up → e2e → doctor → verify → down`."* But DEC-033 (Cycle-1) froze
`doctor` as a **non-normative/historical** term that *"MUST NOT appear in REQs,"* and there
is no `make verify` target (E.1 has `verify-installed`/`verify-uninstalled`, and `e2e`
already runs them). DEC-047 reintroduces the purged `doctor` term and a non-existent `verify`
target into a binding template. Replace with real targets (`make e2e` already covers
verify-installed/uninstalled; add a `make doctor` target if doctor is to be a first-class
target, otherwise drop it from the loop).

### Minor-4 — REQ-MED-002 "MAY override a specific asset" lacks an override mechanism
REQ-MED-002: *"an author **MAY** override a specific asset but the default is the
auto-captured one."* No mechanism is defined (a flag in `.devkit.yml`? a sentinel committed
file the harness won't overwrite?). Given Critical-1 (harness can't write the dir anyway),
this is moot until capture is fixed, but specify the override switch when you do.

### Minor-5 — E.7 lists a skill (`a0-plugin-testkit`) annotated "already in the devkit `skill/`" — naming/location drift
E.7 row: `a0-plugin-testkit` — *"(already in the devkit `skill/`)."* The repo has a `skill/`
dir (singular) and DEC-046/REQ-SKL-001 speak of a vendored `skills/` tree (plural, E.7 set).
Reconcile the singular `skill/` (existing) vs the `skills/` tree the sync populates, and
confirm the testkit skill isn't double-counted across both.

---

## Gap findings (behaviour that should be specified but isn't)

### Gap-1 — No REQ mandates the placeholder thumbnail stubs MUST be replaced (only "non-placeholder" size-checked)
Q-027 admits the harness screenshot ≠ a designed thumbnail and asks who produces the branded
one. REQ-DOC-005 only forbids "the placeholder stub" via a *size/dimension* check — there is
no REQ that the bootstrap-time placeholder **must be replaced before the repo is conformant**,
nor a tracking mechanism (an issue, a TODO the gate flags) for the ~15 reshape-track repos
that ship a stub today. Add a REQ that a stub thumbnail (matched by hash, not size) fails
conformance, and a process REQ that fan-out enumerates which repos still carry a stub.

### Gap-2 — Behaviour-media size/length/format budget is unbounded (Bounded)
REQ-MED-001 mandates "a short GIF (or video)" with no max size/length/format; Q-026 defers
it. Unbounded media in `docs/media/` (committed to every repo, on every green run if
commit-back exists) is a repo-bloat hazard. Add a SHOULD/MUST bound (≤ N seconds, ≤ N MB,
pinned format) — tie to Q-026's resolution.

### Gap-3 — No spec of *what* the screenshot/GIF must show to be conformant
REQ-MED-001 says "screenshot of the installed plugin card/config screen" and "GIF of the
documented behaviour," but nothing makes a **blank/all-white** capture non-conformant. Pair
with Critical-3's fix: the behaviour GIF is the mechanical proxy for behaviour-verify, so it
needs a non-triviality check (frame-diff / non-blank), else both MED and BEH are gameable by
an empty capture.

### Gap-4 — Inter-plugin dependency declaration is required in the README but has no machine-checkable source
REQ-DOC-002 / E.8 require a "## Dependencies (inter-plugin deps)" section, and the glossary
+ Why-block emphasize inter-plugin deps, but there is **no declared field** (in `plugin.yaml`
/ `meta.yaml` / `.devkit.yml`) for inter-plugin dependencies, and the common
`verify-installed` dep check (DEC-013) only covers pip + env vars, not *other A0 plugins*.
So inter-plugin deps are prose-only and unverifiable. Add a declared field + a verify check,
or explicitly scope inter-plugin deps as documentation-only (and say so).

### Gap-5 — Licensing relicensing hazard for borderline first-party repos is unaddressed (LIC)
DEC-050 mandates Apache-2.0 for *first-party*, upstream-license for *forks* — but DEC-043's
classification has a **third class**: build-generated-yet-first-party (`gitnexus`,
`dist/gitnexus`) and first-party repos that may **vendor upstream submodules** (the e2e
`build:` step inits "its OWN (public) submodules … upstream"). Relicensing the *wrapper* to
Apache-2.0 while a vendored-upstream component carries a different license is a real
contributor/provenance hazard the SPEC doesn't address: a first-party repo that bundles
GPL/MIT/BSD upstream code under a single root `LICENSE: Apache-2.0` mis-states the
component's license. Add a REQ: first-party repos that vendor upstream code MUST carry the
upstream license for the vendored subtree (a per-path `LICENSE`/NOTICE), and Apache-2.0
applies only to first-party-authored code. Name the borderline repos (gitnexus, any
submodule-bearing repo).

### Gap-6 — No statement of how Cycle-2 conformance interacts with the unchanged gate (DEC-023)
Cycle-1's DEC-023 froze the `agent-zero-vendor-plugins` gate as static-checks-only,
enforcement per-repo. Cycle-2 adds README/license/media/doctor obligations — are any of these
checked at the **gate** (where the OCI artifact is published to consumers) or purely in the
per-repo PR e2e? A plugin can be republished to the gate without its repo's Cycle-2 README
ever existing. State whether the gate stays Cycle-1-only (and accept that gate-published
artifacts may lack Cycle-2 polish) or gains a thin Cycle-2 metadata check. Tie to DEC-023.

---

## Cross-cutting findings

### XCut-1 — The "machine-checkable" promise (GOV-003) is the connective tissue Cycle-2 keeps breaking
GOV-003 is invoked as the Cycle-2 quality philosophy, but Critical-2 (a0_compat),
Critical-3 (behaviour-verify), Major-1 (schema-valid), Major-2 (extension-points-mounted),
and Major-6 (DOC/thumbnail) are each a place where a binding MUST has **no real mechanical
check** behind it. Closing GOV-003 honestly (strongest-available-proxy + explicit SHOULD for
quality) is the single highest-leverage edit; it reframes five findings at once. Touches
DEC-045/049/052/053, REQ-GOV-003, REQ-DOC-002/004/005, REQ-DR-001, REQ-BEH-001.

### XCut-2 — Distribution-auth hazard repeats across CLAUDE-sync, workflow-render, and media-commit-back
Three Cycle-2 mechanisms write into consumer repos via automation: devkit-sync of the
CLAUDE block + skills (DEC-046), devkit-sync of caller/review workflows (DEC-044/017
re-exposed), and media commit-back (DEC-051). All three share one unstated dependency: **a
principal with write (and for workflows, `workflows:write`) permission that the default
`GITHUB_TOKEN` lacks on fork PRs**. The brief's analogy is exact. Specify the auth principal
and its scopes **once**, centrally (the devkit-sync App), and state explicitly that
fork-originated PRs cannot receive commit-back/sync writes (so media/sync run on
`main`/`workflow_dispatch`, not on contributor-fork PRs). Touches DEC-017, DEC-044, DEC-046,
DEC-051, REQ-MED-001/002, REQ-SKL-003.

### XCut-3 — Cycle-2 re-opens two defects Cycle-1's review explicitly closed
Cycle-1 SPEC-REVIEW-001 closed **Major-6** (one canonical allowed-asset list → E.5/DEC-034)
and **Major-2/3 + XCut-4** (purge stale vocabulary; `doctor` MUST NOT appear). Cycle-2
re-opens both: Major-5 here (new assets absent from E.5) and Minor-3 here (DEC-047
reintroduces `doctor`/`verify` as loop steps; DEC-052 reintroduces `doctor` as a
first-class concept — arguably legitimately, but DEC-033's "MUST NOT appear in REQs" now
conflicts with the DR cluster's REQ-DR-001..003 which *are* about doctor). Reconcile
DEC-033 with the DR cluster: either DEC-033's doctor-ban is narrowed to "the *historical*
effectiveness-check sense of doctor," explicitly permitting the new DR-cluster doctor, or the
DR cluster renames. State the reconciliation so the two don't silently contradict.

### XCut-4 — Traceability: every Cycle-2 REQ traces a DEC and has a verification row (good), but several rows are circular/vacuous
Spot-check: all 18 Cycle-2 REQs (GOV/SKL/DOC/LIC/MED/DR/BEH) have a Trace cell and exactly
one §6 row — structurally clean. But the *content* of several rows restates the REQ rather
than giving an independent acceptance: REQ-DOC-004 ("value matches the e2e image" — vacuous,
Critical-2), REQ-BEH-001 ("stubbing the behaviour fails it" — tests the author's hook not
the standard, Critical-3), REQ-GOV-003 ("each new binding REQ maps to a conformance
assertion" — circular, asserts the thing under audit), REQ-MED-003 ("disabling the verify
removes the GIF" — depends on a capture mechanism that doesn't exist, Critical-1). These are
the same REQs flagged above; the traceability table is *present* but its acceptances are not
yet *meaningful*. No new fix beyond Critical-1/2/3 and Major-6.

---

## Appendix — Cycle-2 traceability spot-check

| Check | Result |
|---|---|
| Every Cycle-2 REQ (GOV/SKL/DOC/LIC/MED/DR/BEH) traces ≥1 DEC | PASS |
| Every Cycle-2 REQ has exactly one §6 verification row | PASS (18 REQs ↔ 18 rows) |
| Acceptances are independent (non-circular) | FAIL — REQ-DOC-004, REQ-BEH-001, REQ-GOV-003, REQ-MED-003 (XCut-4) |
| Cycle-2 tracked assets enumerated in canonical E.5 list | FAIL — DEVELOPING.md, README, LICENSE, docs/media, doctor.py, .devkit.yml, skills tree absent (Major-5) |
| Open questions don't underpin shipped MUSTs | FAIL — Q-025/026/027/028 underpin DOC-004 / MED / DOC-005 / DR (Minor-1) |
| GOV-003 "machine-checkable" honored by sibling Cycle-2 REQs | FAIL — Critical-2/3, Major-1/2/6 (XCut-1) |
| Harness can perform the MED capture/commit it's mandated to | FAIL — read-only mount, no commit-back, failure-only media, no GIF tool (Critical-1) |
| Cycle-2 rollout/fan-out specified (as Cycle-1 ROL was) | FAIL — no Cycle-2 PROCESS/ROL (Major-4) |
| `doctor` term reconciled with DEC-033's ban | FAIL — DR cluster vs DEC-033 (XCut-3) |
