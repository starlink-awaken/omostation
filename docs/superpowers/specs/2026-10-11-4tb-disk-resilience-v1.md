---
schema: md/v1
type: spec
schema_version: specification/v1
status: accepted
lifecycle: spec
spec_version: 1.0.1
bet_id: BET-Y2Q4-T10-243
owner: engineering-agent
last-reviewed: '2026-10-11'
---

# 4.1T 掉线盘兜底与恢复体系设计 (disk-resilience)

> 背景: 4.1T 盘 (disk8: MOVESPEED/SHAREDWORK/SHAREDMODEL) 硬件层可疑——用户 9/7 厂家故障说明
> (mini/MBP/Y7000P 三台主机、多根线、带电 hub、两种桥接芯片均复现, 指向 SSD 主控 RTS5772DL 或固件);
> 2026-10-11 14:47:44 实测一次整条 hub 链路一起掉线 (3 个 SuperSpeed 设备 6 毫秒内同时消失, 约 1 秒后恢复)。
>
> **订正 (2026-10-11 晚, spec 1.0.1)**: 初版写的"大规模掉线 3 次 + 会话内高频掉线 ~10 次 (间隔缩至 3 分钟,
> 与高 IO 相关)"来自 disk-keepalive 的误报日志——launchd 下 `/bin/bash` 无『可移动卷』TCC 授权, `ls` 被拒,
> 于是每个检测周期 (恰为 3 分钟) 都把卷误判成"未挂载"。统一日志留存期内 (约 18 小时) 真实掉线仅 1 次;
> 真实频次待 `disk-keepalive.drops` 积累。用户决策: 先不换盘; 2026-10-11 起做直连对照实验 (摘掉 hub)。

## 1. 威胁模型 (三档)

| 档 | 场景 | 频率 | 现有防线 | 缺口 |
|---|---|---|---|---|
| T1 瞬时掉线 | 卷消失数秒~数分钟, 由 macOS 自动挂回 (10-11 14:47 实测约 5 秒) | **待实测** (日志留存期内真实 1 次/约 18h; 初版"每日常态"为误报) | keepalive v3: `diskutil` 判定挂载, 真实掉线采集到 `.drops`; 不再声称"自愈 100%" | 掉线窗口内 mini 推理全灭; 靠 `.drops` 与日报暴露, 真掉时有桌面通知 |
| T2 长时间离线 | 卷消失数小时 | **未证实** (初版"夜间 8.5h/9.1h 两次"来自误报日志) | keepalive 探测 + 桌面通知 (现仅在卷真未挂载时触发) | 夜间批任务 (备份/迁移) 静默失败: 以 `.drops`/日报为准 |
| T3 盘体死亡 | 4.1T 三卷全灭不可恢复 | 趋势未知; 9/7 厂家故障说明指向主控/固件, 仍按可能发生设计 | 无 | **本设计主攻**: 重建剧本 + 备份闭环 |

## 2. 数据分层保护矩阵 (按可重建性)

| 层 | 数据 | 体量 | 位置 | 保护方式 | RPO | 重建方式 |
|---|---|---|---|---|---|---|
| P0 配置/SSOT | models.json/软链农场/vault-paths/BET | <10M | ~/omlx + 仓内 | git 主仓 + Lex 冷备 + MBP HDD 三副本 | 即时 | git clone |
| P1 稀有资产 | 自制/小众发布者模型 (15 家) | ~225G | SHAREDMODEL/lmstudio | **Lex 全量副本** (2026-10-11 首备, 周度增量) | ≤7d | `resilience rebuild` 从 Lex 回灌 |
| P2 公开资产 | mlx-community 等 7 家 | ~545G | SHAREDMODEL/lmstudio | 清单不备数据 (HF 可重下) | 清单 ≤7d | `resilience rebuild` 批量重下 |
| P3 冷层 | dead models + omlx weights | ~115G | MOVESPEED | Lex 冷备区追加 (月度) | ≤30d | rsync 回灌 |
| P4 可再生产物 | logs/run/cache/Docker | — | 各卷 | 不保护 | — | 再生 |

## 3. RPO/RTO 承诺

- **RPO**: P0 即时 / P1 周度 (≤7d) / P2 清单周度 / P3 月度
- **RTO (T3 盘死后重建到 mini 推理可用)**:
  - 新盘到位 + 卷重建: ~30min (人工)
  - P0 配置恢复: ~10min (脚本)
  - P1 稀有回灌: ~4h @ 40MB/s (Lex→新盘, 225G)
  - P2 公开重下: 视网速, 545G 可后台跑, **不阻塞**推理恢复 (常用模型优先)
  - **mini 推理可用临界点: P0+P1 完成即恢复** (≈4.5h); 全量恢复后台继续
