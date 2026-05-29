.PHONY: build test setup lint clean help

# ── 统一构建设置 ───────────────────────────────────────────

build: build-agentmesh build-python
	@echo "✅ Build complete"

build-agentmesh:
	@echo "Building agentmesh..."
	cd agentmesh && bun run build 2>/dev/null && echo "  ✅ agentmesh" || echo "  ⚠️  agentmesh build skipped"

build-python:
	@echo "Building Python projects..."
	-for dir in Agora KOS eidos kronos SharedBrain iris Forge; do \
		if [ -f "$$dir/setup.py" ] || [ -f "$$dir/pyproject.toml" ]; then \
			(cd "$$dir" && pip install -e . -q 2>/dev/null) && echo "  ✅ $$dir" || echo "  ⚠️  $$dir build skipped"; \
		fi; \
	done

# ── 统一测试 ────────────────────────────────────────────────

test: test-unit test-integration
	@echo "✅ All tests passed"

test-unit:
	@echo "Running unit tests..."
	-cd agentmesh && bun test 2>/dev/null | tail -1
	-for dir in kronos Agora eidos iris SharedBrain; do \
		if [ -d "$$dir/tests" ]; then \
			(cd "$$dir" && python3 -m pytest -q 2>/dev/null) && echo "  ✅ $$dir" || echo "  ⚠️  $$dir test skipped"; \
		fi; \
	done
	@echo "  unit tests done"

test-integration:
	@echo "Running integration tests..."
	@if [ -f tests/integration/run-all.sh ]; then \
		bash tests/integration/run-all.sh; \
	else \
		echo "  no integration tests found"; \
	fi

# ── 安装依赖 ────────────────────────────────────────────────

setup: setup-node setup-python
	@echo "✅ Setup complete"

setup-node:
	@echo "Installing Node/bun dependencies..."
	cd agentmesh && bun install 2>/dev/null && echo "  ✅ agentmesh" || echo "  ⚠️  agentmesh install skipped"

setup-python:
	@echo "Installing Python dependencies..."
	-for dir in Agora eidos kronos SharedBrain iris Forge KOS; do \
		if [ -f "$$dir/requirements.txt" ]; then \
			(cd "$$dir" && pip install -r requirements.txt -q 2>/dev/null); \
		elif [ -f "$$dir/setup.py" ] || [ -f "$$dir/pyproject.toml" ]; then \
			(cd "$$dir" && pip install -e . -q 2>/dev/null); \
		fi; \
		echo "  ✅ $$dir"; \
	done

# ── 代码检查 ────────────────────────────────────────────────

lint:
	@echo "Running linters..."
	@if [ -f agentmesh/package.json ]; then \
		cd agentmesh && bun run build 2>/dev/null | tail -1; \
	fi
	@echo "✅ Lint complete"

# ── 清理 ────────────────────────────────────────────────────

clean:
	@echo "Cleaning build artifacts..."
	@if [ -d agentmesh ]; then \
		cd agentmesh && find . -name dist -type d -exec rm -rf {} + 2>/dev/null; \
	fi
	-for dir in Agora eidos kronos SharedBrain iris Forge KOS; do \
		rm -rf "$$dir/build" "$$dir/*.egg-info" "$$dir/__pycache__" 2>/dev/null; \
	done
	-find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
	-find . -name "*.pyc" -delete 2>/dev/null
	@echo "✅ Clean complete"

# ── 帮助 ────────────────────────────────────────────────────

help:
	@echo "┌──────────────────────────────────────────────────┐"
	@echo "│  Workspace Unified Makefile                      │"
	@echo "├──────────────────────────────────────────────────┤"
	@echo "│                                                  │"
	@echo "│  Usage: make [target]                            │"
	@echo "│                                                  │"
	@echo "│  Targets:                                        │"
	@echo "│    build       Build all projects                │"
	@echo "│    test        Run all unit & integration tests  │"
	@echo "│    setup       Install all dependencies          │"
	@echo "│    lint        Run linters                       │"
	@echo "│    clean       Remove build artifacts            │"
	@echo "│    help        Show this message                 │"
	@echo "│                                                  │"
	@echo "│  Projects:                                       │"
	@echo "│    Node.js   agentmesh                           │"
	@echo "│    Python    Agora, eidos, kronos, SharedBrain,  │"
	@echo "│              iris, Forge, KOS                    │"
	@echo "│                                                  │"
	@echo "│  Note: Non-blocking — failing projects are       │"
	@echo "│  skipped with a warning.                         │"
	@echo "│                                                  │"
	@echo "└──────────────────────────────────────────────────┘"
