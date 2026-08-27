---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 2 任务规格书 + Agent 执行手册

> 日期: 2026-05-29 | 版本: v1.0 | 依据: evolution-roadmap-4phases.md v1.1
> 前序: Phase 1 必须验收通过
> 总时长: 6-8 周 (3 Sprints) | 总任务: 29

---

## Phase 2 全景 Sprint 视图

```
         Sprint 1 (2-3周)                Sprint 2 (2-3周)              Sprint 3 (1-2周)
      KOS 知识图谱 + RBAC          minerva 研究 + kronos 摄取       EU经济 + 免疫 + 集成验证
 ┌──────────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────────┐
 │ W1: GitNexus+Graphify图谱│ │ W3: UltraRAG研究增强     │ │ W5: EU经济全系统化       │
 │ W1: KOS跨域统一检索      │ │ W3: 辅助研究模式         │ │ W5: 免疫审计全覆盖        │
 │ W2: KOS知识共识机制      │ │ W4: MinerU+Firecrawl摄取 │ │ W5: Phase2集成验证        │
 │ W2: RBAC授权框架         │ │ W4: 向量数据库存储       │ │ W6: 性能基线 + 合规检查   │
 │                          │ │ W4: cron定时摄取         │ │ W6: 文档 + Phase2验收     │
 └──────────────────────────┘ └──────────────────────────┘ └──────────────────────────┘
           |                            |                            |
     🚦 M2.1 Go/No-Go             🚦 M2.2 Go/No-Go             🚦 M2.GO 最终验收
```

---

## 📋 Agent 执行命令模板

### Sprint 1 Wave 1: KOS 知识图谱 + 统一检索 (T2.1a-c)

```bash
# T2.1a: GitNexus 代码图谱融入 KOS index
task(category="quick", description="T2.1a: GitNexus → KOS index", prompt='''
Integrate GitNexus code knowledge graph into KOS indexing pipeline.

1. Read the existing KOS index code at /Users/xiamingxing/Workspace/projects/kairon/packages/kos/ to understand the indexing pattern
2. Find or clone GitNexus at /Users/xiamingxing/SharedWork/Knowledge/GitNexus/ (or wherever it is)
3. Create a thin adapter: kairon/packages/kos/src/kos/ingest/gitnexus_bridge.py
   - Calls GitNexus API to get code symbols/relations
   - Converts to KOS Entity/Relation format
   - Indexes into KOS knowledge graph
4. Test: index 1 small repo (e.g., kairon itself) and verify entities appear in KOS search
5. Report: "GitNexus bridge created, X entities indexed from <repo>"
''')

# T2.1b: Graphify 文档图谱融入 KOS index
task(category="quick", description="T2.1b: Graphify → KOS index", prompt='''
Integrate Graphify document knowledge graph into KOS indexing pipeline.

1. Find Graphify at /Users/xiamingxing/SharedWork/Knowledge/Graphify/ (or wherever it is)
2. Create thin adapter: kairon/packages/kos/src/kos/ingest/graphify_bridge.py
   - Calls Graphify CLI to process documents
   - Converts Graphify output to KOS Entity/Relation format
   - Indexes into KOS knowledge graph
3. Test: index 5 README.md files from kairon packages and verify entities
4. Report: "Graphify bridge created, X entities indexed from 5 documents"
''')

# T2.1c: KOS 跨域统一检索
task(category="quick", description="T2.1c: KOS unified cross-domain search", prompt='''
Create a unified search endpoint that queries code (GitNexus) + docs (Graphify) + knowledge (KOS) simultaneously.

1. Create kairon/packages/kos/src/kos/search/unified_search.py
   - Accepts a single query string
   - Fans out to 3 domains (code/docs/knowledge) in parallel
   - Merges and ranks results
2. Expose as MCP tool: "kos_unified_search"
3. Test: query "auth" and verify results from all 3 domains
4. Report: "Unified search: <N> results across <M> domains, latency: <X>ms"
''')
```

### Sprint 1 Wave 2: KOS 共识 + RBAC 授权 (T2.1d + T2.5a-d)

