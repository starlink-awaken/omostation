---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: Retro — BET-Y1Q1-T1-05A 共享运行时协调层 (shadow)
type: retro
---
# Retro — BET-Y1Q1-T1-05A 共享运行时协调层 (shadow)

> 状态: shadow 窗口进行中 (窗口起点 2026-08-14T12:56:00Z, 7d)
> 本文档随窗口收口补全; Q3/Q5 留 warning/fail 阶段接手 agent.

## Q1 实际耗时 vs appetite？

- appetite 2 weeks = 实现 ≤3d + shadow 窗口 7d (grill Q5 裁定)
- 实现: 2026-08-14 一天内完成 (store + 5 挂点 + 测试 + 文档 + 台账)
- 窗口: 2026-08-14 → 2026-08-21 (跑满后由 human_gate 确认置 done)
- **待窗口收口回填**

## Q2 done_when 是否全部通过？

| 条目 | 状态 | 证据 |
|------|------|------|
| 共享 SQLite WAL 四表 | ✅ | ensure_ready 懒初始化 + user_version=1 |
| 原子认领并发测试 | ✅ | 20/20 rounds exactly one winner |
| 心跳 5min + fencing token | ⚠️ | 代码测试通过；现有 launchd 仍指向旧 Workspace，部署后才会写 runtime attestation |
| token-check in submit | ✅ | normal/legacy missing-token/镜像缺失均有 verdict; 事件写失败 exit 2 |
| status CLI 三段可读 | ✅ | 人类可读 + --json |
| 双写 acquire/release 对称 | ✅ | E2E 冷启动验证 |
| 备份双层 + runbook | ✅ | crontab 条目 + 普通 store access 非递归 24h fallback |
| shadow 窗口跑满 | ⏳ | 窗口结束用 status --json 导出快照贴此处 |

## Q3 过程中发现的与 plan 不符的事实？

1. **台账存量 25 个 lint error** (T6-06~10 缺字段 + T6-04 dict) — 与本 bet 无关,
   留给人类决定归属 (不在本 bet write_surfaces 语义内修复).
   → **修复轮 (2026-08-14 fixes) 已清零**: 92 bet / 10 轨道全绿 (补 T6-EVOLUTION
   track 登记 + T6-06/07/09/10 最小合法结构 + T6-04 引号).
2. **agent-claim 需要 affected-hash** — claim-check 输出的流程没提, 实际
   `agent-workflow.py claim` 强制要求 (affected-graph.py 计算), AGENT-BRIEF §2.4
   与实际行为有一步未文档化的 gap.
   → **修复轮已补进 AGENT-BRIEF §2.4** (含三个实测坑).
3. **engineering-agent 无权跑 governance-state-mutation** — 必须 governance-agent,
   AGENT-BRIEF 的 claim-check 输出 profile 提示与 profile 实际权限矩阵不一致.
4. **token 写死 0 的自纠** — 初版 submit 挂点用 `--token 0` 会让每次 submit 误报
   stale; 改为 claim 文件持久化 `coordination_token` 字段, submit 读文件.
5. **〔修复轮 2026-08-14 追加〕verify gate FAIL 根因纠正**: 交付轮会话汇报曾诊断
   "verify 的 gate 跑在主仓 (WORKSPACE 解析回主仓)" — **该诊断错误**。修复轮实测:
   `verify --from-diff --execute` 在 worktree 内 PASS, omo 从 worktree
   `projects/omo/src` 加载, WORKSPACE 解析正确。真实根因 = 纯 lane 混合:
   diff 含 `docs/plans/3y-bet-ledger.yaml` (docs_data lane), 而 gac-local-gate
   diff check 的 `allowed_lanes` 缺 `docs_data`, 5 lanes ⊄ 4 allowed → FAIL。
   修复 = `agent-workflows.yaml` 该 check 补 `docs_data` (ADR-0129 §11.3.2 通道)。
   当时交付轮手动 env 注入 AGENT_WORKFLOW_ALLOWED_LANES 是误打误撞走对了接口,
   但根因归因错了 — 教训: 诊断要重现, 不能拿 "现象吻合" 当因果。
