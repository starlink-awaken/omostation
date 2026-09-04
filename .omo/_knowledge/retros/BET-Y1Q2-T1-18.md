---
title: BET-Y1Q2-T1-18 复盘 — Supervised Blueprint Control Loop × SR-06
type: retro
owner: governance-team
created: 2026-08-16
related:
  - .omo/_knowledge/audits/gate-g1-swarm-readiness-2026-08.md
  - docs/superpowers/specs/2026-08-16-sr06-reject-canary-design.md
context: >-
  T1-18 解冻 (blocked→in_progress, 08-16) 后, SR-06 六轮生产链 canary 全部完成,
  bet 主体交付闭环。轮次详情见 G-1 证据包 §6。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q2-T1-18 复盘

## Q1 实际耗时 vs appetite

appetize 3 days; 实际: 代码 #1437 (08-14, 前任) + SR-06 演练 1 天 (08-16, 本轮六轮)。

## Q2 done_when 全过?

| 项 | 结果 |
|---|---|
| candidate BET 确定性编译 (spec digest 绑定) | ✅ compile_packet 六轮复现 |
| 人工 release (approval 铸造+校验) | ✅ 每轮 fresh approval 过 _approval_state |
| 真实模型输出 (Codex via Orca) | ✅ 五个独立 worker terminal 实录 |
| 实际 diff/receipt 收集 | ✅ R2/R6 candidate git-object patch |
| 独立验证 accept 路径 | ✅ R1/R2 WorkflowVerified |
| reject 后可证明补偿回滚 | ✅ R6 CompensationStarted→WorkflowRecovered→Closed + 基线恢复实测 |
| SR-06 全链演练 (bet 标题) | ✅ 六轮, G-1 6/6 |

全过 → done (human_gate 由 G-1 §7 承接, 与本 bet 状态解耦: bet 验收的是 loop 能力, 蜂群开闸是战略决定)。

## Q3 计划与事实偏差 (SR-06 挖出的 4 个产品缺口, 供后续 bet)

1. **admission TTL×mesh 幂等死锁**: execute 失败重试时 dispatch 被 mesh 幂等拦 + admission 已过期 → 无路可走。需 admission 续期或幂等重放语义。
2. **filesModified 空列表**: Codex worker 首轮 completion report 不填文件清单 → collect 误拒。需 prompt 契约强制或 fallback。
3. **gitignore 盲区**: 越界写到 .omo/workers/runs/ (gitignored) 不进 git delta → verify 看不见。越界检测应含 untracked 扫描。
4. **terminal fallback 200 行截断**: 长输出 worker 被 truncated:true 误伤 fail-closed。需 limit 提升或分页。

另: R3 教训 — task 的 AC 与 packet write_surfaces 自相矛盾时 (要求越界写), 守规 worker 会拒绝, reject 演练应走「AC 命令不可满足」路径而非「要求 worker 违规」。

## Q4 表面积影响

clone 侧: +6 task yaml + 1 spec + 1 evidence + mesh 事件 (~5KB/轮)。主仓: 本 retro + G-1 回填 + 台账状态。净增可忽略, 全部为证据面。

## Q5 给下一个 agent

1. G-1 §7 human_gate 待用户签名 → 签后蜂群合法开闸 (W0+ 波次可启)
2. 4 产品缺口建议立 follow-up bet (T5-ORCH 轨道, P1)
3. 六轮的 packet/dispatch/candidate 全在 agents/blueprint-control-loop/ws/.omo/workers/runs/sr06-* (未 push, 证据面)
4. Orca 侧五个 worker terminal (term_ca696257/0b138445/0cf1e3e8/461c1653/4e59da58) 任务完成后空闲, 可回收 (janitor/orchestration)

## Q6 遗留

- clone 本地 commit (canary 物料) 未 push — 属证据面, 是否入库由 G-1 签名时一并决定
- worker terminal 回收待做 (E7 协议首案)
