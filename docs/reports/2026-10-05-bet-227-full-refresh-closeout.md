# BET-Y2Q4-T10-227 全量投影数据周期刷新通道 — Closeout 报告

- bet: BET-Y2Q4-T10-227
- date: 2026-10-05
- status: done

## 交付物

| 交付 | 位置 | 状态 |
|------|------|------|
| 全量刷新 driver | `bin/panorama/projection-full-refresh.py`（PR #4636 + 修复 #4638） | ✅ origin/main |
| 服务注册 | `.omo/_truth/registry/services.yaml` `omostation.zhixing-projection-fullrefresh` | ✅ |
| script-registry | `bin/_registry/scripts/governance/projection-full-refresh.yaml` | ✅ |
| script_baseline | `governance-checks.yaml` 714→715 | ✅ |
| plist | `~/Library/LaunchAgents/com.omostation.zhixing-projection-fullrefresh.plist` | ✅ 已加载 |
| retro | `.omo/_knowledge/retros/BET-Y2Q4-T10-227.md` | ✅ |
| canary 回执 | `docs/reports/2026-10-05-bet-227-canary.json` | ✅ |

## 验证证据

1. **首跑成功**：revision `c4328205`（data_observed_at=2026-10-04T18:27:15Z），dashboard 200。
2. **driver 修复**：首跑失败 `event_ledger_unavailable` → PR #4638 设置 `OMO_EVENT_LEDGER_DB`。
3. **无漂移**：`gen-service-configs --check` → ok=True, drift=0。
4. **republisher 接续**：全量发布后 republisher 自动续期新 revision。

## 回滚

- driver：revert PR #4636 + #4638（bin/panorama/projection-full-refresh.py）。
- 服务：从 services.yaml 移除 fullrefresh 条目 + `launchctl bootout` + 删 plist。

## 教训

- event_ledger 是运行时文件，不在检出内；publisher 检出必须显式设置 `OMO_EVENT_LEDGER_DB`。
