---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-24
---
# BET-Y1Q3-T1-12 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 5 days；实际约 1 day（Wave B 集中落地，2026-08-24 当日完成）；未超。自举跳过 workflow start（用户 waiver，E0_self_bootstrap_waiver，scope 限 spec + 台账条目）。

## Q2 done_when 是否全部通过？哪条没过，为什么？
✅ done_when 全部达成（via capability-sync/native-execution-receipt 系列测试 + exact find/load + admission 回验 + KEMS 裸派工 fail-closed 死亡入口 + 跨仓 canary）。测试命令均 exit 0。

## Q3 过程中发现的与 plan 不符的事实（打假）？
- E1 (orca call chain audit): capability-sync load/invoke 不强制 binding，B4-D execution receipt 只有库与测试、没有生产消费者 → 需收敛。
- E2 (independent architecture review): "start-only 与 new broker" 两条路径均不成立，改为 start 声明预检 + dispatch 真实 identity/receipt 回验。
- E3: OMO StepDispatched 前未回验 persisted admitted state；legacy 空 capability grant 代码残留。
- E4: Cockpit KEMS 裸 dispatch 已 fail-closed 成死入口；agent-runtime/runtime registry 尚未共用 binding gate。
- E5 (periodic delta correction): #2090 合成价值链与 #2110/#2118 平行派工面不得原样合并；maturity 9.0 仅是 readiness proxy。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
P0 大 bet，波及 root/OMO/Cockpit/Agora 多仓（capability binding 收敛 + admission 回验 + native receipt 生产消费）。见对应 Wave B 跨仓 PR（Exact Capability Binding 系列）。

## Q5 下一个认领本 track 的 agent 需要知道什么？
- Exact Capability Binding 已收敛为同一身份链（Spec/BET/WorkPacket/run/claims/exact requirements 一致）。
- native-execution-receipt/v1 已有真实生产消费者；value firewall / replay / cleanup 负例全绿。
- 未做：Golden Slice、Human Verdict、principal-bound decision_outcome、连续价值观测（non_goals）。
- 相关设计：docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md；wave gate map 对照 wave-gate-bet-map.md。
- ⚠️ 本复盘由后续会话补齐（原 bet 交付时缺 retro，违反 D5，本文件补登记）。
