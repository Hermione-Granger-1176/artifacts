# ─── Build @build ─────────────────────────────────────────────────────────────

.PHONY: validate thumbnails thumbnails-shard styles index site serve generate new optimize-social-image

# Port for the local static preview server (make serve). Override with PORT=NNNN.
PORT        ?= 8000

validate: ## Check artifact directories are complete
	$(VENV_PYTHON) -c "from scripts.build.generate_index import validate; validate()"

thumbnails: ## Generate missing or stale WebP thumbnails (needs Chromium) (make thumbnails [slug=a,b])
	ARTIFACTS_THUMBNAIL_SLUGS="$(slug)" $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) scripts/build/generate_thumbnails.py

thumbnails-shard: ## Generate thumbnails from one shard manifest (make thumbnails-shard shard_manifest=PATH)
	$(call need,shard_manifest,make thumbnails-shard shard_manifest=.artifacts/shard-manifest.json)
	$(VENV_PYTHON) scripts/ci/app_shards.py invalidate-thumbnails --manifest "$(shard_manifest)"
	ARTIFACTS_THUMBNAIL_SHARD_MANIFEST="$(shard_manifest)" $(PLAYWRIGHT_LOCAL_RUN) $(VENV_PYTHON) scripts/build/generate_thumbnails.py

styles: ## Rebuild css/style.css from ordered source partials
	$(VENV_PYTHON) scripts/build/generate_styles.py

index: ## Rebuild js/data.js, js/gallery-config.js, and the README markers
	$(VENV_PYTHON) scripts/build/generate_index.py

site: styles ## Assemble _site/ deploy payload
	$(VENV_PYTHON) scripts/build/prepare_site.py

serve: index site ## Build the packaged site and serve it locally (make serve [PORT=8000])
	@printf '\n  Serving _site/ at \033[1mhttp://localhost:%s/\033[0m  (Ctrl-C to stop)\n\n' "$(PORT)"
	$(PYTHON) -m http.server $(PORT) --directory _site --bind 127.0.0.1

generate: styles thumbnails index ## Rebuild all canonical generated assets

new: ## Scaffold a new artifact directory (make new name=X [src=file.html])
	$(call need,name,make new name=my-artifact [src=file.html])
	$(VENV_PYTHON) scripts/build/scaffold_artifact.py "$(name)" $(if $(src),--from-html "$(src)")

optimize-social-image: ## Recompress the Open Graph share image in place (make optimize-social-image [path=FILE])
	$(VENV_PYTHON) scripts/build/optimize_social_image.py $(if $(path),"$(path)")
