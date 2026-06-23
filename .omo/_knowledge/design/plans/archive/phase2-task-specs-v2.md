---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 2 任务规格书 v2.1（Post-Phase1 gated execution）

> 日期: 2026-05-30 | 版本: v2.1 | 依据: comprehensive-architecture-audit.md + post-phase1 governance
> 前序: Phase 1 code complete；Phase 2 仅允许 M2.0-M2.2 limited-go，full execution 需 Safe Mesh + KOS baseline
> 变更: v1→v2 — 新增 5 Critical缺口修复 + SSOT 7域 + 3 Tech-Intel + 6 安全(ACP/CTRL/SAFE)

---

## v2.1 执行口径

Phase 2 v2.0 的 47 项任务保持为候选池，但不再允许全量并发启动。执行顺序改为：

```text
M2.0 治理收敛与 Phase 1 关闭
  -> M2.1 KOS baseline restore
  -> M2.2 Safe Mesh
  -> M2.3 SSOT 7 域最小注册
  -> M2.4 真实知识闭环
  -> M2.5 扩展能力评审
```

当前唯一可执行入口为 `.omo/tasks/active/*.yaml`。本规格书提供任务候选、上下文和验收要求，不再直接作为 Agent 认领入口。

### M2.0-M2.2 当前 active gate

| Gate | 任务 YAML | 目标 |
|------|-----------|------|
| M2.0 | `M2.0-phase1-governance-close.yaml` | 关闭 Phase 1 治理状态漂移 |
| M2.0 | `M2.0-task-system-seed.yaml` | 建立任务 YAML SSOT |
| M2.1 | `M2.1-kos-index-diagnosis.yaml` | 诊断 KOS 10165→700 退化 |
| M2.1 | `M2.1-kos-repair-plan.yaml` | 制定 no-loss repair plan |
| M2.2 | `M2.2-operation-levels.yaml` | L0-L3 操作分级与拒绝路径 |
| M2.2 | `M2.2-agent-registry-heartbeat.yaml` | Registry heartbeat/cache/identity gate |

### 暂停直接执行的高风险任务

以下任务必须等 M2.2 通过后再进入 active：

- Obsidian / Apple / WeChat / SMB / media 等外部或敏感连接器。
- KOS self、高自主自愈、破坏性备份/恢复。
- 跨域自动研究和 Family OS 调度。

---

## 变更摘要

Phase 2 v1.0（3 Sprint, 29 任务）→ Phase 2 v2.0（4 Sprint, 47 任务），新增:

| 来源 | 新增任务数 | 说明 |
|------|:--------:|------|
| C1 KOS 索引修复 | 2 | 🔴 最紧急 |
| C5 SSOT 7 域注册 | 3 | 基础架构扩展 |
| C2/C3 Obsidian+Apple 连接器 | 3 | iris 扩展 |
| C4 KOS 健康监控 | 2 | ecos 扩展 |
| M1 模型花园 | 2 | forge 扩展 |
| M4 KEMS 运行时 | 2 | sophia 扩展 |
| T1 TokenJuicer 压缩层 | 1 | L2 新能力 (tech-intel) |
| T2 信任图谱层 | 1 | KOS index (tech-intel) |
| T3 BFTS 树搜索 | 1 | minerva 研究 (tech-intel) |

---

## Phase 2 v2.1 全景 Sprint 视图

```
    M2.0-M2.2 Gate              M2.3 最小注册            M2.4 真实闭环             M2.5 扩展评审
   治理收敛 + KOS + Safe Mesh   SSOT 7域最小注册         知识闭环 + 审计          连接器/自动化排序
┌──────────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│ M2.0: Phase1关闭         │ │ SSOT schema/authority│ │ 用户问题→KOS/minerva│ │ 模型花园排序         │
│ M2.1: KOS索引诊断/修复   │ │ 最小查询/校验/追溯   │ │ 保存→审计可见       │ │ Apple/Obsidian评审   │
│ M2.2: 操作分级/RBAC/审计 │ │ 不做全量数据摄取     │ │ 失败注入            │ │ KEMS/跨域研究评审    │
│ M2.2: Registry heartbeat │ │                      │ │                     │ │ Phase2 full-go判定   │
└──────────────────────────┘ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘
         |                          |                      |                      |
   🚦 LIMITED-GO              🚦 M2.3 Go/No-Go      🚦 M2.4 Go/No-Go      🚦 M2.FULL-GO 判定
```

