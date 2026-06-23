---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 1 Sprint 执行计划: 基础设施补完

> 日期: 2026-05-29 | 版本: v1.0 | 状态: 待执行
> 路线图依据: `evolution-roadmap-4phases.md`
> 总时长: 5-6 周 (3 Sprints)
> 架构健康目标: 66.80 → 75/100

---

## 红队审查摘要（自分析 + Oracle 待合并）

在对路线图进行对抗分析后，识别出以下关键风险。Phase 1 的任务设计已内化这些缓解措施：

| # | 风险 | 严重性 | Phase 1 中如何缓解 |
|---|------|:------:|---------------------|
| R1 | **单开发者瓶颈**: 在 Python/TS/Rust/Docker 间频繁切换 | 🔴 CRITICAL | Sprint 1 纯 Python → Sprint 2 纯 TS/Rust, 不做交叉 |
| R2 | **Docker 构建失败**: 国内网络无法拉取镜像 | 🔴 CRITICAL | S1.W1 第一任务: 解决 Docker 环境 |
| R3 | **测试环境缺失**: 集成测试需要 4 个系统同时运行 | 🟠 HIGH | S1.W3 专用于集成测试基础设施 |
| R4 | **gbrain 数据迁移风险**: SQLite → memU schema 不兼容 | 🟠 HIGH | S2.W3 先做兼容性验证再迁移 |
| R5 | **SharedWork 代码质量未知**: 直接 integrate 可能引入 bug | 🟠 HIGH | 所有 SharedWork 融入走 "审查→提取→重写" 流程 |
| R6 | **Phase 依赖脆弱**: P1.1 延迟会级联影响 | 🟡 MEDIUM | Sprint 之间有 buffer week |
| R7 | **EU/免疫系统尚未真实运行**: Phase C 代码未在 Docker 中验证 | 🟡 MEDIUM | S1.W2 先做单元级验证再集成 |
| R8 | **LLM 路由未定义**: LiteLLM 与 agentmesh Gateway 的接口契约不存在 | 🟡 MEDIUM | S2.W1 先定义接口契约再实现 |

---

## Phase 1 全景 Sprint 视图

```
            Sprint 1 (2周)                  Sprint 2 (2周)              Sprint 3 (1-2周)
      kairon × SharedBrain 收尾       agentmesh + gbrain 升级        集成验证 + 文档 + 发布
 ┌──────────────────────────┐  ┌──────────────────────────┐  ┌──────────────────────────┐
 │ W1: Docker 环境修复      │  │ W3: LiteLLM 部署 + 适配   │  │ W5: 全系统集成测试      │
 │ W1: core-models 验证     │  │ W3: agentmesh MCP 注册    │  │ W5: 性能基线采集        │
 │ W1: 遗留任务清零          │  │ W4: memU 编译 + 集成     │  │ W5: 架构合规检查        │
 │ W2: 烟雾测试通过          │  │ W4: gbrain 数据迁移      │  │ W6: 文档 + 发布         │
 │ W2: sharedbrain-bridge   │  │                          │  │ W6: Phase 1 验收        │
 │ W2: .omo 文档同步         │  │                          │  │                          │
 └──────────────────────────┘  └──────────────────────────┘  └──────────────────────────┘
           |                            |                            |
     🚦 M1.1 Go/No-Go             🚦 M1.2 Go/No-Go             🚦 M1.GO 最终验收
```

---

## Sprint 1: kairon × SharedBrain 收尾 (2 周)

> **目标**: 完成 Phase A-0/A/B/C 所有遗留工作。Docker 环境可运行。烟雾测试 6/6 PASS。
> **Python 专属 Sprint** — 不涉及 TypeScript/Rust。

