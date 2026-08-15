# 乙流（遗留任务）清欠轮

> 前置：T1-05A 四轮（#1475/#1477/#1490/#1491）+ 信任修复两轮（#1498/#1512）全部 merge。台账 95 bet lint 全绿。

## Context

上轮遗留分三类：A 尾活打包（WS 前缀核对 + legacy registry 删除）/ B 唯一 in_progress 收尾（T2-02 poller 不落盘）/ C 最老窗口新领（Y1Q1-T1-08 bump-fast）。

## 四个拷问裁定

| # | 分支 | 裁定 |
|---|------|------|
| Q1 | 范围 | A+B+C（尾活打包 + T2-02 修复 + 领 T1-08）|
| Q2 | T2-02 完成边界 | 修 poller + 窗口 08-15 起算 + **保持 in_progress**（红线：窗口 7 天不满不置 done）|
| Q3 | A 类打包边界 | WS 前缀核对 + legacy registry 删除（先验零消费）进治理 PR；mof-deepen 测试面立 candidate bet；PR gate 拍板项单列汇报 |
| Q4 | bump-fast vs bump-pointer | **最优解**：bump-fast 承载全部新逻辑，bump-pointer 改薄别名转发（DRY + 零破坏 + 单一实现）|

## 执行步骤

### 阶段 1：机器侧即时修复（不进 PR，立即生效）

1. **修 signal-poller plist**：`~/Library/LaunchAgents/com.omostation.signal-poller.plist` 的 ProgramArguments[0] 从 Xcode Python 3.9 改 `/opt/homebrew/bin/python3`
2. **kickstart**：`launchctl kickstart -k gui/$(id -u)/com.omostation.signal-poller`
3. **验证**：等 5 分钟看 `.omo/_log/signal-poller-launchd.log` 有无新条目 + `signal-poller.py --health --json` 的 apple_mail_inbox 从 degraded 变 healthy

### 阶段 2：治理轮 PR（A 类 + B 类 retro 段）

worktree `ledger-cleanup` → `agent-workflow.py start governance-state-mutation` → claim 写面：

- **WS 前缀核对**：grep 全仓 `src/cockpit/` / `src/omo/` / `src/ecos/` 等裸前缀→对照 `.gitmodules` 真实路径→修正台账 write_surfaces 字段（只改字段不改代码）
- **legacy registry 删除**：先 `rg -l "agent-worksheets.yaml" bin/ tests/ projects/` 验零消费→删 `docs/plans/3y-bet-ledger.yaml` 里的 legacy 双份 diff_checks（保留 `_root.yaml` 为唯一 SSOT）
- **T2-02 retro 追加**：poller 修复记录 + 窗口 08-15 起算锚点 + netease unreachable 已知缺口记录
- **mof-deepen 测试面 candidate bet**：`BET-Y1Q3-T6-0X` 挂账（write_surfaces=10 模块测试路径，status=candidate，不实施）
- **bump-fast 实施**：`bin/gac/gac-worktree.sh` 新增 `bump-fast` 子命令 + `bump-pointer` 改别名；测试落 `bin/gac/test_bump_fast.py`

### 阶段 3：T1-08 独立 worktree

`gac-worktree.sh claim bet-y1q1-t1-08` → bet-execution → 按 DW 六条逐条落盘 + 计时测试 → retro 五问 → submit → merge

## 验证

1. `signal-poller.py --health --json` → apple_mail_inbox status=healthy（5min 内）
2. `bet-ledger.py lint` → OK（含新 T6-XX candidate）
3. `time bash bin/gac/gac-worktree.sh bump-fast projects/omlxc --latest-main` → < 2s
4. 故意传不可达 SHA → fail-closed 非 0 退出
5. `docs/project-registry.yaml` 对应字段与新指针一致
6. workflow verify 4/4 PASS；PR checks 全绿

## 红线

- T2-02 窗口 7 天不满不置 done（08-22 再评）
- T1-05A 不碰（窗口 08-21）
- 不扩 mof-deepen 实施面（只立 bet 不写测试）
- 不动 PR gate 拍板项（汇报单列）
