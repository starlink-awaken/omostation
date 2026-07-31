.PHONY: install test lint clean

# ─── Install ────────────────────────────────────────────────────────────────
install:
	pip install -e .

install-uv:
	uv pip install -e .

# ─── Test ───────────────────────────────────────────────────────────────────
test:
	python3 -m pytest tests/ -v --tb=short

test-all:
	python3 -m pytest tests/ -v

# ─── Lint ───────────────────────────────────────────────────────────────────
lint:
	ruff check src/
	ruff format --check src/

fmt:
	ruff format src/

# ─── Shell Check ────────────────────────────────────────────────────────────
shellcheck:
	shellcheck scripts/*.sh

# ─── Clean ──────────────────────────────────────────────────────────────────
clean:
	rm -rf src/*.egg-info __pycache__ .pytest_cache
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# ─── Runtime State Sync ────────────────────────────────────────────────────
# Sync project scripts → ~/runtime/scripts/
sync-state:
	cp scripts/health-scan.sh $(HOME)/runtime/scripts/
	cp scripts/service-ctl.sh $(HOME)/runtime/scripts/
	cp scripts/matrix.sh $(HOME)/runtime/scripts/
	cp scripts/env.sh $(HOME)/runtime/config/env.sh
	@echo "Runtime state synced"

# ─── Info ───────────────────────────────────────────────────────────────────
info:
	@echo "Runtime Project v0.1.0"
	@echo "  Python CLI:  src/runtime/cli.py"
	@echo "  Shell:       scripts/"
	@echo "  Protocols:   protocols/L0-registry.yaml"
	@echo "  State:       $$RUNTIME_HOME (default: ~/runtime/)"
