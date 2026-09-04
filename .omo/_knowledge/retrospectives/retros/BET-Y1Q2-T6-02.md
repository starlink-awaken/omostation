---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q2-T6-02 Retro: ADR 分层"
type: retro
---
# BET-Y1Q2-T6-02 Retro: ADR 分层

## 完成日期
2026-08-08

## 交付物
- `bin/adr/adr-coverage.py`: 新增 `classify_layer()` 函数 + `--layer` CLI flag
- 分层结果: 340 active / 11 historical

## 分层判据
- Historical: frontmatter status in {superseded, archived, done, deprecated, withdrawn}
- Active: 其余所有 (accepted, active, proposed, candidate, partial, draft)

## Historical ADRs (11)
0001-0008 (早期归档), 0131 (reserved), 0233 (superseded), 0234 (closeout)

## 关键决策
- 不删任何 ADR 文件 (ADR 是决策记录, 删了就失去追溯能力)
- 分层通过 frontmatter status 自动分类, 无需人工标注
- `--layer` 输出 JSON 供 RAG/onboarding 消费, historical 不进检索面

## 验证
- `adr-coverage.py --layer` 输出正确分层
- `adr-coverage.py --json` 包含 layer 字段
- 文本输出显示 active/historical 计数
