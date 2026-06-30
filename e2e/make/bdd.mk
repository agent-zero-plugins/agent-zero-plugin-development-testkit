# Devkit BDD verification targets (DEC-066) — local, pre-commit-friendly.
#
# A plugin wires these by adding to its Makefile:
#     DEVKIT ?= tests/_testkit
#     include $(DEVKIT)/e2e/make/bdd.mk
#
# Or, with no Makefile at all, run the lint directly:
#     python3 tests/_testkit/e2e/lint/bdd_lint.py .
#
# `make verify` is the one to run BEFORE EVERY COMMIT: it runs the Tier-1 static
# gates (feature-purity, honesty, traceability) — fast, no A0 boot, the same gates
# CI hard-fails on. `make bdd-e2e` runs the full behaviour suite (lint → seam-off
# red-proof → e2e) against a disposable A0 — the local fast loop, heavier.

DEVKIT      ?= tests/_testkit
PLUGIN_ROOT ?= .

.PHONY: verify bdd-lint bdd-e2e install-hooks

verify: bdd-lint ## Pre-commit verification — the Tier-1 static gates (fast, no A0)

bdd-lint: ## Behaviour-BDD honesty/purity/traceability gates (self-skips non-BDD plugins)
	@python3 "$(DEVKIT)/e2e/lint/bdd_lint.py" "$(PLUGIN_ROOT)"

bdd-e2e: ## Full local BDD run (lint + seam-off red-proof + e2e) on a disposable A0
	@echo "Run the full behaviour suite on a disposable A0 (never the operator's live instance)."
	@echo "See $(DEVKIT)/docs/BDD-GATES.md + the a0-plugin-e2e-bdd skill for the local loop, then"
	@echo "inside the devcontainer:  bash $(DEVKIT)/e2e/harness/run-bdd.sh"

install-hooks: ## Install the git pre-commit hook that runs 'make verify'
	@cp "$(DEVKIT)/templates/pre-commit" .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
	@echo "installed .git/hooks/pre-commit → runs 'make verify' before each commit"
