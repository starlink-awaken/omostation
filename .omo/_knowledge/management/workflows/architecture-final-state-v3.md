---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: architecture-final-state-v3.md
deprecated-since: 2026-06-23

---

# eCOS 最终态架构 v3.0 (依赖分析修正版)

> 2026-06-07 | 基于完整 import 清单的精确分析
> v3.0 修正: shared-lib 非空壳(被4包引用) · 双向依赖 2 处 · 实际只能移动 3 包

---

## 一、精确依赖图

```
                         ┌──────────────┐
                         │     wksp     │ (15K, 仅依赖 agora)
                         │    (用户入口) │
                         └──────┬───────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                        agora (38K, I0 枢纽)                      │
│  依赖: agent-runtime + eidos + kos + minerva + shared-lib        │
│  被依赖: wksp                                                     │
└──┬─────────┬──────────┬──────────┬───────────────┬───────────────┘
   │         │          │          │               │
   ▼         ▼          ▼          ▼               ▼
agent-runt   eidos     kos        minerva      shared-lib
 (20K)      (35K)     (14K)      (25K)          (38K)
   │          │ ↕        │          │               │
   │          └─→kos←───┘          │               │
   │                    ↕          │               │
   └──→llm-gateway←────┘          │               │
        (3K)                      │               │
         │ ↕ ssot(14K)            │               │
         └────→┘                  │               │
                                  │               │
                          engine-core(25K)        │
                          ontoderive(6K)          │
                          └──────→┘               │
                                                  │
                          ┌──────→─────→──────→───┘
                          │
                          ▼
                    自包含 7 包 (无依赖, 无人依赖):
                    cron-service(1.8K)  ecos(4K)  forge(8K)
                    kairon-governance(2.5K)  metaos(6K)
                    sophia(1.4K)  symphony-protocol(1K)
```

---

## 二、每包移动可行性

| 包 | 行数 | 被引次数 | 依赖数 | 移动判定 | 说明 |
|----|------|---------|--------|---------|------|
| **agora** | 38K | 1 (wksp) | 5 | 🔴 可移, 高代价 | 改 5 包接口 (import→MCP) |
| **metaos** | 6K | 0 | 0 | 🟢 可直接移 | 自包含, 独立编排引擎 |
| **wksp** | 15K | 0 | 1 (agora) | 🟡 可移, 低代价 | 只依赖 agora, 迁到 cockpit |
| eidos | 35K | 5 | 1 (kos) | 🔴 不可移 | 被 5 包引用, 双向循环 |
| kos | 14K | 4 | 1 (eidos) | 🔴 不可移 | 被 4 包引用, 双向循环 |
| shared-lib | 38K | 4 | 0 | 🔴 不可移 | 被 4 包引用 |
| minerva | 25K | 3 | 5 | 🔴 不可移 | 双向循环 llm-gateway |
| llm-gateway | 3K | 3 | 2 | 🔴 不可移 | 双向循环 minerva |
| 7 自包含 | ~24K | 0 | 0 | 🟢 可自由移 | 不依赖也不被依赖 |

---

## 三、v3.0 最终方案

### 结论: 只移 3 个包, 其他全不动

```
唯一需要移动的:
  1. agora   → projects/agora/   (38K, 独立 I0 项目, 最高代价)
  2. metaos  → projects/metaos/  (6K, 独立编排引擎, 低代价)
  3. wksp    → cockpit/cli/      (15K CLI, 合并入口, 中代价)

不动 (因依赖闭环无法安全拆分):
  kairon 内 21 包: eidos/kos/shared-lib/minerva/engine-core/ontoderive/
                  ssot/llm-gateway/agent-runtime/iris/kronos/codeanalyze/
                  sophia/symphony-protocol/cron-service/ecos/forge/
                  core-models/health-profile/kairon-governance/
                  sharedbrain-bridge
```

### 最终项目布局 (6 项目, 无新增代码)

```
projects/
├── agora/       ← I0 MCP Hub (从 kairon 拆出)
├── kairon/      ← 知识引擎 (21 包, ~260K)
├── gbrain/      ← 知识数据库 (163K TS)
├── metaos/      ← 编排引擎 (从 kairon 移出)
├── omo/         ← 治理 CLI (15K)
├── runtime/     ← L1 基础设施 (3.7K)
└── cockpit/     ← 统一入口 (wksp CLI + hermes)
```

对比 v2.0: 唯一变化是内部定性更精确, 外部方案一致。

---

## 四、agora 独立的技术分析

agora 是唯一需要大手术的包。当前它 import 5 个 kairon 包:

| import | 用途 | 独立后解决方案 |
|--------|------|--------------|
| `agent_runtime` | 使用其 MCP server | 通过 Agora 自己的 MCP 代理调用 |
| `eidos` | Schema 验证 | 保留为引用 (eidos 不动, agora 通过 MCP 调用) |
| `kos` | 知识存储操作 | 保留为引用, 通过 MCP |
| `minerva` | 研究引擎 | 保留为引用, 通过 MCP |
| `kairon_lib` | 工具函数 | 提取需要的工具到 agora 内部 |

**代价**: 修改 5 个包的接口模式 (import→MCP 调用)。这是 v3.0 方案中唯一具有技术风险的步骤。

---

## 五、三个版本对比

| | v1.0 (冲动版) | v2.0 (调查后) | v3.0 (依赖精确) |
|---|-------------|-------------|--------------|
| 废弃包 | 5 个 | 1 个 | 0 个 |
| 搬家 | 11 条 | 3 条 | 3 条 |
| shared-lib | 拆卸 | 边界标记 | **保留**(被4包引用) |
| 准确度 | ❌ 多处错误 | ⚠️ 部分错误 | ✅ 基于精确import数据 |
| 代价 | ~9 天 | ~5 天 | ~5 天 |
| 新项目 | 5→7 | 5→7 | 5→7 |
