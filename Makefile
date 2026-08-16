# ==============================================================================
# Monorepo Root Makefile (Governance, Compute Fabric & Submodule Orchestration)
# ==============================================================================

.PHONY: help \
	fabric-inspect fabric-warm fabric-vram fabric-bench omlxc-fabric omlxc-benchmark \
	gate-local gate-skills gate-ci-surfaces gate-layers gate-phase gate-reachability gate-mof check-layers gac-local-gate \
	test-all test-omlxc test-aetherforge test-cockpit test-kairon test-agora test-omo test-ecos lint-all \
	omlxc-test omlxc-lint kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-lint kairon-build \
	sync-all-docs sync-capability-registry sync-help-docs check-docs-drift sync-submodules ssot-status ssot-log ssot-sync \
	hygiene-worktree hygiene-audit hygiene-janitor hygiene-dir dir-hygiene worktree-guard worktree-prune worktree-cleanup worktree-audit worktree-hygiene worktree-janitor \
	memory-os-check memory-os-env memory-os-env-export memory-os-up memory-os-smoke memory-os-asof-seed \
	omo-status omo-top swarm-activity observability-events observability-adapters observability-trace log-rotate \
	agent-workflows agent-workflow-bootstrap agent-workflow-lint agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflow-doctor agent-workflow-observe agent-workflow-agents agent-workflow-integrations agent-workflow-adapters agent-workflow-status \
	mof-bootstrap m4-health m4-health-compare registry-drift gac-healthcheck gac-drift gac-validate \
	evidence-smoke governance-check governance-verify governance-audit debt-check doc-lint scene-feedback scene-outcome signal-poll

PY := uv run --with pyyaml python

# ── 帮助大盘 ────────────────────────────────────────────────────────────────────

help:
	@echo "\033[1;36m==============================================================================\033[0m"
	@echo "\033[1;36m  OmoStation Monorepo Root Controller\033[0m"
	@echo "\033[1;36m==============================================================================\033[0m"
	@echo ""
	@echo "\033[1;33m🌟 算力织网 (Compute Fabric / omlxc v3.4.0):\033[0m"
	@echo "  make fabric-inspect         采集集群温控、调度乘子与两级缓存状态"
	@echo "  make fabric-warm            一键预热常用系统 Prompt 前缀 (0ms TTFT)"
	@echo "  make fabric-vram            长上下文动态 KV Cache 显存与自愈预算评估"
	@echo "  make fabric-bench           本地模型基准测试大盘报告"
	@echo ""
	@echo "\033[1;33m🛡️ 质量门禁 (Governance & Phase Gates):\033[0m"
	@echo "  make gate-local             本地极速综合门禁 (ci-local-fast)"
	@echo "  make gate-skills            Agent 技能 Frontmatter 与规范门禁 (check-agent-skills)"
	@echo "  make gate-ci-surfaces       CI 工作流与注册表防漂移自检 (check-ci-surfaces)"
	@echo "  make gate-layers            分层依赖架构合规检查 (layer-contract)"
	@echo "  make gate-reachability      子模块可达性与指针防降级门禁"
	@echo "  make gate-mof               MOF 5-check strict 元模型合规校验"
	@echo ""
	@echo "\033[1;33m🧪 测试与代码质量 (Test Suites & QA):\033[0m"
	@echo "  make test-all               触发全仓级联测试 (cascading-test)"
	@echo "  make test-omlxc             运行 omlxc 算力织网 1043+ 单测"
	@echo "  make test-aetherforge       运行 AetherForge 547+ 单测"
	@echo "  make test-cockpit           运行 Cockpit 门禁与单测"
	@echo "  make test-kairon            运行 Kairon 知识引擎单测"
	@echo "  make lint-all               运行全仓 Lint 检查"
	@echo ""
	@echo "\033[1;33m📚 SSOT 注册表与文档同步 (SSOT & Registry):\033[0m"
	@echo "  make sync-all-docs          全量同步能力注册表、MCP 索引与 CLI 参考"
	@echo "  make sync-submodules        同步推送子模块未推送提交至远程"
	@echo "  make check-docs-drift       检测派生文档漂移 (CI 门禁)"
	@echo "  make ssot-status            查看 SSOT 变更与真理源状态"
	@echo ""
	@echo "\033[1;33m🧹 工作区与分支卫生 (Hygiene & Janitor):\033[0m"
	@echo "  make hygiene-worktree       审计与自动清理冗余/过期 Worktree"
	@echo "  make hygiene-dir            检查根工作区未追踪文件与目录卫生"
	@echo ""
	@echo "\033[1;33m👁️ 智能体可观测与大盘 (Multi-Agent Observability):\033[0m"
	@echo "  make omo-status             Multi-Agent Swarm 秒级全景 Rich Panel 快照"
	@echo "  make omo-top                Multi-Agent Swarm 4 象限互动大盘"
	@echo "  make swarm-activity         多 Agent 实时活动面板"
	@echo ""

