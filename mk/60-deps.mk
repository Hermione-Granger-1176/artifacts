# ─── Dependencies @deps ───────────────────────────────────────────────────────

.PHONY: lock lock-update lock-node lock-node-update refresh-ci-pins fix-deps audit-fix-node refresh-action-shas

lock: ## Refresh uv.lock after Python dependency changes
	$(UV) lock

lock-update: ## Upgrade selected Python packages in uv.lock (packages="package ...")
	$(call need,packages,make lock-update packages="package ...")
	$(UV) lock $(foreach pkg,$(packages),--upgrade-package "$(pkg)")

lock-node: ## Refresh package-lock.json after Node dependency changes
	$(NPM) install --package-lock-only

lock-node-update: ## Update selected Node packages in the lockfile (packages="package ...")
	$(call need,packages,make lock-node-update packages="package ...")
	$(NPM) update --package-lock-only $(foreach pkg,$(packages),"$(pkg)")

refresh-ci-pins: ## Refresh the Playwright package, uv lock, and pinned CI image
	$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/refresh_ci_pins.py upgrade-project
	$(MAKE) lock
	$(PY_PATH_PREFIX) $(PYTHON) scripts/ci/refresh_ci_pins.py refresh-image

fix-deps: ## Refresh locks, reinstall, and npm audit fix
	$(MAKE) lock
	$(MAKE) lock-node
	$(MAKE) install
	$(MAKE) node-install
	$(MAKE) audit-fix-node

audit-fix-node: ## Apply available npm audit fixes to package-lock.json
	$(NPM) audit fix --package-lock-only

refresh-action-shas: ## Repin tag-based GitHub Actions refs to commit SHAs (needs GH_TOKEN)
	$(PY_PATH_PREFIX) $(PYTHON) -m scripts.ci.refresh_action_shas
