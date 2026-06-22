---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Workspace 级架构诊断 (全系统视角)

> 2026-06-06 | 467K 行 · 5 个项目 · 2 种语言
> 范围: kairon/ omo/ runtime/ gbrain/ hermes-console

---

## 一、全系统规模

```
PROJECT          LINES     LANG      %     ROLE
─────────────────────────────────────────────────
gbrain           163,226   TS       35%   L4 知识大脑
kairon           299,095   Python   64%   L1-L3 知识工程+基础设施
omo               15,370   Python    3%   L2 治理面
runtime            3,723   Python    1%   L1 运行时矩阵
hermes-console     1,425   TS        0%   L3 入口 + P0 产品
─────────────────────────────────────────────────
TOTAL            467,839
```

---

## 二、5+3+1 映射 - 当前 vs 理想

```
架构层    当前物理位置               理想位置               问题
────────────────────────────────────────────────────────────────────────
L0 协议   runtime/protocols/          runtime/protocols/     ✅ 正确
L1 运行时  runtime/ (3.7K)             runtime/               ⚠️ 太小

L2 OMO   projects/omo/ (15K)          projects/omo/          ✅ 正确
L2 kairon projects/kairon/ (300K)     knowledge-engine/       🔴 太大, 应拆
L2 gbrain projects/gbrain/ (163K TS)  projects/gbrain/       ✅ 正确(但跨语言)

L3 入口  wksp(15K)+runtime MCP       entry-bridge/           🔴 碎片化
        +hermes-console(1.4K)

I0 织层  kairon/agora/ (38K)          projects/i0/agora      🔴 放错项目

P0 产品  hermes-console (构建失败)     dashboard/              🔴 停摆

X1/X2/X3 .omo/ 定义                   .omo/ + runtime/       ⚠️ 零实现
```

---

## 三、5 个结构性问题

### 问题 1: kairon 是一个过大的单体 (300K 行)

```
kairon 当前包含:
  L0 数据模型: core-models(1.6K) + shared-lib(38K) + ssot(14K) = 53K
  L1 基础设施: engine-core(25K) + llm-gateway(3K) + cron-service(2K) = 30K
  L2 知识工程: minerva(25K) + eidos(35K) + kos(14K) + ontoderive(6K) + ... = 90K
  L2 治理:     kairon-governance(2.5K) + metaos(6K) = 9K
  I0 集成:     agora(38K) — 放错层
  L3 入口:     wksp(15K)
  Agent:       agent-runtime(20K) + forge(8K) = 28K
  shared-lib:  38K 倾倒场

问题: 一个项目承担了 4 个层的责任。任何重构都牵一发动全身。
```

### 问题 2: I0(Agora) 在 kairon 内 (38K 行)

```
agora 定义为 I0 集成织层，但代码在 kairon/packages/agora 下。
后果:
- "跨层"重构必须跨项目 (kairon → Kairon 外)
- agora 需要访问 kairon 内包的 MCP 接口 → 循环引用风险
- 拆 agora 出去 = 从 kairon monorepo 里搬走 38K 行 = 大手术
```

### 问题 3: gbrain 是跨语言的"黑盒" (163K 行 TS)

```
gbrain 是 TypeScript, 其余都是 Python。
跨语言通信成本:
- 必须通过 MCP 或 REST (不能直接 import)
- gbrain 有 715 个测试但全部在 TS 生态中
- kairon 无法直接使用 gbrain 的类型或函数
  
实际效果:
  gbrain = 163K 行的"外部 API", 不是"代码库"
  二次开发需要同时维护两套类型定义 (TS + Python)
```

### 问题 4: L3 入口碎片化

```
用户入口有 3 个:
  wksp          — CLI (workspace 命令)       15K 行 Python
  runtime MCP   — MCP 协议接口                 ~200 行
  hermes-console — Web (构建失败)             1.4K 行 TS

这三个没有任何统一的用户体验设计。
wksp 最大但几乎只做研究管理, runtime MCP 只做运维。
```

### 问题 5: runtime 太小 (3.7K) 但责任很大

```
L1 运行时的责任:
  - 服务注册表 (Matrix)
  - 健康监控 + 告警
  - KEI 沙箱
  - 协议管理
  - 事件消费

3.7K 行代码支撑这么多责任, 和 kairon 的 300K 行形成鲜明反差。
要么 runtime 太薄, 要么 kairon 太厚。
实际都有: runtime 太薄(很多功能还在 kairon 里), kairon 太厚(把不该有的都装了)
```

---

## 四、干净架构方案 (从 Workspace 视角)

### 4.1 项目重组