### Wave 1.1 — 环境修复 + 验证 (3 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T1.1.1** | Docker 镜像源配置 | Infra | 2h | Docker Hub 不可达 | 配置镜像代理或本地 registry | `docker pull python:3.12-slim` 成功 |
| **T1.1.2** | Docker Compose build + up | Infra | 4h | T1.1.1 | 5 服务全部 healthy | `docker compose ps` 5/5 healthy |
| **T1.1.3** | core-models import 验证 | Dev | 1h | Phase B 适配器 | 3 个 Z-Spore 适配器 import 成功 | `python -c "from nucleus.Z_Spore... import Entity"` |
| **T1.1.4** | registry.yaml 验证 | Dev | 1h | Phase A registry | Agora registry 包含 SharedBrain 20 tools | `agora registry list \| grep sharedbrain` |
| **T1.1.5** | 遗留任务清单清零 | PM | 2h | Phase C 完成状态 | 所有 delegated 器官状态确认 | 4/4 `.organ_status` = delegated |

**Wave 1.1 出口**: Docker 5/5 healthy + core-models 3/3 import OK + registry 20 tools OK

---

### Wave 1.2 — 烟雾测试 + sharedbrain-bridge (4 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T1.2.1** | 烟雾测试：全链路 MCP 连通 | QA | 4h | T1.1.2 | 6/6 测试 PASS | `pytest tests/integration/smoke_test.py -v` |
| **T1.2.2** | sharedbrain-bridge 包骨架 | Dev | 3h | Phase B/C 代码 | `pyproject.toml` + `__init__.py` + 3 submodules | pip install 成功 |
| **T1.2.3** | EU 计价适配器（桥接 eu-pricing → SB D-Economy） | Dev | 6h | eu-pricing 包 | `sharedbrain_bridge.eu` 模块 | MCP 调用消耗 EU 记录到 SB |
| **T1.2.4** | 免疫审计适配器（桥接 immune_audit → SB D-Immunity） | Dev | 6h | immune_audit.py | `sharedbrain_bridge.immune` 模块 | 知识卡片审计 → HIGH 风险标记 |
| **T1.2.5** | 批量同步适配器（桥接 eidos → SB D-Memory） | Dev | 6h | eidos adapters | `sharedbrain_bridge.sync` 模块 | 10 organs 成功同步 |
| **T1.2.6** | sharedbrain-bridge MCP 注册到 Agora | Dev | 2h | T1.2.3-5 | 5 MCP tools 注册 | `agora registry list \| grep sharedbrain-bridge` |
| **T1.2.7** | 集成测试：sharedbrain-bridge 端到端 | QA | 4h | T1.2.1-6 | 端到端测试 5/5 PASS | 含 EU 消耗 + 免疫审计 + 批量同步 |

**Wave 1.2 出口**: 烟雾 6/6 + bridge 包可安装 + bridge 5 tools 注册 + 端到端 5/5

---

### Wave 1.3 — .omo 文档同步 + Sprint 1 回顾 (2 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T1.3.1** | 更新 CONVERGENCE.yaml（SharedBrain 状态） | Doc | 2h | Phase C delegated 器官 | CONVERGENCE.yaml 反映当前融合状态 | 与 SharedBrain 实际状态一致 |
| **T1.3.2** | 更新 LAYER-INDEX.md（新增 sharedbrain-bridge 包） | Doc | 2h | kairon 19 包 | LAYER-INDEX 含所有包 | 包名、层、状态正确 |
| **T1.3.3** | 更新 PROJECTS.yaml（SharedBrain 器官状态） | Doc | 2h | .organ_status 文件 | PROJECTS.yaml 反映 4 delegated 器官 | 与 .organ_status 文件一致 |
| **T1.3.4** | 更新 architecture-final-vision.md（Phase 1 完成状态） | Doc | 2h | 所有完成状态 | 文档反映实际进展 | 与实际代码一致 |
| **T1.3.5** | Sprint 1 回顾 + 复盘 | PM | 2h | 所有完成 | 回顾纪要 → .omo/summaries/ | 8 个问题已回答 |
| **T1.3.6** | **🚦 Sprint 1 Go/No-Go** | PM | 1h | 全部验收条件 | Go/No-Go 决策 | 决策日志 → .omo/decisions/ |

**Sprint 1 Go/No-Go 验收条件:**
- [ ] Docker 5/5 服务 healthy
- [ ] 烟雾测试 6/6 PASS（含 3 故障场景）
- [ ] core-models 3/3 Z-Spore 适配器 import OK
- [ ] Agora registry 含 SharedBrain 20 tools + sharedbrain-bridge 5 tools
- [ ] sharedbrain-bridge `pip install` 成功
- [ ] 共享桥接端到端测试 5/5 PASS
- [ ] 4 个 delegated 器官状态已同步到 SSOT
- [ ] .omo 文档与代码一致

