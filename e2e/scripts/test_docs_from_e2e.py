#!/usr/bin/env python3
"""Self-check for docs-from-e2e.py. Run directly: `python3 test_docs_from_e2e.py`.

The one thing worth testing here is the scenario<->screenshot match, because
Playwright TRUNCATES long scenario titles in its directory names and inserts a
hash. A naive exact match silently produces a document where every scenario says
"no screenshot captured" — which is exactly what the first version of this script
did, and it looked like a plausible empty result rather than a bug.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "docs-from-e2e.py"

FEATURE = """\
Feature: Commenting on a chat

  Scenario: The comments control is present            # BEH-1, UI-1
    Given I am in a chat

  Scenario: A comment can be attached to selected message text   # BEH-5, BEH-7, BEH-8
    Given I am in a chat

  Scenario: A comment can be deleted                   # BEH-10
    Given I am in a chat

  Scenario: This one never ran                         # BEH-99
    Given I am in a chat
"""

# Real artifact names from run 30866557253 — note the truncated middles and the
# 5-hex-char hash Playwright inserts.
SHOTS = [
    "chat_comments-tests-e2e-features-10-comm-0c7ed-ntrol-is-present-BEH-1-UI-1--test-finished-1.png",
    "chat_comments-tests-e2e-features-10-comm-a57f8-sage-text-BEH-5-BEH-7-BEH-8--test-finished-1.png",
    "chat_comments-tests-e2e-features-10-comm-f5b9e-mment-can-be-deleted-BEH-10--test-finished-1.png",
    # A video must never be picked up as a screenshot.
    "chat_comments-tests-e2e-features-10-comm-0c7ed-ntrol-is-present-BEH-1-UI-1--video.webm",
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "features").mkdir()
        (root / "features" / "10-comments.feature").write_text(FEATURE)
        (root / "artifacts").mkdir()
        for name in SHOTS:
            (root / "artifacts" / name).write_bytes(b"\x89PNG fake")

        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--artifacts", str(root / "artifacts"),
             "--features", str(root / "features"), "--plugin", "chat_comments",
             "--out", str(root / "docs")],
            capture_output=True, text=True, check=True,
        )
        print(out.stdout.strip())

        doc = (root / "docs" / "BEHAVIOUR.md").read_text()
        shots = sorted(p.name for p in (root / "docs" / "screenshots").glob("*"))

        assert "3 of 4 scenarios have one" in doc, doc[:400]
        assert shots == [
            "a-comment-can-be-attached-to-selected-message-text.png",
            "a-comment-can-be-deleted.png",
            "the-comments-control-is-present.png",
        ], shots
        # The scenario with no run must say so rather than be omitted.
        assert "### This one never ran" in doc
        assert "_No screenshot captured" in doc
        # Traceability refs survive into the doc.
        assert "<sub>BEH-5, BEH-7, BEH-8</sub>" in doc
        # A one-token overlap must NOT match (every scenario says "comment").
        assert "a-comment-can-be-attached" in " ".join(shots)

    print("PASS: truncated Playwright slugs matched back to their scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
