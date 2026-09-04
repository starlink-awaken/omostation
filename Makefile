# ==============================================================================
# Monorepo Root Makefile (Governance, Compute Fabric & Submodule Orchestration)
# ==============================================================================

.PHONY: help \
	fabric-inspect fabric-warm fabric-vram fabric-bench omlxc-fabric omlxc-benchmark \
	gate-local gate-skills gate-ci-surfaces gate-layers gate-phase gate-reachability gate-mof check-layers gac-local-gate \
	test-all test-omlxc test-aetherforge test-cockpit test-kairon test-agora test-omo test-ecos lint-all \
	omlxc-test omlxc-lint kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-lint kairon-build \
	sync-all-docs sync-capability-registry check-capability-registry capability-sync capability-check capability-federation-audit sync-help-docs check-docs-drift sync-submodules ssot-status ssot-log ssot-sync \
	hygiene-worktree hygiene-audit hygiene-janitor hygiene-dir dir-hygiene root-directory-governance bin-scripts-convergence-audit worktree-guard worktree-prune worktree-cleanup worktree-audit worktree-hygiene worktree-janitor \
	memory-os-check memory-os-env memory-os-env-export memory-os-up memory-os-smoke memory-os-asof-seed \
	omo-status omo-top swarm-activity observability-events observability-adapters observability-trace log-rotate \
	agent-workflows agent-workflow-bootstrap agent-workflow-lint agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflow-doctor agent-workflow-observe agent-workflow-agents agent-workflow-integrations agent-workflow-adapters agent-workflow-status \
	mof-bootstrap m4-health m4-health-compare registry-drift gac-healthcheck gac-drift gac-validate \
	bridge-runtime corrosion-pipeline scene-journey value-tracker self-evolution weekly-review monthly-healthcheck probe-heartbeat goal-mode-test \
	evidence-smoke governance-check governance-verify governance-audit debt-check doc-lint scene-feedback scene-outcome signal-poll \
	resident-status resident-roles resident-daemon resident-signals resident-alert resident-decision resident-execute resident-sediment resident-memory resident-promote resident-resources resident-ingest \
	bcos-evolve bcos-signals bcos-north-star \
	swarm-status swarm-chaos swarm-decide swarm-audit swarm-demo \
	ast-bootstrap ast-blast ast-audit \
	adr-iteration-rate quota-pressure gov-health-metrics capability-chain-boundary pr-lifecycle

PY := uv run --with pyyaml python
PY_STDLIB := bin/gac/managed-python run --profile stdlib --

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
	@echo "  make capability-federation-audit  只读审计能力跨注册表引用与准入矛盾"
	@echo "  make sync-submodules        同步推送子模块未推送提交至远程"
	@echo "  make check-docs-drift       检测派生文档漂移 (CI 门禁)"
	@echo "  make ssot-status            查看 SSOT 变更与真理源状态"
	@echo ""
	@echo "\033[1;33m🧹 工作区与分支卫生 (Hygiene & Janitor):\033[0m"
	@echo "  make hygiene-worktree       审计与自动清理冗余/过期 Worktree"
	@echo "  make hygiene-dir            检查根工作区未追踪文件与目录卫生"
	@echo ""
	@echo "\033[1;33m⚡️ 混沌对抗与事实大盘 (Chaos & Truth Canvas / ADR-0194):\033[0m"
	@echo "  make chaos-drill            执行 4 项全域混沌注入与红蓝对抗演练"
	@echo "  make chaos-drill-strict     严格模式执行混沌演练 (失败返回非 0)"
	@echo "  make canvas-serve           启动 Dual-Plane Truth Canvas Web 事实大盘 (http://127.0.0.1:8765)"
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

gac-local-gate:  ## 全量治理门禁 (纯验证，不初始化或写入子模块)
	$(PY) bin/gac/gac-local-gate.py

gac-healthcheck:  ## GaC 13-point 健康检查
	$(PY) bin/gac/gac-healthcheck.py

gac-drift:  ## GaC 规则漂移检测
	$(PY) bin/gac/gac-drift.py

gac-validate:  ## GaC 规则验证 (--gate)
	$(PY) bin/gac/gac-validate.py --gate

