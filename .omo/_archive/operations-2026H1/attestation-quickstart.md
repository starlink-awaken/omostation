---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: 主人价值签核启动指南 — 北极星起搏器
type: doc
---

# 主人价值签核启动指南 — 北极星起搏器

> 目标读者: xiamingxing(工作区主人)
> 为什么重要: UHS value 维度 25/85, 其中 `collecting`(50分)与 `proven`(100分)
> 的唯一解锁方式是**连续 4 周、每周 ≥3 个合格人证 episode**。
> 这是系统设计上唯一无法由 agent 伪造的分数——也是最值钱的分数。

## 合格 episode 的四个条件
PersonalEpisodeService 的 readiness 门(projects/omo/src/omo/personal_episode.py):
1. **系统证据**: episode 有系统侧执行痕迹(Action.Succeeded 等 ledger 事件)
2. **accept 结果**: Outcome.Human.v1 且主人判定为接受
3. **负担完整**: burden 字段完整(时间/打断成本如实记录)
4. **review < saved**: 复查耗时 < 系统节省时长(即真的赚了)

## 现状账本
- ledger 已有 1 条 Outcome.Human.v1(principal:xiamingxing) — 万事开头难,开头已完成
- 自动化工具 `cockpit attest` 在建(W3-T1), 建成后草稿自动从 git/ledger/debt 预填

## 手动路径(工具建成前, 今天就能开始)
```bash
# 周日晚花 5 分钟, 回答三个问题并落一条签核:
# 1) 这周哪件事是 agent 替我做完、我认可的?
# 2) 它花了系统多久、帮我省了多久?(burden 与 saved)
# 3) 我复查它用了几分钟?(review < saved 才算合格)
uv run --project projects/omo omo ...   # 具体命令待 W3-T1 提供包装
```

## 倒计时看板
| 周 | 合格数 | 需要 | 状态 |
|----|--------|------|------|
| W+1 | _/3 | 3 | ⬜ 待启动 |
| W+2 | _/3 | 3 | ⬜ |
| W+3 | _/3 | 3 | ⬜ |
| W+4 | _/3 | 3 | ⬜ |

四周全绿 → readiness=passed → north_star `proven` → **UHS value 直冲 100/85 封顶**
→ 全系统 UHS 预计突破 90 分大关。

## 与自动化管线的接线
`cockpit attest`(在建): 扫描近7天 merge(PR)/closed债务/ledger Action.Succeeded
→ 预填草稿 → 你逐条 [c]onfirm/[e]dit/[r]eject → 合格者写入 Outcome.Human.v1。
拒绝项进负样本不再打扰。周度批量为默认节奏。
