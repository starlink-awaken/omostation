.PHONY: test lint fmt install clean partition-lint

test:
	uv run pytest tests/ -q --tb=short

lint:
	uv run ruff check src/ecos/ tests/
	uv run python -m ecos.ssot.tools.partition_import_lint

partition-lint:
	uv run python -m ecos.ssot.tools.partition_import_lint

fmt:
	uv run ruff format src/ecos/ tests/

install:
	uv sync

clean:
	rm -rf .pytest_cache/ src/ecos/__pycache__/ tests/__pycache__/