architecture-check:  ## 架构合规检查
	$(PY) bin/gac/architecture-check.py --strict

architecture-check-quick:  ## 快速架构检查 (pre-commit)
	$(PY) bin/gac/architecture-check.py --quick

architecture-report:  ## 生成架构报告 (JSON)
	$(PY) bin/gac/architecture-check.py --json > .omo/_delivery/architecture/report.json

scene-card-registry:  ## 场景卡注册校验
	$(PY) bin/ssot/scene-card-registry.py --validate --all

dimension-health:  ## 维度健康度采集
	$(PY) bin/gac/dimension-health.py --report

architecture-drift:  ## 架构漂移检测
	$(PY) bin/gac/architecture-drift.py --check

architecture-auto-fix:  ## 架构自动修复 (dry-run)
	$(PY) bin/gac/architecture-auto-fix.py --dry-run

script-registry-validate:  ## 验证全域脚本 444 是否悉数挂号
	$(PY) bin/ssot/script-registry.py validate

adr-iteration-rate:  ## ADR 迭代速率限制 (ADR-4443 教训)
	python3 bin/gac/check-adr-iteration-rate.py

quota-pressure:  ## 治理配额压力监控
	python3 bin/gac/check-quota-pressure.py

gov-health-metrics:  ## 治理健康度量聚合
	python3 bin/gac/governance-health-metrics.py

capability-chain-boundary:  ## MCP 能力链端到端覆盖
	python3 bin/gac/check-capability-chain-boundary.py

pr-lifecycle:  ## PR 生命周期可见性
	python3 bin/gac/check-pr-lifecycle.py

m4-health:  ## M4 health score
	$(PY) bin/mof/m4-health-score.py --emit

m4-health-compare:  ## M4 health score 对比
	$(PY) bin/mof/m4-health-score.py --compare

registry-drift:  ## 注册表漂移检测
	$(PY) bin/mof/gen-project-registry.py

# ── 🔗 链路闭环工具 (Phase 1-3) ──────────────────────────────────────────────

bridge-runtime:  ## 统一桥接运行时状态
	$(PY) bin/gac/bridge-runtime.py --status

corrosion-pipeline:  ## 防腐管道接线 (G1/G2)
	$(PY) bin/gac/corrosion-pipeline-connector.py --dry-run

scene-journey:  ## 场景卡 → Journey 接线
	$(PY) bin/gac/scene-journey-connector.py --list

value-tracker:  ## 价值证明记录
	$(PY) bin/gac/value-tracker.py --report

self-evolution:  ## 自进化循环
	$(PY) bin/gac/self-evolution-loop.py --cycle

weekly-review:  ## 每周价值回顾
	$(PY) bin/gac/weekly-review.py --generate

monthly-healthcheck:  ## 每月架构健康检查
	$(PY) lib/monthly_healthcheck.py --full

probe-heartbeat:  ## 探测器心跳矩阵
	$(PY) bin/gac/probe-heartbeat-monitor.py --status

goal-mode-test:  ## Goal 模式全流程测试
	$(PY) bin/gac/goal-mode-test.py --full-test

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
	cd projects/knowledge/kairon && make test

kairon-test-fast:
	cd projects/knowledge/kairon && make test-fast

kairon-test-diff:
	cd projects/knowledge/kairon && make test-diff

kairon-test-e2e:
	cd projects/knowledge/kairon && make test-e2e

kairon-build:
	cd projects/knowledge/kairon && uv sync

lint-all: omlxc-lint kairon-lint  ## 运行全仓 Lint

omlxc-lint:  ## 运行 omlxc ruff + pyright 严格类型检查
	@echo "── 运行 omlxc 门禁 ───────────────────────────────────"
	cd projects/omlxc && uv run ruff check . && uv run pyright

kairon-lint:
	cd projects/knowledge/kairon && ruff check packages/

# ── 📚 SSOT 注册表与文档同步 (SSOT & Registry) ──────────────────────────────────

sync-capability-registry:  ## 生成只读能力投影 (扫描 MCP/BOS/CLI；非 SSOT)
	@echo "── 生成只读能力投影 ──────────────────────────────────"
	$(PY) bin/ssot/gen-capability-registry.py

