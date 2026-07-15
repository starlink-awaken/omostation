.PHONY: help ci-local ci-local-fast kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint agent-workflow-lint agent-workflow-doctor agent-workflow-observe agent-workflow-agents agent-workflow-adapters agent-workflow-integrations agent-workflow-bootstrap agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflows project-layer-index domain-m1-alignment toolbox-ssot-check gac-local-gate dir-hygiene governance-release-gate submodule-pointer-transaction governance-check governance-sync governance-validate governance-index-check governance-verify governance-audit governance-dashboard debt-check debt-audit debt-leaderboard governance-data governance-query doc-lint x1-check x2-check x3-check x4-check x1-x4-check install-hooks

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
	@echo "=== 架构检查 ==="
	@echo "make check-layers      分层依赖检查 (docs/layer-contract.yaml)"
	@echo "make ssot-status       SSOT 变更状态检查"
	@echo "make ssot-log          SSOT 审计日志查看"
	@echo "make ssot-sync         SSOT 变更记录到审计日志"
	@echo "make sync-submodules   推送子模块未推送的 commit 到远程"
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
	@echo "=== 本地 CI ==="
	@echo "make ci-local            本地 CI 预检 (push 前跑, ~30s, 拦 90% CI 失败)"
	@echo "make ci-local-fast       快速模式 (跳 pytest, ~5s, 仅 governance+lint+yaml)"
	@echo ""
	@echo "make help                显示本消息"

