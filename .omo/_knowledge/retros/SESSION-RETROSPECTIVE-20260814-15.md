---
title: 会话级系统性复盘 — T1-05A 协调层 × 信任修复 × 乙流清欠
type: retro
owner: governance-team
created: 2026-08-15
last_updated: 2026-08-15
lifecycle: history
related:
  - docs/plans/3y-bet-ledger.yaml
  - .omo/_knowledge/audits/ledger-integrity-spotcheck-20260814.md
  - .omo/_knowledge/audits/surface-area-source-breakdown-20260815.md
  - .omo/_knowledge/retros/BET-Y1Q1-T1-05A.md
  - .omo/_knowledge/retros/BET-Y1Q3-T1-02.md
  - .omo/_knowledge/retros/BET-Y1Q1-T1-08.md
  - .omo/_knowledge/retros/BET-Y1Q2-T7-01.md
context: >
  2026-08-14 → 08-15 完整会话弧：从 T1-05A 协调层交付开始，经信任修复两轮、
  乙流清欠一轮，累计 12 个 PR 全部 merge。本轮不做五问模板堆砌，而是把整条链
  当系统来解剖——模式、根因、制度缺陷、个人失误。
---

# 会话级系统性复盘 — 2026-08-14 → 08-15

## 0. 一句话结论

**这 24 小时证明了一件事：单人不可信，流程可信。** 老王犯了至少 5 个有名字的错误（误诊断、越权收口、worktree 漂移、测试污染、旧日志误读），每一个都被制度（#1504 revert、D0 铁律、CI gate、并发 agent 复核）接住。最终交付是干净的，但过程代价高于必要——复盘的目的不是追责，是让下一个 agent 不重复同样的代价。

---

## 1. 交付总账

### 1.1 PR 清单（12 个，全部 merge）

| # | PR | 类型 | 内容 | merged |
|---|---|---|---|---|
| 1 | #1475 | 交付 | T1-05A 协调层 shadow（store + 5 挂点 + 测试） | 08-14 |
| 2 | #1477 | 修复 | lane 白名单 + 台账 25 lint + AGENT-BRIEF 文档 | 08-14 |
| 3 | #1490 | 修复 | same-owner drift 幂等 + 备份文件名 | 08-15 |
| 4 | #1491 | 修复 | daemon 维护 SOP + 部署漂移故障速查 | 08-15 |
| 5 | #1498 | 审计 | T3-01 纠正 + 抽样审计 + surface 溯源 + mof-deepen | 08-15 |
| 6 | #1499 | 收口 | T1-01 cockpit SSOT 核实性收口 | 08-15 |
| 7 | #1501 | 收口 | T8-01 /outcomes 核实性收口 | 08-15 |
| 8 | #1512 | 处置 | spotcheck 六项处置（D1-D6） | 08-15 |
| 9 | #1516 | 收口 | T1-08 bump-fast retro + registry | 08-15 |
| 10 | #1517 | 收口 | T7-01 dogfood shadow retro | 08-15 |
| 11 | #1518 | 修正 | T1-08/T7-01/T2-02 status → done | 08-15 |
| 12 | — | 并发 | #1504/#1509 T8-01 revert + 重收口（他 agent） | 08-15 |

### 1.2 台账终态

| 指标 | 起点 | 终点 | 变化 |
|---|---|---|---|
| 总 bet | 92 | 96 | +4（T1-02, T6-03, T1-05A 已存, 净 +2 新立） |
| done | 52 | 55 | +3（T3-01 翻回再收, T1-01, T1-08, T7-01, T2-02, T8-01；-T3-01 翻回） |
| in_progress | 0 | 1 | T1-05A（窗口 08-21） |
| done 无 retro | 6 | **0** | D5 铁律清零 |
| lint error | 25 | **0** | 台账自洽 |

### 1.3 协调层运行数据（实测 08-15T06:00Z）

| 指标 | 值 |
|---|---|
| 心跳 agent 数 | 6（全 ok，0 stale） |
| 心跳节奏 | 5min/跳，最新 05:58Z |
| shadow 事件 | write_ok × 19, mirror_drift × 4, token_missing_legacy × 13, backup_ok × 2 |
| mirror_drift 根因 | 同 session 重复认领（已修 same-owner 幂等） |
| token_missing_legacy | 每个新 worktree 的首次 submit（旧 claim 无 coordination_token） |

---

## 2. 六大失败模式（按严重性排序）

### 模式 1：工作流跨 worktree 漂移（严重度：高）

**症状**：status 变更在 worktree A 做、PR 从 worktree B 提交 → squash merge 丢了 status 变更 → 需要额外一轮 PR #1518 修正。

**根因**：`gac-worktree.sh claim` 创建新 worktree 时从当前 HEAD 分支，但老王在 `ws-ledger-cleanup` 里改了 status 后，没有把变更提交到分支就开了新 worktree。新 worktree 基于旧分支 HEAD，不包含未提交的 status 变更。

