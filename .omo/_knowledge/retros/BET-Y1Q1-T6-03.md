---
status: active
lifecycle: history
owner: governance-team
bet: BET-Y1Q1-T6-03
last-reviewed: 2026-08-16
---

# BET-Y1Q1-T6-03 复盘

## Q1 实际耗时 vs appetite？
Appetite 2 days。在已有 `work/bet-y1q1-t6-02` 上跟进，未另开 T6-02。

## Q2 done_when
- closeout 后感知不再假 `missing-bet`：是（`bound_state=closed` / `BET-ID (closed)`）
- omo.workflow.cli start 与 wrapper 同一 halt：是
- gen-agent-redlines 含 `vision-to-retro-chain`：是
- 2026-08-16 各洞记账：见下表

## Q3 打假
- T6-02 已 done，本轮登记 T6-03，没有静默重开。
- cockpit `agent start` 本来就转发 `bin/agent-workflow.py`，真正旁路是 `omo.workflow.cli`。
- `docs/generated/` 整目录 gitignore；digest 靠 `make gen-agent-redlines` 现场生成，不入库。
- #1547 已 squash 合入 `737da2b52`（T6-02 链在 main）。T6-03 跟进见 #1555，被 branch protection 挡住，需 CI/人类。

## Q4 净增减
- 根仓：感知谓词 + digest 生成器 + 测试 + 指针
- omo：`28bfeaf` start 硬门 + persist `bet_id`
- GaC required：+0
- ADR：+0

## Q5 下一个 agent
合 #1547 之前 main 上没有 T6-02/T6-03。digest 变更后跑 `make gen-agent-redlines`。不要再给 T6-02 加写面。

## 2026-08-16 洞对照

| 洞 | 状态 | 指针 |
|---|---|---|
| closeout 后 `missing-bet` | **fixed** | `chain_bind.perception_fields` |
| omo CLI 无 `--bet` 可开工 | **fixed** | `omo.workflow.cli` start + `start_run` persist |
| gen-agent-redlines 看不见链红线 | **fixed** | `bin/mof/gen-agent-redlines.py` 附录 `redlines.yaml` |
| tag 未推 origin | **fixed** | `bet/BET-Y1Q1-T6-02-20260815T134729Z` 已 push |
| #1547 未进 main | **fixed** | squash `737da2b52`；map + chain_bind 已在 origin/main |
| T6-03 感知/旁路/digest | **blocked** | #1555 MERGEABLE，branch protection 等 CI/人类 |
| submit 自动 wip 夹带脏文件 | **deferred** | 本 bet non_goal |
| D3/D5 / gbrain+kairon | **deferred** | grill 未授权 |