```bash
# T2.1d: KOS 知识共识机制
task(category="quick", description="T2.1d: KOS multi-agent consensus", prompt='''
Implement a multi-agent knowledge consensus mechanism for KOS.

1. Create kairon/packages/kos/src/kos/collab/consensus.py
   - Given a knowledge card, 3+ agents vote on confidence
   - Confidence = (agree_count / total_agents)
   - Threshold: confidence < 0.6 → flag for human review
2. Expose as MCP tool: "kos_consensus_vote"
3. Test with 3 sample cards (high agreement, low agreement, conflict)
4. Report: consensus mechanism working, sample votes
''')

# T2.5a: RBAC 角色+权限矩阵
task(category="quick", description="T2.5a: RBAC model design", prompt='''
Define and document the RBAC authorization model.

Read: /Users/xiamingxing/Workspace/.omo/plans/evolution-roadmap-4phases.md (P2.5 section)

Create file: /Users/xiamingxing/Workspace/.omo/rbac-model.md

Content:
- 4 Roles: Admin (full), User (read+write+execute), Agent (read+execute), ReadOnly (read)
- Permission matrix: which roles can access which MCP tools
  - Admin: ALL
  - User: kronos*, minerva*, eidos*, kos*, eu-pricing*, sharedbrain-bridge*
  - Agent: minerva/search, kos/search, agentmesh/tools/*
  - ReadOnly: minerva/search, kos/search, eidos/validate
- Role binding: how an agent/process gets a role (env var, token, or identity_bridge)

Report: "RBAC model documented at .omo/rbac-model.md, 4 roles, N MCP tools mapped"
''')

# T2.5b: Agora auth 中间件
task(category="quick", description="T2.5b: Agora RBAC auth middleware", prompt='''
Implement RBAC enforcement in Agora MCP service mesh.

Read: /Users/xiamingxing/Workspace/.omo/rbac-model.md

Create: kairon/packages/agora/src/agora/middleware/auth_middleware.py

Requirements:
- Before routing any MCP call, extract the caller's role (from header "X-Role" or env)
- Check caller's role against the permission matrix
- Allow → route normally, Deny → return 403 with message
- Log all denies to ops audit log

Test:
- Admin role can call any tool
- Agent role cannot call eu-pricing/consume
- ReadOnly cannot call kronos/ingest

Report: "Auth middleware created, 3 test scenarios pass"
''')

# T2.5d: 权限审计日志
task(category="quick", description="T2.5d: RBAC audit logging", prompt='''
Add audit logging for all RBAC authorization decisions.

1. In the Agora auth middleware (from T2.5b), log to:
   - Console (structured JSON, for real-time monitoring)
   - ops database (SQLite, for historical query)
2. Log format: {"ts":"...", "caller":"...", "role":"...", "tool":"...", "result":"allow|deny", "reason":"..."}
3. Expose MCP tool: "ops_audit_log" to query historical decisions
4. Test: 3 allowed calls + 2 denied calls → verify all appear in logs

Report: "Audit logging: N entries in ops DB, queryable via ops_audit_log"
''')
```

### Sprint 2 Wave 3: minerva 研究增强 (T2.2a-c)

```bash
# T2.2a: UltraRAG 融入 minerva
task(category="quick", description="T2.2a: UltraRAG → minerva pipeline", prompt='''
Integrate UltraRAG retrieval framework into minerva's research pipeline.

1. Find UltraRAG at /Users/xiamingxing/SharedWork/Knowledge/UltraRAG/ (or wherever)
2. Create thin adapter: kairon/packages/minerva/src/minerva/retrieval/ultrarag_adapter.py
   - Wraps UltraRAG's retrieval API
   - Outputs minerva-compatible search results
3. Replace/ Augment minerva's existing retrieval stage with UltraRAG
4. Benchmark: compare retrieval quality (recall@10) before vs after
5. Report: "UltraRAG integrated, recall@10: <before> → <after>"
''')

# T2.2b: 辅助研究模式（人工确认）
task(category="quick", description="T2.2b: Assisted research with human confirmation", prompt='''
Implement an assisted research mode in minerva where research results are presented to human for confirmation before being committed.

1. Create kairon/packages/minerva/src/minerva/pipeline/human_review.py
   - Research pipeline: research → draft → pause → wait for human review → commit or reject
   - Human review interface: CLI or simple script that presents findings
2. Create a simple review script: kairon/packages/minerva/scripts/review_research.py
   - Shows draft title, abstract, key findings
   - Accepts: approve / reject / revise
3. Test: run 1 research query → present results → "approve" → commits to KOS index
4. Report: "Assisted research mode working, human review gate operational"
''')

# T2.2c: minerva pipeline ImmuneAudit + EUPricing
task(category="quick", description="T2.2c: Pipeline audit+pricing stages", prompt='''
Integrate the Phase 1 immune audit and EU pricing into minerva's research pipeline.

1. Read existing: kairon/packages/minerva/src/minerva/pipeline/
2. Ensure research pipeline has these stages in order:
   Research → ImmuneAudit → EUPricing → HumanReview → Commit
3. If stages don't exist, create wrappers that call:
   - sharedbrain-bridge immune audit (from Phase 1)
   - eu-pricing consume (from Phase 1)
4. Test: run pipeline → verify each stage logs correctly
5. Report: "Pipeline stages verified: <N> stages, each logs OK"
''')
```

