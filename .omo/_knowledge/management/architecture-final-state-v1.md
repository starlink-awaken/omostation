---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# eCOS/omostation 最终态架构设计

> 2026-06-06 | 版本: v1.0-final-state
> 范围: 467K 行 → 7 个项目 · 5+3+1 严格分层
> 原则: 不保留历史包袱，从干净状态重新设计
> 历史最终态设计提案 / reference only。本文是阶段性目标架构草案，不是当前项目布局、当前代码规模、当前层间归属或当前执行真相 SSOT。
> 当前架构与项目事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、`/.omo/standards/eCOS-v6-Architecture-Alignment.md`。

---

## 零、设计原则

```
1. 层内高内聚，层间松耦合 —— 相同责任的代码在同一个项目里
2. 依赖只向下，不向上、不横向 —— L3 不能依赖 L2，L2 不能依赖 L1
3. 跨语言边界以 MCP 为唯一协议 —— Python ↔ TypeScript 只通过 MCP
4. 治理是第一公民 —— OMO 体系覆盖所有项目的运行态
5. 可观测性内建 —— 日志/事件/监控/成本在每个关键节点自动产生
6. 入口统一 —— 所有交互聚合到 entry-bridge，不提供碎片化入口
```

## 一、项目布局 (7 个项目)

```
Workspace/
├── projects/
│   ├── agora/              — I0 集成织层 (Python, 从 kairon 拆出)
│   ├── kairon/             — L2 知识工程引擎 (Python, 精简单体)
│   ├── gbrain/             — L4 知识大脑 (TypeScript, 不变)
│   ├── omo/                — L2 治理面 (Python, 从 root 移入)
│   ├── runtime/            — L1 运行时基础设施 (Python, 从 kairon 吸收)
│   └── cockpit/            — L3 统一入口 + P0 产品 (TypeScript, 合并)
│
├── .omo/                   — 治理数据层 (所有项目共享)
└── protocols/              — L0 协议定义 (独立于任何项目)
```

---

## 二、逐层设计

### L0 — 协议编织层

```
位置:     protocols/ (独立于所有项目)
职责:     协议定义、版本管理、模型验证
包含:     16 个协议 YAML 定义 + 运行时验证
实现:     Python dataclass + PyYAML

当前状态-已在-runtime/protocols/下。
最终态:   独立于 runtime，因为协议属于全局规范层，不归任何运行时所有。
```

### L1 — 运行时基础设施 (runtime / 当前 3.7K → 目标 25K)

```
当前:     只有 3.7K 行，承担服务注册/健康/AI 沙箱/协议管理
问题:     太薄。很多运行时功能还在 kairon 里。

吸收来源:
  kairon/cron-service(1.8K)      → 定时任务调度
  kairon/agent-runtime/core(8K)  → 任务执行引擎(engine/tools/config)
  kairon/llm-gateway(3K)         → LLM 提供者抽象
  kairon/engine-core 部分(8K)    → 事件总线/重试策略

最终结构:
  runtime/
  ├── src/runtime/
  │   ├── registry/       — Matrix 服务注册表
  │   ├── scheduler/      — 定时任务调度 (原 cron-service)
  │   ├── health/        — 健康监控 + 自动修复
  │   ├── executor/      — 通用任务执行器 (原 agent-runtime 核心)
  │   ├── llm/           — LLM 提供者 (原 llm-gateway)
  │   ├── sandbox/       — KEI 安全沙箱
  │   ├── events/        — 事件总线
  │   ├── protocol/      — 协议加载/验证
  │   └── cli.py         — runtime CLI (已有)
```

```
职责边界:
  ✅ runtime 做: 服务注册、任务调度、LLM 调用、安全沙箱、事件分发
  ❌ runtime 不做: 知识处理、MCP 路由(归 agora)、治理决策(归 omo)
```

### L2 — 治理平面 OMO (15K → 不变)

