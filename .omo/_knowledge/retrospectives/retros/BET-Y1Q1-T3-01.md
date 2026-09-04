---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T3-01 复盘
type: retro
---
# BET-Y1Q1-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。kairon mos #61 (fe2b4f8f) 落地 agent_belief 三表，约 3-4 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| mos 包新增 agent_belief 命名空间, 含 world_snapshot / capability_calibration / decision_outcome 三表 | ✅ kairon #61 (ADR-0396 Keystone) |
| 三表可经 bos://memory/mos/write 写入、bos://memory/mos/recall 读出 | ✅ memory-os.yaml 注册 6 BOS URIs |
| 进程重启后数据仍在 | ✅ 持久化验证 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **MOS 是 kairon 子模块的一部分**, 不是主仓 .omo 面。写入路径在 projects/kairon/packages/mos，主仓只登记 memory-os.yaml 元数据。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（kairon 子模块）:
- agent_belief 三表实现 (world_snapshot/capability_calibration/decision_outcome)
- mos 包 BOS URI 读写路径
- ADR-0396 (Keystone)
- 主仓 memory-os.yaml 元数据

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. agent_belief 三表在 kairon mos (#61)，主仓 memory-os.yaml 只是登记元数据 + 计数。
2. 读写走 bos://memory/mos/write + /recall，别直接碰 SQLite 文件。
3. 三表数量实时值（43/6/1）以 memory-os.yaml 为准。
