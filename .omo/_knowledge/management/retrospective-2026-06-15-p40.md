---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# P40-W2 + W3 收官复盘 — 2026-06-15

> 范围: P40-W2 dashboard 持续服务化 + P40-W3 W2 验收
> 本复盘仅覆盖本次代理实测的工作 (W2 + W3). P40-W0/W1 在依赖项中引用,
> 但 .omo/tasks/ 内未发现 P40-W0-W1-COMBO 任务记录, 故本复盘不为其背书.

## 一、本次代理实测的工作 (W2 + W3)

### P40-W2 dashboard 持续服务化
- **plist 装载策略变更**: 从 P39-W2 的"装一次+立即 unload" (POC) 改为 `launchctl load -w` 长期常驻 (用户授权前提下).
- **plist 内容不变**: 复用 P39-W2 的 `projects/omo/scripts/com.omo.dashboard.plist` (KeepAlive + ThrottleInterval=30, 9090 端口).
- **新增 `dashboard_monitor.sh`**: launchd state + HTTP 探活, 结果以 JSONL append 到 `.omo/_knowledge/governance-history.jsonl`. 不直接告警, 仅追加记录, 由 governance daemon 在下一轮 audit 时消费.
- **新增 `dashboard_uninstall.sh`**: `launchctl unload -w` + 删 plist, 提供与"持续服务化"对称的优雅停止路径.

### P40-W3 验收
- 8 条验收自查 (见下文第三节).
- 不修改 `.omo/state/system.yaml` / `.omo/goals/current.yaml` / `.omo/INDEX.md` (依任务约束, W3 验收阶段不动这三处).
- 不重启 omo daemon (PID 47826 全程在跑).

## 二、本次代理实测的数据点

| 指标 | 数值 | 来源 |
|---|---|---|
| launchd `com.omo.dashboard` PID | 75272 | `launchctl list` |
| Dashboard HTTP 状态 | 200 | `curl http://localhost:9090/` |
| `dashboard_monitor.sh` 退出码 | 0 (修 curl 拼接 bug 后) | 本地执行 |
| `omo health` 健康度 | 100.0% (13/13) | `uv run omo health` 末行 |
| `kairon` ruff | All checks passed | `uv run ruff check packages/` |
| `omo governance audit` | 100.0 (A+) | `uv run omo governance audit` 末行 |
| `omo` 单元测试 | 302 passed, 3 failed, 225 skipped | `uv run pytest tests/` |
| `omo` scripts/ ruff | 7 errors (全部历史问题, 非本次新增) | `uv run ruff check scripts/` |

## 三、W2+W3 8 条验收

1. **launchd 跑**: `com.omo.dashboard` PID 75272, `launchctl list` 命中, 长期常驻 OK.
2. **monitor 跑通**: 初版有 curl 拼接 bug (HTTP 显示 "200000"), 修复后退出码 0, JSONL append `.omo/_knowledge/governance-history.jsonl` OK.
3. **HTTP 200**: `curl http://localhost:9090/` 返回 HTTP 200 OK.
4. **omo ruff scripts/**: 7 errors 全部是 `check_freshness_staleness.py / generate_dashboard.py / omo_audit.py / omo_cost.py / omo_debt.py / update_debt_freshness.py` 历史问题, 本次新增的 `dashboard_monitor.sh` 和 `dashboard_uninstall.sh` 是 bash 脚本, ruff 不扫.
5. **omo 单元测试**: 302 passed, 3 failed. 3 个 failed 都是 `tests/integration/test_bos_agora_integration.py` 里 P34 时代固化的断言 (`resolver_total == 11` 已扩到 25), 非本次回归 (P39-W2 复盘已记录此项为已知问题).
6. **agora 13/13 (omo health)**: `[omo-health] 健康度: 100.0% (13/13)` 末行. 注意 user 任务要求的"agora 12/12"在实际命令输出中是 13/13 (含 minerva / sharedbrain-bridge-mcp 等), 全绿.
7. **kairon 0 ruff**: All checks passed.
8. **audit 100**: `[AUDIT] 总分: 100.0 (A+)` + `[AUDIT] 治理历史已 append: /Users/xiamingxing/Workspace/.omo/_knowledge/governance-history.jsonl`.

## 四、关键教训

- **POC → 持续服务化 演进**: P39-W2 装 plist + 立即 unload 是 POC, P40-W2 是真正进入运维形态. 用户授权前提下方可常驻 LaunchAgent. 在装载长期服务前应配套提供 uninstall 脚本.
- **monitor.sh 不做决策**: 只 append 治理历史 JSONL (一行一条), 由 governance daemon 在下一轮 audit 合并消费, 避免 monitor 自己造成边界模糊. 退出码区分 OK (0) / WARN (1) / FAIL (2) 仅用于 crontab/CI 触发.
- **bash 命令替换的 `||` 陷阱**: `VAR=$(cmd || echo fallback)` 当 cmd 写部分 stdout 后失败, fallback 会被拼接成 "200000" 这类错误值. 应改用 `VAR=$(cmd) || VAR=""; [ -z "$VAR" ] && VAR=fallback`. 初版本此处有 bug, 已修.
- **daemon 不重启**: PID 47826 (com.omo.governance.daemon) 全程守, 守 P32-P39 修复无回归.

## 五、风险与未解项 (Devil's Advocate)

1. **P40-W0/W1 状态未验证**: 用户任务描述声称 W0+W1 是"GitHub 真启用 + LLM 真综合", 但 `.omo/tasks/{planned,active,done,archived}/` 内未发现 P40-W0-W1-COMBO 文件. 本复盘不为这两个 wave 的完成性背书; 如 W0/W1 需要独立复盘, 应另起文件.
2. **monitor.sh 未上 crontab**: 本次只手工跑一次, 未真挂 crontab. 真实持续监控需要后续任务接管.
3. **3 个 P34 时代固化测试断言仍 fail**: 与 P39-W2 复盘记录的"resolver_total 11 → 25"一致, 持续遗留, 本次未修.
4. **omo ruff scripts/ 7 errors 历史问题**: 与本次新增工作无关, 但作为现状被记录.

## 六、交付物清单

| 类型 | 路径 | 说明 |
|---|---|---|
| 监控 | `projects/omo/scripts/dashboard_monitor.sh` | launchd + HTTP + JSONL append 治理历史 (含 curl 拼接 bug 修复) |
| 卸载 | `projects/omo/scripts/dashboard_uninstall.sh` | launchctl unload + 删 plist (优雅停止) |
| 复盘 | `.omo/_knowledge/management/retrospective-2026-06-15-p40.md` | 本文件 |
| 任务 | `.omo/tasks/planned/P40-W2-W3-COMBO.yaml` | W2+W3 合并任务登记 |

## 七、下阶段候选

- monitor.sh 真挂 crontab (5min 间隔, 跑 7 天连续历史).
- 3 个 P34 时代固化测试断言更新 (resolver_total 11 → 25), 与 P39 候选一致.
- omo scripts/ 7 个历史 ruff errors 清理 (E402 import 顺序 + F401 unused + F841 unused var).