check-capability-registry:  ## 只读检查能力投影漂移（与 CI 同一实现）
	@echo "── 检查能力投影漂移 ──────────────────────────────────"
	@$(PY) bin/ssot/gen-capability-registry.py --check --quiet

capability-sync: sync-capability-registry  ## 兼容入口：薄委托到唯一 projection writer

capability-check: check-capability-registry  ## 兼容入口：薄委托到唯一 drift checker

capability-federation-audit:  ## 只读审计 provider/worker/workflow/capability projection 关系图
	@$(PY) bin/capability-sync.py federation-audit --json

sync-help-docs: sync-capability-registry  ## 从注册表生成派生文档
	@echo "── 生成派生文档 ────────────────────────────────────"
	python3 bin/ssot/gen-help-docs.py

sync-all-docs: sync-help-docs  ## 全量文档同步 (注册表 + 所有派生文档)
	@echo "── 全量文档同步完成 ────────────────────────────────"

check-docs-drift: check-capability-registry  ## 检测文档漂移 (CI 门禁)
	@echo "── 检测文档漂移 ────────────────────────────────────"
	@$(PY) bin/ssot/gen-help-docs.py > /dev/null
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

sync-submodule-pointers:  ## 将子模块工作树同步到超项目索引指针
	@echo "── 同步子模块指针 (git submodule update --init) ───────"
	git submodule update --init

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

root-directory-governance:  ## 根目录治理策略与未登记 shadow surface 门禁
	$(PY) bin/ssot/root-directory-governance-scan.py --check --json

bin-scripts-convergence-audit:  ## 校验 bin/scripts 收敛清单、证据与实际入口
	$(PY) bin/ssot/bin-scripts-convergence-audit.py --check --json

hygiene-dir: dir-hygiene
dir-hygiene: root-directory-governance  ## 检查根目录卫生
	$(PY) bin/ssot/dir-hygiene-check.py

worktree-guard:  ## 检查 worktree 数量上限
	bash bin/gac/gac-worktree-guard.sh --check

worktree-prune:  ## 清理已合并/冗余 worktree
	bash bin/gac/gac-worktree-prune.sh --apply

escape-digest:  ## D4 逃逸台账只读聚类 (不改白名单, ADR-0422)
	python3 bin/gac/escape-digest.py --dry-run

hygiene-patrol:  ## 执行全域周度治理自动化巡检 (ADR-0192, 含 escape-digest)
	@echo "── 全域周度治理自动化巡检 ────────────────────────────"
	python3 bin/ssot/weekly-hygiene-patrol.py

hygiene-patrol-strict:  ## 全域治理严格模式巡检 (存在任何违规/漂移时非0退出)
	@echo "── 全域严格治理巡检 (Strict Gate) ───────────────────"
	python3 bin/ssot/weekly-hygiene-patrol.py --strict

sync-documents-clients:  ## 同步生成多客户端 Documents MCP 隔离挂载配置
	@echo "── 同步多客户端 Documents MCP 挂载配置 ───────────────"
	uv run --project projects/ecos ecos-constraint documents sync-clients --mode install

validate-domain-facts:  ## 校验领域事实真源 Schema 与 14 天保鲜期 (ADR-0192)
	@echo "── 校验领域事实真源 Schema 与保鲜度 ─────────────────"
	uv run --project projects/ecos ecos-constraint facts validate

worktree-cleanup:  ## 回收 TTL 过期 worktree
	bash bin/gac/gac-worktree.sh cleanup

# ── 🧬 Clone Lifecycle (独立 clone 生命周期管道) ──────────────────────────────

clone-onboard:  ## 为新 agent 创建 clone + 基线
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID is required" >&2; exit 2)
	@test -n "$(DELIVERY_ATTEMPT_ID)" || (echo "DELIVERY_ATTEMPT_ID is required" >&2; exit 2)
	$(PY_STDLIB) bin/gac/clone-lifecycle.py onboard --agent-id $(AGENT_ID) \
	  --delivery-attempt-id $(DELIVERY_ATTEMPT_ID) \
	  --destination "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/ws" \
	  --profile governance

