# Phase 6X: L1/L2/X1/X2 完成化 + X3 规划

> 日期：2026-05-27 | 模式：.omo 治理
> 原则：每位 Wave 必须有验证门禁

---

## 一、战略：为什么要完成这四层

### 现状回顾

基于当前架构方案 (09-个人AI操作系统-最终架构方案.md) 的实施状态：

```
层     4+1+3 中定义    实际状态          缺口
L4     KOS Self Domain  ✅ 已建(Phase 5)  —
L3     KOS Collab       ✅ 已建(Phase 5)  —
L2     能力层           95% ✅             Resource Accounting
L1     契约层           80% ✅             版本化策略+下游验证
X1     治理             75% 🟡             自动化报告+drift闭环
X2     抗熵             35% 🟡             完整cron治理管线
X3     价值堆栈         90% ✅             Strategy文档
P0     workspace CLI    70% ✅             已有profile命令需对接L4
```

**Phase 5 完成了核心新功能（L4 Self/L3 Collab/X3 Consensus）**，但环绕它们的"基础设施层"（L1契约完整化、L2资源计量、X1治理自动化、X2抗熵管线）还没补完。这四个层的缺口加起来大约 **6-8 小时** 工作。

### 为什么现在做

按架构方案，系统由三层+三个横切面构成。L4/L3/X3 是功能核心，但 **L1/L2/X1/X2 是它们能稳定运行的前提**：

| 层 | 缺什么 | 如果不做的后果 |
|----|--------|---------------|
| L1 | 契约版本化+下游验证 | 项目间数据不一致，schema drift 不可检测 |
| L2 | Resource Accounting | Token消耗不可追溯，成本失控 |
| X1 | 自动化治理报告 | arcnode 校准一次后不再更新，治理数据过时 |
| X2 | 完整抗熵管线 | 知识过期无感知，系统自然退化 |

### 战略目标

完成这四个基础设施层，使系统从"能工作"变为"能持续工作"：

```
修复前: P0危急→全线修复 → 能力层稳定 → L4/L3/X3上线
修复后: [L1完备] + [L2计量] + [X1自动化] + [X2抗熵]

最终状态：所有层 ≥ 90%，系统可自我维持
```

---

## 二、战术：每层怎么打

### L1 (契约层): 80% → 100% (~1.5h)

当前已存在：
- Eidos 8个 Schema (identity-role, value-principle, consensus, task-object, epoch-life, identity-envelope, capability-grant, node-type)
- SSOT 规则引擎
- KOS Entity 15种类型

缺失：
1. **版本化策略文档** — 各 Schema 的 version 字段如何演化
2. **SSOT 新增规则** — 验证下游项目是否遵循 Schema
3. **kronos pipeline-schemas.json → eidos 消费** — 消除重复

### L2 (能力层): 95% → 100% (~2h)

当前已存在：
- 全部 10+ 项目运行且测试通过
- 刚完成 P0+P1 修复

缺失：
1. **Resource Accounting 模块** — 在 agentmesh model-orchestrator 或 Agora 中添加 token/cost 追踪
2. **粒度**：每次 MCP 调用记录 caller/service/tokens/cost/billed_to

### X1 (治理): 75% → 100% (~2h)

当前已存在：
- arcnode-calibrate 工具
- 基线 scorecard (75/100)
- SHA256 治理链

缺失：
1. **自动化周报 cron** — 每周一执行 `arcnode report` + 推送到微信
2. **drift → alert 闭环** — 当架构熵超过阈值时自动告警
3. **扩大覆盖面** — 从核心10项目扩展到所有24项目

### X2 (抗熵): 35% → 100% (~2.5h)

当前已存在：
- freshness_check.sh cron ✅
- wksp 的 decay/freshness 概念 ✅
- 保鲜/健康监控/基线对比脚本 ✅

缺失：
1. **完整 cron 管线** — freshness → health → dual-baseline → auto-archive 串联
2. **arcnode-evolve 脚本** — 熵检测+建议+自动修复
3. **自回收规则** — 6个月未触发的保鲜策略自动归档
4. **自动归档执行** — auto-archive 脚本实际工作

### X3 (价值堆栈): 规划 (~1h)

已存在：
- kos/consensus/ 域 (三级共识模型)
- 4个 MCP 工具
- freshness 概念