# ── 🌟 算力织网 (Compute Fabric / omlxc v3.4.0) ─────────────────────────────────

fabric-inspect: omlxc-fabric
omlxc-fabric:  ## 检查本地算力织网状态 (温控/语义分诊/显存预算/两级缓存)
	@echo "── omlxc 算力织网全景诊断 ────────────────────────────"
	cd projects/omlxc && uv run omlxc fabric inspect

fabric-warm:  ## 预热系统 Prompt 前缀实现 0ms TTFT
	@echo "── 预热系统 Prompt 前缀 ──────────────────────────────"
	cd projects/omlxc && uv run omlxc fabric warm

fabric-vram:  ## 评估模型 KV Cache 显存预算 (默认 coding 32k)
	@echo "── 显存预算评估 ──────────────────────────────────────"
	cd projects/omlxc && uv run omlxc fabric vram coding 32768

fabric-bench: omlxc-benchmark
omlxc-benchmark:  ## 查看本地模型基准测试大盘
	@echo "── 本地模型基准测试榜单 ──────────────────────────────"
	cd projects/omlxc && uv run omlxc benchmark report

# ── 🛡️ 质量门禁 (Governance & Phase Gates) ─────────────────────────────────────

gate-local: ci-local-fast
ci-local-fast: check-layers  ## 本地极速门禁
	@$(PY) bin/gac/ci-local-fast.py

gate-skills:  ## Agent 技能静态合规检查
	@echo "── 检查 Agent Skills 规范 ────────────────────────────"
	python3 bin/ssot/check-agent-skills.py

gate-ci-surfaces:  ## CI 工作流与注册表防漂移检查
	@echo "── 检查 CI Surfaces 注册表 ───────────────────────────"
	python3 bin/gac/check-ci-surfaces.py

gate-layers: check-layers
check-layers:  ## 分层依赖检查 (docs/layer-contract.yaml)
	@echo "── 分层依赖检查 ─────────────────────────────────────"
	$(PY) bin/layer-dependency-check.py

gate-reachability: governance-release-gate
governance-release-gate:  ## 子模块可达性门禁
	$(PY) bin/ssot/submodule-reachability-gate.py --source head --fetch

gate-mof: mof-bootstrap
mof-bootstrap:  ## MOF 5-check strict 校验
	$(PY) bin/mof/mof-bootstrap.py all

gac-local-gate:
	$(PY) bin/gac/gac-local-gate.py

gac-healthcheck:  ## GaC 13-point 健康检查
	$(PY) bin/gac/gac-healthcheck.py

gac-drift:  ## GaC 规则漂移检测
	$(PY) bin/gac/gac-drift.py

gac-validate:  ## GaC 规则验证 (--gate)
	$(PY) bin/gac/gac-validate.py --gate

m4-health:  ## M4 health score
	$(PY) bin/mof/m4-health-score.py --emit

m4-health-compare:  ## M4 health score 对比
	$(PY) bin/mof/m4-health-score.py --compare

registry-drift:  ## 注册表漂移检测
	$(PY) bin/mof/gen-project-registry.py

# ── 🧪 测试与代码质量 (Test Suites & QA) ───────────────────────────────────────

test-all:  ## 触发全仓拓扑级联测试
	@echo "── 全仓受影响项目级联测试 ────────────────────────────"
	@python3 bin/gac/affected-graph.py --changed-projects omlxc,aetherforge,cockpit --json

test-omlxc: omlxc-test
omlxc-test:  ## 运行 omlxc 全量单测 (pytest)
	@echo "── 运行 omlxc 测试 ───────────────────────────────────"
	cd projects/omlxc && uv run pytest -q

test-aetherforge:  ## 运行 aetherforge 全量单测
	@echo "── 运行 aetherforge 测试 ─────────────────────────────"
	cd projects/aetherforge && uv run pytest -q

test-cockpit:  ## 运行 cockpit 测试
	@echo "── 运行 cockpit 测试 ─────────────────────────────────"
	cd projects/cockpit && uv run pytest -q

