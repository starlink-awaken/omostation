---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T7-02
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T7-02 多维日历日程感知与督办闭环设计

## 1. 目标

接入日历数据（ICS 订阅面 + 本地事件注入），自动生成会前速递简报；
对会议录音/转写文本提炼核心议题与交办事项，生成督办清单并入库
Cockpit 待办（signal_router 感知通道）。

## 2. In scope

1. `projects/cockpit/src/cockpit/commands/calendar.py`（新文件）：
   - `parse_ics(text)`：ICS（VEVENT：SUMMARY/DTSTART/DTEND/LOCATION/
     DESCRIPTION）→ 标准事件字典（RFC 5545 子集，零依赖解析）。
   - `prebrief(event, context)`：会前速递简报（时间/地点/议题要点/
     建议准备材料清单，规则生成）。
   - `extract_action_items(transcript)`：转写文本 → 交办事项
     （任务句式规则匹配：动词开头/责任词/时间词标注）+ 决策要点，
     输出结构化督办清单（accuracy 语义以规则命中样例集验证）。
   - `cockpit calendar prebrief --ics <f>` 与
     `cockpit calendar minutes --transcript <f>` 命令面。
2. `bin/bc-os/signal_router.py`（增量）：calendar 事件 → signal 事件
   的投递适配（复用既有路由结构）。
3. `projects/cockpit/tests/test_calendar.py`（新文件）：ICS 解析/
   简报生成/交办抽取（含责任人+时间节点）/signal 投递。

## 3. Out of scope

- 不接真实 CalDAV 服务器/腾讯会议/钉钉 API 凭据（ICS 订阅文本与
  转写文本为注入面，真实通道属部署配置）。
- 录音转写（Whisper/FunASR）属 T2-01 语音链路，本 bet 消费其文本输出。

## 4. 验收（对齐 ledger done_when）

1. ICS 事件自动转化为会前速递简报（含建议准备材料）。
2. 转写文本提炼交办事项（含责任人与时间节点标注），样例集命中。
3. 督办清单结构化入库（signal 路由投递可验证）。
4. 单测全部通过。
