---
status: archived
lifecycle: plan
owner: 夏明星
created: 2026-08-07
archived: 2026-08-15
superseded-by: docs/STRATEGY-CONVERGENCE-MASTER-2026-08.md
last_updated: 2026-08-18
type: ephemeral
---
# 工作区遗留项目架构战略规划 + 战术落地 Roadmap (2026-08-07)

> 基于全面调研 (12 子模块现状 + 治理体系 + agora 衔接点) 制定。
> 目标: 识别遗留项目, 判定去留, 与 agora P1-P8 能力编排大脑 + 主仓治理体系无缝衔接。

## 一、全面分析

### 1.1 项目健康分类 (调研结论)

| 分类 | 项目 | 判定依据 |
|------|------|---------|
| **健康活跃** (5) | agora, cockpit, omo, ecos, l4-kernel | 指针匹配 + 近期 commit + 测试齐 + BOS 引用密 |
| **遗留候选** (5) | gbrain, kairon, cockpit-ui, model-driven, c2g | 债务/分支滞留/remote 漂移/引用弱 |
| **半活跃** (2) | metaos, runtime | 有 BOS 引用但低活跃 |
| **僵尸** (0) | — | 12 项目均有指针+commit+声明 |

### 1.2 关键断点 (架构衔接裂缝)

| # | 断点 | 严重度 | 证据 |
|---|------|--------|------|
| 1 | **DECL_EXEC_GAP** (声明/执行鸿沟) | **critical** | .omo/debt: maturity 100 但 health 68 |
| 2 | 声明但不可执行 | high | agent-runtime(9)/sot-bridge-persona 包不存在, forge enabled=False |
| 3 | 目录 vs registry 不一致 | medium | 20 目录 vs 17 registry, domain-kems 只剩 uv.lock |
| 4 | 债务未闭环 | high | 10 项未闭 (AGENT_COORDINATION/L1_HEALTH_PROBES/TEST_COVERAGE 等) |
| 5 | BET 推进停滞 | medium | 65 BET 仅 4 done, Y1Q2 起 0 执行 |

### 1.3 遗留项目逐项判定 (照 BET-Y1Q2-T1-02 范式"实测调用链")

| 项目 | 现状 | 建议 |
|------|------|------|
| **gbrain** | 5 天停滞, 无 pytest (bun), BOS 引用 14 | **保留**: 作为 L2 引擎有引用; 补测试框架接入 |
| **kairon** | 主工作卡 work 分支, 14 TODO, BOS 引用 67 (最高) | **优先合入**: 工作分支并主仓, 消指针漂移 |
| **cockpit-ui** | remote 指向归档 hermes-console, 零 BOS 声明 | **归档收敛**: 能力并入 cockpit, 与 hermes-console 先例一致 |
| **model-driven** | .omo/debt + 停滞, BET-Y1Q2-T1-02 判定中 | **执行 BET 判定**: 接主链/降 ecos 内库/归档 三选一 |
| **c2g** | BOS 仅 4 处, 战略入口弱化 | **并入 omo** (BET-Y1Q2-T1-01 范式) |

## 二、架构战略: 衔接策略 (三通道入网)

遗留项目接入 agora 能力编排大脑有**三条通道**, 按项目特性选择:

```
┌─ 通道 1: BOS 声明 ──────────┐  bos-services.yaml + package 可解析
│  (轻量, 能力目录可见)        │  → 适用: 有纯函数/工具的项目
├─ 通道 2: KNOWN_BACKENDS ─────┤  mcp_gateway 注册 stdio 后端
│  (MCP 服务, 进程隔离)        │  → 适用: 有 MCP 入口的项目 (kairon/ecos)
├─ 通道 3: external.resources ─┤  entry-point 聚合能力目录
│  (能力目录, 编排可发现)      │  → 适用: 有 provider 的项目 (agora 188 能力)
└──────────────────────────────┘
```