test-kairon: kairon-test
kairon-test:  ## 运行 kairon 全部测试
	cd projects/kairon && make test

kairon-test-fast:
	cd projects/kairon && make test-fast

kairon-test-diff:
	cd projects/kairon && make test-diff

kairon-test-e2e:
	cd projects/kairon && make test-e2e

kairon-build:
	cd projects/kairon && uv sync

lint-all: omlxc-lint kairon-lint  ## 运行全仓 Lint

omlxc-lint:  ## 运行 omlxc ruff + pyright 严格类型检查
	@echo "── 运行 omlxc 门禁 ───────────────────────────────────"
	cd projects/omlxc && uv run ruff check . && uv run pyright

kairon-lint:
	cd projects/kairon && ruff check packages/

# ── 📚 SSOT 注册表与文档同步 (SSOT & Registry) ──────────────────────────────────

sync-capability-registry:  ## 生成能力注册表 SSOT (扫描 MCP/BOS/CLI)
	@echo "── 生成能力注册表 ────────────────────────────────────"
	python3 bin/cockpit/gen-capability-registry.py

sync-help-docs: sync-capability-registry  ## 从注册表生成派生文档
	@echo "── 生成派生文档 ────────────────────────────────────"
	python3 bin/cockpit/gen-help-docs.py

sync-all-docs: sync-help-docs  ## 全量文档同步 (注册表 + 所有派生文档)
	@echo "── 全量文档同步完成 ────────────────────────────────"

check-docs-drift:  ## 检测文档漂移 (CI 门禁)
	@echo "── 检测文档漂移 ────────────────────────────────────"
	@python3 bin/cockpit/gen-capability-registry.py --quiet
	@python3 bin/cockpit/gen-help-docs.py > /dev/null
	@git diff --exit-code projects/cockpit/CAPABILITY-MAP.md docs/CLI-REFERENCE.md docs/INDEX-MCP.md 2>/dev/null || \
		(echo "❌ 文档漂移! 运行 make sync-all-docs 修复" && exit 1)
	@echo "✅ 文档无漂移"

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

sync-submodules:  ## 推送子模块未推送提交到远程
	@echo "── 同步子模块 ────────────────────────────────────────"
	bash bin/sync-submodules.sh

submodule-pointer-transaction:
	bash bin/ssot/submodule-pointer-transaction.sh --dry-run

# ── 🧹 工作区与分支卫生 (Hygiene & Janitor) ────────────────────────────────────

hygiene-worktree: worktree-hygiene
worktree-hygiene:  ## worktree 卫生审计与自动清理
	python3 bin/gac/worktree-hygiene-audit.py --auto-clean --fail-on-unsafe

hygiene-audit: worktree-audit
worktree-audit:  ## 列出可清理的冗余分支
	python3 bin/ssot/check-branch-redundant.py --json

hygiene-janitor: worktree-janitor
worktree-janitor:  ## worktree/废弃分支安全清理
	python3 bin/gac/worktree-janitor.py

hygiene-dir: dir-hygiene
dir-hygiene:  ## 检查根目录卫生
	$(PY) bin/ssot/dir-hygiene-check.py

worktree-guard:  ## 检查 worktree 数量上限
	bash bin/gac/gac-worktree-guard.sh --check

worktree-prune:  ## 清理已合并/冗余 worktree
	bash bin/gac/gac-worktree-prune.sh --apply

worktree-cleanup:  ## 回收 TTL 过期 worktree
	bash bin/gac/gac-worktree.sh cleanup

# ── 🧠 Memory OS (记忆中枢) ───────────────────────────────────────────────────

memory-os-check:  ## Memory OS 门禁
	python3 bin/gac/check-memory-os-surfaces.py

memory-os-env:  ## 查看 Memory OS 环境变量
	bash bin/memory-os-env.sh --check

memory-os-env-export:
	bash bin/memory-os-env.sh --export

memory-os-up:  ## 启动 Memory OS Neo4j 容器
	bash bin/memory-os-neo4j-up.sh

memory-os-smoke:  ## Memory OS 冒烟测试
	bash bin/memory-os-smoke.sh

memory-os-asof-seed:  ## 注入 AliceDemo 双时态事实种子
	bash bin/memory-os-asof-seed.sh

# ── 👁️ 智能体可观测与大盘 (Multi-Agent Observability) ──────────────────────────

omo-status:  ## Multi-Agent Swarm 全景秒级 Rich Panel 诊断快照
	@bash bin/omo-status

