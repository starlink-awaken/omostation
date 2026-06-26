---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-26
---

# ADR-0104: GaC 治理即代码架构 (Governance-as-Code)

- **Status**: ACCEPTED
- **Date**: 2026-06-26
- **Authors**: 老王 (GaC roadmap)
- **Extends**: ADR-0103 (P109 治理赋能三件套), ADR-0094-0102 (omo_lint + governance_surfaces 拆解)
- **Superseded by**: (无)

## Context and Problem Statement

omostation 治理规则散在 4 处 (**M0** Stage/Gate + **L0** MOF/BOS + **L2** omo policy + **X1-X4**), 暴露 3 类根本问题:

1. **多 agent/多 session 并行冲突** (memory `concurrent-agent-contention`): 共享工作树 + 单向 AdvisoryLock + 共享 pre-push gate, agent 互相撞 (Edit 被回滚 / push 被并发债卡 / 测试被半成品污染)
2. **规则增长漂移**: 规则/hook 持续加, 久了规则和实现脱节 (声明了不执行, 无 drift 检测) — "时间久了走偏"
3. **治理规则散落**: M0/L0/L2 各自定义+执行, 重叠且不统一 (X4 一致性在 omo/ecos/model-driven 各实现一次, 改规则要动三处)

**根本矛盾**: **动态性** (规则持续增长, 不改架构) **vs 一致性** (规则间不矛盾 + 实现不漂移).

## Decision

**GaC 治理即代码架构 (Governance-as-Code)** — 激活已有零件, 不新建 project, 三层落点 + 动态一致性 7 机制 + 元治理递归.

### 决策 1: 不新建 `projects/governance/` (4 理由)

1. **GaC 是横切, 不是层** — 横切不该是 project (project 是层/子系统). agora I0 是横切先例 (因有大量 MCP Hub 代码才独立)
2. **GaC 执行分散** — 执行器是 omo/ecos/model-driven (已存在), 新 project 会重叠
3. **GaC 定义已有家** — `governance-checks.yaml` 已存在, 升级为 SSOT 规则注册表
4. **YAGNI** — 新 project = 新代码库 + 新 CI + 新维护. 零件够用, 先组装

GaC 引擎代码先放 `projects/omo` (omo 本是治理工具, GaC 是其演进), 长大 (> 800 行触发 god-module) 再独立.

### 决策 2: 三层落点 (激活已有, 加元治理面)

| 层 | 落点 | 角色 |
|----|------|------|
| **定义层** | `.omo/_truth/registry/governance-checks.yaml::gac` | 规则注册表 (SSOT) |
| **执行层** | 协议体系 (AGENTS.md / MCP / PreToolUse hook / CI gate) | 统一执行通道 |
| **演进层** | `.omo/_knowledge/gac/` (新建) | 元治理面 (北极星 + drift + lifecycle + changelog) |

### 决策 3: 动态一致性 7 机制 (规则/hook 增长保证)

| # | 机制 | 动态性 | 一致性 | 对标 |
|---|------|:---:|:---:|------|
| 1 | 声明式规则 (YAML 数据, 不硬编码) | ✅ | | OPA policy |
| 2 | schema 校验 (加规则强制结构) | | ✅ | pydantic |
| 3 | 泛化执行器 (hook/MCP 读注册表, 规则变执行器不变) | ✅ | | OPA 引擎 |
| 4 | drift 检测 + 自愈 (注册表 vs 实际执行, radar) | | ✅ | K8s controller |
| 5 | 矛盾检测 (规则间一致性) | | ✅ | OPA conflict |
| 6 | 版本 + lifecycle (draft/active/deprecated, gc 清理) | ✅ | ✅ | K8s deprecation |
| 7 | **MOF 元模型派生** (M1→M2→M3, omostation 独有) | ✅ | ✅ | **OPA 没有** |

### 决策 4: 元治理递归 (最深刻)

**GaC 治一切, GaC 自己也要被治**. 用 GaC 机制治 GaC:

