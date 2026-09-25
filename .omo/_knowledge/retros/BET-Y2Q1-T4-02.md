---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
title: BET-Y2Q1-T4-02 复盘
---

# BET-Y2Q1-T4-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
实际耗时 1 小时，远低于 appetite (1 week)，按时按质交付闭环。

## Q2 done_when 是否全部通过？哪条没过，为什么？
全部通过：
1. `mail_daemon.py` 支持 `--status` 结构化运行诊断输出、单实例 PID 锁机制及信号处理（SIGTERM/SIGINT 优雅退出与清理）。
2. 生成了系统常驻 launchd 描述文件 `runtime/cron/com.starlink.mail-daemon.plist`。
3. 实现了向全局事件总线发射标准 `SignalIngressed` 事件（topic: `mesh:signal:mail`），并在 `bin/ssot/resident-routes.yaml` 中完成规则路由注册。
4. 实现了向 Cockpit 统一待办池 `runtime/cockpit/inbox-tasks.json` 的原子投影与基于主题的防重入机制。
5. 专用单元测试 `tests/unit/test_mail_daemon_resident_loop.py` 5 项测试 100% 通过。
6. 本地门禁 `make gac-local-gate` 59 项全部绿色通过，台账 `bet-ledger.py lint` 0 错误。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **bin 脚本配额守恒约束 (check-bin-quota-diff)**：
   - 尝试在 `bin/ssot/` 新增独立 shell 安装脚本时触发了 `check-bin-quota-diff` 阻断。主仓严格实行变更侧配额守恒（净增为 0）。
   - **架构对齐解法**：不随意在 `bin/` 增加一次性包装脚本，而是将常驻 launchd 配置文件置于 `runtime/cron/` 下，核心启停与诊断能力直接内聚在 `mail_daemon.py` 自身，确保代码内聚度且不突破脚本配额。
2. **并发 PR 导致的 script_baseline 飘移**：
   - 主分支刚合并的 PR #4138 将 `script_baseline` 从 690 提升到 698，fork 点较旧的 worktree 执行门禁时会因负向 delta 报错。通过无冲突 fast-forward 对齐最新 `origin/main` 彻底消除。
3. **Spec frontmatter schema 标准化**：
   - accepted spec 必须严格声明 `schema_version: specification/v1` 和 `spec_version: 1.0.0`，且台账在 `IN_PROGRESS` 阶段派生的 `overall_state` 为 `evaluating`，在 `done` 阶段派生为 `delivery_accepted`。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
- 新增规范 Spec: `docs/superpowers/specs/2026-09-21-t4-02-signal-daemon-and-resident-loop-design.md`
- 登记 Spec 索引: `docs/superpowers/specs/README.md`
- 增强核心守护: `bin/ssot/mail_daemon.py` (增加 --status、PID 锁、事件发射、待办投影)
- 增加路由规则: `bin/ssot/resident-routes.yaml` (增加 SignalIngressed 规则)
- 新增系统配置: `runtime/cron/com.starlink.mail-daemon.plist`
- 新增单元测试: `tests/unit/test_mail_daemon_resident_loop.py`
- 更新台账: `docs/plans/3y-bet-ledger.yaml` (新增 BET-Y2Q1-T4-02 并完成状态标记)
- 新增复盘: `.omo/_knowledge/retros/BET-Y2Q1-T4-02.md`

## Q5 下一个认领本 track 的 agent 需要知道什么？
- 邮件与真实信号流已具备常驻守护与 Cockpit 待办投影能力；
- 下一步（方向 2）的核心演化任务是 **Spine Value Pipeline 署名 Diff 自适应学习**：当夏明星在 Cockpit 对 `runtime/cockpit/inbox-tasks.json` 中的公文草稿进行修改署名时，捕获其人工编辑 Diff，自动萃取 DPO 偏好或 MOS 信念，完成自我进化闭环。
