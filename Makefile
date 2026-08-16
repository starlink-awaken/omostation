.PHONY: help ci-local ci-local-fast kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint agent-workflow-lint agent-workflow-doctor agent-workflow-observe agent-workflow-adapters agent-workflow-integrations agent-workflow-bootstrap agent-workflow-verify agent-workflow-compliance agent-workflow-closeout agent-workflows project-layer-index domain-m1-alignment toolbox-ssot-check gac-local-gate dir-hygiene governance-release-gate submodule-pointer-transaction governance-check governance-verify governance-audit governance-dashboard debt-check debt-audit debt-leaderboard governance-data governance-query doc-lint evidence-smoke x1-check x2-check x3-check x4-check x1-x4-check install-hooks pasw-cleanup pasw-status mesh-orphan-cleanup mesh-orphan-cleanup-apply adr-claim mof-bootstrap m4-health m4-health-compare registry-drift state-sync state-sync-dry doc-ssot-lint ssot-guardian gac-healthcheck swarm-activity gac-drift gac-validate agent-workflow-status memory-os-check memory-os-env memory-os-up memory-os-smoke memory-os-asof-seed worktree-prune worktree-guard worktree-cleanup worktree-audit worktree-hygiene worktree-janitor delegation-preflight delegation-alias-check bin-tool-registry-audit bin-tool-registry-audit-strict bin-tool-registry-audit-emit bin-tool-registry-convergence bin-tool-registry-parallel-gaps bin-tool-registry-dependency-risks bin-tool-registry-weekly-governance-report bin-tool-registry-scripts-necessity bin-tool-registry-round9 bin-tool-registry-round10 bin-tool-registry-round11 bin-tool-registry-round12 bin-tool-registry-round13 capability-sync capability-check omo-status omo-top

PY := uv run --with pyyaml python

help:
	@echo "Workspace 根 Makefile — 委派到 projects/"
	@echo ""
	@echo "=== 全局状态与大盘 ==="
	@echo "make omo-status        Multi-Agent Swarm 全景秒级 Rich Panel 诊断快照"
	@echo "make omo-top           Multi-Agent Swarm 4 象限实时互动大盘 (Textual 1.x)"
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
	@echo "make bin-tool-registry-audit             扫描 bin 与 scripts/bin 工具目录（依赖闭环/命名债务）"
	@echo "make bin-tool-registry-audit-strict       扫描并启用严格门禁（脚本层并行用清单托底）"
	@echo "make bin-tool-registry-audit-emit         导出 bin/ scripts/bin 盘点 JSON"
	@echo "make bin-tool-registry-convergence         盘点收敛候选（高出入度聚类）"
	@echo "make bin-tool-registry-parallel-gaps      输出并行命名缺口（bin/scripts 现有重名未纳清单）"
	@echo "make bin-tool-registry-dependency-risks    输出依赖风险热点（出入度 + 并行收敛缺口）"
	@echo "make bin-tool-registry-weekly-governance-report   输出并落盘 依赖风险/并行缺口周报（含 owner/action/sink）"
	@echo "make bin-tool-registry-scripts-necessity   生成 scripts 兼容层必要性快照与固化建议（报告 + JSON）"
	@echo "make bin-tool-registry-round9              并行风险 Top10 一键闭环（strict + gaps + dependency + 周报）"
	@echo "make bin-tool-registry-round10             并行风险 Top10 一键闭环（续一轮）"
	@echo "make bin-tool-registry-round11             并行风险 Top10 一键闭环（继续下一轮）"
	@echo "make bin-tool-registry-round12             并行风险 Top10 一键闭环（继续下一轮）"
	@echo "make bin-tool-registry-round13             并行风险 Top10 一键闭环（继续下一轮）"
scene-feedback:  ## 列出最近的 scene feedback
	@python3 bin/ssot/scene-feedback-collector.py list --limit 10

scene-outcome:  ## 列出最近的 scene outcome (人类裁决)
	@python3 bin/ssot/scene-outcome-recorder.py list --limit 10

signal-poll:  ## 手动执行一次感知面信号轮询
	@python3 bin/ssot/signal-poller.py

ci-local-fast: check-layers
	@$(PY) bin/gac/ci-local-fast.py

