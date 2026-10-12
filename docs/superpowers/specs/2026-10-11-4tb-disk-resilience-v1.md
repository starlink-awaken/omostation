---
schema: md/v1
type: spec
schema_version: specification/v1
status: accepted
lifecycle: spec
spec_version: 1.0.2
bet_id: BET-Y2Q4-T10-243
owner: engineering-agent
last-reviewed: '2026-10-12'
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

新增 1 个 bin/ 脚本 (注册 script-registry); 回归测试 `tests/bin/test_hot_tier_resilience.sh`
(macOS 专用, 其它系统跳过; 每条断言对应一个实测踩过的坑, 并做过变异检查: 对着修复前的脚本跑会大面积变红):

| 子命令 | 功能 | 排程 |
|---|---|---|
| `sync-rare` | SHAREDMODEL/lmstudio 稀有发布者 → Lex 增量 (rsync --bwlimit 40M, 排除公开 7 家); 卷预检; 成功记 `last-sync-rare.ok` | 周任务内 |
| `manifest` | 刷新公开源重建清单 (Lex + 仓内双写); 先写临时文件, **清单为空不覆盖旧的** | 周任务内 |
| `snapshot-links` | models-active 软链清单固化 → ~/omlx/conf/models-active.manifest | 周任务内 |
| `verify` | Lex 副本 vs 热层抽样校验 + 清单新鲜度; **抽样为 0、热层读不到、清单缺失/超 7 天都判失败** | 周任务内 |
| `weekly` | 周任务: 上面四步按序执行, 遇错即停; 结果记 `last-weekly.status`, 整链成功记 `last-weekly.ok`, 失败桌面通知 | 周日 04:00 (经终端 App 启动器, 见 §6) |
| `daily-report` | 日报: 真实掉线 + keepalive 计数 + **周任务心跳** (超 8 天未成功 → 通知并补跑) | 每日 23:50 (launchd 直启) |
| `rebuild <新卷挂载点>` | T3 重建剧本: 建目录 → 稀有回灌 → 公开重下清单打印 → 软链农场重建 | 手动 (灾难时) |
| `selftest-launchd` | 在 launchd 里实测直启 `/bin/bash` 与经终端 App 中转两种启动方式能否读热层、写 Lex | 手动 (装排程前后) |
| `install-schedule` | 生成启动器与 plist 到暂存目录并打印安装命令, **不执行** (排程为人工安装制) | 手动 |

## 5. 掉线感知链 (T1/T2 治理)

1. keepalive UUID 自愈 (v2, 已验证 100%) — 不动
2. macOS 桌面通知 (2026-10-11 已加, 节流 1 条/小时) — 已上线
3. **掉线日报**: 每日 23:50 汇总真实掉线 (`disk-keepalive.drops`) 与 keepalive 探测计数 →
   追加到 `~/Library/Logs/disk-keepalive.daily` (resilience 脚本 daily-report 子命令)
4. **卷预检** (所有读写外接卷的子命令): 先用 `stat` 判是否真挂载 (挂载点与 `/Volumes` 同设备 = 掉线后残留的空目录),
   再用 `ls` / 写探针判能不能用。退出码 75 = 不在线 (稍后重试), 77 = 权限被拒 (launchd 下缺 TCC 授权)。
   掉线周期内 (keepalive `state` ≥ 5) 退避 (exit 75)
5. **周任务心跳** (1.0.2 新增): 周任务跑在终端 App 里, 本身可能根本没起来 —— 装上的排程曾一次都没跑过而无人知晓。
   日报读 `~/.local/state/hot-tier-resilience/last-weekly.ok`: 从未成功或超过 8 天 → 桌面通知, 并经终端 App 补跑
   (两个卷都挂着、启动器存在、20 小时内没试过才补, 避免连环重试)

## 6. launchd 排程 (人工安装制, 沿用 cold-backup-drill 约定)

**TCC 约束 (1.0.2, 2026-10-12 在 launchd 里实测)**: launchd 直接拉起的 `/bin/bash` 对外接卷没有『可移动卷』授权 ——
`ls` / `find` / 写入全部 `Operation not permitted`, 而 `[ -d ]` 与 `stat` 照常成功 (所以只靠 `[ -d ]` 的守卫会放行,
随后 rsync 才失败)。1.0.1 之前的周任务 plist (`/bin/bash -c "sync-rare && …"`) 装上后一次都没运行过 (`runs = 0`);
一旦运行, 会在第一步 `sync-rare` 失败并只留一行日志。启动方式因此按"是否碰外接卷"区分:

| 任务 | 启动方式 | 理由 |
|---|---|---|
| 周任务 (读热层、写 Lex) | launchd → `open -g -j -a iTerm <启动器>` → `weekly` | 负责进程是已获授权的 iTerm。实测 `selftest-launchd`: 直启 `hot=77 lex_write=77`, 经 iTerm `hot=0 lex_write=0` |
| 日报 (只读家目录日志与状态) | launchd 直接跑脚本 | 不碰外接卷 |

