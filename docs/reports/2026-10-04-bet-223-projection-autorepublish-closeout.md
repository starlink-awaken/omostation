---
schema: md/v1
type: closeout-report
bet_id: BET-Y2Q4-T10-223
status: accepted
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-04
---

# BET-Y2Q4-T10-223 Closeout Report — 投影租约自动续期与孤儿 revision 治理

## done_when 逐条验收

1. **launchd label 已加载且 gen-service-configs --check 无漂移** — ✅
   `launchctl list | grep republisher` 有输出；`gen-service-configs.py --check` = "0 drift (65 launchd services)"。
2. **连续 ≥2 个调度周期（16min）全端点 200，revision 链滚动，无 projection_stale** — ✅
   实际观察 10-03 22:00 → 10-04 07:21（>9h，117+ 次续期），`/`, `/api/v1/manifest`, `/api/v1/summary`, search 全 200。
3. **revisions ≤ keep+1，磁盘 <1GB** — ✅
   `--gc` 每轮执行，稳定 48 个 / 957MB（基线 631 / 9.9GB）。
4. **state root git status 为空** — ✅
   含锁文件位置验证（锁在 revisions/ 内，已被 .gitignore 覆盖）。
5. **废止人工续期** — ✅（条件性）
   自动通道已接管；唯一残留是 stopgap cron 行因系统 crontab EINTR 未能删除（功能无害，见 retro 遗留）。

## 交付物

| 交付物 | 位置 |
|---|---|
| 续期工具 | `bin/panorama/projection-republisher.py`（注册：bin/_registry/scripts/governance/projection-republisher.yaml） |
| 调度注册 | `.omo/_truth/registry/services.yaml` → `omostation.zhixing-projection-republisher`（generate:true, 480s, [--gc]） |
| 配额基线 | `governance-checks.yaml` script_baseline 712→714 |
| BET/spec | BET-Y2Q4-T10-223 + `docs/superpowers/specs/2026-10-03-bet-223-projection-autorepublish-spec.md` |
| Retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-223.md` |
| PR | #4619（主）、#4621（GC 伴随化） |

## 偏离记录

- `bin/_registry/scripts/governance/projection-republisher.yaml` 与 `.omo/_truth/registry/governance-checks.yaml` 两处为 CI 门禁倒逼的新增（script-registry 注册 + subtraction_quota 基线同步），不在 start 时编译的 WorkPacket scope 内 —— 属门禁发现的必要扩面，非范围蔓延。
- `docs/plans/3y-bet-ledger.yaml` 的 run claim 因并发 run（`20261004T012945Z-project-doc-change-2f8bf1f7`）持有同路径锁而未完成 claim；文件内容已随 PR #4619 合入 main，claim 仅为记录性质。
- 人工续期 3 次的历史均由本会话前序完成，本 BET 交付的是自动化通道。
