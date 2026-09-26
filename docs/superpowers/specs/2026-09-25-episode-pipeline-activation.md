---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 0.1.0
title: Episode Pipeline Activation — closeout → Outcome.Human.v1 bridge
bet_id: BET-Y2Q4-SH-5
---


# BET-Y2Q4-SH-5 — Episode Pipeline Activation

## Context

`#4312 docs(root-cause)` 分析的 R1 根因是"系统缺乏持续守护"。SH-1/SH-2/SH-3/SH-4 在治理面式化上完成闭环，但**没有触及价值证明回路**。

诊断证据（2026-09-25 BCOS pulse）：

```
status: not_ready
operational_proof: proven
personal_value: not_ready       ← 唯一阻塞项
engineering_delivery: not_measured
```

`runtime/omo/event-ledger.sqlite3` 实际状态：

```
sqlite> SELECT producer, COUNT(*) FROM event_log GROUP BY producer;
omo-sovereignty|1

sqlite> SELECT COUNT(*) FROM event_log WHERE principal_id='principal:xiamingxing';
1
```

**整本 ledger 只有 1 行**（2026-09-23 角色分配）。PersonalEpisodeService 需要 `producer=personal_episode` 的 `EVT_EPISODE_DECISION` 事件，但：

1. 唯一的 producer `scene-outcome-recorder` 从未被自动调用
2. 调用入口 `cockpit /api/v1/scenes/adjudicate` 只在 UI 上点 Accept/Reject 时触发——本期无真实 Cockpit 操作
3. `agent-workflow.py closeout` 是更频繁的真实决策事件源（每 BET 关闭一次），但**完全没有桥接到 scene-outcome-recorder**

T4-01 retro 声称 `qualifying_v2=52, value_proof=PROVEN`，但数据**未进入 live ledger**——retro attestation 是基于 runtime projection 而非 broker-verified facts。这构成 **declared ≠ executed 鸿沟** 的核心证据：

| 维度 | 声明 | 实际 |
|---|---|---|
| Episodes recorded | 52 | 0 |
| PersonalEpisodeService invoked | many times | 0 |
| Personal value gate | would pass | not_ready |

R3 根因（物理-逻辑映射手工）也在这里显形：closeout 的"完成"信号存在于多个平面（agent-workflow close、retro merge、ledger event），但没有自动桥接。

## Goal

激活 PersonalEpisodeService 的 episode pipeline，使 `agent-workflow.py closeout` 自动写入 `Outcome.Human.v1` 到 ledger，让 north-star 走完事实回路：

1. **`closeout --emit-episode`** — `bin/agent-workflow.py closeout` 默认调用 scene-outcome-recorder
2. **`Outcome.Human.v1` bridge** — closeout 转化为 `verdict=accepted` 的 episode decision event
3. **readiness gate 测试** — 在 hermetic 模式下跑 30 个合成 closeout，验证 PersonalEpisodeService 能识别到 30 episodes
4. **north-star pulse** — 在不改变 ledger 历史的前提下，给出现实可证的 ≥30 episodes + 1-week sample
5. **retro record_path**：写入真实 ledger 路径（不再用 runtime projection）入证 T4-01-style attestation

## Non-goals

- **不修 PersonalEpisodeService 算法** — 30 qualifying + 4-week gate 已是 spec，不动
- **不创造 episode** — 只 wire 真实 closeout 事件流，不为达成数字而合成
- **不改 ledger schema** — 已固化在 `projects/omo/src/omo/event_ledger/schema.py`
- **不取代 Cockpit UI 路径** — `/api/v1/scenes/adjudicate` 路径保留；本 BET 只补 closeout 自动路径
- **不预填 episodes** — 不准回填历史 closeout 当 episodes（违反 attribution discipline）

## Done when

- `bin/agent-workflow.py closeout <run-id>` 完成后，**同步**调用 `bin/ssot/scene-outcome-recorder.py record`，写入 `Outcome.Human.v1` 到 `runtime/omo/event-ledger.sqlite3`
- ledger 在 24h 内累积 ≥1 行 `producer=scene-outcome-recorder` 的 outcome event
- `OMO_PRINCIPAL_ID=xiamingxing python3 bin/bc-os/north_star_meter_v2.py --json` 显示：
  - `personal_value.qualifying_episodes > 0`（之前是 0）
  - `four_week_value_gate` 仍 `not_ready` 但 `gate_gaps` 移除 `no_episodes_observed`
- `bin/ssot/test-episode-bridge.py` 在 hermetic 模式下模拟 30 个 closeout，验证 PersonalEpisodeService.readiness 路径走通（**测试用 broker 是隔离 sqlite，不污染 live ledger**）
- `bin/gac/check-episode-pipeline.py` 在每次本地 gate 跑，验证 ledger producer 分布不为空
- T4-01 retro attestation 在 main 上**注明 corrected_path**：从 runtime projection 改为 live ledger（addendum，spec 不变）

## Implementation Plan

### Stage 1: Bridge wiring（0.5 day）