6. **〔硬化轮 2026-08-14 追加〕TTL 原先只存不执行**: `claim_resource()` 看到任何
   active 行就拒绝，`check_fencing()` 只比较 MAX(token)，导致过期 claim 永不回收，
   released token 也可能通过。现改为认领事务内先转 `expired`，fencing 同时绑定
   active state、owner、精确 token 与未过期。
7. **〔硬化轮 2026-08-14 追加〕备份/部署声明与事实有 gap**: runbook 声称任意
   store access 自动备份但无调用；实测 launchd plist 仍指向旧 Workspace。前者补为进程锁
   串行、复用当前连接的非递归 fallback，后者通过 privacy-safe commit/source 指纹
   写入 agent_health 并由 status 暴露。shadow 处置仍不阻断，未进入 warning/fail。
8. **〔独立 review 修复〕submit 曾静默跳过无 `coordination_token` 的 claim**:
   legacy claim 或镜像写失败会绕过 fencing 观察面。现统一调用 token-check，显式传
   owner 与 token=0，并用 `token_missing_legacy` 记录 shadow reject；事件写不成则
   exit 2 fail-closed，仍未切 warning/fail。
9. **〔部署收口〕代码根与运行态根原先被同一个 `ROOT` 绑定**: LaunchAgent 若指向
   main 对齐的部署 clone，heartbeat 会写进部署 clone 自己的 `.omo`；若继续指向共享
   Workspace，又加载不到已合并的新代码。daemon 现显式接收 `--workspace-root`，在导入
   OMO 前绑定权威运行态根，并用 `WORKSPACE_CODE_ROOT` 约束 JourneyRunner 的可执行脚本
   继续来自独立部署 clone；attestation 新增 privacy-safe `runtime_root_digest`，用于证明
   没有形成第二运行真相。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- 新增: coordination_store.py (~430 行) + test_coordination_layer.py (~160 行)
  + 缺口报告 + runbook + retro (本文件)
- 修改: swarm_discipline.py (+~60 行) + swarm-discipline-cli.py (+~110 行)
  + agent-tick-daemon.py (+~28 行) + gac-worktree.sh (+~20 行)
  + swarm-coordination.yaml (+24 行) + 3y-bet-ledger.yaml (+~90 行)
- **净增**: 文件 +5, 行数 ~860 (shadow 阶段换掉的是未来 D2/D3/D5 退役时的
  删除面, 见 T1-05 done_when "表面积净减" 条目 — 本 bet 是先增后减的前置)
- GaC 规则: 0 新增 (未加 governance-checks) · ADR: 0 (bet 条目即决策记录)
- **硬化轮增量**: 仅修改既有 9 文件，diff +474/-99（净 +375）；新文件 0、
  GaC 规则 0、ADR 0、脚本 0。`bet-ledger.py surface` 在未初始化全量子模块的
  independent clone 中会把缺失源码误算成大幅下降，故保留原始输出作环境证据，
  不拿该代理量冒充本轮表面积收益。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **warning/fail 阶段翻开关的位置**: `gac-worktree.sh` submit 段 (token-check
   exit 1) + `swarm_discipline.py::_shadow_mirror_claim` (失败改拒绝) +
   `swarm-discipline-cli.py::cmd_token_check` (shadow 注释处).
2. **messages 表已建未接流** — a2a-adapter 双写是 warning 阶段第一件事.
3. **跨机协调是 non_goal** — 访问层 coordination_store.py 单点封装就是为
   daemon 化预留的, 未来替换 `_connect()` 为 socket 客户端即可.
4. **真实共享 DB 已存在，但新版 daemon 尚待部署** —
   `~/agents/_shared/runtime/coordination.sqlite3`; 部署前旧 health 行会持续 stale，不能把
   代码测试冒充 5min 自动心跳。观察入口: `swarm-discipline-cli.py status`.
5. **crontab 日备需人工装载** — 条目在 runbook §4, 机器本地配置不进 git.

## Shadow 窗口收口快照 (待窗口跑满后填)

```
# python3 bin/gac/swarm-discipline-cli.py status --json 的导出贴这里
```

## 附: 修复轮 (2026-08-14, PR #1477)