- X1 审计 → 审计 GaC 规则执行 (触发率/违规率)
- **X2 抗熵 → drift 检测 GaC 自己** (注册表 vs 实现) ← 防"走偏"核心
- X3 价值 → 规则 ROI (哪些规则真拦问题, 哪些噪音)
- X4 一致 → 规则 SSOT (governance-checks.yaml 唯一源)

### 决策 5: c2g 五原语 = GaC 元治理循环 (设计同构)

```
brainstorm → draft → bet → radar → gc
 (提案)     (Pitch) (注册) (drift) (清理)
```

c2g 的 radar 天然是 GaC drift 检测 (机制 4), gc 天然是规则 lifecycle 清理 (机制 6). **不是工具复用, 是设计同构**.

## Consequences

### 正面
- **统一规则源**: governance-checks.yaml::gac SSOT, 改一处全生效
- **动态一致性**: 7 机制, 规则/hook 增长不漂移
- **多 agent 并行基础**: 协议强制 (hook/MCP) + drift 兜底
- **防走偏**: 元治理递归 (X2 drift 自检 GaC 自己)
- **复用 MOF 优势**: 机制 7 比纯 OPA 强 (元模型约束派生)

### 负面/成本
- 阶段 1-2 需代码 (hook/MCP/schema 校验脚本), 中等工作量
- 阶段 3 规则上 MOF 需 M1 元模型设计
- 现有工具 (omo/ecos/model-driven) 需重定位为"读注册表的执行器" (规则上移, 不内嵌)

## Alternatives Considered

| 方案 | 拒绝理由 |
|------|---------|
| 新建 `projects/governance/` | GaC 横切不是层; 和 omo 重叠; YAGNI |
| 纯 OPA (rego 策略) | 无元模型层 (机制 7); 不复用 omostation MOF |
| 手动协调 (停并发 session) | 治标不治本; 无法 scale 到多 agent |
| 加新 X5 切面 | X1-X4 已是切面; 加层 = 多抽象 (违反 KISS) |
| 协议靠自觉 (纯文档) | 单向锁=没锁 (AdvisoryLock 教训); 必须执行通道兜底 |

## Implementation Roadmap

6 阶段 (详见 `NORTH-STAR.md` + `roadmap-v1.md`):

| 阶段 | 重点 | 交付 | 代码 |
|------|------|------|:---:|
| 0 激活 | 北极星 + schema + 登记 + ADR | 规则可视, 方向锚定 | 零 |
| 1 绑定 | AGENTS.md 导出 + 泛化 hook + MCP | 执行统一 | 中 |
| 2 动态一致 | schema 校验 + drift + 矛盾 + lifecycle | 防走偏上线 | 中 |
| 3 元模型 | 规则上 MOF M1 + 派生链 | 元模型约束 | 中 |
| 4 度量 | 仪表盘 + drift 自愈 | 元治理闭环 | 中 |
| 5 常态化 | radar 每日 + gc 每周 | 持续治 | cron |

## 阶段 0 已交付 (本 ADR 同步)

- ✅ `.omo/_knowledge/gac/NORTH-STAR.md` (北极星)
- ✅ `governance-checks.yaml::gac` (schema + 6 条代表规则 + drift + lifecycle 配置)
- ✅ 本 ADR-0104

## References

- **北极星**: `.omo/_knowledge/gac/NORTH-STAR.md`
- **注册表**: `.omo/_truth/registry/governance-checks.yaml::gac`
- **上游痛点**: memory `concurrent-agent-contention`, memory `bos-decl-exec-gap`, memory `evidence-smoke-mechanism`
- **对标**: OPA (策略即数据), Styra (policy lifecycle), K8s Admission (webhook), GitOps (drift 自愈), Terraform Sentinel (策略即代码)

---

*ADR-0104 v1.0 · 2026-06-26 · GaC 治理即代码 · 动态一致性 7 机制 · 元治理递归*