check-layers:
	@echo "── 分层依赖检查 ─────────────────────────────────────"
	$(PY) bin/layer-dependency-check.py

delegation-preflight:  ## delegation preflight — 会话启动前检查 subagent 委托基础设施 (--json)
	$(PY) bin/delegation-preflight.py --json

delegation-alias-check:  ## delegation alias check — opencode ↔ omlx 网关别名双向交叉检查 (--json)
	$(PY) bin/delegation-alias-check.py --json

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

worktree-hygiene:  ## worktree 卫生审计与自动清理 (dry-run, 需 --execute 才真删)
	python3 bin/gac/worktree-hygiene-audit.py --auto-clean --fail-on-unsafe

worktree-janitor:  ## worktree/废弃分支安全清理 (默认 dry-run)
	python3 bin/gac/worktree-janitor.py
	uv run python bin/gac/worktree-janitor.py

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

governance-check: governance-verify
	@echo "Governance checks complete."

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

TOOL_REGISTRY_SNAPSHOT ?= artifacts/bin-tool-registry-audit.json
BIN_TOOL_REGISTRY_MANIFEST ?= docs/operations/bin-scripts-convergence-manifest.json
TOOL_REGISTRY_SCOPE ?= both
TOOL_REGISTRY_DEPENDENCY_LIMIT ?= 25
TOOL_REGISTRY_WEEKLY_ARTIFACT ?= artifacts/bin-tool-registry-weekly-governance-report.json
BIN_TOOL_REGISTRY_NECESSITY_REPORT ?= docs/operations/bin-scripts-necessity-report.md
BIN_TOOL_REGISTRY_NECESSITY_SUMMARY ?= docs/operations/bin-scripts-necessity-summary.json

bin-tool-registry-audit:  ## 扫描 bin 工具调用图与命名债务
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)"

bin-tool-registry-audit-emit:  ## 导出 bin 盘点 JSON
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --emit

bin-tool-registry-audit-strict:  ## 严格检查（会返回非零）
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --strict

bin-tool-registry-convergence:  ## 输出收敛候选（按度中心）
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --json | \
		python3 -c "import json,sys;data=json.load(sys.stdin);print('Top out-degree convergence:');[print(f'  {path}: {outd}') for path,outd in data.get('top_out_degree',[])];print('Top in-degree convergence:');[print(f'  {path}: {ind}') for path,ind in data.get('top_in_degree',[])]"

bin-tool-registry-parallel-gaps:  ## 输出 bin/scripts 并行清单缺口
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --json | \
		python3 -c "import json,sys;data=json.load(sys.stdin);gaps=data.get('findings',{}).get('parallel_manifest_gaps',[]);print(f'parallel manifest gaps: {len(gaps)}');[print(f' - {item.get(\"name\")}: {\", \".join(item.get(\"gap_reasons\", []))} | bin={\", \".join(item.get(\"bin_files\", []))} | scripts={\", \".join(item.get(\"scripts_files\", []))}') for item in sorted(gaps, key=lambda x: x.get(\"name\", \"\"))]"

bin-tool-registry-dependency-risks:  ## 输出依赖风险热点（便于周例会按影响面收敛）
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --json | \
		TOOL_REGISTRY_DEPENDENCY_LIMIT="$(TOOL_REGISTRY_DEPENDENCY_LIMIT)" python3 -c "import json,sys,os;data=json.load(sys.stdin);hs=data.get('findings',{}).get('dependency_hotspots',[]);limit=int(os.environ.get('TOOL_REGISTRY_DEPENDENCY_LIMIT','25'));print(f'dependency hotspots: {len(hs)} (top {limit})');[print(f' - {item.get(\"path\")} score={item.get(\"risk_score\")} in={item.get(\"in_degree\")} out={item.get(\"out_degree\")} managed={item.get(\"managed_parallel\")} parallel={item.get(\"is_parallel_candidate\")} owner={item.get(\"owner_hint\")} action={item.get(\"recommended_action\")} sink={item.get(\"recommended_sink\")} reasons={\", \".join(item.get(\"dependency_gap_reasons\", []))}') for item in sorted(hs, key=lambda x: x.get(\"risk_score\", 0), reverse=True)[:limit]]"

