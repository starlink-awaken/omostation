---
type: retro
bet_id: BET-Y1Q4-T5-05
status: completed
created: 2026-09-13
closed: 2026-09-13
---

# BET-Y1Q4-T5-05 Retro — 常驻 Agent 2.0 决策因果图化

## 完成内容

- `decision_bridge.py`: 因果决策图 (追加式 JSONL 存储 + BFS 祖先/下游查询)
- `arbitration.py`: 先例仲裁器 (相似度加权置信度, 0.85 HITL 升级阈值)
- `decision_graph.py` (Cockpit): 聚合 handler
- `DecisionGraphViewer.tsx` (cockpit-ui): UI 组件 + 测试
- W3C PROV-O Turtle/JSON-LD 审计导出

## 踩坑记录

- **置信度公式**: 初版用 `占比 * 平均置信度` 导致合成值过低 (0.6167), 改用相似度加权平均后 >= 0.85
- **子模块 worktree**: `.subtrees/omo` 与 `projects/omo` 共享仓库但不同 worktree, push 后需 `bump-pointer` 同步

## 遗留

- [ ] retro 待 closeout 时补完