---

## Sprint 2: agentmesh + gbrain 升级 (2 周)

> **目标**: agentmesh 获得 LLM 智能路由。gbrain 获得 Rust 记忆核心。
> **TypeScript/Rust 专属 Sprint** — 不涉及 Python。

### Wave 2.1 — LiteLLM 部署 + agentmesh 网关适配 (3 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T2.1.1** | LiteLLM Docker 部署 | Infra | 3h | LiteLLM repo | LiteLLM 运行，可代理 3+ 模型 | API 调用返回正确模型响应 |
| **T2.1.2** | LiteLLM 模型配置（至少 3 个模型 + 回退链） | Infra | 2h | T2.1.1 | 配置 YAML + 环境变量 | 模型 A 不可达 → 自动回退到模型 B |
| **T2.1.3** | 定义 agentmesh ↔ LiteLLM 接口契约 | Dev | 2h | T2.1.1 | 接口文档 (OpenAPI/TS types) | 团队审查通过 |
| **T2.1.4** | agentmesh Gateway 实现 LiteLLM 路由适配器 | Dev | 8h | T2.1.3 | `gateway/src/adapters/litellm.ts` | 3 种模型自动路由 + 回退 |
| **T2.1.5** | 配额管理模块（余额检查 + 回退逻辑） | Dev | 6h | T2.1.4 | `gateway/src/quota/manager.ts` | 配额 0 → 回退到免费模型 |
| **T2.1.6** | agentmesh 注册 LiteLLM 工具到 Agora | Dev | 2h | T2.1.4-5 | Agora 新增 LLM 路由工具 | `agora registry list \| grep litellm` |

**Wave 2.1 出口**: LiteLLM 代理就绪 + agentmesh 路由 3+ 模型自动回退

---

### Wave 2.2 — agentmesh MCP 生态扩展 (3 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T2.2.1** | Firecrawl MCP 工具注册到 agentmesh | Dev | 3h | Firecrawl MCP | agentmesh 可调用 Firecrawl 抓取 | 网页抓取 → 返回 markdown |
| **T2.2.2** | EdgeOne Pages MCP 工具注册 | Dev | 2h | EdgeOne MCP | agentmesh 可部署页面 | 部署成功 → 返回 URL |
| **T2.2.3** | agentmesh MCP 工具总数扩展 | Dev | 4h | 新增工具 | Agora 注册 agentmesh 30+ tools | 从 22 → 30+ |
| **T2.2.4** | agentmesh Agent 类型从 SharedWork 扩展 | Dev | 8h | SharedWork Agent 框架 | 新增 3+ Agent 类型 (DeepCode-like, etc.) | 新 Agent 类型通过集成测试 |
| **T2.2.5** | agentmesh 集成测试更新 | QA | 4h | T2.2.1-4 | 集成测试 10/10 PASS | 含新工具 + 新 Agent 类型 |

**Wave 2.2 出口**: agentmesh 30+ MCP tools + 3+ 新 Agent 类型 + 集成测试 PASS

---

### Wave 2.3 — memU 集成到 gbrain (4 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T2.3.1** | memU Rust 核心编译 (macOS + Linux) | Dev | 4h | memU repo | `.dylib` + `.so` 动态库 | `file` 确认架构正确 |
| **T2.3.2** | memU ↔ gbrain 接口定义 (FFI/N-API) | Dev | 3h | T2.3.1 | 接口 TypeScript 类型定义 | 编译通过，无类型错误 |
| **T2.3.3** | gbrain memU 后端实现（替代 SQLite） | Dev | 10h | T2.3.2 | `gbrain/src/backends/memu.ts` | 记忆读写走 memU |
| **T2.3.4** | **兼容性验证**: 现有 74 MCP tools 在 memU 后端运行 | QA | 6h | T2.3.3 | 测试报告 | 74/74 tools 兼容 |
| **T2.3.5** | **数据迁移**: SQLite → memU（如果兼容） | Dev | 6h | T2.3.4 | 迁移脚本 + 验证 | 数据完整性 100% |
| **T2.3.6** | 性能对比: memU vs SQLite（延迟 + 吞吐） | QA | 4h | T2.3.4 | 基准报告 | memU P99 < SQLite P99 × 0.5 |
| **T2.3.7** | **降级策略**: memU 不可达 → SQLite fallback | Dev | 4h | T2.3.3 | 降级逻辑 + 测试 | memU 宕机 → 自动回退 SQLite |
| **T2.3.8** | **🚦 Sprint 2 Go/No-Go** | PM | 2h | T2.1-2.3 | Go/No-Go 决策 | 决策日志 |

