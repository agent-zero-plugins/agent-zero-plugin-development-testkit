#!/usr/bin/env python3
"""
Build a plugin's visual behaviour documentation from its own e2e run (DEC-077).

WHY THIS EXISTS
    Every green e2e already captures a screenshot per BDD scenario, and each
    scenario is a plain-English statement of a behaviour the plugin guarantees.
    Those two facts together ARE the documentation — but the screenshots were
    only ever uploaded as a CI artifact that expires, and the feature files were
    only read by developers. So every repo either had no screenshots at all
    (chat-comments) or hand-captured ones that silently go stale.

    This joins them: scenario name -> its screenshot -> docs/BEHAVIOUR.md. The
    docs are therefore regenerated from a passing test run, so a screenshot can
    never show a state the plugin no longer produces. If a scenario is deleted
    or renamed, its screenshot disappears from the docs on the next run.

WHAT IT DOES NOT DO
    It does not invent prose. The feature file's Scenario line is the caption,
    verbatim. If that reads badly, fix the feature file — the same text is the
    contract the test asserts.

Usage:
    docs-from-e2e.py --artifacts <dir> --features <dir> --plugin <name>
                     --out docs [--title "Display Name"]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# Playwright's per-scenario dir is flattened into the artifact filename by the
# collector (_artifacts.sh), e.g.
#   chat_comments-tests-e2e-features-10-comm-6bdad-an-be-commented-BEH-5-BEH-8--test-finished-1.png
# The middle is a TRUNCATED, slugified scenario title with a hash — Playwright
# shortens long titles, so an exact match back to the feature file is impossible.
# Match on the longest shared token-suffix instead (see _match_scenario).
SHOT_RE = re.compile(r"^(?P<plugin>.+?)-(?P<slug>.+?)--(?P<kind>[a-z-]+-\d+)\.png$")


def _slug_tokens(text: str) -> list[str]:
    """Lowercase alphanumeric tokens — the common ground between a feature-file
    scenario title and Playwright's slugified, truncated directory name."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def parse_features(features_dir: Path) -> list[dict]:
    """Extract scenarios in file order. Keeps the tag comment (# BEH-5, BEH-8)
    because it is the traceability link back to the spec."""
    scenarios: list[dict] = []
    for feature in sorted(features_dir.glob("*.feature")):
        feature_title = ""
        for raw in feature.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("Feature:"):
                feature_title = line.split(":", 1)[1].strip()
            elif line.startswith("Scenario:"):
                body = line.split(":", 1)[1]
                title, _, comment = body.partition("#")
                # Match on title AND the trailing "# BEH-5, BEH-8" comment:
                # Playwright's directory name is built from the whole Scenario
                # line, so the refs are part of the slug's surviving tail.
                scenarios.append(
                    {
                        "feature": feature_title,
                        "title": title.strip(),
                        "refs": comment.strip(),
                        "tokens": _slug_tokens(f"{title} {comment}"),
                        "shot": None,
                    }
                )
    return scenarios


def _match_scenario(scenarios: list[dict], slug: str) -> dict | None:
    """Playwright truncates the middle of long titles, so the artifact slug is a
    prefix+hash+SUFFIX of the real title. The suffix survives intact, so score on
    the longest matching run of trailing tokens and require at least two — one
    shared token ("chat", "comment") is far too weak across a feature file where
    every scenario mentions the same nouns."""
    slug_tokens = _slug_tokens(slug)
    best, best_score = None, 0
    for sc in scenarios:
        if sc["shot"] or not sc["tokens"]:
            continue
        score = 0
        for a, b in zip(reversed(sc["tokens"]), reversed(slug_tokens)):
            if a != b:
                break
            score += 1
        if score > best_score:
            best, best_score = sc, score
    return best if best_score >= 2 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True, type=Path)
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    title = args.title or args.plugin.replace("_", " ").title()

    if not args.features.is_dir():
        print(f"::warning::no features dir at {args.features} — nothing to document")
        return 0

    scenarios = parse_features(args.features)
    if not scenarios:
        print(f"::warning::no scenarios found in {args.features}")
        return 0

    shots_dir = args.out / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    # Only the final screenshot of each scenario: it shows the asserted end state,
    # which is exactly what the caption claims. Intermediate frames would show
    # states the scenario does not guarantee.
    matched = 0
    for png in sorted(args.artifacts.rglob("*.png")):
        m = SHOT_RE.match(png.name)
        if not m or not m.group("kind").startswith("test-finished"):
            continue
        sc = _match_scenario(scenarios, m.group("slug"))
        if sc is None:
            continue
        dest_name = re.sub(r"[^a-z0-9]+", "-", sc["title"].lower()).strip("-") + ".png"
        shutil.copyfile(png, shots_dir / dest_name)
        sc["shot"] = f"screenshots/{dest_name}"
        matched += 1

    lines = [
        f"# {title} — behaviour",
        "",
        "<!-- GENERATED by the devkit (`make docs`) from this plugin's own e2e run.",
        "     Do not edit by hand: every screenshot below is the asserted end state of a",
        "     passing BDD scenario, so it cannot show behaviour the plugin no longer has.",
        "     Captions are the scenario titles verbatim — reword them in tests/e2e/features/. -->",
        "",
        f"Each section is one scenario from `tests/e2e/features/`, with the screenshot the",
        f"test captured at its final assertion. {matched} of {len(scenarios)} scenarios have one.",
        "",
    ]

    current_feature = None
    for sc in scenarios:
        if sc["feature"] != current_feature:
            current_feature = sc["feature"]
            lines += [f"## {current_feature}", ""]
        lines.append(f"### {sc['title']}")
        if sc["refs"]:
            lines.append(f"<sub>{sc['refs']}</sub>")
        lines.append("")
        if sc["shot"]:
            lines.append(f"![{sc['title']}]({sc['shot']})")
        else:
            # Honest gap rather than a silently missing section.
            lines.append("_No screenshot captured for this scenario in the last run._")
        lines.append("")

    out_file = args.out / "BEHAVIOUR.md"
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[docs-from-e2e] {out_file}: {matched}/{len(scenarios)} scenarios illustrated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
