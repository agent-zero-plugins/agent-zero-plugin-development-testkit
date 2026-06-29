#!/usr/bin/env python3
"""BDD honesty + purity linter — Tier-1 repo-level enforcement (devkit DEC-066).

Hard-fails (exit 1) on any violation of the behaviour-first BDD standard. Runs in
the `plugin-e2e` workflow before the e2e itself, so a plugin that drifts from the
standard goes RED on its own PR. Only fires for plugins that ship `tests/e2e/features/`
(non-BDD plugins are untouched).

Gates:
  1 feature-purity   — no selectors / DOM ids / internal-API names in Given/When/Then
  2 honesty          — every @skip has a tracked reason; no swallowed failures in steps;
                       the four docs/spec documents exist
  4 traceability     — every BEH-n in behaviour-spec.md is covered in e2e.feature.md
                       or listed in a tracked-skip/defects section

(Gate 3, the seam-off red-proof, is a runtime check wired separately in the harness.)

Usage:  python bdd_lint.py [PLUGIN_ROOT]   (default: cwd)
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
FEAT_DIR = ROOT / "tests" / "e2e" / "features"
STEP_DIR = ROOT / "tests" / "e2e" / "steps"
SPEC_DIR = ROOT / "docs" / "spec"

REQUIRED_DOCS = ["behaviour-spec.md", "implementation-plan.md", "e2e.feature.md", "e2e-steps-spec.md"]

violations: list[tuple[str, str, str]] = []  # (gate, location, message)


def fail(gate: str, loc: str, msg: str) -> None:
    violations.append((gate, loc, msg))


# Not a BDD plugin → nothing to enforce.
if not FEAT_DIR.exists() or not list(FEAT_DIR.glob("*.feature")):
    print("[bdd-lint] no tests/e2e/features/ — not a BDD plugin, nothing to lint.")
    sys.exit(0)

# ---------------------------------------------------------------- Gate 1: purity
STEP_KW = re.compile(r"^\s*(Given|When|Then|And|But)\b", re.IGNORECASE)
SMELLS = [
    (re.compile(r"\b(querySelector|getElementById|evaluate|addInitScript|dispatchEvent|"
                r"localStorage|sessionStorage|getContext|setContext|newContext|callJsonApi|"
                r"chat_create|showModal|Alpine)\b"), "internal/DOM API name"),
    (re.compile(r"\bx-(data|show|if|text|model|on)\b"), "framework directive"),
    (re.compile(r"(?<![\w.])#[a-zA-Z][\w-]+"), "DOM id selector (#id)"),
    (re.compile(r"(?<![\w])\.[a-z][a-z0-9]*-[a-z0-9-]+"), "CSS class selector (.kebab-class)"),
    (re.compile(r"\[(data-|aria-|class=|id=)"), "attribute selector"),
]
for f in sorted(FEAT_DIR.glob("*.feature")):
    for i, line in enumerate(f.read_text().splitlines(), 1):
        if not STEP_KW.match(line):
            continue
        # Gherkin has no inline comments — a full-line '#' comment never matches a
        # step keyword, so scan the whole step line (don't strip '#', it's a selector).
        text = line
        for rx, why in SMELLS:
            m = rx.search(text)
            if m:
                fail("feature-purity", f"{f.name}:{i}",
                     f"{why} ('{m.group(0)}') in step — behaviour belongs in prose, the 'how' in steps: {line.strip()}")

# --------------------------------------------------------------- Gate 2: honesty
# 2a — every @skip-tagged scenario must carry a reason comment in its body.
for f in sorted(FEAT_DIR.glob("*.feature")):
    lines = f.read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"\s*@skip\b", line):
            # look ahead to the next scenario block for a '#' reason line
            window = "\n".join(lines[i:i + 8])
            if "#" not in "\n".join(lines[i + 1:i + 8]):
                fail("honesty", f"{f.name}:{i+1}",
                     "@skip without a tracked reason — add a '# why + issue/ref' comment in the scenario")

# 2b — no swallowed failures in step files.
if STEP_DIR.exists():
    for f in sorted(STEP_DIR.glob("*.ts")):
        src = f.read_text()
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", line):
                fail("honesty", f"{f.name}:{i}", f"empty catch block swallows a failure: {line.strip()}")
            # a .catch() that neither rethrows nor re-asserts = a silently swallowed failure
            if ".catch(" in line and "throw" not in line and "expect" not in line:
                fail("honesty", f"{f.name}:{i}", f".catch() recovers silently instead of failing: {line.strip()}")

# 2c — the four living docs must exist.
for doc in REQUIRED_DOCS:
    if not (SPEC_DIR / doc).exists():
        fail("honesty", f"docs/spec/{doc}", "required doc missing (the 4-doc model, DEC-060)")

# --------------------------------------------------------- Gate 4: traceability
bspec = SPEC_DIR / "behaviour-spec.md"
efeat = SPEC_DIR / "e2e.feature.md"
if bspec.exists() and efeat.exists():
    beh_defined = set(re.findall(r"\bBEH-\d+\b", bspec.read_text()))
    feat_text = efeat.read_text()
    beh_referenced = set(re.findall(r"\bBEH-\d+\b", feat_text))
    orphans = sorted(beh_defined - beh_referenced, key=lambda b: int(b.split("-")[1]))
    for b in orphans:
        fail("traceability", "docs/spec/e2e.feature.md",
             f"{b} is defined in behaviour-spec.md but neither covered nor tracked-skipped in e2e.feature.md")

# -------------------------------------------------------------------- report out
GATES = ["feature-purity", "honesty", "traceability"]
print(f"[bdd-lint] {ROOT.name}: scanned {len(list(FEAT_DIR.glob('*.feature')))} feature file(s)")
for g in GATES:
    hits = [v for v in violations if v[0] == g]
    print(f"  {'FAIL' if hits else 'PASS'}  gate:{g}  ({len(hits)} issue(s))")
if violations:
    print("\n[bdd-lint] VIOLATIONS:")
    for g, loc, msg in violations:
        print(f"  ✘ [{g}] {loc}\n      {msg}")
    print(f"\n[bdd-lint] {len(violations)} violation(s) — see the standard (devkit SPEC §5.14, DEC-059–066).")
    sys.exit(1)
print("[bdd-lint] ✅ all Tier-1 static gates pass.")
sys.exit(0)
