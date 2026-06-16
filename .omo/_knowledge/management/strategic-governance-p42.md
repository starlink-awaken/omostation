# 战略治理规划:从 Phase 42 到 45

> **SSOT 类型**: 战略治理(governance strategy)
> **签发日期**: 2026-06-16
> **签发人**: 老王(代夏起草) · 实施: P43 W0 试点
> **关联规划**: [`/Users/xiamingxing/Workspace/Plans/c2g-enchanted-coral.md`](../../../Plans/c2g-enchanted-coral.md)
> **关联 SSOT**: [`.omo/state/system.yaml`](../../state/system.yaml) + [`.omo/state/health.yaml`](../../state/health.yaml)
> **状态**: DRAFT (P43 W0 试点中)

---

## 1. 北极星(North Star)

让 omostation 治理从**"文档刷数"** 转向 **"机器审计 + 收口想法"**。

具体表现:
- 任何"想做一个新东西"必须先走 `c2g brainstorm` / `c2g draft`
- 任何任务沉淀必须走 `c2g bet`(M2 防腐层 + CR-STRATEGY-01 拦截)
- 治理分由 `c2g radar` 每日生成,写 SSOT `.omo/state/health.yaml`
- 滞留 Pitch 由 `c2g gc` 每周清理(28d 阈值)
- Phase 推进 = radar 全绿 + 0 异常(自动)

---

## 2. 当前基线(2026-06-16 实测)

```
$ python3 bin/compass_radar.py
📊 治理健康分: 55/100 (3 异常)
   P0 任务: 59 (阈值 5, 战略优先级失衡)
   L3 风险: 1  (需重点 review)
   Owner 集中度: 83% unassigned (单点故障)
```

**对比**:
- 静态打分: 77.5 (无依据)
- 真审计: 55 (c2g.strategy.strategy_audit)

**差距**: 22.5 分 — 真实治理问题被掩盖。

---

## 3. 战略 Bets(P0-P3)

| ID | Bet | 价值向量 | Appetite | Upstream | 状态 |
|----|-----|---------|---------|----------|:----:|
| **BET-COMPASS-01** | cockpit `compass` 命名空间落地 | V1 效率 | 1 周 | 本规划 | 📋 P44 |
| **BET-RADAR-CRON** | radar 每日 cron + 健康分 SSOT | V1 效率 | 3 天 | BET-COMPASS-01 | ✅ P43 W0 |
| **BET-GC-CRON** | gc 每周 cron + 债务路由 | V2 自治 | 3 天 | BET-RADAR-CRON | 📋 P43 W1 |
| **BET-PLANNED-CLEANUP** | 60 planned → 30 | V1 效率 | 2 周 | BET-GC-CRON | 📋 P43 W1-2 |
| **BET-COMPASS-STANDALONE** | c2g 独立化为 `projects/compass` | V2 自治 | 1 月 | 全部前置 | 📋 P45 |

**已完成**:
- ✅ P43 W0: `c2g radar` 真审计接入(90 任务,3 异常触发)
- ✅ P43 W0: `health.yaml` SSOT 落地,`system.yaml` 引用化
- ✅ P43 W0: pre-commit hook 强制 SSOT 一致性(改坏 system.yaml → exit 1)

---

## 4. 关键决策(不可逆)

1. **SSOT 唯一源** = `.omo/state/health.yaml` (c2g radar 生成)
2. **任何想法**必须走 `c2g brainstorm` / `c2g draft`
3. **任何任务**必须走 `c2g bet`
4. **Phase 推进** = radar 全绿 + 0 异常(自动)
5. **健康分字段** = 引用制,非静态 (`health_score_ref: .omo/state/health.yaml`)

---

## 5. P43 W0 试点 evidence(2026-06-16)

| 项 | 状态 | 证据 |
|----|:----:|------|
| c2g 5 tests passed | ✅ | `cd projects/c2g && uv run pytest tests/ -q` → `5 passed in 0.20s` |
| c2g CLI 可用 | ✅ | `uv run --project projects/c2g c2g --help` 列出 5 子命令 |
| radar 真审计 90 任务 | ✅ | 30 done + 60 planned |
| health.yaml 落 SSOT | ✅ | `cat .omo/state/health.yaml` → health_score: 55 |
| system.yaml 引用化 | ✅ | `health_score_ref: .omo/state/health.yaml` |
| pre-commit hook 阻断 | ✅ | 改坏 system.yaml → exit 1 |

---

## 6. P43 W1 计划(下周)

| 任务 | 目标 | 风险 |
|------|------|------|
| 挂 `c2g radar` 每日 cron | 生成器自动化 | 资源消耗监控 |
| 挂 `c2g gc` 每周 cron | 28d 滞留清理 | false positive |
| observability 0 行空壳治理 | 走 c2g 全链路 | 试点失败熔断 |
| planned 任务分类 | 30 active / 30 archive | 工作量 |

---

## 7. 风险与防御(摘自 Plan §9)

| 风险 | 防御 |
|------|------|
| radar cron 资源耗尽 | 控制在 1 min/日, 超阈值熔断 |
| 试点失败, 治理中断 | 熔断机制 (Plan §5.3), 失败退回 |
| SSOT 修复引入新失序 | pre-commit hook 强制 |
| 批量治理病复发 | 限制一次性 commit 文件数 ≤ 10 |
| 想法收口过严, 创新窒息 | brainstorm 失败可自由写 |
| c2g 自身演进干扰治理 | c2g 走独立版本, 治理侧只调稳定 API |
| Phase 推进自动化误判 | 异常告警 > 5 时暂停自动推进 |

---

## 8. 引用文档

- [`/Plans/c2g-enchanted-coral.md`](../../../Plans/c2g-enchanted-coral.md) — 完整规划
- [`.omo/standards/PITCH-TEMPLATE-C2G.md`](../../standards/PITCH-TEMPLATE-C2G.md) — Pitch 模板
- [`.omo/standards/task-yaml-rules.md`](../../standards/task-yaml-rules.md) — 任务 YAML 7 规则
- [`.omo/standards/C2G-Decoupling-Audit.md`](../../standards/C2G-Decoupling-Audit.md) — c2g 独立化(本规划互补)
- [`.omo/_knowledge/management/governance-charter-v1.md`](governance-charter-v1.md) — 5+3+1 宪章
- [`.omo/_knowledge/management/x-axis-implementation-registry.md`](x-axis-implementation-registry.md) — X1-X4 注册表
- [`projects/c2g/src/c2g/strategy.py`](../../../projects/c2g/src/c2g/strategy.py) — radar/gc 真实实现
- [`projects/c2g/src/c2g/bridge_import.py`](../../../projects/c2g/src/c2g/bridge_import.py) — bet 流程
- [`bin/compass_radar.py`](../../../bin/compass_radar.py) — health.yaml 生成器
- [`bin/check_health_ssot.py`](../../../bin/check_health_ssot.py) — SSOT 一致性校验

---

*签发: 2026-06-16 · 老王(代夏起草) · 关联规划 c2g-enchanted-coral · 试点 P43 W0 实证中*
