---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-26
last_updated: 2026-08-26
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-18
type: ssot
last_updated: 2026-09-03
---

# Resident 知识兑现闭环：promote 自动化 + 五问提炼真实入库 + 草稿 retention + retro 索引

> 日期：2026-08-26
> 状态：accepted
> BET：BET-Y1Q3-T10-18
> 上游：resident 体系价值兑现优化轮（T6-14 复盘「接线完整、价值未兑现」）；T10-17 五问提炼能力已实现但产物从未真实入库
> 方向：Task #51 下一里程碑（用户选定「以上全部，依次执行」，本 BET 为方向 A：知识兑现闭环）

## 背景与问题

resident sediment 体系（T10-11 沉淀管线 + T10-15 事件源接入 + T10-17 五问提炼）能力已完整接线，
但**运行自动化缺失 + 产物从未入库**——「接线完整、价值未兑现」最直接的体现：

1. **promote cron 未装配**：`bin/ssot/install-resident-cron.sh` SSOT 已含 `CRON_PROMOTE`
   （每 10min `omo resident promote`，L51），但当前 crontab 缺 promote/ingest/inbox 三个条目，
   `promote.log` 不存在——promote 从未被 cron 运行过。
2. **main 上 resident retro 全为旧格式**：`.omo/_knowledge/retros/resident/*.md`（12 篇）
   全为 2026-08-23 旧清单格式（文件名列表 + 空待完善区），**无任何含五问骨架的产物**。
3. **T10-17 能力未兑现**：`ledger_trace.py` + `promote.py --fill-five-q` 已实现且 dry-run 实测
   （502 草稿 → 14 主题，five_q_filled=14/14，failure_rate 22.9%），但从未真实落盘入库。
4. **草稿无限堆积**：`.omo/_knowledge/sediment/` 508 篇草稿（runs 387/failures 115/inbox 5/signals 1）
   只增不减（gitignored，无 retention 机制）。
5. **retro 无索引**：retros 只被「存在性检查」消费（文件是否存在），内容无人读，无检索路径。

## 目标

让 resident 知识沉淀链路「事件 → 草稿 → 五问提炼 retro → 知识」**真正运行并入库**：

1. **cron 装配对齐 SSOT**：重装 resident cron（`install-resident-cron.sh`）→ crontab 含
   `CRON_PROMOTE`（*/10min）+ `CRON_INGEST` + `CRON_INBOX`，promote 持续自动化运行，
   `promote.log` 落盘可观测。
2. **真实五问 retro 入库**：非 dry-run `omo resident promote` 生成 14 篇含确定性五问骨架的
   retro → 走 worktree + PR 提交 main（`.omo/_knowledge/retros/resident/*.md` 更新，
   main 首次包含 deterministic five_q 骨架产物，兑现 T10-17 价值）。
3. **sediment 草稿 retention**：promote 支持 `--retain-days`（默认 30）：超保留窗口的已聚合
   草稿归档到 gitignored `.omo/_knowledge/sediment-archive/`，防无限堆积；
   `--dry-run --json` 报告含 `archivable_count`。
4. **retro 索引**：promote 落盘后生成 `RETRO_ROOT/index.md`（主题/草稿数/失败率/五问 filled/
   最近生成），入库 main，使 retro 可被检索消费。
5. **测试**：omo 单测覆盖 retention 归档 + index 生成 + promote 真实链路 dry-run 断言。

## 设计

### omo 侧（`projects/omo/src/omo/resident/promote.py`）

- **retention**：`promote()` 新增 `retain_days: int = 30` 参数（CLI `--retain-days`）：
  扫描 `SEDIMENT_ROOT/runs|failures` 下 mtime 超过 `retain_days` 天的草稿，
  移动到 `.omo/_knowledge/sediment-archive/<kind>/`（gitignored）；dry-run 报告含
  `archivable_count`（可归档数）与实际 `archived_count`（落盘时）。
- **index 生成**：`promote()` 落盘后写 `RETRO_ROOT/index.md`，Markdown 表格列出各主题：
  主题名 / 草稿数 / 成功/失败 / failure_rate / five_q_filled / 最近 generated_at；
  dry-run 时 `written_to` 仍为 null 不落 index。
- **幂等**：不重写存量草稿；归档移动不删除（可恢复）；无草稿时 promote 正常返回空报告。

### 主仓侧

- **cron 装配**：运行 `bash bin/ssot/install-resident-cron.sh`（SSOT 已含 CRON_PROMOTE/INGEST/INBOX），
  使 crontab 对齐；确认 `promote.log` 在 cron 运行后落盘。
- **真实产物入库**：共享 checkout（有 sediment/events 运行时数据）跑一次非 dry-run promote，
  将生成的 `retros/resident/*.md`（含五问骨架）与 `index.md` 复制进 worktree 提交 main。
- **spec / 台账**：本 spec + 台账 `BET-Y1Q3-T10-18` 条目。

## done_when (AC)

1. crontab 含 `CRON_PROMOTE`（*/10min `omo resident promote`）+ `CRON_INGEST` + `CRON_INBOX`
   （重装 `install-resident-cron.sh` 后验证），promote.log 存在且非空。
2. `omo resident promote`（非 dry-run）在含运行时数据的 checkout 生成 14 篇含确定性五问骨架
   retro（frontmatter + 骨架段非空），并经 PR 提交 main。
3. `promote.py` 支持 `--retain-days`（默认 30）：dry-run 报告含 `archivable_count`，
   落盘时超窗草稿移入 `.omo/_knowledge/sediment-archive/`（gitignored）。
4. promote 落盘后生成 `RETRO_ROOT/index.md`（主题/草稿数/failure_rate/five_q_filled/生成时间），
   经 PR 提交 main。
5. 测试：`tests/unit/test_resident_promote_retention_index.py` 覆盖 retention 归档 + index 生成。

## verify

- `uv run --directory projects/omo --with pytest python -m pytest tests/unit/test_resident_promote_retention_index.py -q` → exit 0
- `PYTHONPATH=projects/omo/src <python3> -m omo.cli resident promote --dry-run --json`
  → `drafts_scanned >= 400` 且 `topics >= 10` 且 `five_q_filled >= 10`

## non_goals

- 不引入 LLM / 不自动撰写语义项（关键发现/交接建议留运营 agent/人工）
- 不重写存量草稿（幂等不覆盖）
- 不改 events.jsonl schema / 不加事件类型 / 不改 daemon 路由 / 不改五问定义
- 不建决策提案采纳闭环（方向 B 另开 BET）
- 不处理 Agent Cell 子系统（executor/planner/governor 等，方向 C 另开 BET）
- 不补规格文档漂移（inbox/monitor/heartbeat/omo cell，方向 D 另开 BET）