---

## 📋 Agent 执行命令模板 — 新增任务

### Sprint 1 Wave 1: KOS 索引紧急修复 🔴

```bash
# C1: KOS 索引修复 — 诊断
task(category="unspecified-high", description="C1a: Diagnose KOS index degradation", prompt='''
Diagnose why the KOS index has degraded from 10,165 to only ~700 documents.

1. Read the KOS indexing code at /Users/xiamingxing/Workspace/projects/kairon/packages/kos/
2. Check the actual KOS data store:
   - What database/storage is used? (likely LanceDB or Neo4j)
   - Compare stored document count vs expected
3. Check KOS ingestion logs to find when degradation started
4. Identify root cause:
   - Was there a schema change that caused re-indexing?
   - Was there a database migration that lost data?
   - Was there a cleanup script that removed too much?
   - Is the index still being populated (incremental)?
5. Report: root cause diagnosis with recommended fix

This is the HIGHEST PRIORITY task in Phase 2. All knowledge retrieval depends on KOS.
''')

# C1: KOS 索引修复 — 执行
task(category="unspecified-high", description="C1b: Repair KOS index", prompt='''
Repair the KOS index from ~700 back to full coverage.

Based on the diagnosis (C1a), execute the repair.

1. If re-indexing is needed:
   - Scan the original document sources (Obsidian vault at ~/Documents/Obsidian/)
   - Re-ingest all documents into KOS via the kos/ingest pipeline
2. If database recovery is needed:
   - Restore from backup if available
   - Or full re-index from source
3. Add incremental index health check to prevent future degradation
4. Verify: KOS index contains all expected documents
5. Report: "KOS index repaired: <before> → <after> documents indexed"
''')
```

### Sprint 1 Wave 1-2: SSOT 7 域扩展

```bash
# C5: SSOT 域注册
task(category="quick", description="C5a: Register SSOT domains for all 7 knowledge domains", prompt='''
Register all 7 SSOT domains defined in the architecture audit.

Read: /Users/xiamingxing/Workspace/.omo/plans/comprehensive-architecture-audit.md (Section 2.1)

Create domain definition files:

1. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/knowledge.yaml
   - Entities: Article, Book, Paper, Note, Concept, Tag, Source
   - Authority: Obsidian vault (学习进化)

2. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/work.yaml
   - Entities: Project, Task, Document, Meeting, Decision, Regulation
   - Authority: ~/Documents/工作文档/

3. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/family.yaml
   - Entities: Member, HealthRecord, EducationPlan, Event, Asset
   - Authority: FamilyShared iCloud

4. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/ai.yaml
   - Entities: Model, Agent, Tool, Skill, Pipeline, ModelBenchmark
   - Authority: TOOL_REGISTRY + Agora registry

5. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/system.yaml
   - Entities: Service, Port, Config, Rule, Alert, HealthMetric
   - Authority: .omo/ + Hermes ports registry

6. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/data.yaml
   - Entities: Vault, File, Directory, Mount, SyncStatus
   - Authority: filesystem + iCloud

7. /Users/xiamingxing/Workspace/projects/kairon/packages/ssot/domains/media.yaml
   - Entities: Photo, Video, Audio, Album, Collection
   - Authority: SharedDisk 媒体目录

Use the existing sharedbrain.yaml as a template. Each domain file needs: domain name, description, authority, conflict resolution, and at minimum 3 entity schemas.

Report: "SSOT domains: 7/7 registered"
''')
```

### Sprint 2 Wave 4: Obsidian + Apple 连接器

