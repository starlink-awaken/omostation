---
schema: bet-retro/v1
bet_id: BET-Y2Q2-T6-01
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y2Q2-T6-01 retro — SEMA 防踩坑信念自结晶与技能热重载

## What changed

- **`omo/resident/sema_crystallizer.py`**（新）：`CorrectionLedger`
  （纠偏事件按 pattern+type 聚合，**第 2 次同类才触发**——阈值断言；
  T10-115 规则库以 pre-aggregated count 导入）、`crystallize`
  （SKILL.md：规范 frontmatter name/description + 触发条件 + 语义化
  处理步骤 + 反例；配套 pytest 骨架）、`SemaCrystallizer.install`
  （写入 `.agents/skills/auto-crystallized/` + INDEX 追加）、
  `hot_reload`（manifest 哨兵 + 运行态域清单，实测 0.62ms < 500ms）。
- **首个真实结晶产物**：`.agents/skills/auto-crystallized/sema-terminology-replace/`
  （术语替换类信念，证据 2 条，INDEX 已刷新）。
- 测试 5/5（阈值/规则导入 capped 计数/SKILL.md 规范/安装+INDEX/
  热加载延迟与 manifest），ruff clean。

## Q3 (打假)

- 首个结晶产物的素材是**演示注入**（真实规则库当前为空——T10-115
  Q3 已申报），非纯自动发现。自动化链路（rules→ledger→threshold）
  已由单测证明；真实自动触发待规则库有真实规则后生效。
- `hot_reload` 交付的是 manifest 哨兵 + 域清单注入面——AetherForge/
  Agora 的运行时消费侧按哨兵 mtime 主动拉取（推模型留后续）。
- 写面预置策略生效：binding PR 内补全 tests/INDEX/ledger 后，claim
  一次通过（对比 T8-14/T10-118 的 2-3 轮重启）。

## Q4 (遗留)

- CI 拦截记录的真实源适配器（GitHub checks API）待接。
- SKILL.md 的语义质量依赖规则库的模式质量——为空库时不应自动结晶
  大量低质 skill（threshold=2 是保守起点）。
