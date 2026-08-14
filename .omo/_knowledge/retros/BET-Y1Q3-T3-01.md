---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-14
---
# BET-Y1Q3-T3-01 复盘

## Q1 实际耗时（对比 appetite）
从认领到落盘本周观察+周报生成约 1.5 小时；与 appetite 6 周相比远低于上限，未触发 circuit_breaker。

## Q2 done_when 是否全部通过？
| done_when | 状态 |
|---|---|
| 同一 query 经 MOS 与旧双栈返回结果一致性 >= 99%，连续 8 周 | ⏳ 机制已建立但尚未满足：2026-W33 一致性 87.50%（7/8） |
| MOS 成为唯一读写路径（旧路径只读兜底） | ⏳ 已确认 MOS recall 同时有聚合后端并可继续验证，当前为持续观察，不视为本次已决 |
| 一致性报告每周落盘 | ✅ 已落盘：`.omo/_knowledge/audits/mos-dual-stack-consistency/2026-W33.json` 与 `weekly.md` |

## Q3 打假发现
1. `Memory OS` 查询在 MOS 查询链路可返回 7 条结果，但旧双栈 `cockpit search` 本次为空，导致本周 Jaccard 仅 0.875，需继续观察后判断是否归因为索引偏移。
2. `bin/ssot/mos-dual-stack-consistency.py` 已具备 7 根查询的结果比对与周报落盘能力，本次主要完成周度采样，不是立即可判定归并门槛。
3. `make memory-os-smoke` 通过（写入/回读/AS_OF），但 `neo4j` 写入在 `memory-os-smoke` 阶段为不可用告警；该约束不影响当前脚本执行。

## Q4 表面积净变化
本次表面积净增：新增 2 个审计交付文件（在 `.omo/_knowledge/audits/mos-dual-stack-consistency/`）
- `2026-W33.json`：本周一致性快照
- `weekly.md`：8 周滚动周报（含本周 87.5%）

无新增/变更 GaC 规则、ADR、脚本实现。

## Q5 需要人类拍板的事项
1. 是否允许按当前趋势继续 8 周观察（首轮已低于 99%，但在采样期）？
2. 是否需要将 `BET-Y1Q3-T3-01` 设为阻塞态并要求调整 query 集合（目前只看到 `Memory OS` 命中偏差）以提高短期一致性？
3. 是否批准下一步把观察频次固定为每周定时任务（否则人工触发可能导致丢失观察链）。
