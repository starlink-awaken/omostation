.PHONY: help ci-local ci-local-fast kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint agent-workflow-lint agent-workflow-doctor agent-workflow-observe agent-workflow-agents agent-workflow-adapters agent-workflow-integrations agent-workflow-bootstrap agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflows project-layer-index domain-m1-alignment toolbox-ssot-check gac-local-gate dir-hygiene governance-release-gate submodule-pointer-transaction governance-check governance-sync governance-validate governance-index-check governance-verify governance-audit governance-dashboard debt-check debt-audit debt-leaderboard governance-data governance-query doc-lint evidence-smoke x1-check x2-check x3-check x4-check x1-x4-check install-hooks pasw-cleanup pasw-status mesh-orphan-cleanup mesh-orphan-cleanup-apply adr-claim mof-bootstrap m4-health m4-health-compare registry-drift state-sync state-sync-dry doc-ssot-lint ssot-guardian gac-healthcheck swarm-activity gac-drift gac-validate agent-workflow-status memory-os-check memory-os-env memory-os-up memory-os-smoke memory-os-asof-seed worktree-prune worktree-guard worktree-cleanup worktree-audit

PY := uv run --with pyyaml python

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
	@echo "make evidence-smoke    BOS 声明/执行 + feedback 全量 smoke (ADR-0219)"
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
	@echo "=== PASW 子模块隔离 (ADR-0349) ==="
	@echo "make pasw-status         显示 PASW 子模块 worktree 状态"
	@echo "make pasw-cleanup        TTL 回收过期子模块 worktree (默认 24h)"
	@echo ""
	@echo "=== 8维架构 / 运维 / 项目体检 ==="
	@echo "make compass-trace GOAL_ID=<id>  8 维全景元架构追溯 (LifeOS->Goals->C2G->Agora->AetherForge)"
	@echo "make project-inspect PROJ=<name> 17 项目全景 4D 体检与诊断"
	@echo "make debt-synthesize             物理 CSES 债务升维与 C2G Bet 提取"
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
	@echo "=== GaC / MOF / Mesh / ADR / State ==="
	@echo "make gac-healthcheck    GaC 13-point 健康检查"
	@echo "make gac-drift          GaC 规则漂移检测"
	@echo "make gac-validate       GaC 规则验证 (--gate)"
	@echo "make mof-bootstrap      MOF 5-check strict"
	@echo "make m4-health          M4 health score (--emit)"
	@echo "make m4-health-compare   M4 health score delta"
	@echo "make registry-drift     注册表漂移检测 (code->registry)"
	@echo "make mesh-orphan-cleanup   检查孤立 Mesh 运行 (dry-run)"
	@echo "make mesh-orphan-cleanup-apply  关闭孤立 Mesh 运行"
	@echo "make adr-claim SESSION=<s>  占用下一个 ADR 编号"
	@echo "make state-sync         OMO state sync (--json)"
	@echo "make state-sync-dry     OMO state sync dry-run (--json)"
	@echo "make doc-ssot-lint      文档 SSOT 契约检查 (--json)"
	@echo "make ssot-guardian      SSOT guardian (.omo 写入合规)"
	@echo "make agent-workflow-status 当前 workflow 运行状态 (--json)"
	@echo "make memory-os-check     Memory OS SSOT/端口/env 面检查 (phase10)"
	@echo "make memory-os-env       打印/加载 Memory OS 环境 (source bin/memory-os-env.sh)"
	@echo "make memory-os-up        启动 Neo4j（docker→brew）；CLI: cockpit memory --help"
	@echo "make memory-os-smoke     Memory OS 实路径冒烟 (status/write/recall/as_of)"
	@echo "make memory-os-asof-seed as_of 双时态演示种子 + 对照 recall"
	@echo "                       help: cockpit help · discover · cockpit status (含 Memory OS 行)"
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
	@# PASD: 安装 launchd 定时清理 (每 6h 回收过期 worktree)
	@if [ "$$(uname)" = "Darwin" ]; then \
		PLIST_SRC="$(CURDIR)/.omo/_config/pasw-cleanup-launchd.plist"; \
		PLIST_DST="$$HOME/Library/LaunchAgents/com.omostation.pasw-cleanup.plist"; \
		if [ ! -f "$$PLIST_DST" ] && [ -f "$$PLIST_SRC" ]; then \
			mkdir -p "$$HOME/Library/LaunchAgents"; \
			cp "$$PLIST_SRC" "$$PLIST_DST"; \
			launchctl load "$$PLIST_DST" 2>/dev/null || true; \
			echo "  ✅ 已安装 PASW 定时清理 launchd (每 6h)"; \
		else \
			echo "  ⏭ PASW 定时清理已存在或无需安装"; \
		fi; \
	fi

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

