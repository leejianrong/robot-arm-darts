.DEFAULT_GOAL := help
.PHONY: help assets install lint typecheck test test-all check hooks

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

assets: ## Fetch the pinned Menagerie SO-101 model (Apache-2.0)
	@test -d assets/menagerie/robotstudio_so101 || { \
	  git clone -q --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie.git assets/menagerie && \
	  git -C assets/menagerie sparse-checkout set robotstudio_so101 && \
	  git -C assets/menagerie checkout -q 98a70c569c4c1b6da467a20012f766ee1f8dc521; }

install: ## Frozen install
	uv sync --frozen

lint: ## Ruff lint + format check
	uv run ruff check . && uv run ruff format --check .

typecheck: ## Pyright on src/
	uv run pyright

test: ## Fast layer: no assets, no heavy sim
	uv run pytest -m "not integration"

test-all: ## Fast + integration layers
	uv run pytest

check: lint typecheck test ## Pre-push gate (mirrors cheap CI jobs)

hooks: ## Install the pre-push hook
	git config core.hooksPath .githooks