bin-tool-registry-weekly-governance-report:  ## 输出并落盘依赖风险/并行缺口周报（含 owner/action/sink）
	@TOOL_REGISTRY_DEPENDENCY_LIMIT="$(TOOL_REGISTRY_DEPENDENCY_LIMIT)" \
		TOOL_REGISTRY_WEEKLY_ARTIFACT="$(TOOL_REGISTRY_WEEKLY_ARTIFACT)" \
		python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --json | \
		python3 -c "import json, os, sys; from datetime import datetime, timezone; payload=json.load(sys.stdin); stats=payload.get('stats', {}); findings=payload.get('findings', {}); limit=int(os.environ.get('TOOL_REGISTRY_DEPENDENCY_LIMIT', '25')); artifact=os.environ.get('TOOL_REGISTRY_WEEKLY_ARTIFACT', 'artifacts/bin-tool-registry-weekly-governance-report.json'); gaps=sorted(findings.get('parallel_manifest_gaps', []), key=lambda item: item.get('name', '')); hotspots=sorted(findings.get('dependency_hotspots', []), key=lambda item: (item.get('risk_score', 0), item.get('in_degree', 0) + item.get('out_degree', 0)), reverse=True); os.makedirs(os.path.dirname(artifact), exist_ok=True); open(artifact, 'w', encoding='utf-8').write(json.dumps({'generated_at': datetime.now(tz=timezone.utc).isoformat(), 'scope': payload.get('scope'), 'stats': stats, 'parallel_manifest_gaps_top': gaps[:limit], 'dependency_hotspots_top': hotspots[:limit], 'governance_summary': {'parallel_manifest_gaps_total': len(gaps), 'dependency_hotspots_total': len(hotspots)}}, ensure_ascii=False, indent=2)); print('generated weekly governance report: {}'.format(artifact)); print('parallel manifest gaps: total={} top={}'.format(len(gaps), limit)); [print(' - {}: {}'.format(item.get('name'), ', '.join(item.get('gap_reasons', [])))) for item in gaps[:limit]]; print('dependency hotspots: total={} top={}'.format(len(hotspots), limit)); [print(' - {path}: score={score} in={ind} out={outd} managed={managed} parallel={parallel} owner={owner} action={action} sink={sink}'.format(path=item.get('path'), score=item.get('risk_score'), ind=item.get('in_degree'), outd=item.get('out_degree'), managed=item.get('managed_parallel'), parallel=item.get('is_parallel_candidate'), owner=item.get('owner_hint'), action=item.get('recommended_action'), sink=item.get('recommended_sink'))) for item in hotspots[:limit]]"

bin-tool-registry-scripts-necessity:  ## 生成 scripts 兼容层必要性快照与收敛建议
	@mkdir -p "$(dir $(BIN_TOOL_REGISTRY_NECESSITY_REPORT))"
	@mkdir -p "$(dir $(BIN_TOOL_REGISTRY_NECESSITY_SUMMARY))"
	@python3 bin/tool-registry-audit.py --scope "$(TOOL_REGISTRY_SCOPE)" --parallel-manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --json > "$(TOOL_REGISTRY_SNAPSHOT)"
	@python3 bin/generate-bin-scripts-necessity.py --manifest "$(BIN_TOOL_REGISTRY_MANIFEST)" --snapshot "$(TOOL_REGISTRY_SNAPSHOT)" --output "$(BIN_TOOL_REGISTRY_NECESSITY_REPORT)" --json "$(BIN_TOOL_REGISTRY_NECESSITY_SUMMARY)"
	@echo "generated $(BIN_TOOL_REGISTRY_NECESSITY_REPORT)"
	@echo "generated $(BIN_TOOL_REGISTRY_NECESSITY_SUMMARY)"

bin-tool-registry-round9:  ## 并行风险 Top10 一键闭环（建议默认命令）
	@$(MAKE) bin-tool-registry-audit-strict TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-parallel-gaps TOOL_REGISTRY_SCOPE=both
	@$(MAKE) bin-tool-registry-dependency-risks TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-weekly-governance-report TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10 TOOL_REGISTRY_WEEKLY_ARTIFACT=artifacts/bin-tool-registry-weekly-governance-report-round9.json

