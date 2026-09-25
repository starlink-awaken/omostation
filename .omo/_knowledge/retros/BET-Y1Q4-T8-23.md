---
schema: md/v1
status: done
lifecycle: history
owner: unassigned
last-reviewed: 2026-09-25
type: retro
bet_id: BET-Y1Q4-T8-23
done_at: 2026-09-13
merged_reachable_commit: c37ad9ad30
---


# BET-Y1Q4-T8-23 Retro: Resident Flight Deck L1-L4 授权网关 + 四维透明指挥舱

## 交付摘要

- PR #3751 交付设计规范 + ledger 状态更新 + cockpit/cockpit-ui submodule 对齐
- 设计规范: docs/superpowers/specs/2026-09-13-t8-23-resident-flight-deck-design.md
- L1~L4 四阶梯风险-置信度自适应授权网关设计
- Cockpit Resident Flight Deck 四维透明指挥舱（心跳健康 / 任务 DAG / 算力显存遥测 / 人工熔断）

## 踩坑过程

- squash-merge 后原分支 sha 不在 origin/main 祖先链，需放宽 merge-base 校验
- completion_evidence git ref 截断为 10 位短 sha 导致 lint COMPLETION_GIT_REF_INVALID
- bet 标记 done 但缺少 done_at 字段触发 BET_DONE_AT_REQUIRED

## 经验沉淀

- completion_evidence 的 merged_reachable_commit.ref 必须使用 40 位完整小写 hex
- done 状态的 bet 必须同时具备 done_at 日期字段
- value_indicator_policy: false 时 value 轴可保持 NOT_PROVEN 达成 delivery_accepted

---

## 收尾 addendum (2026-09-14, T8-23-cont, run 20260914T064606Z-bet-execution-cdc1afa2)

### 背景：并发 PR 回退 (PITFALL-GAT-006 实录)

- PR #3751 (eed16ec080) 已将 T8-23 置 done + spec 绑定 + completion_evidence(delivery_accepted)
- 后续 PR 272194aed3 (T6-25 & T7-03 closeout, 基于旧 main) 静默回退：T8-23 done→candidate，
  accepted_specifications / completion_evidence / done_at / value_indicator_policy 全丢，
  tracks 注册表 T8-EXECUTION 定义一并丢失（致 claim-check KeyError: 'T8-EXECUTION'）
- 本次收尾 = 回退恢复 + 最小闭环交付

### 本次交付

- `projects/cockpit` (feat/bet-y1q4-t8-23-cont):
  - `HeartbeatMonitor` — 上报时间戳存活判定 + 连续 3 次超时只读降级（bet circuit_breaker 条款落地）
  - `POST /api/flight-deck/heartbeat` 上报端点；snapshot 改读真实监视器（删除硬编码示例心跳）
  - `tests/test_resident_flight_deck.py` — 28 项：L1-L4 边界/黑名单 100% 拦截/熔断 <1s/心跳降级/快照序列化
- ledger 恢复：T8-EXECUTION track 注册补回；spec 重新绑定（既有 canonical spec，digest 重算匹配）；
  completion_evidence 置 evaluating（engineering IN_PROGRESS）；write_surfaces 纠正 .vue→实际 .tsx + 补 api_flight_deck.py

### 验证

- `python3 -m pytest projects/cockpit/tests/test_resident_flight_deck.py` → 28 passed
- `bin/plan/bet-ledger.py lint` → OK (411 bets, 13 tracks, no errors)
- `make gac-local-gate` → PASS (57 checks ALL GREEN)
- ruff check clean（顺手修 import 排序 + 删未用导入）

### 踩坑

- agent-workflow start 在 worktree 内误读主仓 ledger：`omo.workflow.WORKSPACE` 硬编码主 checkout；
  必须先 `submodule update --init projects/omo projects/ecos` 再去掉 PYTHONPATH 覆盖，用 worktree 原生包
- claim interlock actor 解析 `--actor → $USER → governance-agent`：须 `USER=governance-agent` 或 `--actor`
- start 后再改 ledger write_surfaces → WORK_PACKET_SOURCE_DRIFT（无 refresh 命令，只能 close+重开 run）
- spec-init 会重写 spec frontmatter（补空行）致 digest 变化：绑定后须以新 digest 为准并核对 MATCH
- claim ledger/spec 文件自身会被 WORK_PACKET_SCOPE_MISMATCH 拒绝（应走 bet-ledger.py 治理通道）

### 待办（PR 合并后）

- 合并本 PR → completion_evidence engineering VERIFIED + operational PROVEN → `complete` 转 done/delivery_accepted
- 真实遥测（omlxc GPU 数据接入 ComputeTelemetry）与任务 DAG 真实队列接入为后续 BET 范畴