clone-snapshot:  ## 为当前 clone 生成基线 manifest
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID is required" >&2; exit 2)
	@test -n "$(DELIVERY_ATTEMPT_ID)" || (echo "DELIVERY_ATTEMPT_ID is required" >&2; exit 2)
	$(PY_STDLIB) bin/gac/clone-lifecycle.py snapshot \
	  --clone "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/ws" \
	  --output "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/baseline.json"

clone-changeset:  ## 生成跨仓变更集 + claim 校验
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID is required" >&2; exit 2)
	@test -n "$(DELIVERY_ATTEMPT_ID)" || (echo "DELIVERY_ATTEMPT_ID is required" >&2; exit 2)
	@test -n "$(CLAIMS_ROOT)" || (echo "CLAIMS_ROOT is required" >&2; exit 2)
	$(PY_STDLIB) bin/gac/clone-lifecycle.py changeset \
	  --clone "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/ws" \
	  --baseline "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/baseline.json" \
	  --output "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/changeset.json" \
	  --verify-claims --claims-root "$(CLAIMS_ROOT)"

clone-integrate:  ## 推送分支 + PR (dry-run)
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID is required" >&2; exit 2)
	@test -n "$(DELIVERY_ATTEMPT_ID)" || (echo "DELIVERY_ATTEMPT_ID is required" >&2; exit 2)
	$(PY_STDLIB) bin/gac/clone-lifecycle.py integrate \
	  --clone "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/ws" \
	  --agent-id $(AGENT_ID) --delivery-attempt-id $(DELIVERY_ATTEMPT_ID) --dry-run

clone-retire:  ## 清理 clone
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID is required" >&2; exit 2)
	@test -n "$(DELIVERY_ATTEMPT_ID)" || (echo "DELIVERY_ATTEMPT_ID is required" >&2; exit 2)
	$(PY_STDLIB) bin/gac/clone-lifecycle.py retire \
	  --destination "$(HOME)/agents/$(AGENT_ID)/attempts/$(DELIVERY_ATTEMPT_ID)/ws"

clone-onboard-scan:  ## D2: 为活跃 agent 自动创建 clone (dry-run)
	$(PY_STDLIB) bin/gac/agent-clone-onboard.py

clone-onboard-apply:  ## D2: 真正创建 clone
	$(PY_STDLIB) bin/gac/agent-clone-onboard.py --apply

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

swarm-prune:  ## 清理僵尸 Agent 锁与临时状态
	python3 bin/gac/swarm-prune-zombies.py --apply

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

journey-validate:  ## 校验全部旅程 spec (states/transitions/deadlocks) — AGENTS.md §1.8
	@python3 bin/ssot/journey-validator.py