**Sprint 2 Go/No-Go 验收条件:**
- [ ] LiteLLM 代理 3+ 模型自动路由 + 回退
- [ ] agentmesh Gateway LLM 路由配额管理就绪
- [ ] agentmesh 30+ MCP tools
- [ ] gbrain memU 后端: 74/74 tools 兼容
- [ ] memU P99 延迟 < SQLite × 0.5
- [ ] memU 降级 SQLite fallback 就绪
- [ ] 烟雾测试: agentmesh + gbrain 互调正常
- [ ] 架构合规: 0 违规

---

## Sprint 3: 集成验证 + 文档 + 发布 (1-2 周)

> **目标**: 全系统端到端验证。文档全面更新。Phase 1 正式验收。

### Wave 3.1 — 全系统集成测试 (3 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T3.1.1** | 端到端工作流 1: 研究管道 | QA | 4h | Sprint 1+2 | `wksp research "topic" → pipeline → knowledge card` | 全链路 PASS |
| **T3.1.2** | 端到端工作流 2: Agent 编排 | QA | 4h | Sprint 1+2 | `agentmesh task submit → agentmesh execute → SB task complete → EU consume` | 全链路 PASS |
| **T3.1.3** | 端到端工作流 3: 知识索引 | QA | 4h | Sprint 1+2 | `kronos ingest → minerva research → ontoderive derive → kos index → gbrain memory` | 全链路 PASS |
| **T3.1.4** | 故障注入测试: 5 个故障场景 | QA | 4h | 全系统 | Agora 宕机 / SB 宕机 / memU 宕机 / LLM 不可达 / EU 余额不足 | 各系统正确降级 |
| **T3.1.5** | 压力测试: 10 并发 MCP 调用 | QA | 4h | 全系统 | 延迟报告 + 错误率 | 错误率 < 1%, P99 < 500ms |

**Wave 3.1 出口**: 5/5 端到端工作流 + 5/5 故障场景 + 压力测试通过

---

### Wave 3.2 — 性能基线 + 架构合规 (2 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T3.2.1** | 全系统延迟基线采集 | QA | 3h | T3.1.1-5 | 延迟矩阵（本地 vs Docker） | P50/P95/P99 记录 |
| **T3.2.2** | 吞吐量基线条采集 | QA | 2h | T3.2.1 | 各服务 QPS 上限 | 记录每个服务的饱和点 |
| **T3.2.3** | 架构合规自动检查脚本 | Arch | 4h | 10 条法则 | `check-compliance.sh` | 0 违规 |
| **T3.2.4** | 系统健康评分重算 | PM | 2h | 全系统 | 新 D1-D8 评分 | ≥ 75/100 |
| **T3.2.5** | 安全扫描: 密钥泄露 + 依赖漏洞 | Sec | 3h | 全系统 | 安全报告 | 0 CRITICAL/HIGH |

---

### Wave 3.3 — 文档 + 发布 (2 天)