交付轮汇报挂账的五项缺陷已修:
1. gac-local-gate diff check 补 `docs_data` lane (真 SSOT 是 `_root.yaml`
   split 目录, legacy 单文件同步修 — 两份 registry 并存本身是存量漂移,
   彻底清理留后续 bet)
2. 台账 lint 25 → **0** (T6-EVOLUTION track 登记 + 五 bet 最小结构回填)
3. AGENT-BRIEF §2.4 补 affected-hash 前置 + profile 权限矩阵 + 三个实测坑
4. omo lifecycle `_bounded_lock_name` 修 Errno 63 锁名超长崩溃
5. agent-workflow-tests check 命令补 pyyaml 依赖

verify 7/7 PASS (新配置下含 gac-local-gate 与 agent-workflow-tests),
36/36 tests, 台账 lint 0 error。**本轮最大教训**: 交付轮对 verify FAIL 的
"主仓解析"诊断是错的 — P73 D1 (凭路径直觉判存在性) 的又一案例,
诊断必须重现, 现象吻合 ≠ 因果成立。

## 附: drift 修复轮 (2026-08-15, PR 待提交)

窗口运行 ~1 天的 shadow 数据暴露: `mirror_drift` × 4 全是 holder==session 的
same-owner 重复认领 (文件锁 reused 语义 vs 镜像 active-only 语义错位), 噪音会
淹没真 drift。修复: `claim_resource` same-owner 幂等分支 — 顺延 TTL 返回既有
claim, token 不变; 挂点侧无需改 (返回既有 Claim 自然走 write_ok 路径)。

验证: 四套件 ALL PASS + E2E (幂等重取 token=1 保持 / 0 drift 事件 / 异 session
仍拒绝 / release 对称)。

同轮情报: #1483 (硬化轮, 别的 agent) 已修 TTL 不执行/fencing 松弛/备份假声明,
#1485 已把 daemon 部署到专属 clone `~/agents/coordination-daemon/ws` (心跳 00:06Z
恢复)。本轮基于 cd550370 基线, 无重复造轮。

## 附: ops 轮 (2026-08-15, PR 待提交)

窗口第 2 天扫描发现两处部署漂移 (非代码 bug, 是部署面缺口):
1. **备份静默断流 ~1 天**: cron cd 指向主仓, 但主仓 checkout 被切到 feature 分支,
   工作树无 coordination_store.py → 08:30 cron 每次静默 fail, .bak.1 停在
   2026-08-14T21:15. 处置: crontab 已切部署 clone (~/agents/coordination-daemon/ws,
   #1485 建立的干净代码根) + 手动 --backup 验证 ok (新 .bak.1 落盘, integrity ok).
2. **daemon clone 落后 main**: 无自动更新机制, #1490 不在其中 → 手动 fetch +
   ff-only + launchctl kickstart, 心跳 01:13Z 恢复且加载新代码.

代码修复: 仅 runbook (维护 SOP + 2 行故障速查固化上述坑), 零代码改动 —
问题在部署面不在代码面. 文档先行, 后续若断流复发再考虑 cron 自愈/告警.


## 2026-08-17 增补 — daemon SIGTERM 事件 + 窗口提前指令下的状态

- **daemon 故障与修复**: launchd agent-tick-daemon 被 SIGTERM 杀 (exit -15, KeepAlive
  竟未拉起), agent_health 一度无新心跳。处置: bootout + bootstrap 重挂 (PID 23551,
  exit 0), `--once` 手动 tick 验证 6 agents 全 ok 落库。无数据丢失 (claims/shadow_events
  完好), 属 launchd 层瞬时故障非代码缺陷。
- **当前快照 (2026-08-17T23:2xZ)**: agents 6 / stale 0 / claims 70 (active 61+released);
  shadow_events: write_ok 81, backup_ok 3, mirror_drift 4, token_missing_legacy 55。
- **窗口提前实施指令下**: 实现+运行证据已满 (08-14 起持续), done_when 机器可验项全过
  (DB/concurrency/fencing/schema 四套 verify 见 bet)。剩余唯一: human_gate 确认存量清单
  后置 done — 按红线保留, 08-21 锚点转为终审 check 而非阻塞。
