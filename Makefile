.PHONY: test lint fmt install clean

test:
	uv run pytest tests/ -q --tb=short

lint:
	uv run ruff check src/omo/ tests/

fmt:
	uv run ruff format src/omo/ tests/

install:
	uv sync

clean:
	rm -rf .pytest_cache/ src/omo/__pycache__/ tests/__pycache__/