```bash
# C2: Obsidian vault 连接器
task(category="unspecified-high", description="C2: Create Obsidian vault connector", prompt='''
Create an iris connector for Obsidian vaults.

1. Create /Users/xiamingxing/Workspace/projects/kairon/packages/iris/src/iris/connectors/obsidian_connector.py

Requirements:
- Read Obsidian vault at ~/Documents/Obsidian/学习进化/
- Parse .md files with YAML frontmatter
- Extract: title, tags, created/modified dates, backlinks, content
- Convert to KOS Entity format
- Index into KOS knowledge domain
- Support incremental sync (watch for file changes via mtime)

2. Expose as MCP tool: "iris_obsidian_sync"
   - Full sync: re-index entire vault
   - Incremental sync: only changed files since last sync

3. Test: sync the 学习进化 vault → verify entities appear in KOS
4. Report: "Obsidian connector: <N> documents synced to KOS"
''')

# C3: Apple 生态连接器
task(category="unspecified-high", description="C3: Create Apple ecosystem connector", prompt='''
Create an iris connector for Apple Calendar and Reminders.

1. Create /Users/xiamingxing/Workspace/projects/kairon/packages/iris/src/iris/connectors/apple_connector.py

Requirements:
- Calendar: read events from ~/Library/Calendars/ or via AppleScript/EventKit bridge
  - Extract: title, start/end, location, notes, recurrence
  - Convert to family domain Event entities
- Reminders: read from Reminders app
  - Extract: title, due date, priority, list, notes
  - Convert to family domain Task entities

2. If direct Apple API access is not possible via Python, create a wrapper:
   ```python
   # Use osascript to call AppleScript
   import subprocess
   result = subprocess.run(['osascript', '-e', 'tell app "Calendar" to ...'], capture_output=True)
   ```

3. Expose as MCP tool: "iris_apple_calendar" and "iris_apple_reminders"
4. Test: read today's calendar → verify events extracted
5. Report: "Apple connector: <N> events, <M> reminders synced"
''')
```

### Sprint 2 Wave 4: 模型花园

```bash
# M1: 模型花园
task(category="unspecified-high", description="M1a: Create model garden inventory", prompt='''
Create a model garden inventory for the 462GB of local LLM models.

1. Scan model directories:
   - /Volumes/Model/LMStudio/ (449GB)
   - /Volumes/Model/ollama/ (13GB)
   - Any other model locations

2. Create /Users/xiamingxing/Workspace/projects/kairon/packages/forge/src/forge/model_garden.py

Requirements:
- Inventory: scan directories, extract model metadata
  - Model name, provider, parameter count, file size
  - Quantization (if detectable from filename)
  - Date added, last used
- Benchmark: simple inference speed test (tokens/sec) for each model
- Selection: recommend best model for a given task (coding, chat, research)
- Pruning: identify unused models (>30 days) for cleanup suggestion

3. Expose as MCP tool: "forge_model_garden"
   - inventory: list all models
   - benchmark <model>: run speed test
   - recommend <task>: suggest best model

4. Report: "Model garden: <N> models inventoried, <M> benchmarks run"
''')
```

### Sprint 3 Wave 5-6: KEMS 运行时 + KOS 健康监控

