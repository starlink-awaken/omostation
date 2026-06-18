.PHONY: help kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint governance-check governance-sync governance-validate governance-index-check governance-verify governance-audit debt-check doc-lint x1-check x2-check x3-check x4-check x1-x4-check install-hooks

help:
	@echo "Workspace 根 Makefile — 委派到 projects/"
	@echo ""
	@echo "=== 测试 ==="
	@echo "make kairon-test       运行 kairon 全部测试"
	@echo "make kairon-test-fast  运行 kairon 单元测试 (跳过集成/基准)"
	@echo "make kairon-test-diff  运行 kairon 差异测试 (仅修改的包)"
	@echo "make kairon-test-e2e   运行 kairon E2E 测试 (Postgres+gbrian+kairon 容器化)"
	@echo "make kairon-lint       ruff 检查所有包"
	@echo "make kairon-build      安装 kairon 依赖 (uv sync)"
	@echo ""
	@echo "=== 治理 ==="
	@echo "make governance-verify   运行 canonical .omo 验证链"
	@echo "make governance-check    全量治理检查 (verify → index)"
	@echo "make governance-audit    全量治理审计 (债务+文档+健康度)"
	@echo "make governance-sync     同步 .omo/state/system.yaml"
	@echo "make governance-validate 验证任务 Schema"
	@echo "make governance-index-check 检查 INDEX.md 覆盖率"
	@echo ""
	@echo "=== X1-X4 治理框架 ==="
	@echo "make x1-check           X1 审计链检查"
	@echo "make x2-check           X2 抗熵检查"
	@echo "make x3-check           X3 价值栈检查"
	@echo "make x4-check           X4 一致性检查"
	@echo "make x1-x4-check        X1-X4 全维度检查"
	@echo ""
	@echo "=== 债务 ==="
	@echo "make debt-check          检查债务状态"
	@echo "make debt-audit          定期债务审计"
	@echo "make debt-leaderboard    债务排行榜"
	@echo ""
	@echo "=== 可视化 ==="
	@echo "make governance-dashboard 生成 HTML 报告"
	@echo "make governance-data      生成 JSON 数据"
	@echo "make governance-query     查询治理数据"
	@echo ""
	@echo "=== 文档 ==="
	@echo "make doc-lint            检查文档格式"
	@echo ""
	@echo "=== 开发环境 ==="
	@echo "make install-hooks       装 git pre-push 钩子 (子模块自动同步, 防 CI 悬空)"
	@echo ""
	@echo "make help                显示本消息"

install-hooks:  ## 装 git pre-push 钩子 (主仓 push 时自动 sync 子模块, 防 CI 悬空). 新 clone 必跑.
	install -m 755 .githooks/pre-push .git/hooks/pre-push
	@echo "✅ 已装 .git/hooks/pre-push (主仓 push 时自动 sync 子模块, 防 CI 悬空)"

kairon-test:
	cd projects/kairon && make test

kairon-test-fast:
	cd projects/kairon && make test-fast

kairon-test-diff:
	cd projects/kairon && make test-diff

kairon-test-e2e:
	cd projects/kairon && make test-e2e

kairon-lint:
	cd projects/kairon && ruff check packages/

kairon-build:
	cd projects/kairon && uv sync

governance-verify:
	bash bin/verify-omo.sh

governance-check: governance-verify governance-index-check
	@echo "Governance checks complete."

governance-sync:
	python3 scripts/sync_omo_state.py --omo-dir .omo

governance-validate:
	python3 scripts/omo_task_schema.py --all-active

governance-index-check:
	python3 scripts/check-index-coverage.py

# ── 治理审计 ────────────────────────────────────────────────────────────────────

governance-audit: governance-check debt-check doc-lint
	@echo "=== 治理审计完成 ==="

# ── 债务检查 ────────────────────────────────────────────────────────────────────

debt-check:
	@echo "=== 债务状态检查 ==="
	@echo ""
	@echo "--- debt_weight ---"
	@grep "debt_weight:" .omo/state/system.yaml | head -1
	@echo ""
	@echo "--- debt_health ---"
	@grep "debt_health:" .omo/state/system.yaml | head -1
	@echo ""
	@echo "--- resolved_count ---"
	@grep "resolved_count:" .omo/state/system.yaml | head -1
	@echo ""
	@echo "--- unresolved_count ---"
	@grep "unresolved_count:" .omo/state/system.yaml | head -1
	@echo ""
	@echo "=== 债务检查完成 ==="

# ── 文档检查 ────────────────────────────────────────────────────────────────────

doc-lint:
	@echo "=== 文档格式检查 ==="
	@echo ""
	@echo "--- 检查文档版本信息 ---"
	@for f in AGENTS.md CLAUDE.md .omo/_knowledge/governance/README.md; do \
		if [ -f "$$f" ]; then \
			if grep -q "最后更新" "$$f" 2>/dev/null; then \
				echo "  ✓ $$f — 有版本信息"; \
			else \
				echo "  ⚠️  $$f — 缺少版本信息"; \
			fi; \
		fi; \
	done
	@echo ""
	@echo "=== 文档检查完成 ==="

# ── 治理仪表板 ──────────────────────────────────────────────────────────────────

governance-dashboard:
	python3 scripts/generate-governance-dashboard.py -o governance-report.html
	@echo "打开: open governance-report.html"

# ── 债务审计 ────────────────────────────────────────────────────────────────────

debt-audit:
	bash scripts/debt-audit.sh

# ── 治理数据 ────────────────────────────────────────────────────────────────────

governance-data:
	python3 scripts/generate-governance-data.py

# ── 债务排行榜 ──────────────────────────────────────────────────────────────────

debt-leaderboard:
	bash scripts/debt-leaderboard.sh

# ── 治理查询 ────────────────────────────────────────────────────────────────────

governance-query:
	python3 scripts/governance-query.py all

# ── X1-X4 治理框架 ─────────────────────────────────────────────────────────────

x1-check:
	bash scripts/x1-audit-check.sh

x2-check:
	bash scripts/x2-staleness-check.sh

x3-check:
	bash scripts/x3-value-check.sh

x4-check:
	bash scripts/x4-consistency-check.sh

x1-x4-check:
	bash scripts/x1-x4-check.sh
