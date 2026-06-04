# Phase 3 任务规格书 + Agent 执行手册

> 日期: 2026-05-29 | 版本: v1.0 | 依据: evolution-roadmap-4phases.md v1.1
> 前序: Phase 2 必须验收通过
> 总时长: 8-12 周 (3 Sprints) | 总任务: 25
> ⚠️ 核心原则: 所有"自主"操作均需人工确认（Human-in-the-Loop）。KOS 推荐 → 人类确认 → 生效。

---

## Phase 3 全景 Sprint 视图

```
         Sprint 1 (4周)                 Sprint 2 (3周)              Sprint 3 (3周)
      KOS self 辅助进化            自愈全系统 + wksp:// URI      辅助自主研究管线
 ┌──────────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────────┐
 │ W1: nuwa-skill融入KOS    │ │ W5: forge/entropy扩展   │ │ W8: pipeline:json v2    │
 │ W2: KOS辅助发现新模式     │ │ W5: D-Genesis自愈规则   │ │ W8: 管线编排器           │
 │ W3: KOS辅助发现新工具     │ │ W6: 自愈学习+仪表盘     │ │ W9: 自动触发 + 72h验证   │
 │ W4: KOS prompt自优化      │ │ W7: wksp:// URI映射     │ │ W9: Phase 3集成验证      │
 │                          │ │ W7: 全端URI迁移         │ │ W10: 性能基线 + 合规     │
 │                          │ │ W7: URI文档自动生成     │ │ W10: 文档 + Phase 3验收  │
 └──────────────────────────┘ └──────────────────────────┘ └──────────────────────────┘
           |                            |                            |
     🚦 M3.1 Go/No-Go             🚦 M3.2 Go/No-Go             🚦 M3.GO 最终验收
```

---

## 📋 Agent 执行命令模板

### Sprint 1: KOS self 辅助进化

```bash
# T3.1a: nuwa-skill 融入 KOS self
task(category="quick", description="T3.1a: nuwa-skill → KOS self", prompt='''
Integrate nuwa-skill into KOS self-evolution capability.

1. Find nuwa-skill at /Users/xiamingxing/SharedWork/Skills/nuwa-skill/ (or wherever)
2. Create adapter: kairon/packages/kos/src/kos/self/nuwa_skill_adapter.py
   - Calls nuwa-skill to distill a person's thinking framework
   - Outputs a structured Skill definition (name, mental_models, decision_heuristics, expression_patterns)
   - REGISTERS the skill in KOS self registry (does NOT auto-activate)
3. Expose as MCP tool: "kos_self_distill_skill"
4. ⚠️ Human-in-the-loop: generated skill → KOS recommends → human reviews → human activates
5. Test: run on 2 known personas → verify skills generated → human must approve
6. Report: "nuwa-skill integrated, 2 skills generated (awaiting human approval)"
''')

# T3.1b: KOS 辅助发现新模式
task(category="quick", description="T3.1b: KOS assisted pattern discovery", prompt='''
Implement KOS assisted pattern discovery from knowledge graph.

1. Create kairon/packages/kos/src/kos/self/schema_generator.py
   - Analyzes KOS knowledge graph for recurring entity patterns
   - Identifies clusters of similar entities with undocumented relationships
   - Generates eidos Schema proposals
2. ⚠️ Human-in-the-loop: generated schema → KOS recommends → human reviews → (optionally) registers to eidos
3. Expose as MCP tool: "kos_self_discover_schema"
4. Test: run on current KOS index → verify schema proposals generated → must be reasonable
5. Report: "Schema discovery: N patterns found, M schemas proposed (awaiting human review)"
''')

# T3.1c: KOS 辅助发现新工具
task(category="quick", description="T3.1c: KOS assisted tool discovery", prompt='''
Implement KOS assisted tool generation from agent runtime needs.

1. Create kairon/packages/kos/src/kos/self/tool_generator.py
   - Analyzes agentmesh execution logs to identify missing tool capabilities
   - Proposes new MCP tool definitions with parameter schemas
2. ⚠️ Human-in-the-loop: proposed tool → KOS recommends → human reviews → human registers to Agora
3. Expose as MCP tool: "kos_self_discover_tool"
4. Test: run on agent execution history → verify tool proposals → must be reasonable
5. Report: "Tool discovery: N tool proposals generated (awaiting human review)"
''')

# T3.1d: KOS prompt 自优化
task(category="quick", description="T3.1d: KOS prompt optimization", prompt='''
Implement KOS prompt optimization with human review gate.

1. Create kairon/packages/kos/src/kos/self/prompt_optimizer.py
   - Takes a system prompt and a success metric
   - Generates N variants of the prompt
   - Runs A/B test on variants
   - Recommends the best variant
2. ⚠️ Human-in-the-loop: best variant → KOS recommends → human reviews → human applies
3. Expose as MCP tool: "kos_self_optimize_prompt"
4. Test: optimize 1 minerva research prompt → verify recommendation → human decides
5. Report: "Prompt optimizer: best variant scored +X% on metric (awaiting human approval)"
''')
```

