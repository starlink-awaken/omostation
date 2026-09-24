---
type: runbook
domain: ops
service: zhixing-dashboard
port: 43191
last_updated: 2026-09-24
---

# 织星驾驶舱 (:43191) 运维手册

## 架构

```
launchd (gui/501)
├── com.omostation.zhixing-dashboard          live_server.py  :43191, KeepAlive=true, RunAtLoad=true
├── com.omostation.zhixing-dashboard-refresh  orchestrator.py  每 300s 刷新快照
└── com.omostation.zhixing-dashboard-watchdog liveness-watchdog.sh  每 120s 端口级活性探测
```

- 部署目录: `~/.local/share/zhixing-dashboard/`（**不受 git 版本控制**；仓库资产在 `bin/panorama/assets/host/`，由 `bin/gac/zhixing-host-sync.py` 漂移检测/捕获/回滚）
- 资产版本化映射: live_server.py → `bin/panorama/assets/host/live_server.py.asset`（`.asset` 后缀避免被脚本治理面误纳）
- 日志:
  - 服务: `~/Workspace/runtime/dashboard/launchd-zhixing-43191.log`
  - 刷新: `~/.local/share/zhixing-dashboard/launchd-refresh.log`
  - 看门狗: `~/Workspace/runtime/dashboard/watchdog.log`
- 只读服务: 无写 API、无命令执行、loopback-only

## 事故复盘

### 2026-09-24 dashboard 挂了（服务停机 ~6h）

**根因链**:
1. 服务此前靠手动 `nohup` 跑，无进程守护 → 机器 18:46 重启后进程死亡，无自动恢复
2. 当天 14:47 有人创建了 launchd plist 做加固，但 bootstrap **静默失败**（error 5: 服务被 disabled），无人验证端口是否真起来了
3. disabled 标志来自 9 月 22 日「暂停 LLM 定时任务」清理，**launchd 的 disabled 标志存在用户级 overrides 里，与 plist 文件无关、长期残留**；`launchctl list` 看不到（任务直接不显示），属静默失败
4. 无任何告警

**教训（已固化）**:
- launchd `disabled` 标志必须显式查: `launchctl print-disabled gui/$(id -u) | grep <label>`
- bootstrap 后必须验证: `launchctl list | grep <label>` + `curl` 端口
- 清理停用时只 disable 精确 label，不用通配，并记录清单

### 2026-09-24 omlxc 子模块门禁阻塞（推送到阻 ~6h）

**根因链**:
1. 9/24 07:09 — omlxc-fix 分支 (canary + cli/api fix) **squash 合并**进 omlxc origin/main → `ec48f56` (#87)
2. 9/24 14:45 — bot `starlink-awaken` 提 `1d57d78c6` "chore(submodule): bump...omlxc" 把主仓 omlxc 指针从 `ec48f56`**反向回退到 `3ac37cf`**（仅 canary，缺后续修复）
3. squash 后 `3ac37cf` 在 origin/main 历史中不可达 → submodule-reachability 门禁报 "not contained in fetched origin blocks" → 所有推送被阻

**核心冲突**: 自动 bump 流程违反 "no-rewind" 合同（`submodule-autobump.sh` C3: 仅当 current 是 remote main 祖先时才前进）。本次 14:45 的 bump 来自另一工具/流程，方向搞反。

**修复**: `65e25d4f2` 把指针重新推进到 `ec48f56`（origin/main HEAD，包含全部工作）。门禁验证 0 失败。

**长期防护**:
- 子模块 squash/force-push 后必须同步主仓 gitlink
- bump 脚本必须坚守 no-rewind 合同；任何回退操作需人工确认
- 运维手册自身入版本控制（曾丢失一次，已重建）

## 日常操作

```bash
# 状态
launchctl list | grep zhixing && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:43191/

# 重启
launchctl kickstart -k gui/$(id -u)/com.omostation.zhixing-dashboard

# 暂停/恢复（refresh 或 watchdog 同理）
launchctl bootout  gui/$(id -u)/com.omostation.zhixing-dashboard-refresh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.omostation.zhixing-dashboard-refresh.plist

# 注意: bootout 不清 disabled 标志; 若曾 disable 过需先 enable
launchctl enable gui/$(id -u)/com.omostation.zhixing-dashboard

# 漂移检测
python3 bin/gac/zhixing-host-sync.py check      # exit 0 = 无漂移
python3 bin/gac/zhixing-host-sync.py capture    # 部署 → 仓库（版本化）

# 门禁
python3 bin/ssot/submodule-reachability-gate.py --source head --json
```

## 看门狗测试

```bash
# 故障路径（dry-run, 不影响真实服务）
ZHIXING_WATCHDOG_PORT=43999 ZHIXING_WATCHDOG_DRY_RUN=1 \
  ZHIXING_WATCHDOG_STATE=/tmp/wd.state ZHIXING_WATCHDOG_LOG=/tmp/wd.log \
  bash ~/.local/share/zhixing-dashboard/liveness-watchdog.sh  # 跑两次看 ACTION
# 健康路径（静默成功）
bash ~/.local/share/zhixing-dashboard/liveness-watchdog.sh
```

## 排障

| 症状 | 排查 |
|------|------|
| 端口不通 | ① `launchctl list \| grep zhixing` ② `launchctl print-disabled` ③ launchd-zhixing-43191.log |
| 页面数据不刷新 | launchd-refresh.log；手动 `python3 ~/.local/share/zhixing-dashboard/orchestrator.py` |
| 看门狗误报 | watchdog.log；连续 2 次失败才动作，单次只计数 |
| 宿主文件漂移（zhixing-host-drift 退出码 1） | `python3 bin/gac/zhixing-host-sync.py check`；有意变更→capture，意外覆盖→restore |
| 子模块门禁阻塞 | `submodule-reachability-gate.py --source head --json`；查 squash/force-push 后 gitlink 是否同步 |
| launchd bootstrap error 5 | `launchctl print-disabled gui/$(id -u)/<label>`；`launchctl enable` 后再 bootstrap |