不推荐给 `/bin/bash` 开完全磁盘访问权限 (范围过大, 所有 launchd 下的 bash 脚本都会跟着获权)。

```bash
# 生成启动器与 plist 到暂存目录, 并打印安装命令与同已装 plist 的差异 (不执行任何安装)
bash ~/Workspace/bin/ops/hot-tier-resilience.sh install-schedule
# 装好后在真实 launchd 里实测 (直启失败是预期, 经终端 App 必须通过)
bash ~/Workspace/bin/ops/hot-tier-resilience.sh selftest-launchd
# 卸载
launchctl bootout gui/$(id -u)/com.local.hot-tier-resilience
```

安装顺序: 先让主工作区更新到含 `weekly` 的版本 (plist 与启动器指向 `~/Workspace/bin/ops/` 下的稳定路径),
再放启动器、换 plist; 反过来会让周日 04:00 的启动器去调一个还不认识 `weekly` 的旧脚本 (exit 64)。

## 7. 演练与验收

- [x] 首次 `sync-rare` 全量 + `verify` 通过 (2026-10-11); 1.0.2 起 `verify` 对抽样为 0 / 读不到 / 清单缺失或超期判失败
- [ ] `snapshot-links` 清单入库, git 追溯 (现清单在 `~/omlx/conf/`, 未入 git)
- [x] **半演练**: 在 Lex 侧模拟 rebuild 的 P0+P1 段 (软链农场重建 28 链 / 2ms; 稀有抽样回灌 16G / 137s ≈ 119 MB/s) (2026-10-11)
- [ ] 掉线日报连续 7 天产出 (含周任务心跳)
- [x] `selftest-launchd` 在真实 launchd 里通过 (2026-10-12: 直启 `hot=77 lex_write=77`, 经 iTerm `hot=0 lex_write=0`)
- [x] `weekly` 整链在真实卷上跑通 (2026-10-12 手动, 1.2 秒: sync-rare 16 目录 / manifest 36 条 / 软链 29 / verify 抽样 15 不一致 0)
- [ ] 周任务经终端 App 启动器**由 launchd 首次真实触发**并整链成功 (等安装后的第一个周日 04:00, 或日报补跑)
- [ ] 心跳超期 → 通知 + 补跑 在真实环境触发过一次 (把 `last-weekly.ok` 改旧即可验证)
- 全演练 (真换盘) 时机由用户定

## 8. 未决项 (依赖用户/硬件决策)

- 换线/换盘 — 以直连对照实验为准 (2026-10-11 起: 摘掉 hub、直插后置雷电口, 观察 3~7 天看 `.drops` 的 `ss_removed`;
  不再掉 → 问题在 hub 或其上游线, 仍掉且 `ss_removed=1` → 走厂家售后); 结果记入 HW-DISK8-4TB-FLAKY 债务
- Model 1T 卷终态 (TM error 45 未解) — 排空后删卷重建可一并解决。实测 (2026-10-12): `tmutil destinationinfo` 为
  "No destinations configured", TM 偏好 `AutoBackup = 0`、`LastBackupActivity = 2026-03-16` —— 内置盘此前近 7 个月没有 Time Machine 备份,
  目前只靠 2026-10-11 的加密归档 (Lex + NAS); 设目的地需要 sudo, 由用户执行
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
- **1.0.2 (2026-10-12)**: 排程层补洞 —— 修的是"监控修好之后, 执行层其实也从没跑过"。
  1. launchd 下 `/bin/bash` 读写外接卷全部被 TCC 拒 (`selftest-launchd` 实测)。原周任务 plist 装上后 `runs = 0` 一次未运行,
     一旦运行会在 `sync-rare` 失败; 改为经终端 App 启动器 (§6), 新增 `weekly` / `selftest-launchd` / `install-schedule`。
  2. `verify` 在热层读不到时输出"抽样 0 个模型, 不一致 0"并 exit 0 —— 与 1.0.1 修的平铺目录假通过同一类 (空输入当通过)。
     现在抽样为 0、热层读不到、Lex 无清单或清单超 7 天一律失败。
  3. `manifest` 在热层读不到时会用只有标题的空壳覆盖 Lex 上的好清单 (`ls` 静默失败)。现在先写临时文件, 清单为空则保留旧的。
  4. 守卫头注释写"exit 75 = TEMPFAIL"而代码是 `exit 1` (声明与执行不一致)。现在卷不在线 75、权限被拒 77。
  5. 日报新增周任务心跳与补跑 (§5), 防止周任务再次"装上却从未运行"而无人知晓。
  验证: `tests/bin/test_hot_tier_resilience.sh` 全过, 且对着修复前的脚本跑 (`HOT_TIER_SCRIPT=<旧版路径>`) 大面积变红; 真实 launchd 与真实卷上的 `selftest-launchd`、`weekly` 见 §7。