install-hooks:  ## 装 git pre-push + pre-commit + post-commit + prepare-commit-msg 钩子. 新 clone 必跑.
	install -m 755 .githooks/pre-push .git/hooks/pre-push
	install -m 755 .githooks/pre-commit .git/hooks/pre-commit
	install -m 755 .githooks/post-commit .git/hooks/post-commit
	install -m 755 .githooks/prepare-commit-msg-commit-assist .git/hooks/prepare-commit-msg-commit-assist
	@echo "✅ 已装主仓 .git/hooks/pre-push"
	@echo "✅ 已装主仓 .git/hooks/pre-commit"
	@echo "✅ 已装主仓 .git/hooks/post-commit"
	@echo "✅ 已装主仓 .git/hooks/prepare-commit-msg-commit-assist (LLM advisory 写 .commit-suggestion, P76 Phase 9A)"
	@# 遍历 projects/* 子模块，查找实际 hooks 路径并配置软链接实现统一治理
	@for d in projects/*; do \
		if [ -d "$$d" ] && [ -e "$$d/.git" ]; then \
			( \
				cd "$$d" && \
				sub_root=$$(pwd) && \
				hook_dir=$$(git rev-parse --git-path hooks 2>/dev/null || echo ""); \
				if [ -n "$$hook_dir" ]; then \
					abs_hook_dir=$$(python3 -c "import os; print(os.path.abspath('$$hook_dir'))"); \
					mkdir -p "$$abs_hook_dir"; \
					ln -sf "$(CURDIR)/.githooks/pre-commit" "$$abs_hook_dir/pre-commit"; \
					echo "🔗 已绑定子模块 $$d 治理 pre-commit 软链 -> $$abs_hook_dir/pre-commit"; \
					hook_file=$$(python3 -c "import os,sys; print(os.path.relpath(os.path.join(sys.argv[1], 'pre-commit'), sys.argv[2]))" "$$abs_hook_dir" "$$sub_root") || hook_file=""; \
					if [ -n "$$hook_file" ] && git ls-files --error-unmatch "$$hook_file" >/dev/null 2>&1; then \
						git update-index --skip-worktree "$$hook_file" 2>/dev/null || true; \
						echo "   ↪ skip-worktree $$hook_file (F-12 修, 防 type change T 残留)"; \
					fi; \
				fi \
			) \
		fi; \
	done

# ── 本地 CI 预检 ────────────────────────────────────────────────────────────────
# 目的: push 前本地跑一遍 CI 等价检查, 拦 90% CI 失败, 省等 CI 的时间.
# 分两档:
#   ci-local-fast  (~5s)  — GaC gate + ruff + YAML 语法 (无 pytest)
#   ci-local       (~30s) — 上述 + omo pytest + integration tests
# 嵌入点: pre-push hook (见 .githooks/pre-push)

ci-local: ci-local-fast
	@echo ""; \
	echo "── pytest (omo unit tests) ──────────────────────────"; \
	(cd projects/omo && uv run pytest tests/ -q --tb=short 2>&1) | sed 's/^/[pytest] /'; \
	pytest_rc=$${PIPESTATUS[0]}; \
	echo ""; \
	echo "── integration tests ────────────────────────────────"; \
	bash tests/integration/run-all.sh 2>&1 | sed 's/^/[integration] /'; \
	integration_rc=$${PIPESTATUS[0]}; \
	echo ""; \
	if [ "$$pytest_rc" != "0" ] || [ "$$integration_rc" != "0" ]; then \
		echo "❌ ci-local: 有检查未通过 (pytest=$$pytest_rc, integration=$$integration_rc)"; \
		exit 1; \
	else \
		echo "✅ ci-local: 全部通过"; \
	fi

ci-local-fast: check-layers
	@echo "════════════════════════════════════════════════════"
	@echo "  ci-local-fast — 本地 CI 预检 (快速模式, ~5s)"
	@echo "════════════════════════════════════════════════════"
	@CI_LOCAL_FAIL=0; \
	echo "── GaC local gate ───────────────────────────────────"; \
	uv run --with pyyaml python bin/gac/gac-local-gate.py 2>&1 | sed 's/^/[gac] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	echo "── dir-hygiene ──────────────────────────────────────"; \
	uv run --with pyyaml python bin/ssot/dir-hygiene-check.py 2>&1 | sed 's/^/[hygiene] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	echo "── ruff check (omo + scripts) ──────────────────────"; \
	ruff check projects/omo/src scripts --ignore F401,F821,E402,E722 2>&1 | sed 's/^/[ruff] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	echo "── HTML entity 编码检查 (Python/YAML) ──────────────"; \
	if grep -rn '&[gl]t;' projects/ --include='*.py' --include='*.yaml' --include='*.yml' 2>/dev/null; then \
		echo "❌ 发现 HTML 实体编码泄漏 (&gt; / &lt;)，请替换为 > / <"; \
		CI_LOCAL_FAIL=1; \
	else \
		echo "✅ 未发现 HTML 实体编码泄漏"; \
	fi; \
	echo ""; \
	echo "── YAML 语法校验 (workflows + protocols) ───────────"; \
	uv run --with pyyaml python3 bin/ssot/yaml-validate.py 2>&1 | sed 's/^/[yaml] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	if [ "$$CI_LOCAL_FAIL" = "1" ]; then \
		echo "❌ ci-local-fast: 有检查未通过"; \
		exit 1; \
	else \
		echo "✅ ci-local-fast: 全部通过 (~5s)"; \
	fi

check-layers:
	@echo "── 分层依赖检查 ─────────────────────────────────────"
	uv run --with pyyaml python bin/layer-dependency-check.py

ssot-status:  ## SSOT 变更状态检查
	@echo "── SSOT 状态 ────────────────────────────────────────"
	uv run --with pyyaml python bin/ssot-watcher.py status

ssot-log:  ## SSOT 审计日志查看
	@echo "── SSOT 审计日志 ────────────────────────────────────"
	uv run --with pyyaml python bin/ssot-watcher.py log --limit 20

ssot-sync:  ## SSOT 变更记录到审计日志
	@echo "── SSOT 同步 ────────────────────────────────────────"
	@read -p "Author: " author; \
	read -p "Reason: " reason; \
	uv run --with pyyaml python bin/ssot-watcher.py sync --author "$$author" --reason "$$reason"

sync-submodules:  ## 推送子模块未推送的 commit 到远程
	@echo "── 同步子模块 ────────────────────────────────────────"
	bash bin/sync-submodules.sh

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
	uv run --with pyyaml python bin/mof/project-layer-index.py --write

domain-m1-alignment:  ## 校验 project-registry.yaml ↔ eCOS M1 domain 节点对齐 (drift 检测)
	uv run --with pyyaml python bin/ssot/check-domain-m1-alignment.py

toolbox-ssot-check:  ## 校验 ToolBox docs SSOT 契约 (硬编码值检测)
	uv run --with pyyaml python bin/ssot/check-toolbox-ssot.py

gac-local-gate:
	uv run --with pyyaml python bin/gac/gac-local-gate.py
dir-hygiene:  ## 检查根目录卫生 (未追踪未忽略的目录)
	uv run --with pyyaml python bin/ssot/dir-hygiene-check.py

governance-release-gate:
	uv run --with pyyaml python bin/ssot/submodule-reachability-gate.py --source head --fetch

submodule-pointer-transaction:
	bash bin/ssot/submodule-pointer-transaction.sh --dry-run

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
	bash bin/ssot/verify-omo.sh

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
