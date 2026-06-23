---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 知识基座项目复盘

## 项目概览

**时间**: 2026-05-19 ~ 2026-05-21  
**目标**: 构建三层分离的知识基座架构: `Eidos(定义) → KOS(存取) → OntoDerive(推理)`  
**状态**: Phase 1 ✅ + Phase 2 ✅ 完成

---

## 交付清单

### Phase 1 — 基础层

| 交付物 | 状态 | 说明 |
|--------|------|------|
| `.omo/` 管理目录 | ✅ | INVENTORY / AUDIT / ARCH-REVIEW / KNOWLEDGE_ARCH |
| KOS 迁移 Tools/ → kos/ | ✅ | 88 files, .venv, git intact |
| Gateway 项目 | ✅ | 3 MCP wrappers |
| Agent CLI 配置 | ✅ | Claude Desktop, hermes, .zshrc |
| 临时文件清理 | ✅ | ~415MB + 29,131 files |
| Pallas 依赖修复 | ✅ | pyproject.toml optional deps |
| BOS-Skill-CLI MVP | ✅ | 3 features, 27 tests, 77% coverage |
| Sophia 测试扩展 | ✅ | 27 → 87 tests |
| Eidos 项目 | ✅ | Schema/Validator/CLI/23 tests, zero deps |
| KOS ingest 命令 | ✅ | 46,075 files indexed (45,890 KnowledgeCards + 185 RawDocuments) |
| Eidos↔KOS 集成测试 | ✅ | 3 集成测试, 全部通过 |

### Phase 2 — 适配器层

| 交付物 | 状态 | 说明 |
|--------|------|------|
| OntoDerive Eidos Adapter | ✅ | FormalFact/Entity ↔ Eidos Fact/OntologyNode 双向映射 |
| OntoDerive `derive --eidos` | ✅ | 推理结果 Eidos 格式输出 |
| Minerva Eidos Adapter | ✅ | ResearchResult → KnowledgeCard, Entity → OntologyNode |
| Minerva `research --eidos-output` | ✅ | 研究结果导出为 Eidos JSON |
| Agora Eidos 服务注册 | ✅ | `agora register eidos` protocol test |
| Phase 2 集成测试 | ✅ | .omo/tests/test_phase2_integration.py (5 tests) |
| 架构文档更新 | ✅ | ../reference/KNOWLEDGE_ARCH.md Phase 2 章节 |

---

## 架构现状

```
                   ┌──────────────────┐
                   │     Agora        │  服务路由/注册
                   │   v1.5.0         │
                   └──────┬───────────┘
                          │ MCP
      ┌───────────────────┼───────────────────┐
      │                   │                   │
      ▼                   ▼                   ▼
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Eidos   │◄───►│    KOS       │◄───►│  OntoDerive  │
│ v0.1.0   │     │  (Storage)   │     │  v3.5.0      │
│ Schema   │     │  46k 已索引  │     │  FormalPipeline│
│ Validator│     │              │     │  推理引擎    │
│ CLI      │     │              │     │              │
└────┬─────┘     └──────────────┘     └──────────────┘
     │
     ▼
┌──────────┐
│ Minerva  │  研究结果→KnowledgeCard
│ v0.11.0  │
└──────────┘

数据流:
  Define (Eidos Schema)
    → Store (KOS ingest/search)
      → Reason (OntoDerive derive --eidos)
        → Route (Agora register/discover)
          → Research (Minerva --eidos-output)
```

---

## What Went Well

### 1. 三层分离设计落地
从概念论证到可运行代码，Eidos（定义）/KOS（存取）/OntoDerive（推理）三层明确分离，零硬依赖，适配器通过 `try/except ImportError` 保持可选。

### 2. 并行执行策略有效
Wave 1 双线并行（OntoDerive + Minerva 适配器），Wave 2 三线并行（Agora + CLI flag × 2），整体用时比串行节省约 60%。

### 3. 46k 文件全量索引
KOS ingest 成功处理 46,075 个文件，100% 成功率，0 跳过。验证了大规模知识注入的可行性。

### 4. 代码质量把控
- Eidos: 23 tests, zero external dependencies
- 所有适配器均设 `EIDOS_AVAILABLE` 标志
- Final Verification Wave (Oracle 审查) 发现并修复了 None 守卫、字段映射、未使用 import 等问题

---

## What Could Be Improved

### 1. 计划文件与实际执行的脱节
Phase 1 和 Phase 2 的详细计划 (`knowledge-foundation.md`, `knowledge-foundation-phase2.md`) 在执行过程中未及时更新 checkbox，导致 boulder 系统反复触发续接提示。

**根因**: 执行节奏快（并行 Wave），注意力集中在编码和验证，忽略了 plan 文件的同步更新。  
**改进**: 每完成一个 Wave 就立即更新 plan checkbox，不要留到最后批量处理。

### 2. Background Task 超时问题
两次 `deep` category 的 background task 都因 45 分钟无活动超时取消，改用同步 `quick` category 后 1-6 分钟完成。

**根因**: `deep` agent 在复杂跨项目任务中可能陷入循环或过度研究。  
**改进**: 对于跨项目适配器类任务，使用 `quick` category + 详细 prompt 比 `deep` + 开放式 prompt 更可靠。

### 3. Oracle API 不稳定
Final Verification Wave 的 4 个 Oracle 审查者全部首次失败（OpenAI GPT-5.5 API error），fallback 到 GitHub Copilot 后成功。

**根因**: OpenAI API 临时故障，非系统问题。  
**改进**: 高优使用 GitHub Copilot 作为 Oracle 默认，减少 API 故障风险。

### 4. PYTHONPATH 不一致
不同项目的 PYTHONPATH 设置不一致（`src/` 布局 vs 非标准布局），导致验证命令时出错。

**根因**: `ontoderive` 项目使用 `engine/` 根目录而非标准 `src/` 结构。  
**改进**: 项目级 `.python-version` + 统一 Path 约定，或通过 `pip install -e .` 统一安装后验证。

---

## 技术债务

| 项目 | 债务类型 | 优先级 | 说明 |
|------|---------|--------|------|
| KOS | 架构 | LOW | 大量未使用的 CLI 命令（~80个 stub）待清理 |
| OntoDerive | 结构 | LOW | `engine/` 非标准目录布局 |
| Minerva | 覆盖 | MED | 适配器无单元测试（仅集成测试） |
| Eidos | 覆盖 | LOW | CLI test 覆盖率可提升 |

---

## 数据统计

```
Phase 1
├── Commits:          ~8
├── Files created:    25+ (eidos 15, kos 2, .omo 8)
├── Tests added:      38 (eidos 23 + kos ~15)
├── Files indexed:    46,075
└── Duration:         2 天

Phase 2
├── Commits:          ~7
├── Files created:    7
│   ├── ontoderive:   eidos_adapter.py
│   ├── minerva:      eidos_adapter.py
│   ├── agora:        test_eidos_service.py
│   ├── .omo:         test_phase2_integration.py
│   └── .omo/plans:   knowledge-foundation-phase2.md
├── Files modified:   3 (cli.py × 2, ../reference/KNOWLEDGE_ARCH.md)
├── Tests added:      8 (integration 5 + agora 3)
└── Duration:         1 天

合计:
├── 文件:             35+ 新增 / 3 修改
├── 测试:             46
├── 知识文件索引:     46,075
├── 项目:             6 (eidos, kos, ontoderive, minerva, agora, gateway)
└── 总用时:           3 天
```
