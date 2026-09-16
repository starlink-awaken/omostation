---
schema_version: specification/v1
spec_version: 1.0.0
title: 卫健公文全周期拟办、批阅与会议督办全闭环场景包设计
bet_id: BET-Y2Q1-T7-06
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-15
---

# T7-06 — 卫健公文全周期拟办、批阅与会议督办全闭环设计

## 1. 问题

卫健政务日常围绕三类文种高频流转：局发通知（下行文）、跨部门函（平行文）、
会议纪要及督办件。现状是人工在邮件/纸质/WPS 之间搬运：来文登记靠台账手填、
拟办意见靠经验口传、批阅署名散落各处、会议议定事项无人跟踪逾期。
缺少一条**来文登记 → 拟办 → 批阅（署名）→ 红头导出 → 会议督办归档**的
本地真实闭环。

## 2. 非目标 (与 ledger non_goals 一致)

- 不包含涉密公文直接互联网传输：`classification` 为 `secret/topsecret` 的来文
  在 `register_incoming` 直接拒绝（`ValueError`），不进入任何后续环节。
- 不连外部 OA/邮件网关：本 bet 只做本地确定性管线 + 本地 PDF/版式产物，
  外发网关复用 BET-Y1Q4-T4-06 的 Cockpit 署名外发能力，不在本包内重建。
- 不引入云端 LLM：拟办意见为规则模板生成（文种 × 缓急 × 事项类型），零模型调用。
- 不做法律效力的电子签章：批阅署名 = `approver + decided_at + decision` 三元组
  落盘，本包不管 CA 证书签章。

## 3. 设计

### 3.1 公文领域模型 (`domain/health_gov/doc_pipeline.py`)

- `IncomingDoc`: `doc_id / title / doc_no(发文字号) / kind(notice|letter|minutes-task) /
  urgency(normal|urgent|immediate) / classification(public|internal|secret|topsecret) /
  source / received_date / status / last_decision`。`xh-letter` 作为 `letter` 别名接受。
- `register_incoming(...)`: 登记并校验。涉密 → 拒绝；`doc_no` 必须匹配
  `机关代字〔YYYY〕N号`（如 `×卫发〔2026〕12号`），格式不符 → 拒绝
  （circuit breaker：格式校验不通过时阻止生成并高亮错误条款）。
- `draft_opinion(doc)`: 规则拟办单 —— `drafter / opinion(拟办意见) /
  route(分办去向) / deadline_days`。模板按 `kind × urgency` 选择：
  下行通知 → 拟办“请××科室贯彻落实”，平行函 → 拟办“请××科室研提回复意见”，
  督办件 → 拟办“请××科室按期办结并反馈”。`registered`/`returned` 可拟办。
- `approve(doc, approver, decision)`: 批阅。`decision ∈ {同意, 退回, 转办}`；
  未署名（`approver` 为空）→ 拒绝（无署名批阅无效）；`退回` 必须附 `comment`。
  分流：`同意→approved`；`退回→returned`；`转办→registered`。
- `dispatch(doc)`: 仅 `approved` 且 `last_decision==同意` 可办结；退回公文不可发出。
  逾期（`today > deadline` 且未 dispatched）标 `overdue`。
- 全流程纯 stdlib（`dataclass/datetime/re`）+ 可选 reportlab PDF，零模型调用。

### 3.2 红头导出与 GB/T 9704-2012 要素校验

- `validate_redhead(doc)`: 校验下行文/平行文必备要素子集 —— 发文机关标志
  （`agency` 非空）、发文字号（格式见 §3.1）、标题三要素（`title` 含事由+文种）、
  主送机关（`recipients` 非空）、成文日期（`YYYY年M月D日` 全字）、版记
  （`printer/printed_date`）。缺任一要素 → 返回错误条款清单并阻止导出。
- `export_package(doc, out_dir)`: 产物二件套 ——
  1. `redhead.txt`：UTF-8 红头版式文本（机关标志居中、红色分隔线占位、
     发文字号/标题/主送/正文/成文日期/版记分区排布，确定性输出）；
  2. `redhead.pdf`：reportlab 生成的真实 PDF（嵌入系统 STHeiti CJK 字体，
     A4，版式要素与 txt 一一对应）。