### Sprint 2 Wave 4: kronos 全格式摄取 (T2.3a-d)

```bash
# T2.3a: MinerU 集成到 kronos
task(category="quick", description="T2.3a: MinerU → kronos doc parsing", prompt='''
Integrate MinerU high-precision document parser into kronos ingestion pipeline.

1. Find MinerU at /Users/xiamingxing/SharedWork/Ecology/MinerU/ (or wherever)
2. Deploy MinerU as a local service (Docker or Python)
3. Create thin adapter: kairon/packages/kronos/src/kronos/parsers/mineru_adapter.py
   - Calls MinerU API to parse PDF/Word/PPT
   - Returns structured text with tables and images preserved
4. Add to kronos 4-layer pipeline as an optional parser (alongside existing parsers)
5. Test: parse 1 complex PDF (tables + images) → verify output quality
6. Report: "MinerU integrated, test PDF parsed: <N> paragraphs, <M> tables extracted"
''')

# T2.3b: Firecrawl MCP 集成
task(category="quick", description="T2.3b: Firecrawl → kronos web scrape", prompt='''
Integrate Firecrawl MCP into kronos web scraping layer.

1. Find Firecrawl MCP at /Users/xiamingxing/SharedWork/MCP/Firecrawl/ (or wherever)
2. Register Firecrawl as an MCP service in Agora
3. Create kronos adapter: kairon/packages/kronos/src/kronos/scrapers/firecrawl_adapter.py
   - Calls Firecrawl via Agora MCP
   - Returns clean markdown
4. Test: scrape 1 dynamic JS-rendered page → verify content
5. Report: "Firecrawl integrated, test URL scraped: <N> chars extracted"
''')

# T2.3d: cron 定时摄取
task(category="quick", description="T2.3d: cron scheduled ingestion", prompt='''
Set up cron-based scheduled ingestion using kairon's cron-service.

1. Read existing cron-service at kairon/packages/cron-service/
2. Create cron job config: kairon/packages/cron-service/config/kronos_ingest.yaml
   - RSS feed scan: every 1 hour
   - File system watch: every 15 minutes
3. Wrap kronos ingest as a callable MCP tool: "kronos_scheduled_ingest"
4. Test: manual trigger → verify pipeline runs
5. Report: "Cron ingestion configured, <N> jobs, manual trigger test: PASS"
''')
```

### Sprint 3 Wave 5: EU 经济 + 免疫全系统化 + 集成验证 (T2.4a-d)

