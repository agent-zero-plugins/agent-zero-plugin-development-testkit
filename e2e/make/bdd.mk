# Devkit BDD verification targets (DEC-066) — local, pre-commit-friendly.
#
# These ride along with the standard fragment: `-include tests/_testkit/e2e/Makefile.devkit`
# already `-include`s this file, so a plugin that follows the standard gets `make verify`
# for free. (You CAN include it directly for the lint alone, with no A0 targets.)
#
# No Makefile at all? run the lint directly:
#     python3 tests/_testkit/e2e/lint/bdd_lint.py .
#
# `make verify` is the one to run BEFORE EVERY COMMIT: Tier-1 static gates
# (feature-purity, honesty, traceability) — fast, no A0 boot, the same gates CI
# hard-fails on. `make e2e` (from Makefile.devkit) runs the full behaviour suite.

DEVKIT_DIR ?= tests/_testkit
PLUGIN_DIR ?= .

.PHONY: verify bdd-lint bdd-e2e install-hooks

verify: bdd-lint ## Pre-commit verification — the Tier-1 static gates (fast, no A0)

bdd-lint: ## Behaviour-BDD honesty/purity/traceability gates (requires BDD tests — hard-fails if none)
	@python3 "$(DEVKIT_DIR)/e2e/lint/bdd_lint.py" .

bdd-e2e: ## Full local BDD run — alias for `make e2e` (auto-selects the run-bdd harness)
	@$(MAKE) e2e 2>/dev/null || { \
	  echo "Run the full behaviour suite via 'make e2e' (needs Makefile.devkit)."; \
	  echo "See $(DEVKIT_DIR)/docs/BDD-GATES.md + the a0-plugin-e2e-bdd skill."; }

install-hooks: ## Install the git pre-commit hook that runs 'make verify'
	@cp "$(DEVKIT_DIR)/templates/pre-commit" .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
	@echo "installed .git/hooks/pre-commit → runs 'make verify' before each commit"
