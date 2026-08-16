.PHONY: test lint install clean typecheck typecheck-report typecheck-gate typecheck-gate-update

# Install all packages in monorepo
install:
	uv sync

# Run tests on all packages/* — per-package, non-blocking
test:
	@echo "=== 运行所有包测试 ==="; \
	fail=0; \
	for pkg in packages/*/; do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if ! (cd $$pkg && uv run python -m pytest tests/ -q); then \
			fail=1; \
		fi; \
	done; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Fast: unit tests only (skip integration/benchmarks)
test-fast:
	@echo "=== 快速测试（仅 unit）==="; \
	fail=0; \
	for pkg in packages/*/; do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if [ -d "$$pkg/tests" ]; then \
			if ! (cd $$pkg && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks); then \
				fail=1; \
			fi; \
		else \
			echo "  ⏭️ 跳过"; \
		fi; \
	done; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Fast: unit tests only for changed packages (git diff)
test-diff:
	@echo "=== 差异测试（仅修改的包）==="; \
	fail=0; \
	for pkg in $$(git diff --name-only HEAD 2>/dev/null | grep "^packages/" | cut -d/ -f1-2 | sort -u); do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if [ -d "$$pkg/tests" ]; then \
			if ! (cd $$pkg && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks 2>/dev/null); then \
				fail=1; \
			fi; \
		else \
			echo "  ⏭️ 跳过"; \
		fi; \
	done; \
	if [ $$fail -eq 0 ] && [ -z "$${pkg:-}" ]; then \
		echo "  ⏭️  无修改的包"; \
	fi; \
	echo "=== 全部完成 ==="; \
	test $$fail -eq 0

# Parallel: unit tests on all packages simultaneously (max 4 jobs)
test-parallel:
	@echo "=== 并行测试（最多 4 并发）==="; \
	pkgs=""; \
	for pkg in packages/*/; do \
		if [ -d "$$pkg/tests" ]; then \
			pkgs="$$pkgs $$(basename $$pkg)"; \
		fi; \
	done; \
	echo "Packages: $$pkgs"; \
	echo "$$pkgs" | tr ' ' '\n' | xargs -P4 -I{} sh -c ' \
		echo "--- [{}] ---"; \
		cd packages/{} && uv run python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/benchmarks 2>&1 || echo "FAILED: {}"; \
	'

# Lint all packages with ruff
lint:
	ruff check packages/

# Format all packages with ruff
format:
	ruff format packages/

# Typecheck all packages with mypy strict (DEBT-CI-MYPY-STRICT).
# 真相调法 MYPYPATH=src: 修旧 `mypy src` 假绿 (mypy 解析不出跨包 import 当 Any 静默通过,
# 仅 minerva/sophia 撞模块映射冲突才报错). 真实存量 1245 errors (见 mypy-baseline.yaml),
# 故此 target 现会红 — CI 用 typecheck-gate 卡增量, 开发用此 target 看真错误.
typecheck:
	@echo "=== mypy strict 真相检查 (MYPYPATH=src) ==="; \
	fail=0; \
	for pkg in packages/*/; do \
		name=$$(basename $$pkg); \
		echo "--- [$$name] ---"; \
		if ! (cd $$pkg && MYPYPATH=src uv run mypy src --namespace-packages --explicit-package-bases --exclude tests/); then \
			fail=1; \
		fi; \
	done; \
	test $$fail -eq 0

# Typecheck report: per-package mypy error count (真相调法, 服务推进诊断)
typecheck-report:
	@uv run python scripts/mypy_report.py

# Typecheck regression gate: 卡增量不卡存量 (CI 友好, baseline 见 mypy-baseline.yaml)
typecheck-gate:
	@uv run --with pyyaml python scripts/mypy_report.py --baseline mypy-baseline.yaml

# 刷新 baseline (修了真错误后降数; mypy 版本漂移误报时同样刷新)
typecheck-gate-update:
	@uv run python scripts/mypy_report.py --baseline mypy-baseline.yaml --update

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv/

# E2E: 容器化集成测试 (Postgres + gbrain + kairon)
test-e2e:
	@echo "=== E2E 容器化测试 ==="
	cd docker && docker compose up --build --abort-on-container-exit --exit-code-from kairon-test
	cd docker && docker compose down -v
	@echo "=== E2E 完成 ==="

# E2E: 仅启动环境 (不运行测试)
e2e-up:
	cd docker && docker compose up -d --build
	@echo "E2E 环境已启动: postgres:5433, gbrain:3000"

# E2E: 停止环境
e2e-down:
	cd docker && docker compose down -v
