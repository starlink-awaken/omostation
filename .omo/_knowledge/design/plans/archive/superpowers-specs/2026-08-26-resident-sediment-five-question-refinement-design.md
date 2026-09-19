---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-26
last-reviewed: 2026-08-26
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-17
type: ssot
last_updated: 2026-09-03
---

# Resident sediment 五问提炼：确定性骨架 + 半自动完善入口

> 日期：2026-08-26
> 状态：accepted
> BET：BET-Y1Q3-T10-17
> 上游：resident 体系价值兑现优化轮（T6-14 复盘「接线完整、价值未兑现」后四项之一）
> 方向：Task #51 下一里程碑（用户选定「sediment 五问提炼」，混合路径：确定性 + 半自动 + 人工兜底）

## 背景与问题

resident sediment 体系（T10-11 沉淀管线 + T10-15 事件源接入）已完整接线：daemon 消费统一事件流
`.omo/_knowledge/workflow-mesh/events.jsonl`（2511 行）→ sediment 草稿（runs/failures/signals/inbox）
→ promote 聚合为主题 retro。但**所有草稿与 retro 的五问（计划 vs 实际 / 结果与证据 / 关键发现 /
净增减 / 交接建议）全是空 checkbox**（508 篇草稿全是模板占位），「沉淀了但没有提炼」，知识价值未兑现。

代码实证（sediment.py:88-89、promote.py:171）：
- `sediment.py:_sediment_run()` 草稿 body 含「## 待补充(五问/模式提炼)」5 个空 checkbox；
- `promote.py:_write_retro()` 聚合 retro 正文含「## 待完善(运营 agent/人工)」5 个空 checkbox；
- 而 events.jsonl 每条事件 payload **已携带可确定字段**（`WorkflowRequested`→objective/workflow_id，
  `StepFailed`→step_name/error，`WorkflowSucceeded`/`WorkflowClosed`→ok/status/evidence_count），
  同一 run 的完整事件序列足以确定性还原五问骨架的绝大部分，却从未被消费。

T10-11 spec 明确把「sediment 五问自动撰写」列为**演进候选（不在该 BET）**；T10-15 spec 明确把
「信号五问提炼」列为**下一里程碑（B sediment 五问提炼）**——本 BET 正是承接该演进候选，但采用
**混合路径**：确定性部分自动填充，语义部分留给运营 agent/人工，**不引入 LLM、不编造内容**。

## 目标

让 sediment 草稿与聚合 retro 的五问从「全空」升级为「**确定性骨架已填 + 语义项待完善**」：

1. **确定性提取（ledger 追溯）**：新增 `omo.resident.ledger_trace`，读统一事件流 events.jsonl，
   按 `workflow_run_id` 聚合事件序列，确定性提取可确定五问骨架：
   - **计划 vs 实际**：`WorkflowRequested.payload.objective`（计划）+ 事件序列中 step 序列（实际）
   - **结果与证据**：终态事件（Succeeded/Closed/Failed）payload `ok`/`status` + `evidence_count`
   - **失败根因**：`StepFailed`/`WorkflowFailed` 的 `error` + `step_name`（失败点）
   - **指标**：run 事件序列长度、首末事件时间差（run 生命周期）、evidence_count
2. **promote 聚合五问填充**：`resident promote` 新增 `--fill-five-q` 开关（默认 true），
   对每个主题 retro 的「计划 vs 实际 / 结果与证据 / 失败根因 / 指标」填入确定性骨架，
   **「关键发现 / 交接建议」语义项保持空 checkbox**（人工兜底）。
3. **sediment 草稿五问填充**：`sediment.py` 草稿生成时，把事件自带 payload 的可确定字段
   （objective/error/status/evidence_count/step_name）内嵌进草稿，使**新草稿**不再纯空
   （存量草稿幂等不覆盖，由 promote 追溯兜底）。
4. **半自动 CLI 入口**：`resident promote --fill-five-q --json` 输出每个主题的可确定五问骨架
   JSON，供运营 agent 基于 ledger 上下文填写语义项。

## 设计

### omo 侧（`projects/omo/src/omo/resident/`）

