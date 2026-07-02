# ARCHITECTURE-EVOLUTION.md — eCOS Architecture Evolution & Project Boundaries

> 架构演进路线与各项目边界索引。本文档作为项目级 `BOUNDARY.md` 的回指目标。
> 运行时事实（版本、阶段、健康）以 SSOT 为准，本文不复制。

## Source Of Truth

| Need | Read |
|------|------|
| 架构契约 | [`ARCHITECTURE.md`](../ARCHITECTURE.md) |
| 项目元数据 | [`docs/project-registry.yaml`](project-registry.yaml) |
| 愿景与路线图 | [`docs/VISION-ROADMAP.md`](VISION-ROADMAP.md) |
| 治理演进路线图 | [`docs/GOVERNANCE-EVOLUTION-ROADMAP.md`](GOVERNANCE-EVOLUTION-ROADMAP.md) |
| 架构概览图 | [`docs/ARCHITECTURE-DIAGRAM.md`](ARCHITECTURE-DIAGRAM.md) |

## Evolution Vectors

eCOS 架构沿以下稳定向量演进（方向由 [`ARCHITECTURE.md`](../ARCHITECTURE.md) 契约约束）：

1. **入口收敛** — 人工入口收敛到 `cockpit`，Agent 入口收敛到 `agora` MCP。新增顶层入口需更新注册表与边界文档。
2. **治理内化** — `.omo/` 状态面 / `omo` 内核面 / `c2g` 入场面 / `ecos` 协议面 四层治理表面持续内化规则，减少人工纪律依赖。
3. **证据闭环** — KEMS 全闭环控制回路：目标→任务→执行→证据→健康→反馈。
4. **协议沉淀** — L0 MOF 约束（M1 节点 / M2 类型 / 工具链 / daemon）持续从代码萃取为协议。
5. **制造面外挂** — `model-driven` (M0) 将重复结构生成收敛为模板驱动，`aetherforge` 承担网关与调度横切。

## Project Boundaries

每个项目的暴露接口、上下游与配置 SSOT 由该项目的 `BOUNDARY.md` 拥有。下表给出跨项目边界速查：

| Project | Layer | Boundary Doc | 暴露面 | 上游 | 下游 |
|---------|-------|--------------|--------|------|------|
| [`agora`](../projects/agora/BOUNDARY.md) | I0 | BOUNDARY | MCP Hub / BOS URI 路由 / 反向代理 | ecos, runtime | kairon, gbrain, omo, metaos, runtime, l4-kernel, cockpit |
| [`cockpit`](../projects/cockpit/BOUNDARY.md) | L3 | BOUNDARY | CLI / Web / MCP 客户端 | agora, omo | agora, omo |
| [`kairon`](../projects/kairon/BOUNDARY.md) | L2 | BOUNDARY | 引擎（minerva/kos/eidos/iris/ontoderive） | gbrain, ecos | gbrain |
| [`gbrain`](../projects/gbrain/BOUNDARY.md) | L2 | BOUNDARY | 记忆 / 向量存储 / memu | kairon, runtime | kairon |
| [`omo`](../projects/omo/BOUNDARY.md) | L2 | BOUNDARY | 治理内核 / broker / lint / audit | ecos | .omo state plane |
| [`metaos`](../projects/metaos/BOUNDARY.md) | L2 | BOUNDARY | 元操作系统 / 调度 | ecos, runtime | runtime |
| [`runtime`](../projects/runtime/BOUNDARY.md) | L1 | BOUNDARY | 运行时 / 健康监控 / KEI | ecos | observability |
| [`ecos`](../projects/ecos/BOUNDARY.md) | L0 | BOUNDARY | MOF / L0 约束 / SSOT 注册表 | — | 全栈（协议根） |
| [`aetherforge`](../projects/aetherforge/BOUNDARY.md) | X | BOUNDARY | 网关 / 调度 / 锻造 | runtime, ecos | runtime |
| [`bus-foundation`](../projects/bus-foundation/BOUNDARY.md) | X | BOUNDARY | 总线 / 基础设施 | runtime, ecos | runtime |
| [`c2g`](../projects/c2g/BOUNDARY.md) | X | BOUNDARY | 入场面（策略→任务） | omo, ecos | omo |
| [`family-hub`](../projects/family-hub/BOUNDARY.md) | X | BOUNDARY | 家庭管理 / 生活记录 | cockpit, agora | — |
| [`l4-kernel`](../projects/l4-kernel/BOUNDARY.md) | L4 | BOUNDARY | 自我层 / 纯文档上下文 | — | cockpit（上下文） |
| [`model-driven`](../projects/model-driven/BOUNDARY.md) | M0 | BOUNDARY | 模型驱动生成 | ecos | ecos |
| [`observability`](../projects/observability/BOUNDARY.md) | X | BOUNDARY | 观测 / 指标 / 日志 | runtime | — |
| [`omo-debt`](../projects/omo-debt/BOUNDARY.md) | X | BOUNDARY | 债务追踪 | omo | omo |

## Archived Projects

| Project | Status | Successor |
|---------|--------|-----------|
| hermes-console | ARCHIVED | 入口能力收敛到 `cockpit` / `agora`（见 [`docs/PANORAMA.md`](PANORAMA.md)） |
| llm-gateway | ARCHIVED | 快照在 `/_archived/llm-gateway/`，能力并入 [`aetherforge/packages/gateway`](../projects/aetherforge/packages/gateway/) |

## Dependency Direction Contract

由 [`ARCHITECTURE.md` §2](../ARCHITECTURE.md) 拥有，重申：

```text
entry surfaces -> routing mesh -> engines/runtime/protocol -> governed state and evidence
```

规则：
- 不允许下层反向依赖上层（L0 不依赖 L2，L1 不依赖 L3）。
- 横切层（X / M0）可被多层级调用，但不持有治理状态。
- 新增跨层调用须更新双方 `BOUNDARY.md` 与相关注册表。

## Related Documents

| Document | Role |
|----------|------|
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | 架构契约 |
| [`docs/ARCHITECTURE-DIAGRAM.md`](ARCHITECTURE-DIAGRAM.md) | 架构概览图 |
| [`docs/PANORAMA.md`](PANORAMA.md) | 系统全景与 BOS 路由 |
| [`docs/VISION-ROADMAP.md`](VISION-ROADMAP.md) | 愿景与路线图 |
| [`LAYER-INDEX.md`](../LAYER-INDEX.md) | 层级索引 |