### Sprint 2 Wave 5: 器官自愈全系统化

```bash
# T3.2a: forge/entropy 扩展监控范围
task(category="quick", description="T3.2a: Extend entropy monitoring", prompt='''
Extend forge entropy monitoring to cover kairon services + agentmesh.

1. Read existing forge entropy at kairon/packages/forge/src/forge/entropy/
2. Create/update rules to monitor:
   - kairon: minerva, kronos, ontoderive, eidos, kos service health
   - agentmesh: gateway, agent runner health
   - SharedBrain: organ health (already covered by D-Monitoring → agora)
3. Add alerts for each service: timeout, memory leak, CPU spike, crash
4. Expose as MCP tool: "forge_entropy_status" (show all monitored services)
5. Test: simulate 1 service crash → verify alert triggered
6. Report: "Entropy monitoring: N services monitored, alert test: PASS"
''')

# T3.2b: D-Genesis 自愈规则扩展
task(category="quick", description="T3.2b: Extend self-healing rules", prompt='''
Extend SharedBrain D-Genesis self-healing rules for kairon + agentmesh services.

1. Update kairon/packages/forge/src/forge/entropy/rules/sharedbrain_organ_health.yaml
   - Add rules: kairon service restart, agentmesh process restart, Docker service restart
2. Update kairon/packages/forge/src/forge/entropy/healing_trigger.py
   - Add triggers for kairon/agentmesh service anomalies
3. ⚠️ Human-in-the-loop for critical actions:
   - Service restart: auto (safe)
   - Service rollback: human confirmation required
   - Data migration: human confirmation required
4. Test: simulate minerva crash → verify auto-restart triggered → verify service recovers
5. Run 5 simulated anomalies → verify 5/5 self-healing successes
6. Report: "Self-healing: N/5 anomalies recovered, auto-actions: X, human-required: Y"
''')

# T3.2c: 自愈学习
task(category="quick", description="T3.2c: Self-healing learning loop", prompt='''
Implement self-healing learning from healing logs.

1. Create kairon/packages/forge/src/forge/entropy/healing_learner.py
   - Reads healing event logs
   - Identifies patterns: which anomalies recur, which healing actions work
   - Proposes rule improvements
2. ⚠️ Human-in-the-loop: improved rule → recommends → human reviews → human updates
3. Expose as MCP tool: "forge_entropy_learn"
4. Test: feed 10 healing events → verify learning output
5. Report: "Healing learner: N patterns identified, M rule improvements proposed"
''')

# T3.2d: 自愈仪表盘
task(category="quick", description="T3.2d: Self-healing dashboard", prompt='''
Add self-healing statistics to the Agora Dashboard.

1. Read Agora Dashboard code at kairon/packages/agora/src/agora/web/
2. Add a "Self-Healing" section showing:
   - Total heal events (today/week/month)
   - Success/failure rate
   - Top 5 most healed services
   - Recent heal events timeline
3. Data source: forge entropy healing logs (via MCP)
4. Test: dashboard loads, shows sample data correctly
5. Report: "Self-healing dashboard added: N metrics displayed"
''')
```

### Sprint 2 Wave 7: wksp:// URI 统一寻址

```bash
# T3.3a: Agora URI 映射层
task(category="quick", description="T3.3a: Agora wksp:// URI mapping", prompt='''
Implement wksp:// URI resolution in Agora.

Read Agora registry at kairon/packages/agora/src/agora/registry.yaml

1. Create kairon/packages/agora/src/agora/uri_resolver.py
   - Maps wksp:// URIs to actual MCP endpoints
   - Example: wksp://minerva/research → mcp://minerva:8765/research
   - Reads from a URI mapping table in registry.yaml
2. Update registry.yaml: add `uri:` field for each MCP tool
3. Expose MCP tool: "agora_resolve_uri" (returns the actual endpoint for a wksp:// URI)
4. Verify: 100% of registered MCP tools have wksp:// URI
5. Report: "wksp:// URI mapping: N/N tools mapped"
''')

# T3.3b: CLI 迁移到 wksp:// URI
task(category="quick", description="T3.3b: Migrate CLIs to wksp://", prompt='''
Update all CLIs to use wksp:// URIs instead of hardcoded endpoints.

1. Find CLI entry points: wksp, gstack, bos, pallas
2. For each CLI, replace hardcoded mcp://localhost:PORT references with wksp:// URIs
3. The Agora URI resolver handles the actual routing
4. Test: run each CLI command → verify it works through wksp:// URIs
5. Report: "CLI migration: <N> CLIs updated, all commands verified"
''')

# T3.3d: URI 文档自动生成
task(category="quick", description="T3.3d: Auto-generate URI docs", prompt='''
Auto-generate wksp:// URI documentation from Agora registry.

1. Create kairon/packages/agora/src/agora/scripts/generate_uri_docs.py
   - Reads registry.yaml
   - For each tool, generates a documentation page with: URI, description, parameters, examples
2. Output to: .omo/api-docs/ (markdown or HTML)
3. Test: run script → verify docs generated → verify 1 sample URI doc is complete
4. Report: "URI docs generated: N tool docs at .omo/api-docs/"
''')
```

