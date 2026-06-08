.PHONY: test lint fmt install clean

test:
	uv run pytest tests/ -q --tb=short

lint:
	uv run ruff check src/ecos/ tests/

fmt:
	uv run ruff format src/ecos/ tests/

install:
	uv sync

clean:
	rm -rf .pytest_cache/ src/ecos/__pycache__/ tests/__pycache__/
