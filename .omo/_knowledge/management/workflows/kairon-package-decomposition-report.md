---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: kairon-package-decomposition-report.md
deprecated-since: 2026-06-23

---

# kairon 包拆解最终分析报告

> 2026-06-06 | 基于全量调查: 24包依赖分析 + gbrain交互 + workspace规模
> 结论: 24包 → 7项目, 但不需要一次性全量重构

---

## 一、最终结论 (一句话)

```
kairon 不需要全量拆包，只需要拆出两类东西:
  1) 不属于它的 (agora → I0，runtime功能 → L1)
  2) 倾倒场 (shared-lib → 解散)
  
拆完后 kairon 保留 ~180K 行知识工程功能，包数量从 24 → ~15。
不需要拆到 12 包 — 知识流水线内部可以留适度冗余。
```

---

## 二、每包的最终判定

### 🔴 必拆 — 不属于 kairon (3 包)

| 包 | 去向 | 理由 | 搬家难度 |
|----|------|------|---------|
| **agora** (38K) | → projects/agora/ | I0 层，在kairon是放置错误 | **高** (所有包依赖它) |
| **cron-service** (1.8K) | → runtime/scheduler/ | L1 定时调度 | 低 |
| **llm-gateway** (3K) | → runtime/llm/ | L1 LLM 抽象 | 低 |

### 🟡 可拆 — 但需要 kairon 内重组 (4 包)

| 包 | 去向 | 理由 | 搬家难度 |
|----|------|------|---------|
| **shared-lib** (38K) | → 解散到 types/utils/各用包 | 倾倒场，无边界 | **高** (38K行散落) |
| **engine-core** (25K) | → events/executor 各用功能拆分 | 事件总线归 runtime，执行归 executor | 中 |
| **agent-runtime** (20K) | → CLI/MCP 归 cockpit，核心归 runtime | 三个不同功能混在一起 | 中 |
| **wksp** (15K) | → cockpit/cli/ | 用户 CLI，不是 kairon 知识功能 | 中 |

### 🟢 不动 — 保留在 kairon (11 包)

| 包 | 行数 | 保留理由 |
|----|------|---------|
| **core-models** | 1.6K | 最底层数据模型 — 所有包的基础 |
| **eidos** | 35K | Schema/本体验证 — 知识工程核心 |
| **ssot** | 14K | 领域知识 SSOT — 知识工程核心 |
| **kos** | 14K | 知识存储/搜索 — 核心 |
| **minerva** | 25K | 深度研究 — 核心 |
| **ontoderive** | 6K | 事实推导 — 核心 |
| **sophia** | 1.4K | 范式编译 — 核心 |
| **kronos** | 2.9K | 摄取 — 核心 |
| **iris** | 8K | 连接器 — 核心 |
| **codeanalyze** | 7K | 代码分析 — 核心 |
| **forge** | 8K | 工具注册 — 保留 (与 kairon 强绑定) |

### ⚫ 待废弃/合并 (5 包)

| 包 | 动向 | 理由 |
|----|------|------|
| **kairon-governance** (2.5K) | → 功能迁移到 omo | 与 projects/omo 重叠 |
| **metaos** (6K) | → 编排功能归 omo | 与 omo 决策/免疫功能重叠 |
| **ecos** (4K) | → 认知功能归 kos | 实质是 kos 的补充 |
| **sharedbrain-bridge** (0.4K) | → **直接废弃** | 空壳 — 通信已通过 Agora MCP |
| **symphony-protocol** (1K) | → 保留不动 | 形式化协议 — 独立职责 |
| **health-profile** (0.2K) | → models 或 cockpit | 太小，可吸收到 core-models |

---

## 三、搬家的相对难度排序 (从易到难)

```
1. sharedbrain-bridge  废弃       0.4K  立即 ─ 不需要搬
2. llm-gateway          → runtime   3K    3h   ─ 低风险
3. cron-service        → runtime   1.8K  2h   ─ 低风险
4. kairon-governance   → omo       2.5K  3h   ─ 功能对齐
5. metaos              → omo       6K    4h   ─ 功能对齐
6. ecos                → kos       4K    3h   ─ 低风险
7. agent-runtime 拆分  → cockpit   8K    6h   ─ 中等风险
8. wksp               → cockpit   15K   6h   ─ 中等风险
9. engine-core 拆分    → runtime   12K   8h   ─ 中等风险
10. shared-lib 解散             38K   16h  ─ 高风险
11. agora 独立                   38K   16h  ─ 最高风险

总计: ~69 hours (~9天)
```

---

## 四、推荐的实施批次

按「先搬不依赖外部、风险低的，最后搬核心依赖」原则：

```
Batch 1 (今天/明天, 5h):
  ✅ sharedbrain-bridge → 废弃
  ✅ llm-gateway → runtime (进口简单, 独立提供者)
  ✅ cron-service → runtime

Batch 2 (2-3天, 10h):
  ⏳ kairon-governance → omo 对齐 (不再有功能重复)
  ⏳ metaos → omo 功能合并
  ⏳ ecos → kos 合并

Batch 3 (3-4天, 14h):
  ⏳ agent-runtime 拆分 → 核心归 runtime, CLI 归 cockpit
  ⏳ wksp CLI → cockpit
  ⏳ engine-core 拆分

Batch 4 (5-7天, 16h):
  ⏳ shared-lib 解散 → 最复杂, 需要全量回归测试

Batch 5 (7-10天, 16h):
  ⏳ agora 独立 → 最后做的, 最难的, 但最重要的
```

---

## 五、不动包的内部调整建议

对于保留在 kairon 的 11 个包，不需要拆，但可以做内部命名规整:

```
kairon/
├── models/          — core-models (基础数据类型)
├── schema/          — eidos (Schema/验证)
├── domain/          — ssot (领域 SSOT)
├── ingestion/       — kronos + iris (摄取+连接器)
├── derivation/      — ontoderive (推导)
├── knowledge/       — kos (存储/搜索)
├── research/        — minerva (深度研究)
├── paradigm/        — sophia (范式)
├── analysis/        — codeanalyze (分析)
├── forge/           — forge (工具注册)
└── protocol/        — symphony-protocol (协议)
```

内部命名调整不涉及任何代码搬家 — 只在 pyproject.toml 里改名。风险为零，可以做。

---

## 六、每个项目的最终包数

| 项目 | 包数 | 代码量 | 职责一句 |
|------|------|--------|---------|
| **projects/agora** | 1 | 15K | MCP 服务发现/路由/代理 |
| **projects/kairon** | 11 | ~180K | 知识工程流水线 |
| **projects/gbrain** | 1 | 163K TS | 知识持久化存储 + 图谱 + 搜索 |
| **projects/omo** | 1 | 15K | 治理面 — 目标/债务/状态/审计 |
| **projects/runtime** | 5 | 25K | 运行时刻 — 调度/LLM/执行/沙箱/事件 |
| **projects/cockpit** | 2 | 12K | 入口 — CLI (Py) + Web (TS) |
| **protocols/** | 1 | — | L0 协议定义 (YAML, 不编译) |
| **.omo/** | — | — | 治理数据 (所有项目共享) |
```

### 一句话总结

> 从 467K/5项目 变成 467K/7项目，不造新代码，只做组织。kairon 从 24 包减到 15 包 (拆出3, 废弃3, kairon内合并3)。代价 ~9 天，收益是跨层依赖清零、kairon 单包平均规模从 12K 降到 10K。