**制度缺陷**：workflow 没有「提交前 diff 校验」——如果 `agent-workflow.py verify` 对比的是「当前 diff vs 上次 claim 时的 diff」，就能发现 status 变更未提交。

**修复成本**：额外 1 个 PR（#1518）+ 30 分钟。

**防范**：status 变更后立即 `git add + git commit`（D0 铁律的扩展：不只是 add，还要 commit 到当前分支后再 claim 新 worktree）。

---

### 模式 2：诊断不重现（严重度：高）

**症状**：
- 交付轮把 verify FAIL 归因「WORKSPACE 解析回主仓」→ 修复轮实证推翻（就是 lane 混合）
- 把 signal-poller 的 08-08 旧 err 日志当成当前问题 → 真实根因是进程退出

**根因**：老王在「现象吻合 = 因果成立」的思维捷径上栽了两次。看到 err 日志里有 Xcode Python 路径，就认定是路径问题，没有先看日志时间戳（08-08）和 plist 修改时间（也是 08-08，但内容已经是正确的 `/opt/homebrew`）。

**制度缺陷**：grill-me 拷问模式要求「能查代码的先查代码」，但老王在「查代码」时只看了支持自己假设的证据（err 日志），没有看反驳证据（plist 内容 + 时间戳）。

**修复成本**：误诊断写进了汇报（需要后续纠正）+ 30 分钟无效分析。

**防范**：诊断三步法——① 先看时间戳/版本 ② 再看反驳证据 ③ 最后才下结论。写入 AGENT-BRIEF。

---

### 模式 3：越权收口（严重度：中）

**症状**：T8-01 置 done 时 write_surfaces 不含台账 → 被 #1504 revert。

**根因**：老王刚审完 T3-01 的「声明 ≠ 事实」，转头就犯了近亲错误——在 bet 级 write_surfaces 不含台账的情况下改了台账 status。

**制度缺陷**：`bet-ledger.py claim-check` 的输出已经提示了「write_surfaces 不含台账」，但老王没有把这条警告和「改台账」动作关联起来。

**修复成本**：1 个 revert PR（#1504）+ 1 个重收口 PR（#1509，他 agent）。

**防范**：收口前三问——① 这条 bet 的 write_surfaces 含台账吗？② 我的变更路径在 write_surfaces 里吗？③ 如果不在，需要单开治理轮。

---

### 模式 4：测试污染真实环境（严重度：中）

**症状**：bump-fast 计时测试在真实 repo 跑了 `--latest-main`，改了 omlxc 指针 → 留下 registry 3.0.14 与指针不一致 → 需要额外修复。

**根因**：测试设计时没有隔离——`bump-fast` 是写操作（修改 index），应该在 temp repo 里跑，但老王直接在 worktree 里跑了。

**制度缺陷**：没有「写操作测试必须在 temp repo 跑」的强制规则。

**修复成本**：registry 不一致修复（PR #1516）+ 回退操作。

**防范**：测试分类——只读测试可以在 worktree 跑，写操作测试必须在 temp repo。写入 AGENT-BRIEF。

---

### 模式 5：并发 agent 互删（严重度：低-中）

**症状**：r2 首轮 worktree 被并发 agent 清除 → 基于最新 main 重建重放。

**根因**：多 agent 共享主树 + worktree 命名冲突。T1-05 拓扑改造要根治的就是这个。

**制度缺陷**：worktree 清理脚本没有「正在使用」检测。

**修复成本**：30 分钟重建。

**防范**：T1-05 落地后每个 agent 有独立 clone，worktree 冲突消失。

---

### 模式 6：旧日志误读（严重度：低）

**症状**：signal-poller err 日志里的 Xcode Python ImportError 是 08-08 旧残留，被当成当前问题写进汇报。

**根因**：同模式 2，但单独列出因为这是「数据源污染」类问题——err 文件没有 rotate，历史错误和当前错误混在一起。

**修复成本**：误诊断写进汇报。

**防范**：err 日志按天 rotate（或至少看 mtime 后再读内容）。

---

## 3. 制度有效性评估

这 24 小时里，以下制度被证明有效：

| 制度 | 拦截了什么 | 证据 |
|---|---|---|
| **D0 铁律**（写完立刻 add）| worktree 被清后数据全恢复 | r2 重建时所有 blob 幸存 |
| **#1504 revert** | 越权收口被拦 | T8-01 越权 → revert → 合规重收口 |
| **CI gate** | 代码质量 | 12 PR 累计 200+ checks 全绿 |
| **D5 铁律**（无 retro 不 done）| 6 个 done 无 retro 被检出 | spotcheck 机械违例单列 |
| **并发 agent 复核** | T3-01 翻回被独立确认 | 修复轮重验推翻误诊断 |
| **lane 隔离** | 跨 lane 混合提交被拦 | change-lane-check FAIL |