```
当前:     在 root repo 的 projects/omo/ 下
问题:     物理位置在 root git 仓库内，不是独立项目

最终态:   独立 project，有独立建树/测试契约

职责:
  - 目标管理 (Phase goals)
  - 债务追踪 (debt registry)
  - 状态管理 (state/system.yaml)
  - 标准管理 (standards/)
  - 知识面管理 (_knowledge/)
  - 交付物管理 (_delivery/)

接口:
  - omo CLI: 37 子命令，覆盖所有平面
  - omo MCP: FastMCP 服务器，供其他系统查询治理状态
  - 数据: .omo/ 目录为唯一 SSOT
```

### L2 — 知识工程引擎 kairon (300K → ~80K)

```
当前:     300K 行，24 包，4 个层的功能混在一起
问题:     I0(agora) 在这里，L1 运行时功能在这里，数据模型在这里，倾倒场在这里

精简后:   只保留知识工程专精功能，其他迁移到对应层

最终包结构 (12 包):
  L0 层 (kairon 内的数据模型):
    kairon/types/       — 实体/关系/溯源模型 (原 core-models)
    kairon/domain/      — 领域 SSOT (原 ssot)
    kairon/utils/       — 共享工具 (从 shared-lib 提取)

  L2 层 (知识工程流水线):
    kairon/ingestion/   — 摄取 (kronos + iris)
    kairon/derivation/  — 推导 (ontoderive)
    kairon/research/    — 研究 (minerva)
    kairon/paradigm/    — 范式编译 (sophia)
    kairon/storage/     — 知识存储 (kos + eidos 存储部分)
    kairon/analysis/    — 代码分析 (codeanalyze)

  L3 层 (治理 + 连接):
    kairon/governance/  — 巡检/ADR/路由 (瘦身, 只做 kairon 内部治理)
    kairon/bridge/      — sharedbrain 桥接

  废弃迁移:
    agora          → projects/agora/
    agent-runtime  → runtime/executor/
    cron-service   → runtime/scheduler/
    llm-gateway    → runtime/llm/
    shared-lib     → types + utils + 各包
    wksp           → cockpit/
    forge          → 保留
    metaos         → governance/
    symphony       → 保留
    eidos          → types + storage
    codeanalyze    → analysis
```

### I0 — 集成织层 Agora (38K → ~15K 精简后独立项目)

```
当前:     在 kairon/packages/agora 内，38K 行，90+ 文件
问题:     放错位置 + 职责过载

最终态:   projects/agora/ (独立项目)

职责 (精简后):
  ✅ MCP 服务注册与发现
  ✅ MCP 请求路由与代理
  ✅ 服务健康检查
  ✅ 事件总线 (EventBus)
  ✅ A2A 任务管理 (Agent-Agent)
  ❌ Web dashboard (→ cockpit 项目)
  ❌ CLI 工具 (→ kairon CLI)
  ❌ 治理审计 (→ omo)

实现方式:
  - 所有跨层/跨包的 MCP 调用必须经过 agora
  - 各包向 agar 注册 MCP 入口，不暴露独立端口
  - agora 提供 stdio + HTTP + SSE 三种传输
```

### L3 — 统一入口 cockpit (当前 16K+ → ~12K)

```
当前:     wksp(15K) + hermes-console(1.4K) + runtime MCP = 三个碎片

最终态:   projects/cockpit/ (TypeScript + Python 混合)

组成:
  cockpit/
  ├── cli/           — Python CLI (从 wksp 保留研究/知识/数据管理)
  ├── mcp/           — MCP server for AI agents (原 runtime MCP)
  ├── web/           — TypeScript Vite (原 hermes-console 重启)
  └── bridge/        — TaskObject 路由 (L3 专属)
```

### 各层边界总览

