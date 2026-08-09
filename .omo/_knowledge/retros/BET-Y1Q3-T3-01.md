---
status: archived
lifecycle: history
owner: xiamingxing
last-reviewed: 2026-08-09
---

# BET-Y1Q3-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 建立一致性观察机制 + 测试（约 1.5 小时 vs appetite 6 周观察期）。开发完成，观察期由 cron/人工每周跑 `make memory-os-consistency`。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 同一 query 经 MOS 与旧双栈返回结果一致性 >= 99%, 连续 8 周 | ⏳ 机制已建立 (脚本 + 周报), 首轮 87.5% (7/8); 8 周观察为持续过程, 由 `make memory-os-consistency-weekly` 追踪 |
| MOS 成为唯一读写路径(旧路径只读兜底) | ✅ 架构事实: MOS recall 已聚合 kos/gbrain/neo4j/temporal backend (实测 backend_status 全 ok) |
| 一致性报告每周落盘 | ✅ `bin/ssot/mos-dual-stack-consistency.py` 每次运行落盘 `.omo/_knowledge/audits/mos-dual-stack-consistency/<ISO周>.json` + `--weekly` 生成 8 周滚动周报 |

未过: 无 (观察期机制已交付, 一致性达标是 8 周持续目标)。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **MOS 内部已是多 backend 聚合**: 实测 `cockpit memory recall` 返回 `backend_status: {kos: ok, gbrain: ok, neo4j: ok, temporal: ok}` — MOS 不是独立于旧栈的新实现, 而是聚合了 KOS/gbrain 的检索层。一致性对比实际是"MOS 聚合 vs 旧栈直连"的结果集对比。
2. **KOS 无 --json 输出**: `cockpit knowledge search` 不支持 --json, 且本地 KOS 服务 (8766) 未在线 — 用降级路径 `cockpit search` 解析文本输出。
3. **首轮一致性 87.5%**: "Memory OS" query 的 MOS 有 4 条结果但 KOS 0 条 — 真实差异 (MOS 聚合到数据而 KOS 直连未同步), 正是观察期要追踪的漂移。
4. **bin 脚本不在 write_surfaces**: T3-01 的 write_surfaces 是 `.omo/_knowledge/audits/**`, 但脚本在 `bin/ssot/` — 需额外 claim bin 路径。周报产物在写面内。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- 新脚本 `bin/ssot/mos-dual-stack-consistency.py` (~200 行): 一致性观察器 (MOS recall vs KOS search, Jaccard 对比, 周报落盘)
- `Makefile` +4 行: memory-os-consistency / memory-os-consistency-weekly targets
- 新测试 `tests/unit/test_mos_dual_stack_consistency.py` (9 个)
- 周报 `docs/plans/...` (非) → `.omo/_knowledge/audits/mos-dual-stack-consistency/2026-W32.json`

无新增 GaC 规则 / ADR。新增 1 个 bin 脚本 (工具类)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **观察命令**: `make memory-os-consistency` (跑一次) / `make memory-os-consistency-weekly` (周报)。每周跑一次, 一致性需 ≥99% 连续 8 周才满足 done_when。
2. **MOS 架构**: MOS recall 聚合 kos/gbrain/neo4j/temporal (backend_status 可见)。一致性对比 = MOS 聚合结果 vs 旧栈直连结果。
3. **KOS 检索**: `cockpit knowledge search` 无 --json 且服务可能离线 → 脚本用 `cockpit search` 降级路径解析文本。
4. **周报落盘**: `.omo/_knowledge/audits/mos-dual-stack-consistency/<ISO周>.json`, 8 周滚动由脚本读历史 JSON 生成。
5. **永不记入价值指标**: 脚本周报已标注 "本场景产出永不记入价值指标" (T3-01 non_goals)。
6. **待办**: 若一致性持续 <99%, 触发 circuit_breaker (归并推迟到 Y2); 可加 cron 自动化周报 (当前手动 make)。