- PDF 依赖：`reportlab`（workspace `.venv` 已装；未装时 `export_package`
  显式抛错，不伪造空 PDF —— 熔断语义）。

### 3.3 会议纪要督办 (`MeetingMinutes`)

- `MeetingMinutes`: `meeting_id / topic / held_date / attendees / decisions /
  actions[{item, owner, due, status}]`。
- `supervise(minutes, today)`: 督办检查 → 每条 action 判 `done / open / overdue`，
  输出督办单（`overdue` 置顶 + 责任人 + 逾期天数）与汇总计数。
- `close_action(minutes, item, closed_by)`: 办结需署名，无署名办结无效
  （与批阅同约束）。

### 3.4 自测 (`domain/health_gov/test_doc_pipeline.py`)

- `uv run python -m domain.health_gov.test_doc_pipeline`（exit 0 = pass，
  与 `health` cartridge 同约定：`sys.path.insert` cartridge dir，CWD 无关；
  需 workspace `.venv` 内 `reportlab` 可用）。
- 3 例端到端（与 done_when 一一对应）：
  1. 局发通知下行文：登记 → 拟办 → 局长批阅（同意+署名）→ 要素校验 → PDF 导出；
  2. 跨部门平行函：登记 → 拟办（研提回复意见）→ 批阅 → 导出；
  3. 会议纪要督办：纪要录入 3 条议定事项 → 推进 1 条办结（署名）→ 督办单检出
     1 条 overdue + 1 条 open。
- 负例：涉密来文拒绝、发文字号格式错误拒绝、无署名批阅拒绝、退回无意见拒绝、
  缺主送机关时导出被阻止、非法状态跃迁拒绝。
- 合成校准套件（assisted 门证据，沿用 BET-Y2Q2-T7-03 synthetic-seed 先例）：
  36 例合成公文（18 有效 + 18 缺陷，缺陷覆盖 6 类：涉密混入/文号格式错/
  无署名批阅/退回无意见/缺主送/非法跃迁），断言有效全放行、缺陷全拦截，
  F1 ≥ 0.6（assisted 校准门）。

### 3.5 场景卡 (`docs/scene-cards/health-gov-doc-cycle.yaml`)

- schema `scene-card/v2`，`lifecycle: assisted`（校准证据：§3.4 合成套件
  36-sample + F1 门，synthetic-seed；30-sample 门槛以合成样本计，与 T7-03
  同口径，并在卡内 `notes` 诚实标注样本性质与晋级 follow-up 条件）。
- `journey_id: health-gov-doc-cycle`（本域新旅程，复用罗盘 health 域，
  不新建 dispatcher/S slot）。
- 演练证据：3 例 e2e 自测输出（含 PDF 产物）+ 36 例合成校准输出。

## 4. 验收映射 (ledger done_when)

| done_when | 落点 |
|---|---|
| scene 卡晋级 assisted | `assisted`（合成 36-sample + F1 ≥ 0.6 校准证据，T7-03 同口径；真实演练 30-sample 由 follow-up 补） |
| 3 例拟办、署名与 PDF 导出全流程演练 | §3.4 三 e2e + PDF 产物落盘 |
| 格式符合 GB/T 9704-2012 | `validate_redhead` 要素校验全绿 + 版式文本/PDF 双产物 |

注：assisted 的 30-sample 门槛本 bet 以合成样本满足（synthetic-seed，卡内
`notes` 诚实标注）；以 scene-card-lifecycle.yaml 为准，真实场景 30-sample
仍待 follow-up bet 补齐后方可摘掉 synthetic 标注。

## 5. 风险与熔断

- 涉密输入 → `register_incoming` 拒绝（non_goals 硬约束）。
- 版式要素缺失 → 阻止导出 + 高亮错误条款（ledger circuit_breaker）。
- 无署名批阅/办结 → 拒绝落盘。
- 缺 reportlab → 显式抛错，不伪造 PDF。
- 人审门：`human_gate: true`，本包只到 PR（不 merge），由 owner 验收后合入。