**判定原则**: 实测调用链 (resolve_bos_uri 可达 + func 可解析 + 参数契约匹配), 非设计意图。

## 三、战术落地 Roadmap (分阶段)

### 阶段 1: 止血 (低风险高价值, 1-2 天)
| 项 | 动作 | 目标 |
|----|------|------|
| 1.1 | **kairon 工作分支合入** | 消指针漂移, BOS 引用 67 真实可达 |
| 1.2 | **domain-kems 归档** | 目录 vs registry 一致 (20→19) |
| 1.3 | **unimplemented 全量登记** | 声明透明度 (agt/iris/apple_mail 补齐) |

### 阶段 2: 治理 (中风险, 2-3 天)
| 项 | 动作 | 目标 |
|----|------|------|
| 2.1 | **DECL_EXEC_GAP 闭环** | registry lint 全量 + 悬空包清理 (agent-runtime/sot-bridge) |
| 2.2 | **gbrain 测试框架接入** | 补 pytest/bun test, 健康分纳入 |
| 2.3 | **debt 优先级闭环** | AGENT_COORDINATION/L1_HEALTH_PROBES 先修 |

### 阶段 3: 收敛 (需判定, 3-5 天)
| 项 | 动作 | 目标 |
|----|------|------|
| 3.1 | **cockpit-ui 归档** | 能力并入 cockpit (hermes-console 先例) |
| 3.2 | **model-driven BET 判定执行** | 接主链/降 ecos/归档 三选一 |
| 3.3 | **c2g 并入 omo** | 减少子模块指针漂移面 |

### 阶段 4: 强化 (持续)
| 项 | 动作 | 目标 |
|----|------|------|
| 4.1 | **声明驱动生成** | 从 bos-services 自动生成测试/文档/mock |
| 4.2 | **BET 推进恢复** | Y1Q2 起 65 BET 执行率 >50% |
| 4.3 | **全链路 trace** | request_id 贯穿 8 层 |

## 四、风险与缓解

| 风险 | 缓解 |
|------|------|
| kairon 工作分支合入冲突 | 先 rebase 到最新 main, 冲突手动解 |
| cockpit-ui 归档丢能力 | 先审计 cockpit 已覆盖, 归档仅 remote 指向 |
| model-driven 判定分歧 | 照 BET-Y1Q2-T1-02 流程, human_gate |
| 悬空包清理误伤 | registry lint 全量校验 + CI 兜底 |

## 五、与现有架构衔接总结

- **不推倒重来**: 12 项目均健康有声明, 战略是"治理 + 衔接"非"重构"
- **三通道入网**: 遗留项目按能力特性接入 agora (BOS/KNOWN_BACKENDS/entry-point)
- **判定照范式**: 实测调用链 (resolve 可达 + func 解析 + 契约匹配), 非设计意图
- **归档有先例**: hermes-console→cockpit-ui, compute-mesh/swarm-engine→aetherforge
- **债务有台账**: DECL_EXEC_GAP critical 首修, 其余按严重度推进

## 阶段 3 实测判定修正 (2026-08-07)

经实测调用链 (BET-Y1Q2-T1-02 范式) 复核, 三个收敛项全部修正:

| 项目 | 原判 | 实测 | 修正决策 |
|------|------|------|---------|
| cockpit-ui | 归档 | 已在 L3 架构 (cockpit 前端表现层, COCKPIT_UI_ROOT/DIST env 挂载), remote 名是历史 hermes-console | **保留** (架构内, 无需归档) |
| model-driven | BET 判定中 | 活跃 (pyright sweep) + 被消费 (agora BOS 2 服务 + cockpit coverage 列生命周期/OKR) | **保留接主链** |
| c2g | 并入 omo | 活跃 (ruff/pyright sweep) + X 层战略需求引擎 (V2P→C2G) 独立定位 | **保留独立** |

**治理价值**: 避免误归档活跃项目 — 判定用实测调用链 (BOS 声明/被消费/维护活跃), 非设计意图或低引用假设。
