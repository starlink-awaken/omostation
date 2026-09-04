---
lifecycle: history
owner: governance-team
last_updated: 2026-08-14
title: BET-Y1Q3-T3-01 复盘
type: retro
---
# BET-Y1Q3-T3-01 复盘

## Q1 实际耗时（对比 appetite）
从认领到落盘本周观察+周报生成约 1.5 小时；与 appetite 6 周相比远低于上限，未触发 circuit_breaker。

## Q2 done_when 是否全部通过？
| done_when | 状态 |
|---|---|
| 同一 query 经 MOS 与旧双栈返回结果一致性 >= 99%，连续 8 周 | ⏳ 机制已建立且已复核：2026-W33 一致性 87.50%（7/8）仍未达标 |
| MOS 成为唯一读写路径（旧路径只读兜底） | ⏳ `cockpit status` 显示 KOS/AGORA 未健康，旧栈服务偏差明确，当前不纳入本次并发归并判定 |
| 一致性报告每周落盘 | ✅ 已落盘：`.omo/_knowledge/audits/mos-dual-stack-consistency/2026-W33.json`、`2026-W33-intervention.json` 与 `weekly.md` |

## Q3 打假发现
1. `Memory OS` 不再用“空旧栈”解释：直接复核确认旧栈 `cockpit search` 只返回 `search-trace` 类行，且带 `▸  search-trace: Memory OS  ...`，当前脚本在不解析 JSON 时会把它当成可比 ID，导致一部分一致性偏差噪声化。
2. `cockpit status` 连续观察到 `KOS`、`Agora SSE` `healthy=false`，旧栈服务偏差是实测事实，不是计划缺陷。
3. 直接复核同组 query 的一致性后本轮跌到 0.5（含手工扩展查询集时），说明本次差异不止单点波动，必须同步修复与服务告警再复评。  

## Q4 表面积净变化
本次表面积净增：新增 3 个审计交付文件（在 `.omo/_knowledge/audits/mos-dual-stack-consistency/`）
- `2026-W33.json`：本周一致性快照
- `2026-W33-intervention.json`：即刻修复记录（原因、命令证据、后续同步计划）
- `weekly.md`：8 周滚动周报（含本周 87.5%，及“立即处理/增加项”）

无新增/变更 GaC 规则、ADR、脚本实现。

## Q5 需要人类拍板的事项
1. 是否批准本条改为“服务偏差优先”处理：先修复 KOS/AGORA 健康后再回归一致性门槛？  
2. 是否同意将当前观察频率提升为每周 2 次（周一/周三）并保留 10 条 query 的扩容清单？  
3. 是否同意先不改脚本 parser（暂存为人工复核期），仅用 intervention 记录与告警联动推进同步修复？  

---

## 状态纠正记录（2026-08-15，台账信任修复轮）

**status: done → in_progress，done_at 已清除。** 纠正依据（全部可复核）：

1. done_when 第 1 条（一致性 ≥ 99% 连续 8 周）**未满足**：实测 W32 = 1.0（2026-08-09）、W33 = 0.875（2026-08-14，`.omo/_knowledge/audits/mos-dual-stack-consistency/2026-W33.json`），窗口仅运行 1 周；本 retro Q3 复核后一致性跌至 0.5。
2. done 系 commit `d8486d28d`（#1494 "governance convergence closeout notes and ledger completion"）批量收尾时误标——与本 retro Q2（2⏳ 1✅）直接矛盾，属 AGENT-BRIEF §1.3「声明 ≠ 事实」真实案例。
3. **时钟不重置**：8 周观察窗口锚点保留 W32 首次观察（2026-08-09），W32/W33 结果为真实历史，窗口至 ~2026-10-03；本条在此期间保持 in_progress，期间任何 agent 不得再标 done。
4. Q5 三个待人类拍板项维持悬置，未因纠正而消失。

处置权限：人类 2026-08-15 指令明确授权状态纠正（"把 status 从 done 改回 in_progress"）。
