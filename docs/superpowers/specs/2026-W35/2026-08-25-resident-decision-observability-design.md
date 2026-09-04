---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-25
last-reviewed: 2026-08-25
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-13
type: ssot
last_updated: 2026-09-03
---

# Resident 决策提案可观测出口 (decision 提案收件箱 + CLI 审计)

> 日期：2026-08-25
> 状态：accepted
> BET：BET-Y1Q3-T10-13
> 上游：BET-Y1Q3-T6-14 复盘 §6（docs/reports/2026-08-24-resident-system-deep-review.md）

## 背景与问题

T6-14 复盘实测确认 resident 体系「接线完整、价值未兑现」，§6 防腐缺口原文：

> **decision 提案缺少可观测出口**。decision_agent 的产出（决策提案）只有水位文件计数，
> 没有沉淀到可检索的 `.omo/_knowledge/` 或提案收件箱，导致"大脑决策"既无输入追踪
> （输入是 StepFailed）也无输出审计。

现状核实（2026-08-25）：

- decision_agent（`projects/omo/src/omo/resident/decision.py`）把提案 JSON 写到
  `.omo/_knowledge/evolution-proposals/`（已堆积 **3898** 个），路径虽在 `_knowledge` 下，
  但**无索引、无 CLI 查询入口、无沉淀消费**——JSON 是机器可读的原始堆叠，不在知识检索体系内。
- `resident status` 面板只显示 decision 水位文件计数（resident-decision.json mtime），
  不展示任何提案内容 → 「大脑决策」产出不可审计。
- 输入追踪（trace_id / event_id / workflow_run_id）已在提案 JSON 的 `trigger_event` 中保留，
  但无面向人的视图。

## 目标

补齐 decision 提案的可观测出口，让「大脑决策」既有输入追踪也有输出审计：

1. **提案收件箱（可检索 md 视图）**：decision_agent 写提案时同步写一份人读 md 草稿
   （status: draft + trace_id 溯源）到 `.omo/_knowledge/decision-proposals/` 收件箱，
   与 JSON 一一对应，可通过 grep / 文档检索直接看到「决策了什么、基于什么事件」。
2. **CLI 输出审计出口**：`omo resident decision list/status/show` 子命令——
   扫描 evolution-proposals JSON（含历史 3898 条，立即可审计），输出提案清单、统计分布、
   单条详情；让「大脑决策」的产出可查、可追踪、可复盘。
3. **输入追踪保留**：md 收件箱 frontmatter 完整保留 trigger_event（event_type /
   trace_id / workflow_run_id / event_id）溯源链。

## 非目标

- 不改提案 JSON 契约（`resident-decision/v1` schema 与 evolution-proposals 落点保持兼容）。
- 不引入 LLM 调用（提案内容仍由 evolution-agent 的 `scan_internal` 确定性生成）。
- 不解决提案内容本身的知识提炼/行动闭环（那是运营 agent/人工复盘，另开 BET）。
- 不对历史 3898 个 JSON 批量回填 md 文件（避免模板草稿膨胀）；历史通过 CLI 按需渲染，
  全量可查。

## 设计

### 1. 提案收件箱 md 视图（增量双写）

`decision.py` `_write_proposal()` 写 JSON 后，同步写一份 md 草稿：

```
.omo/_knowledge/decision-proposals/decision-{ts}-{slug}.md   (与 JSON 同 slug 一一对应)
```

md 内容（人读、可 grep）：

```markdown
---
schema: resident-decision/v1
status: draft
trigger_event_type: StepFailed
trace_id: ...
workflow_run_id: ...
event_id: ...
generated_at: ...
---

# 决策提案 (事件驱动草稿)

## 触发事件
- event_type / trace_id / workflow_run_id / event_id

## 提案内容 (N 条)
- [severity] type=... level=... source=... proposal=...
```

- 文件名与 JSON 复用同一 `ts` + `slug`（`decision-{ts}-{slug}`），幂等（每次触发新文件，不覆盖）。
- 落点 `.omo/_knowledge/decision-proposals/` 是收件箱语义：人读、可检索、可 grep。

### 2. CLI 输出审计出口

在 `decision.py` 的 `main()` 增加子命令分发（兼容原有 `--json` 事件消费模式）：

| 子命令 | 功能 | 输出 |
|--------|------|------|
| `list [--limit N]` | 扫描 evolution-proposals JSON（按文件名倒序=时间倒序），列最近 N 条 + 汇总统计 | 表格 + 计数（总提案数、按 event_type 分布） |
| `status` | 决策快照：总提案数、触发事件分布、最近提案时间、建议类型/级别分布 | 对齐 `resident status` 面板风格 |
| `show <file>` | 渲染单条提案为 md 视图（读 JSON → 格式化） | 人读 md |
| `--json <event>`（原模式） | 单事件 → 提案（保留兼容） | `{"written": ..., "path": ...}` |

- 历史 3898 个 JSON 无需预渲染：`list`/`status` 直接扫描目录，立即可审计。
- `show` 对单条输出完整溯源 + 提案明细，满足「输出审计」。

### 3. 接线与兼容

- `omo resident decision`（`cli.py` SUBCOMMANDS 已含 decision）直接调用 `decision.main`，
  无需改 cli.py 注册表。
- `bin/ssot/decision-agent.py`（兼容脚本，WP-I 双路径保留）保持原 JSON 写入契约不变；
  可观测出口统一收敛到 `omo resident decision` CLI。
- `resident status` 面板不做改动（仍显示水位；提案内容由 `decision status` 提供）。

## 接口

- `omo.resident.decision`：`_write_proposal` 增量双写 md 收件箱；`main` 增
  `list/status/show` 子命令。
- `projects/omo/src/omo/resident/decision.py`：核心改动文件。
- 新增测试：`projects/omo/tests/test_resident_decision.py`。

## 测试

- 单元测试（fixture 临时 WORKSPACE）：
  1. `_write_proposal` → evolution-proposals 下 JSON 与 decision-proposals 下 md 均生成，
     md frontmatter 含 trigger_event 溯源 + `status: draft`。
  2. `list --limit N`：扫描 N 条 + 汇总统计正确（含空目录容错）。
  3. `status`：快照字段齐全（总数/分布/最近时间），空目录不报错。
  4. `show <file>`：渲染含触发事件 + 提案明细。
  5. 幂等：同事件重复触发写不同文件（ts 不同），不覆盖。
- CLI 冒烟：`omo resident decision status` 在真实工作区可运行，输出 3898 条历史统计。

## 验收 (done_when)

1. `decision.py` `_write_proposal` 双写 JSON + md 收件箱，md frontmatter 含
   `status: draft` 与 trigger_event 溯源。
2. `omo resident decision list/status/show` 三个子命令可用，`list`/`status`
   直接扫描 evolution-proposals 全量（含历史）并输出统计。
3. 新增 `test_resident_decision.py` 单元测试全绿。
4. 真实工作区 `omo resident decision status` 可输出 3898 条历史统计（冒烟验证）。

## 关联

- BET-Y1Q3-T6-14（复盘，已 done）· BET-Y1Q3-T10-12（事件源接入，已 done）·
  ADR-0396（DigitalAgent）· `projects/omo/src/omo/resident/decision.py`
- 演进候选（不在本 BET）：决策提案 → 行动闭环接线（decision → execution）、
  decision 提案内容知识提炼（LLM 路径）。