```
┌─────────────────────────────────────────────────────────┐
│                L3 统一入口 cockpit                       │
│   workspace CLI | MCP Server | Web Dashboard            │
└─────────────┬───────────────────────────┬───────────────┘
              │                           │
     ┌────────▼───────┐           ┌───────▼──────────┐
     │  L2 OMO 治理    │           │  L2 kairon 引擎  │    L2 gbrain 记忆
     │  goals/debt/   │           │  12 包知识处理    │    163K TS
     │  state/standards│          │                   │
     └────────┬───────┘           └───────┬───────────┘
              │                           │
              └───────────┬───────────────┘
                          │
                  ┌───────▼──────────┐
                  │  I0 Agora 织层   │  ←─ 所有跨层通信的唯一通道
                  │  服务发现/路由/事件│
                  └───────┬──────────┘
                          │
                  ┌───────▼──────────┐
                  │  L1 runtime 运行 │
                  │  调度/执行/LLM/沙箱│
                  └───────┬──────────┘
                          │
                  ┌───────▼──────────┐
                  │  L0 protocol 协议│
                  │  16 协议定义+验证  │
                  └──────────────────┘
```

---

## 三、迁移路径: 4 个里程碑

### M1: agora 独立 (拆出 38K)

```
前置条件: 无
操作:     kairon/packages/agora → projects/agora/
          agora 不再 import kairon 内部包
          所有需要从 kairon 获得的功能改为协议化: MCP tools

风险:     高 (所有包依赖 agora 注册)
时间:     2-3 天
产出:     projects/agora/ (独立 Python 项目)
```

### M2: runtime 增厚 (吸收 L1 功能)

```
前置条件: M1 完成
操作:     kairon/cron-service → runtime/scheduler/
          kairon/llm-gateway → runtime/llm/
          kairon/engine-core → runtime/events/ + runtime/optimize/
          kairon/agent-runtime/core → runtime/executor/

风险:     中 (大量 import 需要更新)
时间:     3-4 天
产出:     runtime 从 3.7K → 25K, kairon 从 300K → 270K
```

### M3: kairon 重组 (内部分层)

```
前置条件: M1 + M2 完成 (不依赖外部的 fork)
操作:     shared-lib → 解散
          eidos → types + storage
          ssot → domain
          (其余调整为最终包结构)

风险:     高 (shared-lib 38K 行需要慎重维护 import)
时间:     3-5 天
产出:     kairon 内部分层明确, 12 个包, ~80K 行
```

### M4: cockpit 启动 (统一入口)

```
前置条件: M1 + M2 完成
操作:     hermes-console → 修复构建
          wksp CLI 核心 → cockpit/cli/
          runtime MCP → cockpit/mcp/
          创建统一 index 页

风险:     低
时间:     2-3 天
产出:     projects/cockpit/ (Python CLI + TS Web)
```

---

## 四、关键决策记录

| # | 决策 | 选项 | 最终选择 | 理由 |
|---|------|------|---------|------|
| ADR-1 | agora 放哪里 | kairon 内 vs 独立项目 | **独立项目** | 它是 I0 层, 不是 L2 层 |
| ADR-2 | gbrain 是否换成 Python | 是 vs 否 | **保持 TS** | 163K 行重写不可行, 边界已清晰 |
| ADR-3 | wksp 保留还是废弃 | 保留 vs 废弃 | **保留 CLI, 合并到 cockpit** | 15K 行产品代码有价值 |
| ADR-4 | shared-lib 怎么拆 | 保留 vs 解散 → 3 个目 标包 | **解散** | 倾倒场, 无边界, 长期负债 |
| ADR-5 | 跨语言通信 | MCP vs REST vs gRPC | **MCP** | 已经在用, 协议工具/资源, 与 agent 生态一致 |

---

## 五、对比快照

| 维度 | 当前 (06-06) | M1 后 | M2 后 | M3 后 | M4 后 (最终态) |
|------|------------|-------|-------|-------|----------------|
| 项目数 | 5 | 5 | 5 | 5 | **7** |
| kairon  | 300K (24 包) | 262K | 238K | **80K (12 包)** | 80K |
| agora   | kairon 内 | **独立** | 独立 | 独立 | 独立 |
| runtime | 3.7K | 3.7K | **25K** | 25K | 25K |
| 总数    | 467K | 467K | 467K | 467K | 467K |
| 跨层指向违规 | 5 处 | 2 处 | 0 处 | 0 处 | 0 处 |
| 跨语言边界 | MCP(正常) | MCP | MCP | MCP | MCP |
| CLI  | 碎片化 | 碎片化 | 碎片化 | 碎片化 | **cockpit 统一** |