```bash
# T2.4a: Agora EU 路由中间件
task(category="quick", description="T2.4a: Agora EU routing middleware", prompt='''
Implement EU cost routing middleware in Agora. NOT EU pricing logic — just routing.

Read the existing EU pricing package at kairon/packages/eu-pricing/

Create: kairon/packages/agora/src/agora/middleware/eu_router.py

Requirements:
- Before routing MCP calls, call eu-pricing service to check EU balance
- If insufficient, return 402 Payment Required
- After successful MCP call, call eu-pricing to consume EU
- EU costs are configured per tool (not hardcoded in Agora)
- Admin role is exempt from EU checks

Test:
- Normal call: EU consumed correctly
- Insufficient balance: 402 returned
- Admin call: no EU check

Report: "EU router middleware: 3 test scenarios pass"
''')

# T2.4b: agentmesh EU 计价集成
task(category="quick", description="T2.4b: agentmesh EU pricing", prompt='''
Add EU (Energy Unit) cost tracking to agentmesh agent tool calls.

1. Read agentmesh Gateway code at /Users/xiamingxing/Workspace/projects/agentmesh/
2. Create: agentmesh/src/eu-tracker.ts
   - Before agent tool call: check EU balance via Agora
   - After tool call: consume EU via Agora
   - On insufficient EU: stop agent, return error
3. Add EU cost field to agent execution logs
4. Test: run 1 agent with tool calls → verify EU consumed in logs
5. Report: "agentmesh EU tracking: N EU consumed for agent execution"
''')

# T2.4c: gbrain EU 计价集成
task(category="quick", description="T2.4c: gbrain EU pricing", prompt='''
Add EU cost tracking to gbrain memory operations.

1. Read gbrain memory write code at /Users/xiamingxing/Workspace/projects/gbrain-repo/
2. Add EU check before memory writes (create/update)
3. Consume EU after successful write
4. Log EU consumption with memory operation metadata
5. Test: write 10 memories → verify 10 EU consumption entries
6. Report: "gbrain EU tracking: N EU consumed for M memory operations"
''')

# T2.4d: 免疫审计接入 kronos + agentmesh
task(category="quick", description="T2.4d: Immune audit for kronos+agentmesh", prompt='''
Extend immune audit from minerva (Phase C2b) to kronos and agentmesh.

1. kronos: Before committing ingested data to pipeline, run immune audit
   - Flag high-risk content for human review
2. agentmesh: Before agent output is committed to knowledge base, run immune audit
   - Flag high-risk agent outputs
3. Create shared audit wrapper: kairon/packages/minerva/src/minerva/pipeline/audit_wrapper.py
   that any module can call
4. Test:
   - kronos: ingest 1 normal + 1 suspicious content → verify suspicious flagged
   - agentmesh: agent outputs 1 normal + 1 risky → verify risky flagged
5. Report: "Immune audit extended: kronos + agentmesh, 2/2 test scenarios pass"
''')
```

### Sprint 3 Wave 6: 集成验证 + 文档 + 验收 (T2.x-验证)

```bash
# Phase 2 集成验证
task(category="quick", description="Phase2: Integration verification", prompt='''
Run comprehensive integration verification for Phase 2.

1. KOS unified search: query "machine learning" → verify results from code+docs+knowledge
2. minerva assisted research: run 1 research → human confirms → commits to KOS
3. kronos full pipeline: ingest 1 document → parse → audit → price → index
4. RBAC enforcement: Admin can do anything, Agent cannot consume EU
5. EU economy: simulate balance depletion → verify 402 + degradation
6. Immune audit: inject risky content → verify flagged

Each test: report PASS/FAIL with evidence (logs/output)

Report: "Phase 2 integration: <N>/6 tests pass"
''')
```

---

## 📋 Phase 2 验收检查清单

```
Phase 2 最终验收 — Prometheus 执行

□ P2.1 — KOS 知识图谱
  □ GitNexus bridge 索引 3+ 仓库 (verify: kos search returns code entities)
  □ Graphify bridge 索引 10+ 文档 (verify: kos search returns doc entities)
  □ 跨域统一检索: query "auth" → results from 3 domains
  □ 知识共识: 3-agent vote working, confidence scores output

□ P2.2 — minerva 研究增强
  □ UltraRAG integrated, recall improved
  □ 辅助研究模式: human review gate working
  □ Pipeline stages: Research→ImmuneAudit→EUPricing→HumanReview→Commit

□ P2.3 — kronos 摄取
  □ MinerU integrated, complex PDF parsing verified
  □ Firecrawl integrated, dynamic page scraping verified
  □ Vector DB storage for pipeline artifacts
  □ cron scheduled ingestion configured

□ P2.4 — EU 经济全系统化
  □ Agora EU router: 正常消耗 + 余额不足402 + Admin免检
  □ agentmesh EU tracking: agent tool calls consume EU
  □ gbrain EU tracking: memory writes consume EU
  □ EU costs anchored to real API prices (verify: pricing table documented)

□ P2.5 — RBAC 授权
  □ RBAC model documented (.omo/rbac-model.md)
  □ Agora auth middleware: 4 roles enforced
  □ agentmesh Agent permission binding
  □ Audit logging: all deny decisions logged

□ P2.6 — 集成 + 文档
  □ Phase 2 integration: 6/6 tests pass
  □ Performance baseline: P50/P95/P99 recorded
  □ Architecture compliance: 10 laws 0 violations
  □ Health score ≥ 82/100
  □ README/AGENTS.md updated
  □ Phase 2 retrospective → .omo/summaries/phase2-retrospective.md

ALL □ CHECKED → Phase 2 GO → Phase 3
ANY □ UNCHECKED → Phase 2 NO-GO
```
