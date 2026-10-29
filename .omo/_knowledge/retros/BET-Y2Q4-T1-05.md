---
schema: md/v1
status: draft
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-29
type: retro
id: BET-Y2Q4-T1-05
bet_id: BET-Y2Q4-T1-05
date: 2026-10-29
---

# BET-Y2Q4-T1-05 Retro — 口径归一与 Agent Brief 真实物化结项闭环

## 交付概要

| 项 | 交付与证据 |
|---|---|
| 台账机读出口序列化 | `bin/plan/bet-ledger.py list --json` 彻底修复 `date`/`datetime` 序列化崩溃，全部日期标准化为 ISO-8601 字符串 |
| 入口层 Agent Brief 真实物化 | 新增物化器 `bin/panorama/materialize-agent-brief.py`，从 `zhixing-dashboard` 活的 projection revision 原样物化到 `runtime/dashboard/agent-brief.json`，保留真实时间并注入包含 `revision_id` 与 `manifest_sha256` 的完整 provenance |
| 废除 TTL 假绿机制 | `bin/ssot/auto-pruner.py` 的 `prune_brief()` 不再对 `agent-brief.json` 强行篡改时间戳，杜绝 35 天停更却误报绿灯的假象 |
| 规划层只读探针通过 | `planning_probe.py --mode all` 判定 `SCHEDULED_OK`，解释器判定 `OK`，读数层判定 `ONE_LIVE_TWO_STATIC`，实现日历/台账/目标覆盖三读数分离 |
| 仓库健康周报同步 | `bin/gac/check-readme-hardcoded.py --update-health` 自动刷新 `docs/operations/repository-health.md`，真数规模更新为 574 / 568 |

## 关键收益与架构对齐

1. **去假绿与诚实报警**：物化器绝不伪造 `generated_at`，若上游数据未前进则如实报警，彻底消除了依靠改动 mtime 假装活跃的暗坑。
2. **三套口径边界清晰**：
   - 【工程产出量】：台账（`3y-bet-ledger.yaml`）568 / 574 已完成；
   - 【能力达成度】：目标覆盖（`agent-brief.json` 快照）；
   - 【基建成熟度】：七域完成度（`ROADMAP.md` 阶段规划）。
   明确禁止将不同义或不同时刻的读数强行相减，并在探针与 Brief 中显式并列。
3. **两机对齐与门禁全绿**：遵循双机一体纪律，`mbp` 与 `mini` 均执行验证并消除漂移。

## 验证结论

- `python3 bin/plan/bet-ledger.py list --json` ✅ (exit 0, valid ISO dates)
- `python3 bin/plan/bet-ledger.py lint` ✅ (574 bets, 16 tracks, 0 errors)
- `python3 bin/panorama/materialize-agent-brief.py --check` ✅ (exit 0)
- `python3 /Users/xiamingxing/Project/work-agent/scripts/planning_probe.py --mode all` ✅ (SCHEDULED_OK)