```bash
# M4: KEMS 运行时
task(category="deep", description="M4: Create KEMS methodology runtime", prompt='''
Create a KEMS methodology runtime that operationalizes the KEMS v3.0 framework.

1. Read KEMS methodology at ~/Documents/学习进化/经验积累/ (any KEMS-related documents)

2. Create /Users/xiamingxing/Workspace/projects/kairon/packages/sophia/src/sophia/kems_runtime.py

The KEMS runtime should:
- Four Planes (四平面):
  - Knowledge Plane: entity extraction, relation building
  - Experience Plane: pattern recognition, case matching  
  - Methodology Plane: process template execution
  - System Plane: infrastructure monitoring
  
- Three Chains (三链):
  - Data Chain: raw → structured → knowledge
  - Method Chain: requirement → solution → verification
  - Evolution Chain: observe → hypothesize → experiment → learn

- Three Protocols (三协议):
  - Knowledge Protocol: entity schema + validation rules
  - Process Protocol: workflow definition + orchestration
  - Evolution Protocol: learning loop + adaptation rules

3. Each plane/chain/protocol maps to existing kairon components:
   - Knowledge Plane → KOS index
   - Experience Plane → gbrain memory
   - Methodology Plane → ontoderive
   - System Plane → ecos
   - Data Chain → kronos → eidos → KOS
   - Method Chain → minerva → ontoderive → KOS
   - Evolution Chain → KOS self

4. Expose as MCP tool: "sophia_kems"
   - analyze <domain>: apply KEMS to a domain
   - plan <goal>: generate methodology-driven plan

5. Test: run KEMS analysis on Knowledge domain → verify output uses 四平面+三链
6. Report: "KEMS runtime operational, test domain analysis complete"
''')

# C4: KOS 健康监控
task(category="unspecified-high", description="C4: Implement KOS health monitoring", prompt='''
Create KOS health monitoring to prevent future index degradation.

1. Create /Users/xiamingxing/Workspace/projects/kairon/packages/ecos/src/ecos/kos_health_monitor.py

Requirements:
- Daily index health check:
  - Document count vs expected (based on source vault sizes)
  - Index integrity (random sample verification)
  - Search quality (query 5 known documents → verify found)
  - Index latency (P50/P95/P99 search time)
  
- Alert thresholds:
  - Document count drops >5% in 1 day: WARNING
  - Document count drops >20%: CRITICAL (auto-pause indexing)
  - Search quality <80% (known docs not found): CRITICAL
  
- Auto-remediation:
  - WARNING: trigger incremental re-sync
  - CRITICAL: pause writes, notify human, wait for investigation

2. Expose as MCP tool: "ecos_kos_health"
   - status: show current health metrics
   - reindex <domain>: trigger re-index of a domain
   - history: show health trends over time

3. Test: run health check → verify metrics → simulate degradation → verify alert
4. Report: "KOS health monitor operational, daily checks scheduled"
''')
```

### Sprint 4: Phase 2 集成验证 (新增任务)

```bash
# Phase 2 v2 集成验证
task(category="quick", description="Phase2v2: Integration verification", prompt='''
Run comprehensive Phase 2 v2 integration verification:

1. KOS repair: verify index count restored → query 10 known docs → 10/10 found
2. SSOT domains: verify 7/7 domains registered → each has schemas
3. Obsidian sync: sync 学习进化 vault → verify entities in KOS → search works
4. Apple connector: read today's calendar → verify events in family domain
5. Model garden: inventory models → verify count > 10 → benchmark 1 model
6. KEMS runtime: analyze Knowledge domain → verify 四平面+三链 output
7. KOS health: run health check → verify metrics → simulate degradation alert
8. RBAC enforcement: Agent cannot access admin tools → denies logged

Each test: report PASS/FAIL with evidence

Report: "Phase 2 v2 integration: <N>/8 tests pass"
''')
```

---

## 📋 Phase 2 v2.0 验收检查清单

