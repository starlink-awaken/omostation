---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-26
last_updated: 2026-08-26
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-19
type: ssot
last_updated: 2026-09-03
---

# Resident 决策采纳闭环：提案状态机 + ADR 自动化 + north_star 知识消费轴

> 日期：2026-08-26
> 状态：accepted
> BET：BET-Y1Q3-T10-19
> 上游：resident 体系价值兑现优化轮；方向 B（Task #51 下一里程碑，用户选「以上全部依次执行」）

## 背景与问题

decision 角色（WP-F）每 2min 事件驱动写入决策提案（`.omo/_knowledge/evolution-proposals/` 3945 篇 JSON），
并提供 `omo resident decision list/status/show` 审计入口。但决策链路「单向写、无回读」：

1. **提案只写不消化**：3945 篇 proposal JSON 无状态字段，无法区分 new/adopted/executed/verified，
   无采纳→执行→验证状态机。
2. **proposal-to-adr 手动**：`bin/ssot/proposal-to-adr.py` 读最新 proposal → ADR 草稿（status: draft）
   → `decisions/`，仅 CLI 手动触发，不在 cron/CI，无自动推进。
3. **north_star 无知识消费轴**：`bin/bc-os/north_star_meter_v2.py`（value truth snapshot，纯投影）
   输入仅为 Outcome.Human.v1 episodes/evidence/verdict，**不读 sediment/retro/proposal**——
   知识沉淀的价值无度量。

## 目标

让决策提案从「只写不消化」变为「可采纳→可执行→可验证」的闭环，并让价值度量纳入知识消费：

1. **提案状态机**：`proposal-to-adr.py` 支持提案 status 字段（`new/drafted/adopted/executed/verified`），
   CLI `--mark-status <proposal-id> <status>` 推进（枚举校验 + 合法迁移），`--dry-run --json`
   报告含 `status_counts`（各状态提案数）。
2. **ADR 草稿自动化**：proposal-to-adr 接 cron（每天 01:00 自动把最新未消化提案转为 ADR 草稿，
   **不自动采纳**——人工/运营 agent 兜底），迁移到 `drafted` 状态。
3. **north_star 知识消费轴**：`north_star_meter_v2.py` 输出新增 `knowledge_consumption` section
   （`proposal_adoption_rate` = adopted+executed+verified / total proposals；`retro_referenced` =
   被 decisions/ 引用的 resident retro 数），**纯投影增量，不改现有 value 轴判定**。
4. **测试**：覆盖状态机迁移 + north_star 知识轴输出。

## 设计

### 主仓 `bin/ssot/proposal-to-adr.py`

- **状态机**：proposal JSON 支持 `status` 字段；合法值 `new/drafted/adopted/executed/verified`；
  合法迁移 `new→drafted→adopted→executed→verified`（允许跨步向前，禁止回退）。
- `--mark-status <proposal-id> <status>`：对指定 proposal 推进状态（幂等：已至目标状态则 noop）。
- `convert()`：处理最新 `new` 状态 proposal → 生成 ADR 草稿（现有逻辑）→ 标记为 `drafted`。
- `--dry-run --json` 报告：`status_counts`（按状态统计提案数）+ `drafted`/`adopted` 等计数。
- 兼容：无 `status` 字段的历史 proposal 视为 `new`（迁移时补写）。

### 主仓 `bin/bc-os/north_star_meter_v2.py`

- 新增 `_knowledge_consumption(workspace)` 投影函数：读
  `.omo/_knowledge/evolution-proposals/*.json`（统计 status 分布 → 采纳率）+
  `.omo/_knowledge/retros/resident/*.md` 与 `decisions/*.md`（统计 retro 被引用数）。
- 输出 snapshot 增 `knowledge_consumption` section（`proposal_total/adoption_rate/retro_referenced`）。
- **不改 value 轴判定逻辑**（`overall`/`value` 保持现行为）。

### cron

- `install-resident-cron.sh` 增 `CRON_PROPOSAL_ADR`（`0 1 * * *` 每天 01:00
  `python3 bin/ssot/proposal-to-adr.py`），与 resident 块同管理。

## done_when (AC)

1. `proposal-to-adr.py` 支持 `--mark-status <proposal-id> <status>`（枚举+迁移校验），
   `--dry-run --json` 报告含 `status_counts`；历史无状态 proposal 视为 `new`。
2. `convert()` 处理最新 `new` proposal → ADR 草稿并标记 `drafted`（dry-run 不落盘）。
3. `install-resident-cron.sh` 含 `CRON_PROPOSAL_ADR`（每天 01:00），重装后 crontab 可见。
4. `north_star_meter_v2.py` 输出含 `knowledge_consumption`（proposal_total/adoption_rate/retro_referenced），
   现有 value 轴判定不变。
5. 测试：`tests/unit/` 或根仓测试覆盖状态机迁移 + 知识轴输出。

## verify

- `python3 bin/ssot/proposal-to-adr.py --dry-run --json` → exit 0 且含 `status_counts`
- `PYTHONPATH=bin/bc-os python3 bin/bc-os/north_star_meter_v2.py --json`
  → 输出含 `knowledge_consumption`
- 相关 pytest 测试 exit 0

## non_goals

- 不自动采纳/执行提案（人工/运营 agent 兜底，只自动生成 ADR 草稿）
- 不改 decision.py 提案写入 schema（proposal JSON 结构不变，仅增 status 字段兼容读取）
- 不改 north_star 现有 value 轴判定 / 不重算历史快照
- 不引入 LLM 自动撰写 ADR 决策内容
- 不处理 Agent Cell 子系统（方向 C 另开 BET）/ 不补规格文档漂移（方向 D 另开 BET）
