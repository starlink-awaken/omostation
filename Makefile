.PHONY: help kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint agent-workflow-lint agent-workflow-doctor agent-workflow-observe agent-workflow-agents agent-workflow-adapters agent-workflow-integrations agent-workflow-bootstrap agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflows project-layer-index domain-m1-alignment toolbox-ssot-check gac-local-gate dir-hygiene governance-release-gate submodule-pointer-transaction governance-check governance-sync governance-validate governance-index-check governance-verify governance-audit governance-dashboard debt-check debt-audit debt-leaderboard governance-data governance-query doc-lint x1-check x2-check x3-check x4-check x1-x4-check install-hooks

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
	@echo "make agent-workflow-bootstrap 一次性输出 agent 启动上下文"
	@echo "make agent-workflows    列出 agent 可执行治理流程"
	@echo "make agent-workflow-agents 列出 agent profile 角色注册表"
	@echo "make agent-workflow-integrations 列出内部治理能力契约"
	@echo "make agent-workflow-adapters 列出外部工具 adapter 契约"
	@echo "make agent-workflow-lint 校验 agent workflow SSOT"
	@echo "make agent-workflow-verify 基于当前 diff 规划 agent 验证"
	@echo "make agent-workflow-compliance 审计 agent workflow 合规闭环"
	@echo "make agent-workflow-closeout RUN_ID=<id> 执行验证并关闭 run"
	@echo "make agent-workflow-doctor 检查 BMAD/OpenSpec/GStack/beads 适配器"
	@echo "make agent-workflow-observe 审计 agent workflow run/lock/ledger"
	@echo "make gac-local-gate     运行 GaC 本地硬门 (含 adapter/MOF/doc/lane checks)"
	@echo "make governance-release-gate 运行发布前远端可达性硬门"
	@echo "make submodule-pointer-transaction 运行子模块指针事务 dry-run"
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
	@echo "make project-layer-index 重新生成项目分层索引 digest"
	@echo "make dir-hygiene         检查根目录卫生 (未追踪未忽略的目录)"
	@echo ""
	@echo "=== 开发环境 ==="
	@echo "make install-hooks       装 git pre-push + pre-commit 钩子 (子模块同步 + GaC/SSOT gate)"
	@echo ""
	@echo "make help                显示本消息"

install-hooks:  ## 装 git pre-push + pre-commit 钩子 (子模块同步 + GaC/SSOT gate). 新 clone 必跑.
	install -m 755 .githooks/pre-push .git/hooks/pre-push
	install -m 755 .githooks/pre-commit .git/hooks/pre-commit
	@echo "✅ 已装 .git/hooks/pre-push (push 时 sync 子模块 + Phase 2a direct-push-to-main advisory 守卫, 防 CI 悬空)"
	@echo "✅ 已装 .git/hooks/pre-commit (commit 时 GaC/SSOT 本地硬门)"

agent-workflows:
	uv run --with pyyaml python bin/agent-workflow.py list

agent-workflow-bootstrap:
	uv run --with pyyaml python bin/agent-workflow.py bootstrap

agent-workflow-lint:
	uv run --with pyyaml python bin/agent-workflow.py lint

agent-workflow-verify:
	uv run --with pyyaml python bin/agent-workflow.py verify --from-diff

agent-workflow-compliance:
	uv run --with pyyaml python bin/agent-workflow.py compliance

agent-workflow-closeout:
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required"; exit 2)
	uv run --with pyyaml python bin/agent-workflow.py closeout "$(RUN_ID)"

agent-workflow-doctor:
	uv run --with pyyaml python bin/agent-workflow.py doctor

agent-workflow-observe:
	uv run --with pyyaml python bin/agent-workflow.py observe

agent-workflow-agents:
	uv run --with pyyaml python bin/agent-workflow.py agents

agent-workflow-integrations:
	uv run --with pyyaml python bin/agent-workflow.py integrations

agent-workflow-adapters:
	uv run --with pyyaml python bin/agent-workflow.py adapters

project-layer-index:
	uv run --with pyyaml python bin/project-layer-index.py --write

domain-m1-alignment:  ## 校验 project-registry.yaml ↔ eCOS M1 domain 节点对齐 (drift 检测)
	uv run --with pyyaml python bin/check-domain-m1-alignment.py

toolbox-ssot-check:  ## 校验 ToolBox docs SSOT 契约 (硬编码值检测)
	uv run --with pyyaml python bin/check-toolbox-ssot.py

gac-local-gate:
	uv run --with pyyaml python bin/gac-local-gate.py
dir-hygiene:  ## 检查根目录卫生 (未追踪未忽略的目录)
	uv run --with pyyaml python bin/dir-hygiene-check.py

governance-release-gate:
	uv run --with pyyaml python bin/submodule-reachability-gate.py --source head --fetch

submodule-pointer-transaction:
	bash bin/submodule-pointer-transaction.sh --dry-run

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