```
Phase 2 v2.0 最终验收 — Prometheus 执行

□ P2.0 — KOS 索引修复 🔴
  □ Root cause diagnosed (C1a report)
  □ Index repaired (document count restored)
  □ Repair verification: 10/10 known docs found in search

□ P2.1 — SSOT 7 域扩展
  □ 7/7 domain YAML files created
  □ Each domain has ≥3 entity schemas
  □ SSOT validate: 0 errors across all domains

□ P2.2 — 知识图谱 + RBAC (保留 v1.0)
  □ GitNexus + Graphify bridges (v1.0 tasks)
  □ 跨域统一检索 (updated for 7 domains)
  □ RBAC 4 角色 + 凭证分发 (v1.0 tasks)

□ P2.3 — 连接器
  □ Obsidian vault 连接器: documents synced to KOS
  □ Apple 生态连接器: calendar+reminders synced
  □ WeChat/SMB 连接器: deferred to Phase 3

□ P2.4 — 模型花园 (新增)
  □ Model inventory: all 462GB models cataloged
  □ Benchmark: ≥5 models benchmarked (tokens/sec)
  □ Recommend: model recommendation for 3 tasks works

□ P2.5 — KEMS 运行时 (新增)
  □ KEMS runtime operational
  □ 四平面映射到 kairon 组件
  □ Test domain analysis produces valid output

□ P2.6 — KOS 健康监控 (新增)
  □ Daily health check scheduled
  □ Alert thresholds configured
  □ Degradation simulation: alert triggered correctly

□ P2.7 — minerva 研究增强 + kronos 摄取 (保留 v1.0)
  □ UltraRAG + MinerU + Firecrawl (v1.0 tasks)
  □ 辅助研究模式 + HITL gate

□ P2.8 — EU 经济 + 免疫 (保留 v1.0)
  □ Agora EU router + agentmesh/gbrain EU tracking
  □ Immune audit extended to kronos + agentmesh

□ P2.9 — 集成 + 文档
  □ Phase 2 v2 integration: 8/8 tests pass
  □ Architecture compliance: 10 laws + new SSOT rules
  □ Health score ≥ 82/100 (with new metrics)
  □ Phase 2 v2 retrospective → .omo/summaries/

ALL □ CHECKED → Phase 2 v2 GO → Phase 3
```

---

## v1.0 → v2.0 任务映射

| v1.0 任务 | v2.0 状态 |
|-----------|----------|
| T2.1a-c (KOS知识图谱) | ✅ 保留, Sprint 2 W3 |
| T2.1d (共识) | ✅ 保留 |
| T2.5a-d (RBAC) | ✅ 保留 |
| T2.2a-c (minerva研究) | ✅ 保留, Sprint 3 W6 |
| T2.3a-d (kronos摄取) | ✅ 保留, Sprint 3 W6 |
| T2.4a-d (EU经济+免疫) | ✅ 保留, Sprint 3 W6 |
| — | **新增**: C1a-b (KOS修复) Sprint 1 W1 |
| — | **新增**: C5a-c (SSOT 7域) Sprint 1 W1-2 |
| — | **新增**: C2 (Obsidian连接) Sprint 2 W4 |
| — | **新增**: C3 (Apple连接) Sprint 2 W4 |
| — | **新增**: M1 (模型花园) Sprint 2 W4 |
| — | **新增**: M4 (KEMS运行时) Sprint 3 W5 |
| — | **新增**: C4 (KOS健康) Sprint 3 W6 |
| — | **🆕 T1** (TokenJuicer) Sprint 1 W1 |
| — | **🆕 T2** (信任图谱) Sprint 1 W2 |
| — | **🆕 T3** (BFTS树搜索) Sprint 3 W6 |

---

## 🆕 技术情报驱动的新增任务

### T1: TokenJuicer 压缩层 (Sprint 1 W1)

```bash
task(category="unspecified-high", description="T1: TokenJuicer compression layer", prompt='''
Create a Token compression layer for kairon pipelines. Inspired by OpenHuman's TokenJuice.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kronos/src/kronos/compressors/token_juicer.py

Requirements:
1. HTML→Markdown compression (reduce 40-60% tokens by removing CSS/JS/formatting)
2. Deduplication (hash-based content dedup, skip identical docs)
3. Multi-byte preserving (Chinese/Japanese/Korean characters preserved)
4. URL stripping (remove tracking parameters, normalize)
5. Whitespace normalization

Expose as MCP tool: "kronos_token_compress"
- compress <text>: compress text and report savings
- batch <files>: compress multiple files

Test: compress 5 HTML pages → report token savings
Report: "TokenJuicer: compressed <N> docs, saved <X>% tokens"
''')
```

### T2: 信任图谱层 (Sprint 1 W2)

