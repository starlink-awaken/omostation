# BET-Y2Q4-T10-226 看门狗分级恢复 + host 资产回同步 — Closeout 报告

- bet: BET-Y2Q4-T10-226
- date: 2026-10-05
- status: done

## 交付物

| 交付 | 位置 | 状态 |
|------|------|------|
| 看门狗分级恢复 | deploy 仓 `starlink-awaken/zhixing-dashboard` commit `6c678f0` | ✅ origin/main |
| host 资产回同步 | workspace `bin/panorama/assets/host/`（PR #4636 / 52a6cf192） | ✅ merged |
| retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-226.md` | ✅ |
| canary 回执 | `docs/reports/2026-10-05-bet-226-canary.json` | ✅ |

## 验证证据

1. **watchdog 分级恢复**：deploy 仓 origin/main 含 `6c678f0`；launchctl `com.omostation.zhixing-dashboard-watchdog` 已加载并运行。
2. **host 资产回同步**：`zhixing-host-sync.py status` → 7 受管文件全部 in_sync（drifted=0）。
3. **dashboard 可用**：:43191 `/api/v1/manifest` → 200。

## 回滚

- watchdog：deploy 仓 `git revert 6c678f0`（单 commit，无副作用）。
- host 资产：workspace revert PR #4636 中 `bin/panorama/assets/host/` 的 3 个文件。

## 教训

- deploy 代码变更会导致读端 CODE_DRIFT（revision 的 dashboard_code_oid 过期），需全量发布修复。
- 推送 gate 的分支名必须合规（feat//fix// 等前缀），否则 pre-push branch-naming 静默阻断。