bin-tool-registry-round10:  ## 并行风险 Top10 一键闭环（续一轮）
	@$(MAKE) bin-tool-registry-audit-strict TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-parallel-gaps TOOL_REGISTRY_SCOPE=both
	@$(MAKE) bin-tool-registry-dependency-risks TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-weekly-governance-report TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10 TOOL_REGISTRY_WEEKLY_ARTIFACT=artifacts/bin-tool-registry-weekly-governance-report-round10.json

bin-tool-registry-round11:  ## 并行风险 Top10 一键闭环（继续下一轮）
	@$(MAKE) bin-tool-registry-audit-strict TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-parallel-gaps TOOL_REGISTRY_SCOPE=both
	@$(MAKE) bin-tool-registry-dependency-risks TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-weekly-governance-report TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10 TOOL_REGISTRY_WEEKLY_ARTIFACT=artifacts/bin-tool-registry-weekly-governance-report-round11.json

bin-tool-registry-round12:  ## 并行风险 Top10 一键闭环（继续下一轮）
	@$(MAKE) bin-tool-registry-audit-strict TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-parallel-gaps TOOL_REGISTRY_SCOPE=both
	@$(MAKE) bin-tool-registry-dependency-risks TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-weekly-governance-report TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10 TOOL_REGISTRY_WEEKLY_ARTIFACT=artifacts/bin-tool-registry-weekly-governance-report-round12.json

bin-tool-registry-round13:  ## 并行风险 Top10 一键闭环（继续下一轮）
	@$(MAKE) bin-tool-registry-audit-strict TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-parallel-gaps TOOL_REGISTRY_SCOPE=both
	@$(MAKE) bin-tool-registry-dependency-risks TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10
	@$(MAKE) bin-tool-registry-weekly-governance-report TOOL_REGISTRY_SCOPE=both TOOL_REGISTRY_DEPENDENCY_LIMIT=10 TOOL_REGISTRY_WEEKLY_ARTIFACT=artifacts/bin-tool-registry-weekly-governance-report-round13.json

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

# ── Agent Workflow & Swarm Observability ──────────────────
omo-status:  ## Multi-Agent Swarm 全景秒级 Rich Panel 诊断快照
	@bash bin/omo-status

omo-top:  ## Multi-Agent Swarm 4 象限实时互动大盘 (Textual 1.x)
	@bash bin/omo-top

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

# ── 统一事件面 (observability-unified-architecture) ─────────────────
observability-events:  ## 统一事件面: emit/search/trace (可观测×事件×治理联动)
	$(PY) bin/ssot/observability-events.py $(OBS_CMD)

observability-adapters:  ## 事件面适配器: 8 通道增量同步 (swarm/gate/debt/health/...)
	$(PY) bin/ssot/observability-events.py adapters run

observability-trace:  ## 按 trace_id 跨链查询 (运行时→事件→治理)
	$(PY) bin/ssot/observability-events.py trace $(TRACE_ID)

log-rotate:  ## 日志轮转 (launchd 守护日志, 默认 5MB 阈值)
	$(PY) bin/ssot/log-rotate.py $(LOG_ROTATE_ARGS)

capability-sync:  ## 生成 capability registry (四源扫描)
	uv run --with pyyaml python bin/capability-sync.py sync

capability-check:  ## capability registry 反漂移校验
	uv run --with pyyaml python bin/capability-sync.py check

debt-predict:  ## Phase 5 动态代码债务蔓延预测引擎
	$(PY) bin/gac/debt-predictor.py

journey-validate:  ## Journey State Graph 状态图表达验证器
	$(PY) bin/ssot/journey-validator.py


gap-verify:  ## 能力缺口台账清零率验证 (Gap Registry)
	@python3 bin/ssot/verify.py --mode gap

task-verify:  ## Task 完成验证门禁 (防止虚假完成)
	@python3 bin/ssot/verify.py --mode task


pasw-cleanup-dryrun:  ## 预览回收 (不删除)
	@bash bin/gac/gac-worktree-cleanup.sh --dry-run

.PHONY: machine-config-lint
machine-config-lint:  ## 检查写机器级配置的脚本集合有无未审阅新成员
	python3 bin/ssot/machine-config-write-lint.py

.PHONY: swarm-prune
swarm-prune:
	python3 bin/gac/swarm-prune-zombies.py --apply