adr-number-check:  ## 检查 ADR 编号冲突
	@python3 bin/ssot/adr-number-check.py

scene-card-check:  ## 验证所有 scene card readiness (双轨自动路由)
	@for f in docs/scene-cards/*.yaml; do \
		echo "── $$(basename $$f) ──"; \
		python3 bin/ssot/scene-card-lifecycle.py --scene-card $$f check 2>&1 \
			| python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  ready={d[\"ready\"]} type={d.get(\"scene_type\",\"?\")} blockers={len(d.get(\"activation_blockers\",[]))}')" 2>/dev/null \
			|| echo "  (check failed)"; \
	done

scene-chain-check:  ## 验证场景链 downstream_refs (检测缺失目标 + 反馈环)
	@python3 bin/ssot/scene-chain-validator.py

journey-check:  ## 验证所有 journey spec (状态机 + 不可达/死锁检测)
	@python3 bin/ssot/journey-validator.py

tool-audit:  ## 审计 bin/ssot/ 工具使用情况 (标记 dormant)
	@python3 bin/ssot/tool-usage-audit.py

scene-feedback:  ## 列出最近的 scene feedback
	@python3 bin/ssot/scene-feedback-collector.py list --limit 10

scene-outcome:  ## 列出最近的 scene outcome (人类裁决)
	@python3 bin/ssot/scene-outcome-recorder.py list --limit 10

signal-poll:  ## 手动执行一次感知面信号轮询
	@python3 bin/ssot/signal-poller.py

ci-local-fast: check-layers
	@echo "════════════════════════════════════════════════════"
	@echo "  ci-local-fast — 本地 CI 预检 (快速模式, ~5s)"
	@echo "════════════════════════════════════════════════════"
	@CI_LOCAL_FAIL=0; \
	echo "── GaC local gate ───────────────────────────────────"; \
	$(PY) bin/gac/gac-local-gate.py 2>&1 | sed 's/^/[gac] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	echo "── dir-hygiene ──────────────────────────────────────"; \
	$(PY) bin/ssot/dir-hygiene-check.py 2>&1 | sed 's/^/[hygiene] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
	echo "── ruff check (omo + scripts) ──────────────────────"; \
	ruff check projects/omo/src scripts --ignore F401,F821,E402,E722 2>&1 | sed 's/^/[ruff] /' || CI_LOCAL_FAIL=1; \
	echo ""; \
 	echo "── HTML entity 编码检查 (Python/YAML) ──────────────"; \
 	if grep -rn '&[gl]t;' projects/ --include='*.py' --include='*.yaml' --include='*.yml' 2>/dev/null \
 	   | grep -v 'tests/' | grep -v 'test_' | grep -v 'replace(' | grep -v '\.git/' \
	   | grep -v node_modules | grep -v '\.venv'; then \
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
	$(PY) bin/layer-dependency-check.py

ssot-status:  ## SSOT 变更状态检查
	@echo "── SSOT 状态 ────────────────────────────────────────"
	$(PY) bin/ssot-watcher.py status

ssot-log:  ## SSOT 审计日志查看
	@echo "── SSOT 审计日志 ────────────────────────────────────"
	$(PY) bin/ssot-watcher.py log --limit 20

ssot-sync:  ## SSOT 变更记录到审计日志
	@echo "── SSOT 同步 ────────────────────────────────────────"
	@read -p "Author: " author; \
	read -p "Reason: " reason; \
	$(PY) bin/ssot-watcher.py sync --author "$$author" --reason "$$reason"

sync-submodules:  ## 推送子模块未推送的 commit 到远程
	@echo "── 同步子模块 ────────────────────────────────────────"
	bash bin/sync-submodules.sh

# ── Worktree 治理 (P74: 防堆积) ──────────────────────────
worktree-guard:  ## 检查 worktree 数量上限 (超 MAX_WORKTREES=8 返回 1)
	bash bin/gac/gac-worktree-guard.sh --check

worktree-prune:  ## 清理已合并/冗余 worktree (gac-worktree-prune.sh --apply)
	bash bin/gac/gac-worktree-prune.sh --apply

worktree-cleanup:  ## 回收 TTL 过期 worktree (委托 gac-worktree-cleanup.sh)
	bash bin/gac/gac-worktree.sh cleanup

worktree-audit:  ## 列出可清理的冗余分支 (check-branch-redundant --json)
	python3 bin/ssot/check-branch-redundant.py --json

# ── 能力注册表 + 文档自动生成 (P0-T2) ─────────────────────
sync-capability-registry:  ## 生成能力注册表 SSOT (扫描 MCP/BOS/CLI)
	@echo "── 生成能力注册表 ────────────────────────────────────"
	python3 bin/cockpit/gen-capability-registry.py

sync-help-docs: sync-capability-registry  ## 从注册表生成 CAPABILITY-MAP/CLI-REFERENCE/INDEX-MCP
	@echo "── 生成派生文档 ────────────────────────────────────"
	python3 bin/cockpit/gen-help-docs.py

sync-all-docs: sync-help-docs  ## 全量文档同步 (注册表 + 所有派生文档)
	@echo "── 全量文档同步完成 ────────────────────────────────"

check-docs-drift:  ## 检测文档漂移 (CI 门禁)
	@echo "── 检测文档漂移 ────────────────────────────────────"
	@python3 bin/cockpit/gen-capability-registry.py --quiet
	@python3 bin/cockpit/gen-help-docs.py > /dev/null
	@git diff --exit-code docs/generated/ projects/cockpit/CAPABILITY-MAP.md docs/CLI-REFERENCE.md docs/INDEX-MCP.md 2>/dev/null || \
		(echo "❌ 文档漂移! 运行 make sync-all-docs 修复" && exit 1)
	@echo "✅ 文档无漂移"

evidence-smoke:  ## BOS 全量 evidence smoke (agora .venv bootstrap + resolve rate)
	@echo "── evidence-smoke (ADR-0219) ────────────────────────────"
	@test -d projects/agora || (echo "init agora: git submodule update --init projects/agora" && git submodule update --init projects/agora)
	python3 bin/gac/evidence-smoke.py --json | python3 -c "import sys,json;d=json.load(sys.stdin);b=d.get('bos') or {};print(f\"score={d.get('evidence_health_score')} partial={d.get('partial')} resolve={b.get('resolve_rate')} gap={b.get('gap')} feedback={ (d.get('feedback_loop') or {}).get('alive')}\")"


agent-workflows:
	$(PY) bin/agent-workflow.py list

agent-workflow-bootstrap:
	$(PY) bin/agent-workflow.py bootstrap

agent-workflow-lint:
	$(PY) bin/agent-workflow.py lint

agent-workflow-verify:
	$(PY) bin/agent-workflow.py verify --from-diff

agent-workflow-compliance:
	$(PY) bin/agent-workflow.py compliance

agent-workflow-closeout:
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required"; exit 2)
	$(PY) bin/agent-workflow.py closeout "$(RUN_ID)"

agent-workflow-doctor:
	$(PY) bin/agent-workflow.py doctor

agent-workflow-observe:
	$(PY) bin/agent-workflow.py observe

agent-workflow-agents:
	$(PY) bin/agent-workflow.py agents

agent-workflow-integrations:
	$(PY) bin/agent-workflow.py integrations

agent-workflow-adapters:
	$(PY) bin/agent-workflow.py adapters

project-layer-index:
	$(PY) bin/mof/project-layer-index.py --write

gen-agent-redlines:  ## 生成 docs/generated/agent-redlines.md (agent 红线/灰线 severity digest, ADR-0171)
	$(PY) bin/mof/gen-agent-redlines.py

domain-m1-alignment:  ## 校验 project-registry.yaml ↔ eCOS M1 domain 节点对齐 (drift 检测)
	$(PY) bin/ssot/check-domain-m1-alignment.py

toolbox-ssot-check:  ## 校验 ToolBox docs SSOT 契约 (硬编码值检测)
	$(PY) bin/ssot/check-toolbox-ssot.py

gac-local-gate:
	$(PY) bin/gac/gac-local-gate.py
dir-hygiene:  ## 检查根目录卫生 (未追踪未忽略的目录)
	$(PY) bin/ssot/dir-hygiene-check.py

rebase-regen:  ## ADR-0384 D1: 并发 rebase 后一键全量再生成 (M1 + docs + ruff + mof stat)
	bash bin/ssot/rebase-regen.sh

governance-release-gate:
	$(PY) bin/ssot/submodule-reachability-gate.py --source head --fetch

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
	@echo "--- 文档治理 ownership/lifecycle/freshness ---"
	@$(PY) bin/ssot/doc-governance-check.py --no-new-warnings
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

# ── P84 collab dual-track / control experiment ───────────────────────────────

collab-dualtrack:
	$(PY) bin/collab/export-dualtrack.py --quiet

collab-status:
	$(PY) bin/collab/export-dualtrack.py --throughput-only

collab-adv-report:
	$(PY) bin/collab/adv-fail-report.py

collab-control-exp:
	$(PY) bin/collab/control_experiment.py --batch both --workers 4

collab-recommend-mode:
	$(PY) bin/collab/recommend_mode.py --list-types

m2-ssot-inventory:
	$(PY) bin/mof/m2-ssot-inventory.py

bos-stdio-inventory:
	$(PY) bin/collab/bos-stdio-inventory.py

bos-stdio-candidates:
	$(PY) bin/collab/bos-stdio-inventory.py --migrate-candidates --limit 15

m2-ssot-batch1:
	$(PY) bin/mof/m2-ssot-inventory.py --emit-batch 1

# ── GaC 门禁 ──────────────────────────────────────────────
gac-healthcheck:  ## GaC 13-point 健康检查
	$(PY) bin/gac/gac-healthcheck.py

swarm-activity:  ## 多 agent 实时活动面板 (active runs/locks/worktree/claims/子模块 dirty/冲突)
	python3 bin/gac/swarm-activity-dashboard.py

gac-drift:  ## GaC 规则漂移检测
	$(PY) bin/gac/gac-drift.py

gac-validate:  ## GaC 规则验证 (--gate)
	$(PY) bin/gac/gac-validate.py --gate

# ── MOF / 元模型 ──────────────────────────────────────────
mof-bootstrap:  ## MOF 5-check strict (mof-bootstrap.py all)
	$(PY) bin/mof/mof-bootstrap.py all

m4-health:  ## M4 health score (--emit)
	$(PY) bin/mof/m4-health-score.py --emit

m4-health-compare:  ## M4 health score delta 对比
	$(PY) bin/mof/m4-health-score.py --compare

registry-drift:  ## 注册表漂移检测 (code->registry)
	$(PY) bin/mof/gen-project-registry.py

# ── Mesh ──────────────────────────────────────────────────
mesh-orphan-cleanup:  ## 检查孤立 Mesh 运行 (dry-run)
	python3 bin/mesh/mesh-orphan-cleanup.py

mesh-orphan-cleanup-apply:  ## 关闭孤立 Mesh 运行
	python3 bin/mesh/mesh-orphan-cleanup.py --apply

# ── ADR ───────────────────────────────────────────────────
adr-claim:  ## 占用下一个 ADR 编号 (SESSION=<session>)
	@test -n "$(SESSION)" || (echo "SESSION is required"; exit 2)
	python3 bin/adr/next-adr-id.py --session "$(SESSION)" --claim

# ── State Sync ────────────────────────────────────────────
state-sync:  ## OMO state sync (--json)
	uv run --project projects/omo omo state sync --json

state-sync-dry:  ## OMO state sync dry-run (--json)
	uv run --project projects/omo omo state sync --dry-run --json

# ── SSOT 文档检查 ─────────────────────────────────────────
doc-ssot-lint:  ## 文档 SSOT 契约检查 (--json)
	$(PY) bin/ssot/doc-ssot-lint.py --json

ssot-guardian:  ## SSOT guardian (.omo 写入合规)
	$(PY) bin/ssot/ssot-guardian.py

# ── Agent Workflow status ─────────────────────────────────
agent-workflow-status:
	$(PY) bin/agent-workflow.py status --json

memory-os-check:  ## Memory OS light gate (SSOT / ports / env / catalog; blocking)
	python3 bin/gac/check-memory-os-surfaces.py

memory-os-env:  ## Show / export Memory OS env (source: eval "$$(make -s memory-os-env-export)")
	bash bin/memory-os-env.sh --check

memory-os-env-export:
	bash bin/memory-os-env.sh --export

memory-os-up:  ## Start Neo4j for Memory OS
	bash bin/memory-os-neo4j-up.sh

memory-os-smoke:  ## Memory OS CLI smoke: status + write + recall + as_of
	bash bin/memory-os-smoke.sh

memory-os-asof-seed:  ## Seed bi-temporal AliceDemo facts + print as_of comparison
	bash bin/memory-os-asof-seed.sh


# ── PASW: Per-Agent Submodule Worktree (ADR-0349) ──────────
pasw-status:  ## 显示 PASW 子模块 worktree 状态
	@bash bin/gac/gac-worktree.sh list

pasw-cleanup:  ## TTL 回收过期子模块 worktree (默认 24h, 可 PASW_TTL_HOURS=12)
	@bash bin/gac/gac-worktree-cleanup.sh

panorama:  ## 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产)
	PYTHONPATH=projects/omo/src $(PY) -m omo.cli panorama

compass-trace:  ## 8 维全景元架构追溯 (LifeOS->Goals->C2G->Agora->AetherForge)
	PYTHONPATH=projects/omo/src $(PY) -m omo.cli compass trace $(GOAL_ID)

project-inspect:  ## 17 项目全景 4D 体检与诊断
	PYTHONPATH=projects/omo/src $(PY) -m omo.cli project inspect $(PROJ)

debt-synthesize:  ## 物理 CSES 债务升维与 C2G Bet 提取
	PYTHONPATH=projects/omo/src:bin/gac $(PY) bin/gac/omo_debt_synthesizer.py


pasw-cleanup-dryrun:  ## 预览回收 (不删除)
	@bash bin/gac/gac-worktree-cleanup.sh --dry-run
