---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-09
---
# BET-Y1Q3-T3-03 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。08-09 标记 done，但 done_when 第 1 条（partial_simulation 清零）在标记时**未真正满足** —— memtheta 仍是 partial_simulation + default: legacy。补 retro 时发现并修正为 legacy_simulation + default: false。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| memory-os.yaml 中不再出现 partial_simulation 状态 | ⚠️ 标记 done 时未过 (grep -c=1); 补 retro 时修正 (status: legacy_simulation, default: false) → 现 grep -c=0 |
| mem0 / memtheta 代码归档或明确标记 experimental 且默认不加载 | ✅ mem0: stub_optional + default false; memtheta: legacy_simulation + default false |
| 适配器审计文档更新 | ✅ memory-os.yaml notes + STRATEGY 文档如实标注 |

未过: 第 1 条在 done 时实际未过（verify 命令 `grep -c partial_simulation` expect 0 但实为 1）。这正是 D5 retro 强制要抓的「声称 done 但 verify 不过」。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **done 判定与 verify 分离**: bet 标记 done 时没有真跑 verify 命令，导致 partial_simulation 残留。retro 强制 + gate 化让这类「纸面 done」暴露。
2. **circuit_breaker 生效**: "有真实调用方 → 保留但必须标真实状态" — 修正保留了 memtheta 代码但如实标注 legacy_simulation，而非删除（仍有 raw track 事件发射）。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- memory-os.yaml: memtheta status partial_simulation→legacy_simulation, default legacy→false
- 无新增 GaC 规则 / ADR

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **done_when 的 verify 命令必须在标 done 前真跑**，别信「应该过了」。
2. memtheta 保留但 legacy_simulation + default false；mem0 stub_optional + default false。
3. 适配器真实状态以 memory-os.yaml 为准，STRATEGY/deep-review 文档不得声称「生产可用」。