**`ledger_trace.py`（新建）**：
- `iter_run_sequences(events_path)`：逐行读 events.jsonl → 按 `workflow_run_id` 分组为有序事件序列
  `{run_id: [Event,...]}`（保持 occurred_at/文件序）
- `extract_deterministic_five_q(sequence)` → `dict` 骨架：
  ```python
  {
    "run_id": str,
    "workflow_id": str|None,          # WorkflowRequested.payload.workflow_id
    "objective": str|None,            # WorkflowRequested.payload.objective (计划)
    "steps": [str,...],               # StepStarted/StepDispatched/StepFailed 的 step_name 序列 (实际)
    "outcome": {ok, status, evidence_count} | None,   # 终态事件 payload (结果与证据)
    "failure": {step_name, error} | None,             # StepFailed/WorkflowFailed (失败根因)
    "metrics": {"event_count": int, "duration_s": float|None},  # 指标
  }
  ```
- `load_run_skeletons(events_path)` → `{run_id: skeleton}` 全量索引（promote 调用一次，内存缓存）

**`promote.py`**：
- 新增 `--fill-five-q`（action store_true / 默认 true 用 `default=True`？——显式布尔更清晰：
  `--fill-five-q` 默认开启，`--no-fill-five-q` 关闭）
- `_write_retro()` 接收 ledger skeletons；「## 待完善」段改为：确定性项渲染为填充列表
  （`- **计划 vs 实际**：<objective> / <steps...>`），语义项保留 `- [ ] 关键发现` / `- [ ] 交接建议`
- 新增 `_render_deterministic_five_q(topic, bucket, skeletons)` 渲染确定骨架
- `--json` 报告含 `five_q_filled` 计数（多少主题获得确定性骨架）

**`sediment.py`**：
- `_sediment_run()` 草稿 body 增加「## 事件 payload 摘要（确定性）」段：从 `event.payload` 提取
  objective/error/status/ok/evidence_count/step_name 存在字段内嵌（不读事件流文件，仅用当前事件）
- 五问 checkbox 保持（语义项人工填），但草稿顶部已有可确定信息，非纯空

**`cli.py`**：promote 子命令透传 `--fill-five-q` 参数（resident promote 已存在，参数增补即可）

### 测试（omo 侧）

- `test_ledger_trace.py`：构造 events.jsonl fixture（run 含 Requested→Started→Succeeded 全序列）
  → `iter_run_sequences` 聚合正确 + `extract_deterministic_five_q` 提取 objective/steps/outcome/
  failure/metrics 各字段（含失败 run、缺终态 run 的容错）
- `test_resident_promote_five_q.py`：mock sediment 草稿 + events.jsonl → `promote --fill-five-q`
  产出 retro 含确定性骨架、「关键发现/交接建议」仍为空 checkbox、--json 报告含 five_q_filled

## 非目标

- **不引入 LLM / 不自动撰写语义项**（关键发现、交接建议、净增减的语义判断留运营 agent/人工；
  延续 T10-11「不自动撰写『五问』正文」边界，本 BET 只填充**可确定**部分）
- **不重写存量 508 篇草稿**（幂等不覆盖；存量经 promote 追溯在 retro 层面获得骨架）
- **不新增事件类型 / 不改 events.jsonl schema / 不改 daemon 路由**
- **不扩展五问定义**（沿用现有 5 项：计划 vs 实际 / 结果与证据 / 关键发现 / 净增减 / 交接建议）

## 验收

- [ ] `ledger_trace.extract_deterministic_five_q` 对真实 run 序列（如
      `20260803T063243Z-governance-state-mutation-0fd89888`）正确提取
      objective/steps/outcome/failure/metrics
- [ ] `resident promote --fill-five-q`（或默认）产出 retro：确定性项已填、
      「关键发现 / 交接建议」保持空 checkbox；`--json` 报告含 `five_q_filled`
- [ ] `sediment.py` 新草稿含「事件 payload 摘要（确定性）」段（objective/error/status 内嵌）
- [ ] omo 单测 + 集成测试全绿；主仓 gac-local-gate 通过