```
bin/agent-workflow.py closeout
  ↓ (after chain_bind.evaluate_closeout → verdict.ok)
  subprocess: bin/ssot/scene-outcome-recorder.py record \
    --scene-card <scene_card_for_run_workflow> \
    --run-id <run-id> \
    --adjudication accepted \
    --actor closeout-bridge \
    --notes "auto-bridged from agent-workflow closeout"
```

**Key constraint**: subprocess failure must NOT block closeout (matches existing scene-outcome-recorder `except: pass` pattern; episode bridge is non-blocking).

### Stage 2: Scene card resolver（0.5 day）

`agent-workflow closeout` 的 `--scene-card` 需要解析：每个 workflow type 映射到一个 scene card：

```yaml
# bin/ssot/workflow-scene-map.yaml (new)
project-code-change: scenes/agent-workflow-closeout.yaml
project-doc-change: scenes/agent-workflow-closeout.yaml
governance-state-mutation: scenes/agent-workflow-closeout.yaml
bet-execution: scenes/bet-closeout.yaml
governance-audit: scenes/agent-workflow-closeout.yaml
```

新建 2 个 scene card（draft → shadow 即可，不需 supervised）。

### Stage 3: Hermetic test（0.5 day）

```python
# bin/ssot/test-episode-bridge.py
# 用 tmpdir 复制 ledger schema，跑 30 次 mock closeout
# 验证 broker.read(event_type=EVT_EPISODE_DECISION) 长度 == 30
# 验证 PersonalEpisodeService.readiness 路径返回 qualifying_episodes > 0
```

### Stage 4: Gate guard（0.25 day）

```python
# bin/gac/check-episode-pipeline.py
# 检查 event_log 中 producer=scene-outcome-recorder 行数 ≥ 1
# 若 0 行（且最近 closeout > 24h 前）→ warn + suggest bridge 检查
# exit 0 by default (warn mode)
```

### Stage 5: T4-01 retro addendum（0.25 day）

在 `.omo/_knowledge/retros/BET-Y2Q2-T4-01.md` 追加一节"Episode Pipeline Correction"，说明本 BET 才让 retro 主张真正落地。

## Risk Assessment

| Risk | Probability | Mitigation |
|---|---|---|
| subprocess 阻塞 closeout | Medium | try/except, return OK regardless |
| Scene card 不存在 | Low | fallback 到 generic scene card (auto-create) |
| Ledger write 触发 schema migration | Very Low | broker 已固化为 append-only，幂等 by `(producer, idempotency_key)` |
| 历史 closeout 漏写导致 north-star 数字偏小 | High (acceptable) | spec 已说明不预填；数字增长是真实反映 |
| 并发 closeout 撞 ledger | Medium | broker `UNIQUE(producer, idempotency_key)` 保证幂等 |

## Risks of NOT doing this BET

- north-star **永远** `personal_value=not_ready`，sustainability metric 无法激活
- T4-01 retro 主张的 "52 qualifying episodes" **永远是投影**，与 declared ≠ executed 陷阱一致
- SH-1..4 建立的治理面闭环缺一条腿——系统治理得再干净，无法证明治理产生了价值
- BCOS X3 北极星轴 `personal_value` 锁死，业务域三角（work / research / knowledge）不通

## Acceptance

- 4 个 done_when 项必须实际验证（不为 compile-pass / test-pass）
- T4-01 retro addendum 必须手动署名（human-required，apoptosis protection）
- 北极星 pulse 必须 `qualifying_episodes > 0`
## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | bridge 触点：closeout vs weekly-review vs retro sign-off | **closeout** | closeout 是最频繁的、状态确定的、principal-acceptable 事件（每周 5-15 次）。weekly-review 是周级聚合；retro sign-off 触发频率更低 |
| 2 | bridge 同步 vs 异步 | **同步** | 简单可证；ledger write 失败不影响 closeout（try/except）；不让 pending 队列变成新债务 |
| 3 | prefill 历史 closeout 当 episodes | **禁止** | 违反 attribution discipline；会让 north-star 数字撒谎。SH-5 只接新 closeout；数字从 0 真实增长 |
| 4 | scene card 解析策略 | **workflow → scene 映射表** | 比自动推断更可控；为不同 workflow type 显式赋 scene，避免 magic |
| 5 | ledger schema 是否扩展 | **不动** | 已固化在 schema.py；扩展会触发所有 producer 的兼容性检查 |
| 6 | T4-01 retro 是否更新 | **加 addendum，不改原文** | T4-01 已 done；rewrite 会破坏 ledger commit 锚定；addendum 是诚实而非改史 |
| 7 | 同步 Close 后的 evidence 验证 | **看 ledger live 数字** | runtime projection 已不适用；T4-01 retro 投影与实际差距是本 BET 触发根因 |

## Bootstrap authorization

- workflow: `project-code-change` → `governance-state-mutation`（改 bin/agent-workflow.py 触发 governance-state）
- agent: governance-agent
- worktree: 必走 `bin/gac/gac-worktree.sh claim sh5-episode-bridge`
- ADR-0203 流程: bootstrap → start --profile governance-agent --bet BET-Y2Q4-SH-5 → claim → work → closeout
- appetite: 2 days
- human_gate: true（T4-01 addendum 必须主人审）
