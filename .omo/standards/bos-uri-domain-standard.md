---
status: draft
lifecycle: standard
owner: governance-team
last-reviewed: 2026-07-02
---

# BOS URI Domain Standard (5 域锁定 + 命名规范)

> SSOT: `projects/agora/etc/bos-services.yaml` 是运行时注册表.
> 本标准定义 5 域职责边界 + kind 标签 + 跨仓 rename 流程.
> 决策: ADR 待登记 (BOS-URI-DOMAIN-NORM).

## 5 域职责 (eCOS v6 锁定)

| Domain | 前缀 | 职责 | 边界 |
|--------|------|------|------|
| `memory` | `bos://memory/` | 知识与事实源 (摄取/存储/检索) | 摄取连接器, RAG 检索, 知识图谱 |
| `governance` | `bos://governance/` | 治理与律法 (任务/审计/状态) | OMO 状态, metaos 决策, agent-workflow |
| `analysis` | `bos://analysis/` | 认知与推演 (研究/推导/代码分析) | 深度研究, 本体推导, 代码智能 |
| `persona` | `bos://persona/` | 人格与心智 | runtime agent, 个人知识桥接 |
| `capability` | `bos://capability/` | 能力与生态 (工具/执行) | LLM 网关, 算力网格, 第三方工具 |

扩展域 (`meta` / `omo` / `swarm` / `system` / `toolbox`) 走 `kind: bridge | facet` 标签,
不与 5 主域混淆.

## kind 标签 (schema v2 引入, 2026-07-02)

每个 service 必须带 `kind` 字段:

- `kind: service` — 正常服务 (默认, 5 主域内)
- `kind: bridge` — 桥接器 (跨域/单点入口, 扩展域内)
- `kind: facet` — 协议面 (meta/swarm/system, 协议/资源类, 非业务能力)

## 跨域越界检查 (已知违规, 待跨仓 rename)

以下 URI 域归属不匹配, 需多仓协调 rename (P2-2 计划):

| 当前 URI | 越界 | 建议新 URI | 影响 |
|----------|------|------------|------|
| `bos://analysis/iris/*` (6 条) | iris 是摄取连接器, 应在 memory | `bos://memory/iris/*` | 45 处引用 (含 agora consumers + tests) |
| `bos://ecos/workflow/*` (8 条) | workflow 不属 L0 协议, 应在 system | `bos://system/workflow/*` | 86 处引用 (含 agora + metaos consumers) |
| `bos://persona/health-profile/*` (4 条) | health-profile 是 L4 域元数据, 不属人格 | `bos://capability/health-profile/*` | 27 处引用 (含 omo consumers) |

### Rename 流程 (跨仓破坏性变更)

1. **Phase 1 (本标准发布)**: 把 `kind:` 标签和 `deprecated_uri:` 字段加进 `bos-services.yaml` schema
2. **Phase 2 (agora PR)**: 改 `bos-services.yaml` 加新 URI + `deprecated_uri:` 旧 URI redirect 钩子
3. **Phase 3 (consumer PR)**: agora/metaos/omo 各 submodule 起 PR 切到新 URI
4. **Phase 4 (主仓 bump)**: 根仓 bump submodule 指针, 验证 gac-local-gate + tests
5. **Phase 5 (gc)**: radar_cron 跑 gac-gc 确认 0 consumer 引用旧 URI 后, 删除 deprecated 字段

## 5 域守护规则 (CR-L0-BOS-DOMAIN-NORM, 计划)

`executor: [ci_gate]`, `check_type: bos_resolve`, 守:

- 5 主域边界 (memory/governance/analysis/persona/capability) 不混用
- 扩展域 URI 必须带 `kind: bridge | facet`
- 跨域越界需在 standards 文档先登记 (如本文件), 不能直接 commit

## 反模式

- ❌ 在 5 主域内放协议/桥接器 (走 `kind: bridge` + 扩展域)
- ❌ 改 BOS URI 不更新 standards 文档
- ❌ 消费者硬编码 URI 字符串 (应走 `bos_resolver` 查询)
