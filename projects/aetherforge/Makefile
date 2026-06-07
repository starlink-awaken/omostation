.PHONY: install sync clean lint test run-mcp run-gateway run-mesh

# ── Setup ────────────────────────────────────────────────────────────

install:  ## Install all workspace packages (editable)
	uv sync

sync:     ## Sync lockfile
	uv lock

clean:    ## Clean build artifacts
	rm -rf dist/ .eggs/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

# ── Development ──────────────────────────────────────────────────────

.PHONY: lint
lint:     ## Run ruff linter
	uv run ruff check packages/ src/

.PHONY: format
format:   ## Run ruff formatter
	uv run ruff format packages/ src/

.PHONY: test
test:     ## Run pytest
	uv run pytest

# ── Run ──────────────────────────────────────────────────────────────

run-mcp:  ## Start unified MCP server (stdio)
	uv run aetherforge-mcp

run-gateway: ## Start gateway CLI
	uv run aetherforge gateway list

run-mesh: ## Start mesh CLI
	uv run aetherforge mesh list

# ── Docker ───────────────────────────────────────────────────────────

docker-build: ## Build Docker image
	docker compose build

docker-up:    ## Start Docker services
	docker compose up -d

docker-down:  ## Stop Docker services
	docker compose down

docker-logs:  ## View Docker logs
	docker compose logs -f

# ── Info ─────────────────────────────────────────────────────────────

.PHONY: info
info:     ## Show workspace status
	@echo "AetherForge — $(shell uv run python3 -c 'import aetherforge; print(aetherforge.__version__)')"
	@echo "Packages:"
	@ls -1 packages/
	@echo ""
	@uv run aetherforge gateway list 2>/dev/null || echo "(gateway providers not available)"
	@echo ""
	@uv run aetherforge mesh status 2>/dev/null || echo "(mesh not available)"

# ── Help ─────────────────────────────────────────────────────────────

help:     ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
