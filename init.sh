#!/usr/bin/env bash
# One-shot devkit adoption. Run from the plugin repo root, once, right after:
#   git submodule add https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit tests/_testkit
#   bash tests/_testkit/init.sh
#
# Idempotent: safe to re-run (e.g. after a devkit bump) to re-copy root assets.
# What it does: writes the root Makefile (include) + .devkit.yml if absent, copies
# the root-level assets (caller workflows + .gemini), and installs the pre-commit hook.
set -euo pipefail

DEVKIT="tests/_testkit"
[ -d "$DEVKIT/e2e" ] || { echo "✗ $DEVKIT not found — run 'git submodule add <devkit-url> $DEVKIT' first."; exit 1; }

# Infer PLUGIN_DIR + names from the plugin.yaml (root-layout → '.', else usr/plugins/<name>).
PY="$(find . -name plugin.yaml -not -path "./$DEVKIT/*" -not -path './.git/*' 2>/dev/null | head -1)"
if [ -n "$PY" ]; then
  PDIR="$(dirname "$PY")"; PDIR="${PDIR#./}"
  NAME="$(sed -nE 's/^name:[[:space:]]*"?([A-Za-z0-9_-]+)"?.*/\1/p' "$PY" | head -1)"
  DISP="$(sed -nE 's/^title:[[:space:]]*"?([^"]+)"?.*/\1/p' "$PY" | head -1)"
else
  PDIR="."; NAME="my_plugin"; DISP=""
  echo "⚠ no plugin.yaml found — using placeholder PLUGIN_DIR='.'; edit the Makefile after."
fi
[ -n "${DISP:-}" ] || DISP="$NAME"
PROBE="A0_$(printf '%s' "$NAME" | tr '[:lower:]' '[:upper:]')_TEST_PROBE"

# 1. root Makefile
if [ ! -f Makefile ]; then
  cat > Makefile <<MK
PLUGIN_DIR          := $PDIR
PLUGIN_DISPLAY_NAME := $DISP
-include $DEVKIT/e2e/Makefile.devkit
MK
  echo "✓ wrote Makefile (PLUGIN_DIR=$PDIR)"
elif ! grep -q 'Makefile.devkit' Makefile; then
  printf '\n-include %s/e2e/Makefile.devkit\n' "$DEVKIT" >> Makefile
  echo "✓ appended the devkit include to your existing Makefile"
else
  echo "✓ Makefile already includes the devkit"
fi

# 2. .devkit.yml
if [ ! -f .devkit.yml ]; then
  cat > .devkit.yml <<YML
plugin_dir: $PDIR
display_name: $DISP
# If the plugin has agent-driven behaviour needing an e2e seam, enable it here:
# e2e_pod_env:
#   $PROBE: "1"
YML
  echo "✓ wrote .devkit.yml"
fi

# 3. copy the root-level assets + install the hook (the Makefile now resolves the include)
make link-devkit
make install-hooks

cat <<DONE

✅ devkit adopted. Review, then commit:
   git add .gitmodules $DEVKIT Makefile .devkit.yml .github/workflows .gemini
   git commit -m "chore: adopt plugin devkit"

Next:  make verify     # Tier-1 gates locally (fast, no A0)
       make e2e        # full behaviour suite in the devcontainer
To author the behaviour tests, follow the a0-plugin-e2e-bdd skill.
DONE
