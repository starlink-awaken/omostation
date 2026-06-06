# Architecture Decision Records — 索引

> 全部 ADR 文件位于本目录 `.omo/_knowledge/decisions/`
> 制度启用: 2026-06-05 (Phase 28 W3) · MADR 风格

---

## 索引表

| # | 标题 | Status | Date | Authors | 文件 |
|---|------|--------|------|---------|------|
| 0001 | agora 路由表精简策略 | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0001-agora-routes-deferred.md |
| 0002 | kairon-assistant / kairon-voice 首批归档 | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0002-pkg-archive-p28-w2.md |
| 0003 | P28 TECH-RADAR 实施绕过 agora | ACCEPTED | 2026-06-05 | omostation P28-W3 | 0003-tech-radar-bypass-agora.md |
| 0004 | kaironcloud-billing 归档（W6 评估） | ACCEPTED | 2026-06-05 | omostation P28-W6 | 0004-kcb-archived.md |
| 0005 | P29 架构升级（kairon 31 包 → L1 工程层） | ACCEPTED | 2026-06-05 | omostation P29 | 0005-architecture-p29-upgrade.md |
| 0006 | kairon 17 包合并到 14 包（方向 C — 3 组瘦包合并，砍 data-pipeline） | ACCEPTED | 2026-06-06 | omostation P31-W0 | 0006-kairon-package-merge.md |

---

## 命名规则

`NNNN-<kebab-case-title>.md`，编号 4 位 zero-padded 全局递增。

- 0001-0099: Phase 28 期间决策
- 0100-0999: 后续 Phase 决策
- 1000+: 长生命周期核心架构决策

## Status 状态机

```
   PROPOSED ──> ACCEPTED ──> DEPRECATED
                    │
                    └──> SUPERSEDED by ADR-NNNN
```

| Status | 含义 |
|--------|------|
| `PROPOSED` | 提案中，待评审；尚未落地实施 |
| `ACCEPTED` | 已接受并实施；当前生效 |
| `DEPRECATED` | 仍有效但不再推荐用于新场景；旧系统维持 |
| `SUPERSEDED` | 已被新 ADR 替代（必须填 `Superseded by: ADR-NNNN`） |

---

## 主题分类

### L0 — 路由/网关（agora）

- ADR-0001: agora 路由表精简策略（L1 包按需注册）
- ADR-0003: P28 TECH-RADAR 实施绕过 agora（W1 演示豁免）

### L1 — 包治理（kairon 31 包）

- ADR-0002: kairon-assistant / kairon-voice 首批归档
- ADR-0005: P29 架构升级（kairon 31 包 → L1 工程层）
- ADR-0006: kairon 17 包合并到 14 包（方向 C，3 组：llm-gateway-kernel / sot-bridge / protocols-layer）— **ACCEPTED**

---

## 维护责任

- **新增 ADR**: 任何 Phase 收尾时由治理 Agent 触发（参考 `README.md` 维护规则）
- **冲突处理**: 编号冲突时由人类审批
- **过期判定**: 每个 Phase 入口处审阅已 `ACCEPTED` 的 ADR，决定是否需 `DEPRECATED`
  或 `SUPERSEDED`

---

## 相关文件

- 模板与规则: [`README.md`](./README.md)
- 候选收集任务: `P28-W1-ADR-COLLECT`（已完成）
- 制度化任务: `P28-W3-ADR-SETUP`（本批 ADR 的来源）

---

*最近更新: 2026-06-06 · Owner: P31-W0-KAIRON-MERGE-ACCEPTED · 0006 状态 PROPOSED → ACCEPTED*