任务：
- 撰写 `41-X3-价值堆栈策略文档.md`
- 定义 7 个价值层级（Axiom/Principle/Theory/Framework/Knowledge/Skill/Tool）
- 每层级半衰期、保鲜策略、执行者
- 与 X2 cron、L1 Schema、L4 Self 的集成点

---

## 三、执行：Phase → Wave → Task

### Wave L1-1: 契约版本化 (~45min)

| # | 任务 | 文件 | 操作 | 验证 |
|---|------|------|------|------|
| L1-1.1 | 写版本化策略文档 | `~/Documents/学习进化/基建架构/41-L1-契约版本化策略.md` | semver策略+backward/breaking分类+过期规则 | 文档落盘 |
| L1-1.2 | SSOT新增版本验证规则 | `SSOT/tool/ssot-kernel/src/.../patterns/` | 新增 `version_consistency` pattern + 测试 | `pytest test_version -q` |
| L1-1.3 | kronos 消费 eidos schema | `kronos/tests/` + schemas/ | 删除独立pipeline-schemas.json, import eidos | `pytest tests/ -q` |

**波门禁：** `python3 -c "from eidos.schemas.registry import Registry; r=Registry(); assert len(r.list_schemas())>=8"`

### Wave L2-1: Resource Accounting (~2h)

| # | 任务 | 文件 | 操作 | 验证 |
|---|------|------|------|------|
| L2-1.1 | 定义 ResourceAccounting 数据模型 | `agora/.../resource_accounting.py` | CallRecord dataclass(caller/service/tokens/cost_usd/billed_to/timestamp) | import可用 |
| L2-1.2 | 实现 MCP 调用拦截+日志 | `agora/.../middleware.py` | request hook: 记录每次MCP调用的tokens+cost+caller | 拦截日志写入DB |
| L2-1.3 | CLI 查询: cost/top/quota | `agora/.../cli.py` | `agora accounting report --period day` | CLI输出可用 |
| L2-1.4 | 测试+E2E | `tests/` | 模拟MCP调用并验证记录 | `pytest test_accounting -q` |

**波门禁：** `agora accounting top --period day` 返回非空列表

### Wave X1-1: 治理自动化 (~2h)

| # | 任务 | 文件 | 操作 | 验证 |
|---|------|------|------|------|
| X1-1.1 | arcnode report cron | `~/.hermes/scripts/arcnode-weekly-report` | 生成+推送到微信的cron脚本 | `./arcnode-weekly-report --dry-run` |
| X1-1.2 | drift → alert 脚本 | `~/.hermes/scripts/arcnode-drift-alert` | 熵阈值检查+微信推送 | drift超阈时收到告警 |
| X1-1.3 | arcnode validate —all | arcnode CLI扩展 | 验证所有24个项目是否有 ARCH_NODE.yaml | 项目清单 |
| X1-1.4 | 覆盖率合规报告 | 配合 report | 显示当前覆盖率+缺失项目 | 报告≥80%覆盖 |

**波门禁：** `arcnode report --output /tmp/test-report.md` 返回成功+推送微信

### Wave X2-1: 抗熵管线 (~2.5h)

| # | 任务 | 文件 | 操作 | 验证 |
|---|------|------|------|------|
| X2-1.1 | arcnode-evolve 脚本 | `~/.hermes/scripts/arcnode-evolve` | 读取 drift → 分析熵变 → 生成建议 → auto-fix | 运行后熵值稳定 |
| X2-1.2 | cron 管线串联 | 更新各cronjob | freshness → health → dual-baseline → auto-archive 串行 | `watch --diff cron` 所有OK |
| X2-1.3 | auto-archive 实装 | `wksp/scripts/auto-archive` | 实际执行归档操作而非dry-run | 文件被归档 |
| X2-1.4 | 自回收规则实装 | freshness_check.sh + cron | 6个月未触发的保鲜策略暂停 | 检查更新 |

**波门禁：** `freshness_check.sh --json` 返回结构化的保鲜报告JSON

### Wave X3-1: 价值堆栈规划 (~1h)

