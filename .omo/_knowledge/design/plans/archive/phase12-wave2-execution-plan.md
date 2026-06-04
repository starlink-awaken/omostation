# Phase 12 Wave 2 执行计划：注册表启用 + 场景 MVP + pilot ADR

> 日期: 2026-06-01 | 状态: completed
> 包名: P12-W2-REGISTRY-SCENARIO-PILOT-ADR
> 入口: Wave 1 元模型定稿 + 核心扫描完成 (≥50 注册)
> 目标: 注册表实际启用 + 首个场景可运行 + P0 融合 pilot 选择

---

## G12.2.1 — P0 融合 pilot ADR

**目标**: 在 LiteLLM 和 memU 中选择一个 Phase 12 pilot；未选项进入 Phase 14 backlog。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T2.1 | P0 pilot selection ADR | 对 LiteLLM → agentmesh Gateway 与 memU → gbrain 记忆后端做价值/风险/接口成熟度评估，选择 1 个进入 Wave 3 | `.omo/plans/phase12-p0-pilot-adr.md` | ADR 明确 winner、non-winner backlog、rollback plan |
| T2.2 | Pilot interface contract | 为选定 pilot 写最小接口契约和 smoke path | `registry/pilot-contract.yaml` | 契约能被 schema 校验 |
| T2.3 | Non-selected P0 backlog | 将未选 P0 项登记到 Phase 14 backlog | `phase14-deferred-ecosystem-backlog.md` update | backlog 中有明确 deferred reason |

**依赖**: Wave 1 元模型定稿

**融合深度**: Wave 2 只做 ADR 和契约，不做深度吸收。

---

## G12.2.2 — 注册表启用

**目标**: 注册表工具链可用，首个场景定义并运行

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T2.4 | 能力注册工具链 | 实现 `omo capability register` 批量注册脚本，支持 yaml 文件导入和交互式注册 | 注册 CLI 生产可用 (`wksp/pkg/registry/`) | 批量注册 50 个能力 ≤10s |
| T2.5 | 能力发现 UI | 注册表 Web 浏览界面，支持按类型/标签/状态过滤 | `omo registry browse` 或 Web UI | 可浏览所有注册能力 |
| T2.6 | 首个场景定义 | 定义 `research-pipeline` 场景 (kronos→ontoderive→minerva→gbrain) | `scenarios/research-pipeline.yaml` | 场景编排可通过 I0 执行 |

**依赖**: T2.1-T2.3 完成 (P0 融合为场景提供基础能力)

---

## G12.2.3 — 技术文章知识化启动

**目标**: 建立技术文章采集管道，首批 30 篇文章入库

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T2.7 | 技术文章 ingestion policy | 定义外部文章来源、版权/保留策略、质量评分、样例入库规则 | `.omo/standards/article-ingestion-policy.md` | policy 覆盖来源、去重、引用、保留、质量阈值 |
| T2.8 | 文章结构化样例 | 定义文章元信息 + 摘要 + 关键观点样例 schema | `registry/article-samples.yaml` | 5 条样例可校验 |
| T2.9 | Phase 14 expansion backlog | 将批量文章入库和知识图谱扩张移入 Phase 14 | `phase14-deferred-ecosystem-backlog.md` update | backlog 有 article expansion workstream |

**依赖**: T1.7 (SharedWork 扫描) 确定文章源

**质量过滤**: 自动摘要 + 质量评分 (相关性/原创性/深度) ≥70 分才入库

---

## 交付物清单

```
.omo/
├── scenarios/
│   └── research-pipeline.yaml            ← 首个场景
├── registry/                             ← 注册表启用
│   ├── pilot-contract.yaml               ← P0 pilot 契约
│   └── article-samples.yaml              ← 文章样例
├── plans/
│   └── phase12-p0-pilot-adr.md           ← pilot 选择 ADR
└── standards/
    └── article-ingestion-policy.md       ← 外部文章知识化策略
```

---

## Exit Gate

- [x] P0 pilot ADR 完成，只选择 1 个 Wave 3 pilot
- [x] 注册表工具链可用 (`omo capability register/discover`)
- [x] 首个场景 `research-pipeline` 可运行
- [x] 文章 ingestion policy + 5 条样例完成
- [x] 未选 P0 和批量文章入库进入 Phase 14 backlog
