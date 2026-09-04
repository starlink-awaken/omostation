---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-25
last_updated: 2026-08-25
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-11
type: ssot
last_updated: 2026-09-03
---

# Resident sediment 草稿→完整知识晋升管线 (promote 增强 + 自动化)

> 日期：2026-08-25
> 状态：accepted
> BET：BET-Y1Q3-T10-11
> 上游：BET-Y1Q3-T6-14 复盘 §4/§5/§8（docs/reports/2026-08-24-resident-system-deep-review.md）

## 背景与问题

T6-14 复盘实测确认 resident 体系「接线完整、价值未兑现」：

- **sediment 产出 100% 是模板占位**：`.omo/_knowledge/sediment/{runs,failures}/` 下 412 条草稿
  只有事件元数据 + 5 个空 checkbox（计划 vs 实际 / 结果与证据 / 关键发现 / 净增减 / 交接建议），
  没有任何一篇完成真正的知识提炼，使「知识沉淀」名存实亡。
- **promote 命令已存在但未实际消费**：`omo resident promote` 已能按 workflow 主题聚合
  412 草稿 → 12 篇 retro candidate（`.omo/_knowledge/retros/resident/`），但：
  1. 未接入 cron（`install-resident-cron.sh` 无 promote 行），只能手动触发；
  2. 产出仍是「文件列表 + checkbox」的候选聚合，**没有失败根因分类、没有按主题/类型的
     成功率统计、没有可检索的结构化指标**——「失败沉淀没有变成可检索的避坑知识」（复盘 §4）。

复盘 §8 下一步点名：「补一条『草稿→完整知识』的晋升管线（promote 场景升迁已列 CLI，
但未见实际消费）」。

## 目标

让 sediment 沉淀从「不可检索的散件」升级为「可检索、可统计、可溯源的主题知识」：

1. **promote 产出增强**：聚合 retro 从 checkbox 列表升级为带结构化 frontmatter +
   指标统计的提炼文档，包括：
   - 每个主题的 runs/failures 计数、失败率；
   - 失败 event_type 分布（StepFailed / WorkflowFailed / StepTimeout 根因画像）；
   - 草稿 → ledger 的可追溯链接（event_id / trace_id / run_id 溯源）；
   - 统一 frontmatter（topic / kind / counts / failure_breakdown / generated_at），
     供检索与统计工具消费。
2. **promote 接入 cron**：`install-resident-cron.sh` 增加 promote 定时聚合行
   （低频，如每 30min），使晋升管线自动化。
3. **可验证**：`promote` 真实跑通生成增强版 retro，产出可检索指标。

## 非目标

- 不引入 LLM 调用：本 BET 保持确定性启发式提炼（从草稿元数据/文件名/ledger 溯源），
  不自动撰写「五问」正文（留给运营 agent/人工）。
- 不改 sediment 草稿生成逻辑（模板占位问题属上游事件源供给，另开 follow-up）。
- 不改五类角色运行时行为。

## 设计

### 1. promote.py 产出增强

`omo.resident.promote` 聚合逻辑扩展：

- `_aggregate()` 除按 topic 聚合 runs/failures 文件名外，追加结构化统计：
  - 每个草稿读取 frontmatter/元数据行（event_type、producer、event_id、trace_id）；
  - 按 topic 统计 `runs_count / failures_count / total`；
  - 按 topic 统计失败 event_type 分布（`failure_breakdown: {StepFailed: n, ...}`）；
  - 失败率 = failures / total（保留两位）。
- `_write_retro()` 输出升级：
  - 前置 YAML frontmatter：`topic / kind: aggregated-retro / status: candidate /
    counts / failure_breakdown / coverage / generated_at`；
  - 正文保留 runs/failures 列表（追溯用），新增「失败根因画像」小节；
  - 每个草稿条目保持文件名（含 run_id / event_id 后缀），即天然溯源链接。
- 保持 `--dry-run`（只统计不落盘）与 `--limit` 行为，新增 `--json` 输出完整统计。

### 2. cron 自动化

`bin/ssot/install-resident-cron.sh` 增加一行（低频，避免频繁写盘）：

```
*/30 * * * * cd <workspace> && PYTHONPATH=<omo src> <python3.11+> -m omo.cli resident promote >> <log> 2>&1
```

沿用既有 cron 的探测式 python 绝对路径（规避 crond PATH python3=3.9 陷阱）。

### 3. 数据流

```
events.jsonl --(sediment daemon)--> sediment/{runs,failures}/*.md (模板草稿)
                                            |
                                            v  (promote, 手动或 cron)
                          retros/resident/<topic>.md (增强版聚合: frontmatter + 指标 + 溯源)
```

## 接口

- `omo resident promote [--dry-run] [--limit N] [--json]`（行为兼容增强）
- `install-resident-cron.sh`（新增 promote 行）

## 测试

- promote 单元测试：给定 fixture 草稿目录，断言聚合统计正确（runs/failures 计数、
  失败率、failure_breakdown、frontmatter 生成、dry-run 不落盘）。
- 集成验证：真实运行 `promote` 生成增强版 retro，抽查 frontmatter 与指标。

## 验收 (done_when)

1. `promote` 产出 retro 含 frontmatter（topic/counts/failure_breakdown）与失败根因画像。
2. `install-resident-cron.sh` 含 promote 行且 dry-run 语法校验通过。
3. 新增 promote 单元测试全绿。
4. 真实运行生成增强版 retro，指标可检索（无回归）。

## 关联

- BET-Y1Q3-T6-14（复盘，已 done）· ADR-0396（DigitalAgent）· `resident-routes.yaml`
- 演进候选（不在本 BET）：sediment 五问自动撰写（LLM 路径）、事件源接入 workflow 生命周期。
