# Phase 12 Wave 1 执行计划：能力生态元模型 + 核心扫描基线

> 日期: 2026-06-01 | 状态: completed
> 包名: P12-W1-METAMODEL-SCAN
> 入口: Phase 11 所有 Wave 关闭 + 健康分 ≥97
> 目标: 定义能力生态的元模型和基础协议，完成核心 workspace 能力扫描基线

---

## G12.1.1 — 能力生态元模型设计

**目标**: 定义 Capability/Skill/Tool/Plugin/Connector 5 种能力类型的元模型及其注册协议

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T1.1 | 设计 Capability 元模型 | 定义 5 种能力类型 (Capability/Skill/Tool/Plugin/Connector) 及其 Schema，包含 id/type/protocol/entrypoint/lifecycle/scenario_tags | `.omo/standards/capability-metamodel.md` | 模型可实例化，5 种类型各有完整定义 |
| T1.2 | 设计能力声明文件格式 | `capabilities.yaml` 格式定义，包含所有必填和可选字段，附带 JSON Schema | `capabilities.schema.yaml` | 验证所有字段通过 Schema 校验 |
| T1.3 | 设计全局注册表结构 | 注册表目录 `.omo/registry/` 及其子目录 capabilities/packages/connectors/scenarios 结构 | `.omo/registry/INDEX.md` | 目录创建可用，索引可读 |
| T1.4 | 设计场景定义格式 | `scenario.yaml` 格式定义，场景描述 + 能力绑定 + 数据流声明 | `scenario.schema.yaml` | 验证场景格式通过 Schema 校验 |
| T1.5 | 设计能力发现/注册 CLI | `omo capability scan/register/discover/bind` CLI 命令规范 | `omo capability --help` 输出规范 | CLI 可通过，显示完整命令列表 |

**依赖**: 无（本 Wave 起始任务）

**风险**: 元模型过度设计 → MVP 仅 5 个核心字段，先运行再优化

---

## G12.1.2 — 核心能力扫描基线

**目标**: 扫描 workspace 内核心可注册能力单元；SharedWork 只做分类抽样，不做全量融合承诺。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T1.6 | `projects/` 核心扫描 | 识别 kairon、agentmesh、gbrain、SharedBrain 下核心可注册能力单元 (包/模块/CLI/MCP 工具) | `registry/projects-capabilities.yaml` | ≥50 个能力注册项 |
| T1.7 | `SharedWork/` 分类抽样 | 23 分类项目只做分类抽样和候选标注，未选项进入 Phase 14 backlog | `registry/sharedwork-sample.yaml` + `phase14-deferred-ecosystem-backlog.md` update | ≥10 项目有抽样记录，未选项有 backlog/exclusion reason |
| T1.8 | 系统包生态扫描 | 执行 uv/brew/npm/pip/cargo `list --installed`，汇总所有依赖包 | `registry/system-packages.yaml` | 包生态清单完整，版本号记录 |
| T1.9 | Agent CLI 审计 | 收集所有 CLI 工具名称、参数、功能描述，包括 wksp/omo/hermes/各项目 CLI | `registry/agent-clis.yaml` | CLI 清单完整，含功能描述 |
| T1.10 | CLI 统一入口设计 | 设计 `wksp` CLI 作为主入口的方案，含子命令树和迁移路径 | `design/cli-unification-plan.md` | 方案评审通过，路径图清晰 |

**依赖**: T1.1-T1.5 元模型定稿后开始

**风险**: SharedWork 项目量大 → Phase 12 只做抽样和候选标注，深度融合进入 Phase 14

---

## 交付物清单

```
.omo/
├── standards/
│   ├── capability-metamodel.md           ← 能力元模型
│   └── scenario.schema.yaml              ← 场景 Schema
├── registry/
│   ├── INDEX.md                          ← 注册表索引
│   ├── projects-capabilities.yaml        ← projects/ 能力
│   ├── sharedwork-sample.yaml            ← SharedWork 抽样能力
│   ├── system-packages.yaml              ← 系统包
│   └── agent-clis.yaml                   ← Agent CLI
└── design/
    └── cli-unification-plan.md           ← CLI 统一方案
```

---

## Exit Gate

- [x] 能力元模型定稿 (Capability/Skill/Tool/Plugin/Connector 5 种类型完整定义)
- [x] 注册表结构可用 (`registry/` 目录就绪，INDEX.md 可读)
- [x] 核心扫描完成 (≥50 能力注册，SharedWork ≥10 项抽样)
- [x] CLI 统一方案通过评审
- [x] 每任务交付物通过验证标准
