---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-11-09
type: ssot
---

# Workspace 项目资产索引

> 更新: 2026-11-09 (truth-docs 到期复核: §1.1 补齐 registry 里漏列的 5 个 active 项目; family-hub 实为 paused; hermes-console 归位 §1.2; knowledge 按 registry 的复合体口径合并)
> 更新: 2026-09-25 (truth-docs 到期复核: c2g/omo-debt 内包、_archived 引用移除、hermes/agora-dashboard 收敛口径对齐 registry)
> 性质: 项目资产导航，不是 live runtime snapshot。
> 当前项目身份、状态、路径与技术栈以 [../../docs/project-registry.yaml](../../docs/project-registry.yaml) 为准；
> 项目级边界与调用链以各项目 `ARCHITECTURE.md` / `CALLCHAIN.md` / `BOUNDARY.md` 为准。
>
> 运行时状态 (governance score / mof-version / lint) 见各自 SSOT:
> `bin/mof/mof-version show` / `.omo/_truth/mof-version.yaml`. P43 闭环模式文档化:
> `.omo/_knowledge/patterns/p43-closed-loop-pattern.md`.

---

## 概览

| 维度 | 当前事实 |
|------|----------|
| 根仓库 | `omostation` workspace root |
| 项目注册表 SSOT | [../../docs/project-registry.yaml](../../docs/project-registry.yaml) |
| 架构全景 SSOT | [../../docs/PANORAMA.md](../../docs/PANORAMA.md) |
| `.omo` 角色 | 治理状态面与证据锚点，不替代各 repo 自身说明 |
| 项目运行时事实 | 以各项目本地 CI / 测试 / 探针为准 |

---

## 一、当前项目身份路由

### 1.1 Active 项目

- `projects/l4-kernel/` — L4 自我层管理面
- `projects/cockpit/` — L3 唯一人类 CLI / Web 入口
- `projects/cockpit-ui/` — L3 Web 控制台前端表现层（挂载至 cockpit `/`）
- `projects/agora/` — I0 MCP Hub / BOS 路由
- `projects/knowledge/` — L2 知识工程复合体（`gbrain` Postgres RAG + `kairon` python 引擎 monorepo，BET-Y1Q3-T6-01）
- `projects/omo/` — L2 治理内核
- `projects/metaos/` — L2 编排引擎
- `projects/runtime/` — L1 运行时
- `projects/omlxc/` — L1 本地算力运行时（`omlxcd` 守护进程、物理放置与算力驾驶舱）
- `projects/surface/` — L1 TinyBOS 边缘具身协议（Rust；P2P mesh 编解码 + 传感器桥接 + 场景触发，BET-Y1Q4-T8-22）
- `projects/ecos/` — L0 协议层
- `projects/aetherforge/` — X 横切能力与算力框架
- `projects/model-driven/` — M0 生命周期横切框架
- `projects/bus-foundation/` — 总线能力
- `projects/domain-cartridges/` — L2 领域场景卡内容包（BET-Y2Q4-T7-01）
- `projects/observability/` — 可观测性栈
- `toolbox`（外部存储 `~/ToolBox/`）— L1-L3 本地服务入口能力，registry 注册为项目但**不在 `projects/` 下**

### 1.2 Archived / Legacy / 内包收敛

- `projects/c2g/`、`projects/omo-debt/` — 2026-09 起经 ADR-0412 内包进 `runtime` + `projects/omo`，不再作为独立项目存在；身份以 `docs/project-registry.yaml` 为准
- `projects/_archived/` — 子模块引用已移除；历史迁移资料见各项目归档区与 `docs/PANORAMA.md` 项目附录

- `projects/agora-dashboard/` — 已合并进 cockpit HTTP 入口（见 `docs/project-registry.yaml` 收敛记录）；独立入口已收敛，不再作为当前 Web 面
- `projects/hermes-console/` — 已合并进 `cockpit-ui`（registry `archived` 条目）
- `projects/family-hub/` — registry `status: paused`，非 active
- `projects/mesh-router/` — registry `status: archived`，owner 已收敛至 `aetherforge`
- 其他已归档能力以 [../../docs/PANORAMA.md](../../docs/PANORAMA.md) 的项目附录为准

### 1.3 使用原则

1. 项目身份、状态、路径变更先改 [../../docs/project-registry.yaml](../../docs/project-registry.yaml)，不要先改派生文档；[../PROJECTS.yaml](../PROJECTS.yaml) 注册各项目归档/活跃状态，供 SSOT 引用链校验。
2. 项目级运行时计数、测试数、MCP/route 数不写入本文件。
3. 具体架构、边界、调用链以项目内三件套文档为准。
4. 历史快照可以保留，但必须显式标记为 legacy / archived，不能继续冒充 active 入口。

---

## 二、关键指针

- 项目注册表: [../../docs/project-registry.yaml](../../docs/project-registry.yaml)
- 架构全景: [../../docs/PANORAMA.md](../../docs/PANORAMA.md)
- `.omo` 治理面边界: [../standards/omo-governance-surfaces.md](../standards/omo-governance-surfaces.md)
- `.omo` 根导航: [../INDEX.md](../INDEX.md)

---

## 三、治理约束

1. `_truth/INVENTORY.md` 只做索引与路由，不复写运行时快照。
2. 项目状态漂移先收敛到 [../../docs/project-registry.yaml](../../docs/project-registry.yaml)，再由派生文档引用。
3. 历史清单、旧阶段快照、旧包数只能作为迁移证据，不得继续被当成当前事实源。
