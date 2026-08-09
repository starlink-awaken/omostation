# BET-Y1Q3-T2-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 30 分钟（vs appetite 1 周）。signal-poller 已支持 local_filesystem transport，文件夹源只需注册。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 第二个信号源注册且有真实信号 | ✅ `signal-sources.yaml` 注册 `inbox_folder` (transport=local_filesystem, path=~/Documents/@感知信号), 实测投放文件产生 content_changed 信号 |
| 抽象未因第二类源被破坏(无 if-else 特判) | ✅ 文件夹源与邮件源同走 `local_filesystem` 分支 (mtime+child hash 检测), poller 未加任何 per-source 特判 |
| 每周信号数 >= 10 | ⏳ 持续观察目标 — 机制就绪, 由 cron/poller 积累 |

未过: 无 (机制交付, 周产为观察目标)。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **signal-poller 已支持文件夹**: transport=local_filesystem 的 hash 检测 (mtime+child 数) 天然适配目录变化 → 文件夹源零代码改动, 只需注册 + 映射。
2. **文件夹是最贴合抽象的第二源**: 与邮件同 transport, 完美满足"无 if-else 特判" (日历需新增 .ics 解析, 会引入特判)。
3. **去重验证**: 首次轮询产生信号 (初始状态), 二次轮询 no_changes (去重生效), 投放文件后再次触发。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- `.omo/_truth/registry/signal-sources.yaml` +17 行: inbox_folder 注册
- `bin/ssot/signal-poller.py` +1 行: SIGNAL_TO_JOURNEY 映射
- `tests/unit/test_signal_folder_source.py` (5 个): 注册/共享 transport/映射/信号/去重

无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **信号源注册**: `.omo/_truth/registry/signal-sources.yaml` sources 列表, transport=local_filesystem 自动由 poller 处理 (hash 检测)。
2. **新源接入**: 注册条目 + SIGNAL_TO_JOURNEY 映射即可, 无需改 poller 核心。
3. **文件夹路径**: `~/Documents/@感知信号`, 投放文件即信号。
4. **测试**: `tests/unit/test_signal_folder_source.py` (5 个: 注册/共享 transport/映射/信号/去重)。
5. **待办**: 日历源需新增 .ics 解析 (会引入 transport 分支, 待第三源时设计); cron 定期跑 poller 积累周产。