scene-card-check:  ## 场景卡就绪度报告 — 任一 blocker 即非零退出 (BET-Y1Q3-T4-03 honest gate)
	@ready=0; blocked=0; for f in docs/scene-cards/*.yaml; do \
		[ -e "$$f" ] || continue; \
		if python3 bin/ssot/scene-card-lifecycle.py --root . check --scene-card "$$f" >/dev/null 2>&1; then \
			ready=$$((ready+1)); else blocked=$$((blocked+1)); fi; \
	done; echo "scene-cards: ready=$$ready with-blockers=$$blocked"; \
	echo "单卡详情: python3 bin/ssot/scene-card-lifecycle.py check --scene-card <file>"; \
	test "$$blocked" -eq 0

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

agent-workflow-bootstrap: fabric-warm
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

health-trend:  ## 终端 ASCII 健康趋势图 (compass_radar history)
	uv run --with pyyaml python bin/gac/health-trend-chart.py

health-trend-json:  ## 输出 health trend JSON (供其他工具消费)
	uv run --with pyyaml python bin/gac/health-trend-chart.py --json

cockpit-dashboard-start:  ## 后台启动 cockpit Web 控制台 (port 8090, 默认) — 单实例, 状态在 runtime/cockpit-dashboard.{pid,log}
	bash bin/runtime/start-cockpit-dashboard.sh

cockpit-dashboard-stop:  ## 停止后台 cockpit Web 控制台
	bash bin/runtime/start-cockpit-dashboard.sh stop

cockpit-dashboard-status:  ## 查看 cockpit Web 控制台状态 (running / not running)
	bash bin/runtime/start-cockpit-dashboard.sh status

cockpit-install:  ## 安装 cockpit 软链接至 ~/.local/bin/cockpit (全局免路径调用)
	@mkdir -p $(HOME)/.local/bin
	@ln -sf $(CURDIR)/bin/cockpit $(HOME)/.local/bin/cockpit
	@echo "✅ 已成功安装 cockpit 至 $(HOME)/.local/bin/cockpit"
	@echo "   请确保 $(HOME)/.local/bin 在 PATH 中即可在任意终端直接执行 cockpit"

cockpit-completions-install:  ## 生成当前 Shell 补全脚本
	@./bin/cockpit completion zsh > $(HOME)/.cockpit-completion.zsh 2>/dev/null && \
		echo "✅ 已生成 Zsh 补全脚本: $(HOME)/.cockpit-completion.zsh (可在 ~/.zshrc 中添加: source ~/.cockpit-completion.zsh)" || true

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

chaos-drill:  ## 运行全域混沌注入与红蓝对抗演练 (ADR-0194)
	@echo "── 全域混沌注入与红蓝对抗演练 ────────────────────────────"
	python3 bin/ssot/chaos-governance-drill.py

chaos-drill-strict:  ## 严格模式运行全域混沌演练 (发现未通过项即失败)
	python3 bin/ssot/chaos-governance-drill.py --strict

chaos-drill-full:  ## 12 项全套混沌演练 (BET-Y1Q3-T10-120: strict + JSON report + 防腐护栏巡检)
	@echo "── 12 项全套混沌演练 + 防腐护栏自动化巡检 ────────────────"
	python3 bin/ssot/chaos-governance-drill.py --strict --json | tee docs/reports/2026-09-09-chaos-suite-validation.md
	@echo "── 防腐护栏 GaC 巡检 ──────────────────────────────────────"
	make gac-local-gate
	@echo "── chaos-drill-full COMPLETE ────────────────────────────────"

canvas-serve:  ## 启动 Dual-Plane Truth Canvas Web 事实大盘 (ADR-0194)
	uv run --project projects/ecos ecos-constraint facts serve --port 8765

# ==============================================================================
# Resident Agent System (2026-08-23, WP-A~I / ADR-0396)
# 常驻智能体体系 — 事件驱动 5 类角色 + 规则级路由订阅
# 规格: docs/architecture/resident-agent-system-v1.md
# ==============================================================================

OMO_RESIDENT := uv run --directory projects/omo python -m omo.cli resident

resident-status:  ## resident 运行状态快照 (daemon/events/sediment/alert/ledger)
	$(OMO_RESIDENT) status

resident-roles:  ## resident 五类角色配置 (sediment/decision/execute/monitor/heartbeat)
	$(OMO_RESIDENT) roles

resident-daemon:  ## resident daemon 单次 tick (调试)
	$(OMO_RESIDENT) daemon --once

resident-signals:  ## resident 个人信号输入 (WP-D)
	$(OMO_RESIDENT) signals

resident-alert:  ## resident 告警转发 (WP-E)
	$(OMO_RESIDENT) alert

resident-decision:  ## resident 决策提案 (WP-F)
	$(OMO_RESIDENT) decision

resident-execute:  ## resident 执行 worker (WP-G, 批准门)
	$(OMO_RESIDENT) execute

resident-sediment:  ## resident 知识沉淀 (WP-A)
	$(OMO_RESIDENT) sediment

resident-memory:  ## resident 记忆 (WP-H/I)
	$(OMO_RESIDENT) memory

resident-promote:  ## resident 场景升迁
	$(OMO_RESIDENT) promote

resident-resources:  ## resident 资源领域隔离 (M4.2)
	$(OMO_RESIDENT) resources

resident-ingest:  ## resident 事件摄入 (WP-A)
	$(OMO_RESIDENT) ingest

# ==============================================================================
# BCOS 业务域系统 (2026-08-23, W1~W4)
# 业务闭环: 信号路由 → 进化引擎 → 北极星价值度量
# 规格: docs/architecture/bcos-system-v1.md
# ==============================================================================

bcos-evolve:  ## BCOS 进化引擎四阶段 (observe/propose/evaluate/approve, dry-run 默认)
	python3 bin/bc-os/evolution_engine.py

bcos-signals:  ## BCOS 统一信号路由 (W1-D2, 公文/会议/调研/代码)
	python3 bin/bc-os/signal_router.py --inbox "$$HOME/Documents/@感知信号" || true

bcos-north-star:  ## BCOS 北极星价值度量 v2 (排除 self-data)
	python3 bin/bc-os/north_star_meter_v2.py --json || true

# ==============================================================================
# 自治蜂群与防腐体系 (Self-Governing Swarm & Anti-Corrosion)
# 4 域守卫 + B.D.S.K. 4 角制衡 + 因果黑板 + Devil 变异注入 + Keeper 减法
# ==============================================================================

swarm-status:  ## 蜂群 4 域守卫态势与因果黑板概览
	@uv run --directory projects/cockpit python -m cockpit.cli swarm status

swarm-chaos:  ## @Devil 红队混沌变异注入攻击测试
	@python3 bin/gac/devil-chaos-runner.py --inject all

swarm-decide:  ## @Sage & @Keeper Decision-Inbox 架构裁决工作台
	@uv run --directory projects/cockpit python -m cockpit.cli decide

swarm-audit:  ## @Keeper 减法配额与资产健康度核算
	@python3 bin/gac/keeper-subtraction-engine.py --audit

swarm-demo:   ## 蜂群自治全链路真实场景演练 (6 幕闭环)
	@python3 bin/gac/swarm-e2e-scenario.py

# ==============================================================================
# AST 语义调用链与爆炸半径 (AST Semantic Callgraph & Blast Radius)
# ==============================================================================

ast-bootstrap: ## 全仓 AST 语义符号与调用链自举构建
	@python3 bin/gac/ast-index-bootstrap.py

ast-blast:     ## 分析当前 Git 暂存改动的 AST 爆炸半径 (0.3ms 极速反查)
	@python3 bin/gac/ast-blast-radius.py --diff

ast-audit:     ## AST 语义引擎物理自检与证伪测试
	@python3 bin/gac/ast-blast-radius.py --selftest

# ==============================================================================
# Service Gateway (ops 控制面)
# ==============================================================================

ops:  ## ops 状态总览
	python3 bin/ops/cli.py status

ops-summary:  ## 系统概览
	python3 bin/ops/cli.py summary

ops-up:  ## 启动所有服务 (DAG 分层)
	python3 bin/ops/cli.py up

ops-down:  ## 停止所有服务 (逆拓扑)
	python3 bin/ops/cli.py down

ops-deps:  ## 依赖图
	python3 bin/ops/cli.py deps

ops-discover:  ## 自动发现服务
	python3 bin/ops/cli.py discover

ops-validate:  ## 配置校验
	python3 bin/ops/cli.py validate

ops-generate:  ## 生成部署配置
	python3 bin/ops/cli.py generate

ops-recover:  ## 自动恢复失败服务
	python3 bin/ops/cli.py recover

ops-health-cron:  ## 健康检查定时任务 (每 5 分钟)
	python3 bin/ops/health-check-cron.py

ops-dashboard:  ## Web 仪表盘
	python3 bin/ops/dashboard.py --port 8091

ops-metrics:  ## Prometheus 指标导出
	python3 bin/ops/cli.py metrics --text

ops-metrics-server:  ## Prometheus 指标服务器
	python3 bin/ops/cli.py metrics --port 9090

ops-alert:  ## 告警检查
	python3 bin/ops/alert.py --check

ops-template:  ## 服务模板列表
	python3 bin/ops/cli.py template list

ops-batch-up:  ## 批量启动服务
	python3 bin/ops/cli.py batch up

ops-batch-down:  ## 批量停止服务
	python3 bin/ops/cli.py batch down

ops-drift:  ## 配置漂移检测
	python3 bin/ops/cli.py drift

ops-drift-fix:  ## 配置漂移检测 + 自动修复
	python3 bin/ops/cli.py drift --fix

ops-catalog:  ## 服务目录
	python3 bin/ops/cli.py catalog

ops-graph:  ## 可视化依赖图
	python3 bin/ops/cli.py graph

ops-score:  ## 系统健康评分
	python3 bin/ops/cli.py score

ops-history:  ## 服务健康历史
	python3 bin/ops/cli.py history

ops-metrics-unified:  ## 统一指标聚合
	python3 bin/ops/unified_metrics.py --once

ops-metrics-server:  ## 统一指标服务器
	python3 bin/ops/unified_metrics.py --port 9091

ops-slo:  ## SLO 追踪报告
	python3 bin/ops/slo_tracker.py --report

ops-slo-record:  ## 记录 SLO 指标
	python3 bin/ops/slo_tracker.py --record

ops-slo-json:  ## SLO JSON 输出
	python3 bin/ops/slo_tracker.py --json

ops-cost:  ## 成本追踪报告
	python3 bin/ops/cost_tracker.py --report

ops-cost-record:  ## 记录成本
	python3 bin/ops/cost_tracker.py --record

ops-cost-json:  ## 成本 JSON 输出
	python3 bin/ops/cost_tracker.py --json

ops-runbook:  ## 自动化 Runbook (全部场景)
	python3 bin/ops/runbook.py all

ops-runbook-down:  ## 服务宕机检测+恢复
	python3 bin/ops/runbook.py service-down

ops-runbook-latency:  ## 高延迟诊断
	python3 bin/ops/runbook.py high-latency

ops-runbook-resource:  ## 资源耗尽检测
	python3 bin/ops/runbook.py resource-exhaustion

ops-runbook-deps:  ## 依赖故障追踪
	python3 bin/ops/runbook.py dependency-failure

ops-env:  ## 显示当前环境配置
	python3 bin/ops/env_config.py show

ops-env-list:  ## 列出所有环境
	python3 bin/ops/env_config.py list

ops-env-apply:  ## 应用环境配置
	python3 bin/ops/env_config.py apply

ops-env-apply-dry:  ## 预览环境配置变更
	python3 bin/ops/env_config.py apply --dry-run

ops-monitor:  ## 持续监控守护进程
	python3 bin/ops/monitor_daemon.py

ops-monitor-once:  ## 单次健康检查
	python3 bin/ops/monitor_daemon.py --once

ops-monitor-json:  ## 健康检查 JSON 输出
	python3 bin/ops/monitor_daemon.py --once --json

ops-catalog-api:  ## 服务目录 API
	python3 bin/ops/catalog_api.py --port 8092

ops-dashboard:  ## Web 仪表盘
	@echo "Opening Service Gateway Dashboard..."
	@open docs/observability/dashboard.html 2>/dev/null || xdg-open docs/observability/dashboard.html 2>/dev/null || echo "Open docs/observability/dashboard.html in your browser"

ops-alert:  ## 智能告警检查
	python3 bin/ops/smart_alert.py --check

ops-alert-report:  ## 告警报告
	python3 bin/ops/smart_alert.py --report

ops-capacity:  ## 容量规划报告
	python3 bin/ops/capacity_planner.py --report

ops-capacity-json:  ## 容量规划 JSON
	python3 bin/ops/capacity_planner.py --json

ops-templates:  ## 服务模板列表
	python3 bin/ops/templates.py list

ops-template-show:  ## 显示模板详情
	python3 bin/ops/templates.py show

ops-template-apply:  ## 应用模板创建服务
	python3 bin/ops/templates.py apply

# ── Git Hooks 安装 ──────────────────────────────────────────────────────────────

install-hooks:  ## 安装 Git hooks (.githooks/ → .git/hooks/)
	@mkdir -p .git/hooks
	cp .githooks/pre-commit .git/hooks/pre-commit
	cp .githooks/pre-push .git/hooks/pre-push
	cp .githooks/commit-msg .git/hooks/commit-msg
	cp .githooks/post-commit .git/hooks/post-commit
	cp .githooks/prepare-commit-msg-commit-assist .git/hooks/prepare-commit-msg
	cp .githooks/pre-edit-architecture.sh .git/hooks/pre-edit-architecture
	chmod +x .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/commit-msg .git/hooks/post-commit .git/hooks/prepare-commit-msg .git/hooks/pre-edit-architecture
	@echo "✅ Git hooks installed (including pre-edit-architecture)"