```bash
task(category="unspecified-high", description="T2: Trust graph layer for KOS index", prompt='''
Add a trust/confidence scoring layer to KOS index. Inspired by trustgraph-ai.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kos/src/kos/trust_layer.py

Requirements:
1. Per-entity trust score (0.0-1.0):
   - Source authority: official docs > peer-reviewed > blog > social media
   - Cross-validation: entities confirmed by multiple sources get higher trust
   - Age decay: older entities with no recent validation decay
2. Per-relation confidence:
   - Direct evidence > inferred > speculative
3. Trust propagation: high-trust entities increase trust of linked entities
4. Query-time filtering: search results include trust score; low-trust filtered by default

Expose as MCP tool: "kos_trust_score"
- entity <id>: get trust score
- propagate: run trust propagation across entire graph

Test: score 10 known entities → verify authority ranking
Report: "Trust layer: <N> entities scored, propagation complete"
''')
```

### T3: BFTS 树搜索 (Sprint 3 W6)

```bash
task(category="deep", description="T3: BFTS tree search for minerva", prompt='''
Add Best-First Tree Search (BFTS) to minerva research pipeline. Inspired by AI-Scientist-v2.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/minerva/src/minerva/search/bfs_search.py

Requirements:
1. Parallel exploration: 
   - Decompose research question → N sub-questions
   - Explore each in parallel (fan-out)
2. Dynamic pruning:
   - Score each branch by relevance * source_trust
   - Prune branches with score < threshold
3. Best-first selection:
   - Continue exploring top-K branches
   - Merge results into synthesis
4. Configurable:
   - max_depth: 3 (default)
   - max_branches: 5 (default)
   - prune_threshold: 0.3

Expose as MCP tool: "minerva_bfs_search"
- research <query> [depth]: run BFTS research

Test: research "AI regulation impact on healthcare" → verify multiple branches explored
Report: "BFTS search: <N> branches explored, <M> pruned, synthesis generated"
''')
| — | **新增**: Phase 2 v2 集成验证 Sprint 4 |
| — | **🆕 ACP_1**: Agent Registry+心跳 Sprint 2 W3 |
| — | **🆕 ACP_2**: Task Dispatcher+优先级 Sprint 2 W3 |
| — | **🆕 ACP_3**: Agent沙箱 Sprint 2 W4 |
| — | **🆕 CTRL_1**: L2控制器原型 Sprint 3 W5 |
| — | **🆕 SAFE_1**: 操作分级框架 Sprint 3 W6 |
| — | **🆕 SAFE_2**: 死锁检测器 Sprint 3 W6 |

## 🆕 架构审计驱动的新增安全任务

### ACP_1: Agent Registry + 心跳 + 缓存

```bash
task(category="unspecified-high", description="ACP_1: Agent Registry with heartbeat", prompt='''
Upgrade Agent Registry with heartbeat detection and local caching.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kos/src/kos/agent_registry.py

Requirements:
1. Heartbeat: each Agent reports health every 10s. Registry auto-deregisters after 30s silent.
2. Local Cache: Agent saves last-known registry state locally. If Registry unreachable, uses cache.
3. Agent Identity Verification: each Agent identified by Ed25519 signature. Registry rejects unverified.
4. Backup Registry: secondary Registry on standby (Agora can host a backup).
5. MCP tools: kos_agent_register, kos_agent_list, kos_agent_heartbeat

Test: register 2 agents → kill 1 → verify auto-deregister after 30s
Report: "Agent Registry: heartbeat+缓存就绪"
''')
```

### ACP_2: Task Dispatcher + 优先级队列

```bash
task(category="unspecified-high", description="ACP_2: Task Dispatcher with priority", prompt='''
Upgrade Task Dispatcher with priority queues and QoS.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kos/src/kos/task_dispatcher.py

Requirements:
1. Priority: P0(CRITICAL)<5min, P1(HIGH)<30min, P2(NORMAL), P3(LOW)
2. Preemption: P0 arrival → pause current P2/P3 task
3. QoS: P0 guarantee 5min start, P1 guarantee 30min start
4. Agent Match: task → query Registry → find best Agent (capability × priority match)
5. MCP tools: kos_task_submit(priority, task), kos_task_status(task_id)

Test: submit P0 task while 100 P3 tasks queued → verify P0 jumps queue
Report: "Dispatcher: priority preemption verified"
''')
```

### ACP_3: Agent 沙箱

```bash
task(category="unspecified-high", description="ACP_3: Agent Sandbox", prompt='''
Implement Agent Sandbox for new Agent validation.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kos/src/kos/agent_sandbox.py

Requirements:
1. Sandbox Environment: isolated Docker container, no external network, read-only data
2. 7-day probation: new Agent runs in sandbox for 7 days before production
3. Auto-evaluation: detect anomaly? privilege escalation? resource abuse?
4. Human review: sandbox report → human approves → agent.status = "active"
5. Rejection: fails evaluation → agent.status = "rejected" → human reviews why
6. MCP tools: kos_sandbox_start(agent), kos_sandbox_status(agent), kos_sandbox_report(agent)

Test: register test agent → sandbox 1h → verify evaluation report generated
Report: "Agent Sandbox: probation framework operational"
''')
```

### CTRL_1: L2 控制器原型 (带滞回)

```bash
task(category="unspecified-high", description="CTRL_1: L2 Controller with hysteresis", prompt='''
Create L2 Capability Controller prototype with PID and hysteresis.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/metaos/src/metaos/l2_controller.py

Requirements:
1. Monitor: L2 service health (minerva/kronos/sophia latency, error rate, CPU)
2. PID Control: smooth adjustment of concurrency, not binary on/off
3. Hysteresis: latency > 2x baseline → reduce concurrency; latency < 1x → restore. 60s cooldown.
4. Cross-layer feedback: receives health alerts from ecos, adjusts L2 accordingly
5. MCP tools: l2_controller_status, l2_controller_adjust(service, param, value)

Test: inject latency spike → verify: PID smooth reduction → recovery → hysteresis prevents oscillation
Report: "L2 Controller: PID+hysteresis operational, oscillation test PASS"
''')
```

### SAFE_1: 操作分级框架

```bash
task(category="unspecified-high", description="SAFE_1: Operation Level framework", prompt='''
Implement L0-L3 operation classification and enforcement.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/forge/src/forge/operation_levels.py

Requirements:
1. L0(自主): read-only ops, no human needed
2. L1(审计): low-risk writes, auto-execute but logged
3. L2(确认): high-risk writes, pause → human confirm → execute
4. L3(冷静期): destructive ops, pause → human confirm → 24h wait → final confirm → execute
5. Integration: every MCP tool registered with its operation level
6. Enforcement: Agora checks operation level before dispatching. Deny if level requires confirmation.
7. MCP tools: forge_op_level(classify_tool), forge_op_confirm(operation_id)

Test: attempt L2 write without confirmation → denied → human confirms → executes
Report: "Operation Levels: L0-L3 enforced, deny test PASS"
''')
```

### SAFE_2: 死锁检测器

```bash
task(category="unspecified-high", description="SAFE_2: Deadlock Detector", prompt='''
Implement Agent deadlock detection.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/metaos/src/metaos/deadlock_detector.py

Requirements:
1. Dependency Graph: track which Agent is waiting for which other Agent
2. Cycle Detection: DFS detect circular wait → deadlock confirmed
3. Resolution: terminate lowest-priority Agent in the cycle → notify human
4. Checkpoint: terminated Agent resumes from last checkpoint after resolution
5. Timeout: any Agent wait > 5min → flag as potential deadlock
6. MCP tools: metaos_deadlock_check, metaos_deadlock_resolve

Test: create artificial deadlock (A waits B, B waits A) → verify detected + resolved
Report: "Deadlock Detector: cycle detection verified, resolution test PASS"
''')
```

**Sprint 数**: 3→4 | **任务数**: 29→47 | **新增工时**: ~120h
