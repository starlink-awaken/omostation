---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# L3 入口桥接矩阵收口方案

> 状态: proposed
> 日期: 2026-06-05
> 范围: `wksp` / `agora` / `projects/runtime` / `sharedbrain-bridge`
> 目标: 给当前 workspace 一个清楚的入口矩阵，而不是继续让多个入口互相重叠

---

## 1. 问题定义

当前系统不是没有入口，而是入口太多且职责重叠：

- `wksp`
- `runtime` CLI / MCP
- `agora`
- `sharedbrain-bridge`
- 各包自带 CLI

这会导致三类问题：

1. 用户不知道从哪进。
2. 运维不知道哪个入口代表系统主路径。
3. 架构审计无法判断“入口能力”到底落在哪一层。

所以 L3 现在的核心任务不是新增入口，而是**收口入口矩阵**。

---

## 2. 设计原则

### 2.1 一类入口只服务一类用户意图

- 人的日常操作入口 -> `wksp`
- 运行时/基础设施观察入口 -> `runtime`
- 服务织物/路由/聚合入口 -> `agora`
- 历史兼容/外部化边界入口 -> `sharedbrain-bridge`

### 2.2 入口可以协同，但不能语义重叠

允许：

- `wksp` 调用 `agora`
- `wksp` 读取 `runtime` 状态
- `agora` 对接 `sharedbrain-bridge`

不允许：

- `runtime` 变成第二个产品 CLI
- `agora` 变成第二个日常用户入口
- `sharedbrain-bridge` 继续假装自己桥接一个 live sibling repo

### 2.3 入口收口优先于功能扩张

在 `knowledge-capture-search` 主路径没有稳定前，不再新增同类入口。

---

## 3. 目标入口矩阵

| 入口 | 目标角色 | 主要用户 | 负责什么 | 不负责什么 |
|---|---|---|---|---|
| `wksp` | operator home | 人类操作者、日常使用者 | research/import/status/contracts/profile/quickstart/product demo | 服务聚合、底层路由、协议注册 |
| `runtime` | runtime home | 运维、基础设施操作者 | protocol/matrix/health/KEI/I0 查询与基础控制 | 产品旅程、知识闭环、治理编排 |
| `agora` | fabric home | 系统集成者、服务操作者、LLM tool router | MCP 聚合、服务发现、路由、事件、管道、治理控制面 | 日常用户研究入口、治理 SSOT |
| `sharedbrain-bridge` | boundary seam | 兼容维护者、迁移期操作者 | 外部化 SharedBrain 边界上的 sync/audit/eu/immune 能力 | live sibling repo 入口、主用户入口 |

---

## 4. 每个入口的定界

### 4.1 `wksp`

当前判断：

- 已具备最像“产品级统一入口”的 CLI 形态
- 命令集覆盖 research/import/status/contracts/profile/quickstart/demo
- 最适合承担 operator home

结论：

- `wksp` 应被定义为默认的人类 CLI 入口
- 所有“给人直接用”的日常旅程优先往 `wksp` 收敛

限制：

- 不直接吞掉 Agora 路由和 Runtime 协议能力
- 不自己维护第二套运行时状态真相

### 4.2 `runtime`

当前判断：

- 已经有 `protocol`, `matrix`, `health`, `kei`, `i0` 等命令和查询能力
- 本质是 L0/L1/I0 的观察与基础设施入口

结论：

- `runtime` 应固定为 runtime home
- 它服务“看系统、测系统、控系统”，不服务“日常用系统”

限制：

- 不承担产品旅程组装
- 不承担业务研究工作流

### 4.3 `agora`

当前判断：

- 是最厚的 MCP 汇聚与服务控制面
- 已经承担注册、路由、代理、事件、治理和工具目录

结论：

- `agora` 应被定义为 fabric home
- 所有跨服务能力聚合、工具代理、语义路由都往 `agora` 收敛

限制：

- 不作为默认的人类日常 CLI
- 不声明自己是治理真相源

### 4.4 `sharedbrain-bridge`

当前判断：

- 包还活着，但旧的 SharedBrain repo 已归档
- 继续用旧叙事会制造边界幻觉

结论：

- `sharedbrain-bridge` 只保留 externalized boundary seam 角色
- 它桥接的是外部化运行时/数据语义，不是 live sibling repo

限制：

- 不作为主入口
- 不再对外叙述为 “kairon <-> live SharedBrain repo bridge”

---

## 5. 主路径映射

### 5.1 用户级主路径

当前推荐主路径：

1. 用户从 `wksp` 或后续 product shell 发起意图
2. `wksp` 按需调用 `agora` / `gbrain` / `kairon`
3. `agora` 负责跨服务路由与能力聚合
4. `kairon` 负责 binding / trace / contract
5. `.omo` 负责 evidence / policy / recovery state

### 5.2 运维级主路径

1. 运维从 `runtime` 查看 protocol / matrix / health
2. 从 `agora` 查看服务注册、路由、事件和代理状态
3. 从 `.omo` 看治理态和 closeout/evidence

---

## 6. 实施顺序

### Step 1

补齐四个入口的 README / package docs / capability docs，先把边界说清。

### Step 2

把 `wksp` 明确标成 operator home，把 `runtime` 明确标成 runtime home。

### Step 3

把 `knowledge-capture-search` 明确绑定到：

- user entry: `wksp` / product shell
- fabric route: `agora`
- runtime observation: `runtime`
- evidence/governance: `.omo`

### Step 4

逐步移除或降级重复入口说明，避免用户继续被多个入口误导。

---

## 7. 验证口径

### 文档验证

- `wksp` README 明确 operator-home 角色
- `sharedbrain-bridge` README 不再声称桥接 live sibling repo
- 相关架构文档对四个入口的描述一致

### 行为验证

- `wksp` 可承担一条主用户旅程的入口语义
- `runtime` 输出运行时健康和协议状态
- `agora` 仍承担路由与聚合，不被 `wksp` 复制

### 审计验证

- 后续架构审计能明确回答：
  - 用户从哪进？
  - 运维从哪看？
  - 服务从哪聚合？
  - SharedBrain 边界还剩什么？

---

## 8. 最终结论

L3 的正确终局不是“只剩一个二进制”，而是：

- 一个默认的人类入口
- 一个默认的运行时入口
- 一个默认的集成织物入口
- 一个受控的历史兼容边界

只要这个矩阵稳定，后面的主路径、治理闭环和产品层收敛才不会继续漂。