### Sprint 3: 辅助自主研究管线 + 验收

```bash
# T3.4a: pipeline:json v2 定义
task(category="quick", description="T3.4a: pipeline:json v2 spec", prompt='''
Define the pipeline:json v2 protocol for assisted autonomous research.

1. Read v1 spec at kairon/packages/eidos/ (if exists) or define from scratch
2. Create kairon/packages/eidos/schemas/pipeline_v2.json
   - v2 additions over v1:
     - Condition branches (if research_score < 0.5 → retry with different approach)
     - Parallel stages (fan-out research → merge results)
     - Human-in-the-loop gates (pause → wait for human approval → continue)
     - EU cost estimation per stage
     - Immune audit integration at checkpoints
3. Register schema in eidos: `eidos validate pipeline_v2.json`
4. Report: "pipeline:json v2 schema defined, eidos validation: PASS"
''')

# T3.4b: 管线编排器
task(category="quick", description="T3.4b: Pipeline orchestrator for v2", prompt='''
Implement pipeline:json v2 orchestrator in Agora.

1. Create kairon/packages/agora/src/agora/pipeline/orchestrator_v2.py
   - Loads pipeline:json v2 definition
   - Executes conditional branches
   - Handles human-in-the-loop gates (sends notification, waits for response)
   - Tracks EU cost throughout the pipeline
   - Reports per-stage metrics
2. Expose as MCP tool: "agora_pipeline_run_v2"
3. Test: run a simple 3-stage pipeline with 1 branch + 1 HITL gate
4. Report: "Pipeline v2 orchestrator: test pipeline executed, branches resolved, HITL gate held"
''')

# T3.4c: 自动触发 + 72h 验证
task(category="quick", description="T3.4c: Auto trigger + 72h validation", prompt='''
Set up automatic research pipeline triggering and validate for 72 hours.

1. Configure cron-service to trigger research pipeline:
   - Hourly: scan RSS feeds → ingest → research → index
   - Daily: full research cycle with human review gate
2. Create monitoring: kairon/packages/ecos/ (or ops) to track pipeline health
3. Run validation:
   - Start pipeline auto-trigger
   - Monitor for 72 hours continuously
   - Record: total runs, success rate, failures, human review counts, EU consumed
4. Report after 72h:
   - Runs: N total, M successful (X%)
   - Human reviews: Y requested, Z approved
   - EU consumed: XYZ units
   - Failures: list each with root cause
5. Target: ZERO unplanned failures in 72h
''')

# Phase 3 集成验证
task(category="quick", description="Phase3: Integration verification", prompt='''
Run comprehensive Phase 3 integration verification.

1. KOS self: distill 1 skill → propose → human confirms → skill activated
2. KOS self: discover 1 pattern → propose schema → human confirms → registered in eidos
3. Self-healing: simulate 3 anomalies → auto-heal succeeds → log records
4. wksp:// URI: resolve 10 random URIs → all return valid endpoints
5. Pipeline v2: run 1 assisted research with branch + HITL gate → human confirms → research committed
6. 72h auto-run: pipeline triggered hourly → check 24h subset for stability

Each test: report PASS/FAIL with evidence.

Report: "Phase 3 integration: <N>/6 tests pass"
''')
```

---

## 📋 Phase 3 验收检查清单

```
Phase 3 最终验收 — Prometheus 执行

□ P3.1 — KOS self 辅助进化
  □ nuwa-skill 可蒸馏 3+ 人物 Skill（human must approve each）
  □ 辅助发现 ≥ 5 Schema proposals, eidos validate 通过
  □ 辅助发现 ≥ 5 Tool proposals, human review
  □ Prompt optimizer: A/B test working, human applies best variant

□ P3.2 — 器官自愈全系统化
  □ forge/entropy 监控 10+ services across kairon+agentmesh+SharedBrain
  □ 5/5 simulated anomalies successfully self-healed
  □ Healing learner: N rule improvements proposed
  □ Self-healing dashboard: on Agora, showing real data

□ P3.3 — wksp:// URI 统一寻址
  □ 100% MCP tools have wksp:// URI
  □ All CLIs (wksp/gstack/bos) use wksp:// URIs
  □ URI docs auto-generated at .omo/api-docs/

□ P3.4 — 辅助自主研究管线
  □ pipeline:json v2 schema defined + eidos validated
  □ Pipeline orchestrator: DAG branches + HITL gates working
  □ 72h auto-run: ZERO unplanned failures

□ P3.5 — 集成 + 文档
  □ Phase 3 integration: 6/6 tests pass
  □ Performance baseline: P50/P95/P99 recorded
  □ Architecture compliance: 10 laws 0 violations
  □ Health score ≥ 88/100
  □ Human-in-the-loop: ALL autonomous decisions have audit trail
  □ Phase 3 retrospective → .omo/summaries/phase3-retrospective.md

ALL □ CHECKED → Phase 3 GO → Phase 4
ANY □ UNCHECKED → Phase 3 NO-GO
```