| ID | Task | Owner | Duration | Input | Output | Acceptance |
|----|------|-------|:--------:|-------|--------|------------|
| **T3.3.1** | README.md 更新 | Doc | 2h | 全系统 | 新 README（架构图 + 快速开始 + 项目列表） | `git clone && make test-all` 可行 |
| **T3.3.2** | AGENTS.md 更新 | Doc | 2h | 全系统 | 开发指南（每个项目的构建/测试/部署） | 新人可按 AGENTS.md 跑通 |
| **T3.3.3** | API 文档自动生成 | Doc | 3h | Agora registry | 所有 MCP 工具文档 | 每条工具有描述 + 参数 + 示例 |
| **T3.3.4** | Phase 1 复盘报告 | PM | 3h | 所有完成 | → `.omo/summaries/phase1-retrospective.md` | 8 个复盘问题已回答 |
| **T3.3.5** | Phase 2 启动准备 | PM | 2h | Phase 1 复盘 | Phase 2 启动检查清单 | Sprint 分解已就绪 |
| **T3.3.6** | **🚦 Phase 1 最终验收** | PM | 2h | 全部验收条件 | 验收报告 + Go/No-Go | 决策日志 |

---

## Phase 1 最终验收条件

```
必须全部通过 (ALL):
□ Docker 5/5 服务 healthy
□ CI 管道: 单元测试 + 构建 + 集成测试 全部通过
□ 全系统 MCP 连通性: kairon → SB → agentmesh → gbrain 全链路
□ agentmesh Gateway 通过 LiteLLM 路由到 3+ 模型
□ gbrain memU 后端 74/74 tools 兼容
□ memU P99 延迟 < SQLite × 0.5
□ 架构合规自动检查 0 违规
□ 安全扫描 0 CRITICAL/HIGH
□ 端到端工作流 3/3 PASS
□ 故障注入 5/5 PASS
□ 压力测试错误率 < 1%
□ 系统健康评分 ≥ 75/100
□ 新人 `git clone && make test-all` 1 次成功
□ README/AGENTS.md/API 文档更新
□ Phase 1 复报告已写

ALL PASS → 🟢 GO to Phase 2
ANY FAIL → 🔴 NO-GO, fix and re-verify
```

---

## 依赖关系图

```
Sprint 1 ──────────────→ Sprint 2 ──────────────→ Sprint 3
│                         │                         │
├─ W1.1 (Docker)         ├─ W2.1 (LiteLLM)         ├─ W3.1 (集成测试)
│  └─→ W1.2 (Tests)      │  └─→ W2.2 (MCP扩展)    │  ├─ 依赖 S1+2 全部
│                         │                         │  └─→ W3.2 (合规)
├─ W1.2 (Bridge)         ├─ W2.3 (memU)            │
│  └─→ W1.3 (Docs)       │  └─ 可并行 W2.1/2.2   │
│                         │                         │
└─ M1.1 Go/No-Go ────────┴─ M1.2 Go/No-Go ────────┴─ M1.GO 最终验收

Sprint 1 内部优先级:
  W1.1 → W1.2 → W1.3 (严格串行: 环境 → 开发 → 文档)

Sprint 2 内部优先级:
  W2.1 + W2.2 → 可并行 (不同开发者)
  W2.3 依赖 W2.1 完成 (需要 Docker 环境部署的 memU)
```

---

## 时间估算

| Sprint | Wave | 任务数 | 预计工时 | 日历日 | 备注 |
|--------|------|:------:|:--------:|:------:|------|
| Sprint 1 | W1.1 | 5 | 10h | 3d | Docker 环境修复可能延迟 |
| | W1.2 | 7 | 29h | 4d | 最重 Wave，并行开发 |
| | W1.3 | 6 | 11h | 2d | 文档为主 |
| | **小计** | **18** | **50h** | **9d** | buffer: 3d |
| Sprint 2 | W2.1 | 6 | 23h | 3d | 部署 + 开发 |
| | W2.2 | 5 | 19h | 3d | 并行 W2.1 |
| | W2.3 | 8 | 39h | 4d | 最重 Wave，含迁移 |
| | **小计** | **19** | **81h** | **10d** | buffer: 2d |
| Sprint 3 | W3.1 | 5 | 20h | 3d | 全手工测试 |
| | W3.2 | 5 | 14h | 2d | 性能 + 合规 |
| | W3.3 | 6 | 14h | 2d | 文档为主 |
| | **小计** | **16** | **48h** | **7d** | buffer: 3d |
| **Phase 1 总计** | | **53** | **~179h** | **~26d** | 含 buffer ~6 周 |