- 掉线期间 (T1/T2): mini 推理不可用, **gateway 已有 MBP/Ollama 跨节点 fallback**
  (omlx cluster probe + engine_policy fallback 链), 请求自动路由, 无需人工

## 4. 工具箱: bin/ops/hot-tier-resilience.sh (单脚本多子命令)

新增 1 个 bin/ 脚本 (baseline 718→720, 注册 script-registry):

| 子命令 | 功能 | 排程 |
|---|---|---|
| `sync-rare` | SHAREDMODEL/lmstudio 稀有发布者 → Lex 增量 (rsync --bwlimit 40M, 排除公开 7 家) | 周日 04:00 launchd (人工安装) |
| `manifest` | 刷新公开源重建清单 (Lex + 仓内双写) | 同上 |
| `snapshot-links` | models-active 28 软链清单固化 → ~/omlx/conf/models-active.manifest (git 化) | 同上 |
| `verify` | Lex 副本 vs 热层抽样校验 (10 文件 hash) + 清单新鲜度 | 同上 |
| `rebuild <新卷挂载点>` | T3 重建剧本: 建目录 → 稀有回灌 → 公开重下清单打印 → 软链农场重建 | 手动 (灾难时) |

## 5. 掉线感知链 (T1/T2 治理)

1. keepalive UUID 自愈 (v2, 已验证 100%) — 不动
2. macOS 桌面通知 (2026-10-11 已加, 节流 1 条/小时) — 已上线
3. **掉线日报**: keepalive 日志每日 23:50 汇总 (次数/时长/自愈率) → 追加到
   `~/Library/Logs/disk-keepalive.daily` — 本设计新增 (resilience 脚本 daily-report 子命令)
4. 掉线窗口守卫: 备份/迁移任务前检查卷在线 + 掉线计数 >0 则降速/暂缓 (sync-rare 内置)

## 6. launchd 排程 (人工安装制, 沿用 cold-backup-drill 约定)

plist 模板内嵌于脚本头注释。安装/卸载命令在文档此处:

```bash
# 安装 (确认排程后人工执行)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.hot-tier-resilience.plist
# 卸载
launchctl bootout gui/$(id -u)/com.local.hot-tier-resilience
```

## 7. 演练与验收

- [ ] 首次 `sync-rare` 全量 (今日后台完成中) + `verify` 通过
- [ ] `snapshot-links` 清单入库, git 追溯
- [ ] **半演练**: 在 Lex 侧模拟 rebuild 的 P0+P1 段 (软链农场在 /tmp 重建 + 稀有抽样回灌 1 个模型) — 计时验收
- [ ] 掉线日报连续 7 天产出
- 全演练 (真换盘) 时机由用户定

## 8. 未决项 (依赖用户/硬件决策)

- 换线/换盘 — 以直连对照实验为准 (2026-10-11 起: 摘掉 hub、直插后置雷电口, 观察 3~7 天看 `.drops` 的 `ss_removed`;
  不再掉 → 问题在 hub 或其上游线, 仍掉且 `ss_removed=1` → 走厂家售后); 结果记入 HW-DISK8-4TB-FLAKY 债务
- Model 1T 卷终态 (TM error 45 未解) — 排空后删卷重建可一并解决
- SHAREDWORK 空卷用途 (P2 SMB 跨机共享) — 硬件不稳期间不启用新负载
- MBP HDD 冷备镜像自动推送 (现手动 rsync --partial; drill 尾部可挂自动)

## 9. 订正记录

- **1.0.1 (2026-10-11 晚)**: 订正威胁模型的频率数据。初版把 disk-keepalive 的"未挂载 / REMOUNT / NEEDS_ATTENTION"计数当作真实掉线,
  而该计数在 launchd 下因 TCC 误判失真 (根因与复现见 `Plans/macmini-7t-ancient-twilight.md` 的「综合存储架构 v2」)。
  数据分层、重建剧本、备份闭环的设计结论不依赖掉线频率, 保持有效; 与频率相关的优先级与"短期不换线"的决策按 `.drops` 实测重估。
  同批修复: `hot-tier-resilience.sh verify` 对直接放在 `lmstudio/` 下的平铺模型目录被静默当成已校验 (两边 `cd` 都失败, `diff` 判一致);
  `daily-report` 改为同时报告真实掉线, 并修掉 `grep -c … || echo 0` 在 0 命中时输出两行的折行问题。
- 附带后果: 守卫 `guard_hot_online` 读 keepalive 的 `state` 计数 (≥5 退避); 误报期间 `state` 恒为百位数, 周日 04:00 的定时 `sync-rare` 会被静默拦下。
  v3 修复后计数归零, 该守卫才恢复正常。
