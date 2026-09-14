# T8-24 总揽签署材料 — A9 全景观测终验完成

> 生成: 2026-09-12 | 用途: BET-Y1Q4-T8-24 human_gate 签署依据
> 状态: 24A done / 24B done / 24C in_progress (实现已合, evidence 收账中) / 24D done / 24E done

## done_when 逐条对照

| # | done_when | 状态 | 证据 |
|---|---|---|---|
| 1 | Observatory 统一数据面收敛至 cockpit | ✅ | 24A 保真度矩阵 7/7 aligned; fidelity 工具 cockpit#164 |
| 2 | 前端 6 大正交 Store 建立 | ✅ | cockpit-ui#9 (六面 Zustand Store, 11 tests) |
| 3 | Studio 工作台深度升级 | ✅ | cockpit-ui#12/#14 (真实数据+Diff+Dry-run); #3635 spec |
| 4 | Operations/Mission 工作台交付 | ✅ | cockpit-ui main 1cabb54; #3637 binding |
| 5 | A9 门禁终验 + 43191 退役 | ✅ | T8-25 #3622; T8-24E #3636 (43191 PID 仍在, entry 已退役) |

## 保留事项

- done_when#4 旧 API 废除: 52 个 api_* 需 cockpit-ui 消费方分析, defer 至 24E 后续
- 24C operational: NOT_PROVEN (待前端消费深度验证)
- 43191 PID 51391: 进程仍在 (entry 已退役, 物理停止需 human 确认)

## 签署决策项

1. 确认 T8-24 总揽 done (24A-E 全 done)
2. 确认 43191 物理停止 (kill PID 51391) 或保留为只读参考
3. 确认 52 个旧 api_* 废除计划时间表