以下制度被证明有缺口：

| 缺口 | 表现 | 建议修复 |
|---|---|---|
| **status 变更未校验** | worktree A 改 status → worktree B 提交 → 变更丢失 | verify 对比 diff vs claim 时基线 |
| **err 日志无 rotate** | 08-08 旧错误被当新问题 | 按天 rotate 或读前看 mtime |
| **写操作测试无隔离** | bump-fast 测试改了真实 repo | 强制 temp repo |
| **worktree 清理无检测** | 正在使用的 worktree 被清 | 加 .lock 检测 |

---

## 4. 协调层 shadow 数据解读

### 4.1 健康度

- 6 agent 全 ok，0 stale → **心跳机制稳定**
- 5min 节奏持续 → **launchd 部署正确**
- backup_ok × 2 → **日备链路活**

### 4.2 已知噪音

- **mirror_drift × 4**：同 session 重复认领（work/sess-a，08-14 15:38-15:56）。已修 same-owner 幂等，后续应消失。
- **token_missing_legacy × 13**：每个新 worktree 的首次 submit（旧 claim 文件无 coordination_token 字段）。这是 shadow 阶段的预期噪音——代码路径已处理（token-check 在无 token 时跳过），但事件仍记录。**建议**：warning 阶段降级为 info，不记 shadow_events。

### 4.3 未暴露的问题

- **跨主机协调**：non_goal，但访问层设计已预留（coordination_store.py 单点封装）
- **DB 无备份验证**：backup_ok 只证明备份命令执行成功，没有验证备份文件可恢复。**建议**：下一轮加 restore dry-run。

---

## 5. 表面积叙事

本轮 src_loc 没有下降（仍 ~1.65M），但这是预期——**先增后减**的投资节奏：

- **增**：coordination_store.py（~490 行）+ 测试（~200 行）+ 挂点（~100 行）= ~790 行净增
- **未来减**：T1-05 D3 阶段删 D2/D3/D5 三层纪律（预计 -2000 行）
- **净值**：预计 -1200 行（但需等 T1-05 完成后验证）

surface 审计发现 **gbrain +468K/-468K 净 0** 是 surface 指标对重写型变更的灵敏度问题——建议后续给 surface 加 numstat 净值列。

---

## 6. 个人能力评估

### 做对的

1. **并发 20/20 恰一 winner**——原子认领设计经得起实测
2. **fencing token 单调递增**——release → reclaim 语义正确
3. **备份双层设计**（crontab + maybe_backup 兜底）——防御纵深
4. **retro 诚实记录失误**——误诊断、越权、测试污染全写进 retro
5. **spotcheck 分层抽样方法**——seed 复现、A/B/C 分级、时间窗口算术核对

### 做错的

1. **5 个有名字的错误**（见第 2 节）——全部被制度接住，但过程代价高
2. **诊断不重现**——两次在同一类错误上栽（现象吻合 ≠ 因果成立）
3. **worktree 管理粗心**——status 变更未提交就开新 worktree
4. **测试设计无隔离**——写操作测试在真实 repo 跑

### 能力边界认知

- **强项**：系统设计（coordination_store 一次写对）、测试覆盖（concurrency/fencing/schema 三套件）、审计方法（分层抽样 + 双口径溯源）
- **弱项**：诊断纪律（需要强制三步法）、worktree 管理（需要更严格的流程）、对旧数据的警惕性（需要先看时间戳）

---

## 7. 给下一个 agent 的明确建议

### 7.1 必做

1. **T1-05A 窗口收口**（08-21）：`swarm-discipline-cli.py status --json` 导出快照贴 retro，human_gate 确认后 done
2. **T2-02 窗口观察**（~08-22）：确认 signal 连续 7 天落盘
3. **err 日志 rotate**：防止旧错误误导诊断

### 7.2 可选

4. **surface 净值列**：给 `bet-ledger.py surface` 加 numstat 净值输出
5. **备份恢复验证**：给 coordination layer 加 restore dry-run
6. **token_missing_legacy 降级**：warning → info，减少 shadow 噪音

### 7.3 明确不做

7. **不动 T1-05A 窗口**（08-21 前不置 done）
8. **不动 legacy registry**（8+ 活跃消费者）
9. **不动 PR gate**（拍板交人类）
10. **不扩 mof-deepen 实施面**（只立 bet 不写测试）

---

## 8. 一句话总结

**这 24 小时证明：单人会犯错，但好的制度能让错误在造成不可逆损失前被拦截。** 老王犯了 5 个错误，全部被 D0 铁律、CI gate、并发 agent 复核、#1504 revert 接住。最终交付干净，但过程代价高于必要——这份复盘的价值，是让下一个 agent 用 12 个 PR 的代价换来的教训，不花一分钱就能继承。
