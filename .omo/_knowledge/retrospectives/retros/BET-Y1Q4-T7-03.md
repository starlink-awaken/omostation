---
type: ephemeral
status: archived
---

# BET-Y1Q4-T7-03 Retro — 政策雷达晨报

## 做对了

- spec-first 契约一次过（新 BET 的 accepted_specifications 流程首次走通）
- 降级路径生产验证（首跑即 gov.cn 不可达——circuit_breaker 不是纸面条款）
- 规则打标而非 LLM 先行：白名单零分过滤 = 结构性零噪音，比概率性 LLM 判稳

## 踩坑

- BET verify 命令 `-m bin.bc_os`（连字符目录不可做模块）——#2788 批量加 BET 时
  的模板笔误，本 PR 修正；后续 16 个新 BET 的 verify 命令建议批量自查同型
- 首跑频道名混入（RSS channel title）——真数据首跑的价值再证（P95 首班规则）

## 下一步

- 管线第二站 T2-01：事件总线接入 + launchd 07:30 调度（晨报从命令变日程）
- LLM 深度研判层（规则白名单做召回，LLM 做排序/摘要——两段式）