| # | 任务 | 文件 | 操作 | 验证 |
|---|------|------|------|------|
| X3-1.1 | 写价值堆栈策略文档 | `~/Documents/学习进化/基建架构/42-X3-价值堆栈策略.md` | 定义7层+半衰期+保鲜+执行者+集成点 | 文档落盘 |
| X3-1.2 | X3↔L1 schema 集成分析 | 同上文档 | consensus schema + versioning 如何对接 | 对接图 |
| X3-1.3 | X3↔X2 cron 集成分析 | 同上文档 | freshness 策略如何被X2 cron执行 | 对接图 |

**波门禁：** 文档包含每层的集成点表格

---

## 四、执行顺序与依赖图

```
Day 1 (~3h):
  Wave L1-1 (契约版本化, 45min)
  └→ Wave L2-1 (Resource Accounting, 2h)  [独立, 可并行]
  Wave X3-1 (价值堆栈规划, 1h)  [独立, 可并行]

Day 2 (~3h):
  Wave X1-1 (治理自动化, 2h)  [独立]
  └→ Wave X2-1 (抗熵管线, 2.5h) [部分依赖X1-1的report格式]

总计：~6h 实际工时
```

### 并行策略

```
[Day 1 并行组]
Agent 1: L1-1 契约版本化 (45min)
Agent 2: L2-1 Resource Accounting (2h)  
Agent 3: X3-1 价值堆栈规划 (1h)

[Day 2 并行组]
Agent 1: X1-1 治理自动化 (2h)
Agent 2: X2-1 抗熵管线 (2.5h)
```

---

## 五、完成标准

### 门禁表

| 检查 | 门禁 |
|------|------|
| L1 版本化 | `eidos list-schemas | wc -l` ≥ 8, 每个有 version 字段 |
| L2 Accounting | `agora accounting top --period day` 返回数据 |
| X1 治理报告 | `arcnode report --output /tmp/r.md` + cron 推微信 |
| X2 抗熵管线 | 所有4个cron脚本健康 + `freshness_check.sh --json` 有输出 |
| X3 规划文档 | 文档落盘 + 包含集成点表格 |

### 最终评分目标

| 层 | 当前 | 目标 | Δ |
|----|:---:|:---:|:--:|
| L1 | 80% | **100%** | +20 |
| L2 | 95% | **100%** | +5 |
| X1 | 75% | **100%** | +25 |
| X2 | 35% | **100%** | +65 |
| **加权** | ~71% | **~100%** | +29 |
| **Workspace健康度** | 76/100 | **~85/100** | +9 |

---

## 六、TASK_POOL 更新表

| ID | Task | Wave | 预估 | 状态 |
|----|------|------|:----:|:----:|
| L1-1.1 | 契约版本化策略文档 | L1-1 | 20min | **plan** |
| L1-1.2 | SSOT版本验证规则 | L1-1 | 15min | **plan** |
| L1-1.3 | kronos 消费 eidos schema | L1-1 | 10min | **plan** |
| L2-1.1 | ResourceAccounting 数据模型 | L2-1 | 30min | **plan** |
| L2-1.2 | MCP 调用拦截+日志 | L2-1 | 45min | **plan** |
| L2-1.3 | CLI 查询 | L2-1 | 30min | **plan** |
| L2-1.4 | 测试+E2E | L2-1 | 15min | **plan** |
| X1-1.1 | arcnode report cron | X1-1 | 30min | **plan** |
| X1-1.2 | drift → alert 脚本 | X1-1 | 30min | **plan** |
| X1-1.3 | arcnode validate --all | X1-1 | 30min | **plan** |
| X1-1.4 | 覆盖率合规报告 | X1-1 | 30min | **plan** |
| X2-1.1 | arcnode-evolve 脚本 | X2-1 | 45min | **plan** |
| X2-1.2 | cron 管线串联 | X2-1 | 30min | **plan** |
| X2-1.3 | auto-archive 实装 | X2-1 | 30min | **plan** |
| X2-1.4 | 自回收规则实装 | X2-1 | 45min | **plan** |
| X3-1.1 | 价值堆栈策略文档 | X3-1 | 40min | **plan** |
| X3-1.2 | X3↔L1 集成分析 | X3-1 | 10min | **plan** |
| X3-1.3 | X3↔X2 集成分析 | X3-1 | 10min | **plan** |

**合计：18 tasks，~6h 工时**

---

*方案结束。待你确认后可在 .omo 注册并启动执行。*