omo-top:  ## Multi-Agent Swarm 4 象限实时互动大盘 (Textual 1.x)
	@bash bin/omo-top

swarm-activity:  ## 多 agent 实时活动面板
	python3 bin/gac/swarm-activity-dashboard.py

observability-events:  ## 统一事件面: emit/search/trace
	$(PY) bin/ssot/observability-events.py $(OBS_CMD)

observability-adapters:  ## 事件面适配器
	$(PY) bin/ssot/observability-events.py adapters run

observability-trace:  ## 按 trace_id 跨链查询
	$(PY) bin/ssot/observability-events.py trace $(TRACE_ID)

log-rotate:  ## 日志轮转
	$(PY) bin/ssot/log-rotate.py $(LOG_ROTATE_ARGS)

# ── 🔧 治理闭环、委托与会话前置 ────────────────────────────────────────────────

delegation-preflight:  ## 检查 subagent 委托基础设施
	$(PY) bin/delegation-preflight.py --json

delegation-alias-check:  ## 检查网关别名交叉匹配
	$(PY) bin/delegation-alias-check.py --json

scene-feedback:  ## 列出最近的 scene feedback
	@python3 bin/ssot/scene-feedback-collector.py list --limit 10

scene-outcome:  ## 列出最近的 scene outcome
	@python3 bin/ssot/scene-outcome-recorder.py list --limit 10

signal-poll:  ## 手动执行感知面信号轮询
	@python3 bin/ssot/signal-poller.py

evidence-smoke:  ## BOS evidence smoke
	@echo "── evidence-smoke (ADR-0219) ────────────────────────────"
	@test -d projects/agora || (echo "init agora: git submodule update --init projects/agora" && git submodule update --init projects/agora)
	python3 bin/gac/evidence-smoke.py --json | python3 -c "import sys,json;d=json.load(sys.stdin);b=d.get('bos') or {};print(f\"score={d.get('evidence_health_score')} partial={d.get('partial')} resolve={b.get('resolve_rate')} gap={b.get('gap')} feedback={ (d.get('feedback_loop') or {}).get('alive')}\")"

governance-verify:
	bash bin/ssot/verify-omo.sh

governance-check: governance-verify
	@echo "Governance checks complete."

governance-audit: governance-check debt-check doc-lint
	@echo "=== 治理审计完成 ==="

debt-check:
	@echo "=== 债务状态检查 ==="
	@if [ -f .omo/state/system.yaml ]; then \
		echo "--- debt_weight ---"; grep "debt_weight:" .omo/state/system.yaml | head -1; \
		echo "--- debt_health ---"; grep "debt_health:" .omo/state/system.yaml | head -1; \
		echo "--- resolved_count ---"; grep "resolved_count:" .omo/state/system.yaml | head -1; \
		echo "--- unresolved_count ---"; grep "unresolved_count:" .omo/state/system.yaml | head -1; \
	fi
	@echo "=== 债务检查完成 ==="

doc-lint:
	@echo "=== 文档格式检查 ==="
	@$(PY) bin/ssot/doc-governance-check.py --no-new-warnings
	@echo "=== 文档检查完成 ==="

governance-dashboard:
	python3 bin/gac/governance-dashboard.py

debt-audit:
	python3 bin/gac/debt-integrity-check.py

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

agent-workflow-status:
	$(PY) bin/agent-workflow.py status --json

project-layer-index:
	$(PY) bin/mof/project-layer-index.py --write

gen-agent-redlines:
	$(PY) bin/mof/gen-agent-redlines.py

domain-m1-alignment:
	$(PY) bin/ssot/check-domain-m1-alignment.py

toolbox-ssot-check:
	$(PY) bin/ssot/check-toolbox-ssot.py

rebase-regen:
	bash bin/ssot/rebase-regen.sh

state-sync:
	uv run --project projects/omo omo state sync --json

state-sync-dry:
	uv run --project projects/omo omo state sync --dry-run --json

doc-ssot-lint:
	$(PY) bin/ssot/doc-ssot-lint.py --json

ssot-guardian:
	$(PY) bin/ssot/ssot-guardian.py

adr-claim:
	@test -n "$(SESSION)" || (echo "SESSION is required"; exit 2)
	python3 bin/adr/next-adr-id.py --session "$(SESSION)" --claim

mesh-orphan-cleanup:
	python3 bin/mesh/mesh-orphan-cleanup.py

mesh-orphan-cleanup-apply:
	python3 bin/mesh/mesh-orphan-cleanup.py --apply
