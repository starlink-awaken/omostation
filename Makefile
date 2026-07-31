.PHONY: test lint fmt install clean

test:
	uv run pytest src/cockpit/tests/ tests/ -q --tb=short

lint:
	uv run ruff check src/cockpit/ tests/

fmt:
	uv run ruff format src/cockpit/ tests/

install:
	uv sync

clean:
	rm -rf .pytest_cache/ src/cockpit/__pycache__/ tests/__pycache__/
