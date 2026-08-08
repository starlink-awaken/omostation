# BET-Y1Q2-T6-01 复盘

**Q1 实际耗时 vs appetite？超出比例？**
Appetite: 1 week. 实际: ~30 min. 大幅低于预期 — 规则审查范围清晰, 脚本均已有执行器, 无需新建.

**Q2 done_when 是否全部通过？哪条没过，为什么？**
- ✅ 逐条审查 26 条 required/error 规则, 统计各自的历史违规次数
- ✅ 3 条无本地执行器的 required 规则降级为 advisory (ci_gate only, 未接入 gac-local-gate)
- ✅ 4 条 superseded 规则已归档 (lifecycle=superseded, 含 superseded_by/superseded_reason)
- ✅ advisory 规则不动
- ✅ make gac-local-gate 43/43 ALL GREEN

**Q3 过程中发现的与 plan 不符的事实（打假）？**
1. 原 bet 目标 "134→≤100" 被 evidence E10 修正 — 真正有成本的是 required+error (26条), 不是 advisory (105条). 删 advisory 是有害优化.
2. 4 条 required 规则 name/description 为空 — 文档债, 非功能债. 已补.
3. 3 条规则 (MOF-CAPABILITIES-DRIFT, METAOS-REGISTRY-DRIFT, MCPTOOL-IMPL-DRIFT) 有执行脚本但未接入 gac-local-gate, 只在 CI 生效. 本地开发无预警 → CI 突然失败 = 误伤成本高. 降级 advisory 直到接入本地门禁.
4. MCPTOOL-IMPL-DRIFT 检测到 30 个声明无实现的工具漂移 — 是有效检查, 但不应阻断提交.

**Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？**
- required 规则: 24 → 21 (净减 3)
- advisory 规则: 105 → 108 (净增 3)
- 总规则数: 136 (不变)
- 文件变更: 1 (.omo/_truth/registry/governance-checks.yaml)
- 代码行: +11 / -3
- ADR: 0 (无新 ADR)
- 脚本: 0 (无新脚本)

**Q5 下一个认领本 track 的 agent 需要知道什么？**
1. T6-02 (ADR 分层) 是下一个减法项 — 344→≤200, 但 bet 说 "只分层不裁剪", 实际是分类而非删除.
2. T6-03 (bin 脚本清理) 需要先跑 `check-ci-surfaces.py` 看 orphan 状态.
3. 降级的 3 条规则后续应接入 gac-local-gate 后再升回 required — 这是 T6-05 (配额制门禁) 的前置.
4. gac-local-gate.py 的 CHECKS 列表是规则是否 "真正生效" 的判据 — 不在里面的 required 规则 = 纸老虎.