```
     ┌─────────────────────────────────────────────┐
     │              eCOS Workspace                  │
     │  467K 行 → 目标: 分 7 个项目, 边界清晰       │
     └─────────────────────────────────────────────┘

L4    ┌────────────────────────────┐
      │   projects/hermes-console  │  <-- 统一 Web 面板 (从 MVP 重启)
      │   TS React · ~5K           │
      └──────────┬─────────────────┘
                 │
L3    ┌──────────▼─────────────────┐
      │   projects/entry-bridge    │  <-- 新建: 统一入口层
      │   从 wksp CLI 提取核心      │      wksp 的 CLI + runtime MCP
      │   Python · ~10K            │      MCP 服务器 → 合并
      └──────────┬─────────────────┘
                 │
L2    ┌────┬─────┼──────┬──────────┐
      │    │     │      │          │
      │ OMO  kairon     │  gbrain  │
      │15K  │engine(180K)│  163K   │
      │    │     │      │          │
      └────┴──┬──┴──────┴──────────┘
              │
L1    ┌───────▼─────────┐
      │   runtime        │  <-- 吸收 kairon 的运行时部分
      │   从 3.7K → 20K  │      cron-service, agent-runtime 核心
      └───────┬─────────┘
              │
L0    ┌───────▼─────────┐
      │   protocol       │  <-- runtime/protocols/ 不变
      │   16 协议定义     │
      └─────────────────┘

I0    ┌─────────────────┐
      │   agora          │  <-- 从 kairon 移出, 独立项目
      │   Python MCP Hub │      kairon/agora → projects/agora
      │   38K → 15K(精简)│      拆掉 dashboard/A2A
      └─────────────────┘
```

### 4.2 变化总结

| 项目 | 当前 | 目标 | 变化 |
|------|------|------|------|
| **kairon** | 300K, 24 包 | **180K**, 知识工程专精 | -120K (移出 agora + runtime 部分) |
| **agora** | 在 kairon 内 | **projects/agora (独立)** | 从 kairon 拆出, 精简到 15K |
| **runtime** | 3.7K | **20K** | 吸收 cron-service + agent-runtime 核心 |
| **entry-bridge** | 没有 | **10K (新建)** | wksp CLI 核心 + runtime MCP 合并 |
| **hermes-console** | 1.4K (broken) | **5K (重启)** | 统一 Web 面板 |
| **omo** | 15K | **15K** | 不变 (治理层) |
| **gbrain** | 163K TS | **163K TS** | 不变 (跨语言边界明确) |

### 4.3 依赖规则 (硬约束)

```
entry-bridge  ← 依赖 →  agora  ← 依赖 →  kairon
     │                          │
     │                          ▼
     └────── 依赖 ────────→  runtime
                                    │
                                    ▼
                                protocol (L0)
```

```
规则:
  1. kairon 不知道 agora 的存在 (agora 是 I0, 是 kairon 的 client)
  2. kairon 不知道 runtime 的存在 (runtime 是 L1, 是 kairon 的 infrastructure)
  3. entry-bridge 统一所有入口
  4. omo 只与 .omo/ 目录交互, 不关心 kairon/runtime 的实现
```

---

## 五、渐进实施路径

| 阶段 | 操作 | 代码移动 | 风险 |
|------|------|---------|------|
| **P0 短期** | ako 从 kairon 拆出到 projects/agora | 38K 行搬家 | 高 (所有包依赖 agora) |
| **P1 短期** | cron-service + agent-runtime 核心 → 合并到 runtime | 22K 行搬家 | 中 |
| **P2 中期** | wksp CLI 核心 → entry-bridge (wksp 保留, 变薄) | 8K 行 | 中 |
| **P3 中期** | shared-lib → 解散 | 38K 行分散 | 高 |
| **P4 长期** | hermes-console 重启 (修复构建) | 修复 + 扩展 | 低 |
| **P5 长期** | kairon 从 180K→ 保留知识工程核心 | 精简 | 中 |

### 建议: 从 P0 (agora 拆出) 开始

agora 拆出是所有后续步骤的前提。它在 kairon 内一天，kairon 的"跨层"问题就存在一天。但:

```
agora 拆出的前提条件:
  1. agora 需要独立运行 (standalone FastAPI)
  2. kairon 各包通过 MCP 调用 agora, 不是直接 import
  3. 现有 `kairon/agora → kairon/*` 的 import 依赖需要消除
  
  当前 agora 依赖: eidos, kos, minerva, core-models
  拆出后: agora 不能直接 import kairon 的任何包
  全部通过 MCP 调用 → 这意味 agora 的某些功能需要重新设计
```

---

## 六、与 OMO 治理的关系

```
.omo/ (治理层) 位于 Workspace 根目录, 不隶属任何项目。

  omo CLI 视察所有项目:
    omo state health   → 读 runtime Matrix
    omo i0 status      → 读 agora
    omo log search     → 读 KEI 审计 (全局)
    
  项目各自的治理由 omo 统一覆盖, 不重复:
    kairon-governance  → 应与 omo 对齐或废弃
    metaos             → 编排功能归 omo 或 runtime
```
