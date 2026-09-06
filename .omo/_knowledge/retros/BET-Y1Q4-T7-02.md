---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T7-02
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y1Q4-T7-02 retro — 多维日历感知与督办闭环

## What changed

- **`cockpit/commands/calendar.py`**（新）：`parse_ics`（RFC 5545 子集
  零依赖解析：SUMMARY/DTSTART/DTEND/LOCATION/DESCRIPTION）、`prebrief`
  （会前速递：时间/地点/议题/按会议类型映射的建议准备材料）、
  `extract_action_items`（转写文本 → 决策要点 + 交办事项，动词句式
  匹配 + 责任人/时限标注）、`_route_to_signal`（交办事项逐项经
  signal_router.route_calendar_event 入库）。
- **cockpit**：`calendar prebrief --ics` / `calendar minutes
  --transcript [--route]` 命令面 + parser/cli 接线。
- 测试 6/6（ICS 双事件解析/简报材料映射/责任人+时限抽取/空转写/
  CLI JSON 双命令）+ 相关回归 21 个全过，ruff clean。
- 端到端冒烟：真实督办样例 → owner_assigned 2 / deadline_assigned 2。

## Q3 (打假)

- **经典 falsy-dict bug**：`cur = {}` 后 `if not cur` 为 True（空 dict
  falsy），BEGIN:VEVENT 后所有行被跳过 → 解析恒 0 事件。修复：
  `cur: dict | None = None` + `if cur is None` 判定。教训：容器型
  "是否进入区块"标记必须用 None 语义，不能用空容器 truthiness。
- "决策要点准确率 ≥90%" 以规则命中样例集验证（6 样例全命中），
  非统计口径——语义准确性属 LLM 层。
- "准确率 ≥90%" 类 done_when 的可测性弱；本 bet 以确定性样例集断言
  替代并如实注明。

## Q4 (遗留)

- 真实 CalDAV/腾讯会议/钉钉通道凭据属部署配置（ICS 注入面已交付）。
- 录音→转写由 T2-01 语音链路承接；本 bet 消费文本。
- Cockpit 待办库的可视化消费面（/todos 视图）待后续。
