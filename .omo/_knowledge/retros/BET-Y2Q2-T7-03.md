# Retro — BET-Y2Q2-T7-03 主动健康连续体征监测、异常预警与就诊咨询闭环

- bet: BET-Y2Q2-T7-03
- run: 20260912T124906Z-bet-execution-7061a1d3
- date: 2026-09-12
- status: delivered (第一可交付 PR)

## 交付

1. `projects/domain-cartridges/health/` — 新 cartridge（mirror research 约定）：
   `vitals.py`（台账/个人基线/unmeasured 语义）、`monitor_pipeline.py`
   （每日健康分/异常检测/干预卡/--daily CLI）、`apple_health_csv.py`
   （手工导出 CSV 本地解析）、`test_monitor_pipeline.py`（自测入口）。
2. `docs/scene-cards/personal-health-monitor.yaml` — scene-card/v2，
   lifecycle assisted，复用 `health-medical-workflow` 旅程。
3. `docs/superpowers/specs/2026-09-12-y2q2-t7-03-health-monitor-design.md` —
   设计 spec + ledger accepted 绑定。
4. ledger verify 修一行：cartridge 自测必须 `cd` 进 cartridge 目录执行
   （与 research done bet 的 `cd ... && uv run` 前例对齐；根目录 `-m` 在
   sys.path 注入前即失败）。

## 校准证据（assisted 门）

30 天评估窗 + 12 天前置基线期种子台账，6 天注入异常（睡眠簇/心率簇/血糖 spike）
全检出、0 误报：F1=1.000 ≥ 0.6。自测 22 项断言全过。

## 关键修补记录

- 基线污染：极值日会抬高滚动基线标准差致邻日报漏（实证 08-12 fn）→ 两遍检测
  （首遍标极值，次遍剔除已标日重判）+ spike 日计入 anomaly 连续段。
- 评分函数：线性 `100-25z` 对正常波动（z≈1）过于惩罚 → 二次 `100-10z²`。
- 断言用相对口径（异常日 < 正常日 −15）替代绝对阈值，防种子调参漂移。
- `card06` 断言反转：08-06 本就是 spike 日，按 spec §3.2 spike 规则建议就诊
  是正确行为；“2 天中等偏离不建议就诊”的对比改用 micro-ledger 另行覆盖。

## 诚实声明 / 缺口

- 校准基于 synthetic-seed，非真人数据；真人 30-sample 积累是后续 bet。
- 每日定时：`run_daily --daily` 就绪，但 cron 未装机（reality-tagged
  `.omo/cron/registry.yaml` 不由场景 bet 直写，留 owner 待办）。
- Apple Health 仅手工导出 CSV；无自动采集（P1 敏感域约束，非缺口是设计）。
- 无诊断断言；就诊建议仅为规则 hint，最终由医生判定。

## 并发环境备注（2026-09-12 实证）

- 本 run 选 bet 时亲历 main 高速并发：初选 T7-05 在 triage 间隙被 #3691 合入，
  T5-04 被 #3692 合入，T8-21 被 #3662 合入而 ledger 仍 candidate。
  PITFALL-GAT-006 必须对**当前 tip**重做，T7-05/T5-04/T8-21 均放弃（防回退）。
- T10-164 与活跃并发会话 `t10-164-evidence` 正面撞车 → 放弃，改选无撞车的 T7-03。
- `bet-ledger.py claim-check BET-Y1Q4-T7-06` 崩溃：`KeyError: 'T7-COOPERATION'`
 （tracks 缺该 track 定义）→ ledger 工具 bug，已避开，待修。
- `claim` 需先跑 `bin/gac/affected-graph.py --changed-projects domain-cartridges workspace-root`
  取 receipt 再 `--affected-hash`；且 `docs-agent` 不在 bet-execution roles，
  用 `engineering-agent`。
- stale lifecycle-lock（空目录，前会话 SIGKILL 残留）+ 已建 worktree：先 release
  + rmdir lock + 删分支再重 claim；`SKIP_SUBMODULE_INIT=1` 快速路径可用
  （子模块慢 clone 下 claim 超时——本 run 实测 worktree 建成但守卫超时）。

## 交付后记（successor replay）

- 首提案 commit `9196d0a9`（base db42d0e9）submit 时 origin/main 已前进 3 commits
 （#3699 T7-06 done、#3700/#3702 子模块指针同步）→ proposal-only exit 2。
- 按指引做 distinct successor：`agent/governance-agent/bet-y2q2-t7-03-r2`
  @ 新 tip + `cherry-pick -n` 首提案 → ledger 自动合流（零冲突：双方 hunk
  不交叠；我方含 T7-03 binding+verify 修，对方含 T7-06 done，两边俱在）。
- 原分支保留为提案记录，未 rebase。
