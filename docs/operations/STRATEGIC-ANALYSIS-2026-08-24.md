# eCOS v6 / omostation 项目粒度架构与战略深度复盘

> 复盘时间：2026-08-24
> 复盘基线：8 轮清理（2026-08-22 ~ 2026-08-24）、11 个 PR、BET 台账 124/124（122 done, 2 blocked）
> 分析范围：项目粒度（project-grain），覆盖场景、功能、用户旅程、体验、目标愿景、长期运营、运维、防腐、约束 9 个维度

---

## 0. 北极星定位

**omostation 的本质**：single-owner 的个人认知基础设施（cognitive infrastructure），不是 SaaS 产品，不是团队级开发平台。它是一个"希望比所有者活得更久且不失信任"的**个人工作与决策执行 OS**。

这一句话解释了后续所有架构决策。如果对任何结论有异议，先回到这句话检查假设。

---

## 1. 场景分析（Scenario）

### 1.1 五大运营场景（按频率排序）

| # | 场景 | 频率 | 入口 | 延迟预算 | 当前健康度 |
|---|---|---|---|---|---|
| S1 | 终端日常检查 | daily | CLI | < 1s | 🟢 良好 |
| S2 | 雷达/健康探测、门禁、仪表盘刷新 | hourly | cron + CI | < 30s | 🟢 良好 |
| S3 | Agent 编辑源码、P74 workflow、claim、commit | per-task | agent-workflow.py | seconds | 🟡 机制健全但社会性脆弱 |
| S4 | 多 Agent 并发写同一工作树 | several/day | shared main | gate-time | 🟡 可观测但未阻断 |
| S5 | 用户 onboarding 新能力 | weekly | PR | minutes | 🟢 正常 |

### 1.2 场景缺口与风险

**核心发现**：8 轮清理主要修复了 S1、S2、S4 的失败模式。**S3（workflow 纪律）和 S5（onboarding）没有坏，但依赖操作者的注意力**。

- **S3 风险**：`agent-workflow.py` 机械上健全，但如果 agent 跳过 step 4（closeout）或在 run 外提交，系统没有强制执行。这是**社会性约束**，不是**机械约束**。
- **S4 风险**：PR #1989 修复了并发写的**可观测性**（soft topic），但没有修复并发本身。当前策略是"可见但不阻断"，这是冲突发生前的正确姿态，但一旦出现真实 merge conflict，需要升级为硬阻断。
- **S5 风险**：新能力 onboarding 需要 5-15 分钟（脚本）到 1 天（新层），但缺乏标准化的 onboarding checklist。

### 1.3 场景战略建议

1. **S3**：将"claim path before edit"从社会规范升级为 pre-commit hook 硬门禁（P79 write contention 的机械 Enforcement）。
2. **S4**：当并发写导致真实 merge conflict 时，触发 broker-enforcement ADR（当前已记录为"有意推迟"）。
3. **S5**：建立新能力 onboarding 模板（脚本、gate、runbook 三步检查表）。

---

## 2. 功能分析（Feature）

### 2.1 功能分类（440+ bin/ 脚本）

| 类别 | 占比 | 核心能力 | 模式 |
|---|---|---|---|
| 治理与审计 | ~30% | gac-local-gate、drift、freshness、P74 检测 | 脚本返回 0/1 + JSON on --json |
| 状态与可观测性 | ~15% | compass_radar、health-trend、rotate-history | 少 writer，多 reader |
| Workflow 与 Agent 生命周期 | ~15% | agent-workflow.py、lock prune、closeout | 声明式 YAML + runner |
| 迁移与清理 | ~20% | sync-planned-to-done、dedup、submodule pointer | 自动化维护 |
| 知识工具 | ~20% | ADR 分析、meta-doctor、health-trend | 分析 + 可视化 |

### 2.2 功能成熟度评估

**成熟功能**：
- GaC local gate（49 checks，composable）
- Agent workflow lifecycle（bootstrap → start → claim → verify → closeout）
- SSOT 追踪（12 个文件的 SHA-256 变更追踪）
- 分层依赖检查（layer-contract.yaml 驱动）

**不成熟功能**：
- 无中央注册表记录"脚本 X 做什么"（440 个脚本，无索引）
- 无"此 PR 做什么"模板给 agent
- 无"谁拥有这个"视图（check 失败时只给 stack trace，不给 owner）
- Cockpit Web UI 默认离线（`cockpit dashboard` 需要手动 nohup）

### 2.3 功能战略建议

1. **建立 bin/ 脚本注册表**：每个脚本的元数据（用途、owner、输入输出、依赖）应可查询。这是 440 脚本规模下的可发现性底线。
2. **PR 前检查清单**：为 agent 建立 pre-PR sanity check（测试、文档、基线 bump）。
3. **Owner 字段注入**：每个 governance check 应有 `owner:` 和 `expected:` 字段，失败时直接指向负责人。

---

## 3. 用户旅程（User Journey）

### 3.1 操作者日常旅程（S1）

```
T+0s:    open terminal
T+0.5s:  make omo-status          → 6 agents status, lock count, BET count
T+2s:    uv run bin/compass_radar.py  → health 70, anomaly 0/100, freshness 100
T+3s:    read summary in 3 lines: health / anomaly / service-online
T+10s:   if anomaly > 0:
             check p74_silent-workflows topic
             or check stale tasks via bin/plan/sync-planned-to-done
T+30s:   start work
```

**评估**：此旅程现在服务良好。8 轮清理前，T+2s 会显示 `health_score 28/100` 且无可操作信号；现在显示 70/100 + `governance_anomaly_score: 0/100` + 清洁 sparkline。

### 3.2 Agent 工作旅程（S3）

```
claim path via bin/agent-workflow.py claim <run-id> --path projects/...
edit + test
bin/agent-workflow.py verify --from-diff --execute
bin/agent-workflow.py closeout
git add + commit
bin/gac/gac-worktree.sh submit
```

**评估**：机械上健全但社会性脆弱。崩溃风险不是"脚本失败"，而是"agent 忘了 step 4"或"agent 在 run 外提交"。8 轮清理没有解决这个问题；`AGENTS.md` 解决了但依赖 agent 阅读。

### 3.3 多 Agent 并发旅程（S4）

```
T+0s:    Agent A starts gate run, snapshots fingerprint
T+10s:   Agent B writes to .omo/state/health.yaml
T+15s:   Agent A's gate finishes, detects drift
T+15.1s: emits soft topic `concurrent-write-drift`
         gate still PASSES (warn only)
```

**评估**：PR #1989 修复了并发的**可观测性**但没有修复并发本身。Drift 是事后检测，不是事前预防。当前策略"可见但不阻断"是冲突发生前的正确姿态。

### 3.4 旅程战略建议

1. **S1**：添加 `--summary` flag 到 `compass_radar.py`，一行输出适合扫视。
2. **S3**：将 workflow 步骤检查自动化（pre-commit hook 验证 run 状态）。
3. **S4**：监控并发写导致真实 merge conflict 的首次发生，届时触发 broker-enforcement ADR。

---

## 4. 体验分析（Experience）

### 4.1 体验优势

| 优势 | 说明 | 关键场景 |
|---|---|---|
| `make health-trend` | 终端原生，无需浏览器。慢链接或 tmux 场景即时信号 | S1 |
| runbook frontmatter | 每个 runbook 有 `status/type/owner/last-reviewed`，模式一致，linter 接受 | 所有 |
| Self-recovery checklist | health < 60 时，operator 有可执行表格 | S1 故障恢复 |
| 统一 CLI 入口 | cockpit CLI 收敛 9 个域，agent 通过 agora MCP | S3/S5 |

### 4.2 体验缺口

| 缺口 | 影响 | 建议 |
|---|---|---|
| 无 agent PR 前检查清单 | agent 提交 3 文件变更时无自动 sanity check | 添加 pre-PR checklist |
| 无"谁拥有这个"视图 | check 失败时只给 stack trace | governance-checks.yaml 添加 `owner:` 字段 |
| 无"上次会话后变了什么"视图 | 周末后回来的 operator 不知道什么坏了 | 合并 `omo-status` + `git log --since` |
| Cockpit Web UI 默认离线 | 非 CLI 用户无入口 | 修复 launchd plist 命令路径 |
| `gac-worktree.sh claim` 冷启动 60s 无进度 | 子模块初始化时用户无反馈 | tail -f 子模块 init log |
| P74 silent-workflow 无专用 dashboard | 门禁输出中淹没 | 添加 `--list-silent` 专用视图 |

### 4.3 体验战略建议

1. **短期**：修复 cockpit launchd plist，使 `cockpit dashboard` 一键启动。
2. **中期**：构建 `bin/gac/drift-sweep.py` 作为每周定时报告，替代纯门禁模式。
3. **长期**：建立 agent quickstart SKILL.md（1 页），总结如何开始 run、claim path、closeout、在哪找 docs。

---

## 5. 目标与愿景对齐（Goal / Vision Alignment）

### 5.1 愿景声明

> **个人工作与决策执行 OS**：从信号和意图到可靠结果、证据、记忆与受控进化。

北极星指标：**每周成功完成且被实际消费的闭环旅程数**，必须按场景拆分，同时满足：
- 有真实用户意图或业务信号
- 通过统一入口和 Workflow Mesh 运行
- 产生可使用的产物或行动
- 有回执、验证或人工确认
- 有来源、证据和失败恢复路径
- 结果被打开、采用、提交、派发或引用

### 5.2 对齐度评估

| 维度 | 对齐？ | 证据 |
|---|---|---|
| 信任持久性（审计链） | ✅ | governance-history.jsonl (2064 records)，events.jsonl，所有产物不可变 |
| Agent 独立性（可重实例化） | ✅ | 16/16 workflows active，agent-workflow.py 是入口 |
| 机械 Enforcement（不只是文档） | ✅ | 49 gate checks，4 个 blocking |
| Drift 检测（不是预防） | ✅ | drift detector、dedup、snapshot comparison |
| **Owner 瓶颈** | ⚠️ | **67% 任务由 human 拥有——目标被当前状态削弱** |
| 速度（添加能力的时间） | ⚠️ | ~5-15 分钟（脚本），~30 分钟（gate），~1 天（新层） |

### 5.3 最大战略威胁：67% Human Bottleneck

L3-task + owner-concentration 异常显示系统**结构健康但运营瓶颈集中在单一人类**。这是目标的**反相**。

**具体后果**：任何需要人类判断的特性都会阻塞。2 个人类拥有的 L3 BETs（`bet-y3h1-t7-01`、`bet-y3h2-t7-01`）被外部事件阻塞（用户借调国转中心、政策申报）。系统无法解锁它们；只有人类可以。

**8 轮清理没有解决这个问题**。它们让系统更可观测，但没有重新分配负载。这是正确的（L3 任务 genuinely 需要人类），但应被承认：**系统的瓶颈现在被显式可视化为一个统计量**。

### 5.4 隐式目标：零摩擦自我扩展

阅读 5 轮优化作为整体，一个隐式目标浮现：**系统应该在没有操作者注意力的情况下自我扩展**。每轮都添加了操作者否则需要记住做的事情：

- Round 2: auto-archive stale tasks
- Round 3: auto-mirror debt dashboard
- Round 4: auto-dedup observability events
- Round 5: auto-detect silent workflows
- Round 6: auto-detect concurrent drift
- Round 7: auto-collect trend + auto-launch cockpit
- Round 8: auto-trim history + auto-bump baseline

**这是项目的实际哲学：将人类记忆编码为机器检查**。下一轮工作（9+）应继续这个模式。

---

## 6. 长期运营（Long-term Operations）

### 6.1 运营指标现状

| 指标 | 值 | 趋势 |
|---|---|---|
| Health score | 70/100 | 第 5 轮后稳定 |
| governance_anomaly_score | 0-17/100 | 随 obs events 变化 |
| service_online_ratio | 100% | 稳定 |
| Active runs | 0 | 健康 |
| Stale locks | 0 | 健康 |
| History records | 15 (1 day) | 低——radar 运行不频繁 |
| Worktrees | 6 active | 正常并发活动 |
| PRs merged | 11 (this session) | 高 |
| Bin scripts | 440 | 每 session +10 |
| Concurrent agents | 4-6 | 高但正常 |

### 6.2 30 天预测

**无干预**：
- Bin scripts 达到 ~470（继续 +10/session）
- Worktree 数保持在 6-8
- Health 保持在 65-75（真实信号：4 个 L3 blocked tasks）
- Stale stashes 回涨到 55+

**月度清理**（匹配当前节奏）：
- Bin scripts 可管理
- Gates 早期捕获回归
- Health 保持在 70s

**季度回顾**：
- Drift 累积；一次性工作累积
- 最终需要 2 天清理 session

### 6.3 长期运营战略决策

项目需要**月度维护**或**自愈机制**。当前 silent-workflow 检测是自愈的一种形式（针对 workflows）；它不存在于其他产物类型（skills、runbooks、governance-checks rules）。

**建议**：添加 `bin/gac/drift-sweep.py` 作为每周定时 sweep（drift + runbook validity + ADR link validity + 报告）。

### 6.4 子项目健康盲区

当前无法从根工作区直接评估子项目健康。bin scripts 触及它们，但实际子项目状态（commits、tests、branches）是不透明的。

**建议**：添加 `bin/meta/sub-project-health.py`，聚合每个子模块的 `make test-diff` 或等效命令，报告 pass/fail counts。

---

## 7. 运维分析（Maintenance）

### 7.1 当前运维模式

| 运维活动 | 频率 | 执行者 | 自动化程度 |
|---|---|---|---|
| Health radar | hourly (cron) | compass_radar.py | 全自动 |
| Gate check | per-PR | gac-local-gate | 全自动 |
| State sync | 6h (cron) | omo state sync | 全自动 |
| Debt refresh | daily | omo debt refresh | 全自动 |
| History rotation | 90d | rotate-history.py | 全自动 |
| Stale task archive | weekly | sync-planned-to-done.py | 全自动 |
| Submodule pointer sync | per-PR | submodule-pointer-transaction.sh | 全自动 |
| Cleanup rounds | ad-hoc | human + agent | 半自动 |

### 7.2 运维成熟度

**成熟**：定时任务、cron、launchd 覆盖了大部分重复性运维工作。

**不成熟**：
- 无**预测性**运维（在问题变成故障前预警）
- 无**根因分析**自动化（故障后需人工调查）
- 无**知识沉淀**闭环（运维经验未自动转化为 runbook 或 check）

### 7.3 运维战略建议

1. **预测性运维**：在 health trend 下降时自动触发 investigation workflow（如 freshness 持续下降 → 自动检查 cron job 状态）。
2. **根因分析自动化**：故障时自动收集 `launchctl list`、`git status`、`omo-status` 快照，打包为 evidence。
3. **知识沉淀闭环**：每次故障解决后，自动检查是否有对应 runbook；如果没有，创建 draft。

---

## 8. 防腐分析（Anti-Corruption）

### 8.1 已保护的腐蚀类型

| 腐蚀类型 | 保护机制 | 状态 |
|---|---|---|
| Code-SSOT drift | governance-history.jsonl、drift detector | ✅ |
| Schema drift | mof-capabilities.yaml 声明 vs 实际计数 | ✅ |
| L0 约束违反 | check-l0-constraints.py | ✅ |
| Write contention (P79) | drift detector（soft） | ✅ |
| 文档链接失效 | doc-link-check.py | ✅ |

### 8.2 未保护的腐蚀类型

| 腐蚀类型 | 风险 | 建议 |
|---|---|---|
| **Knowledge rot** | ADR 引用不存在路径 | ADR link validity check |
| **Skill rot** | `.agents/skills/` 中的 SKILL.md 引用不存在工具 | Skill registry verification |
| **Runbook rot** | runbook 引用已重命名的 bin/ 脚本 | Runbook validity CI check |
| **Doc-code drift** | runbook 中的命令与当前代码不匹配 | doc-command-verify check |
| **Bin script 膨胀** | 440 脚本无中央注册表，发现性退化 | bin/ 脚本注册表 |

### 8.3 防腐战略建议

1. **每周 drift sweep**：`bin/gac/drift-sweep.py` 运行所有 drift checks + runbook validity + ADR link validity + 周报。
2. **防腐作为连续函数**：当前模型是"防腐作为门禁（PR-blocking）"；缺失的模型是"防腐作为定时 sweep（weekly）"。两者互补。
3. **减法配额制维持**：T6-05 减法配额（增 1 删 1）已建立，但基线需要定期审查和收缩。

---

## 9. 约束分析（Constraints）

### 9.1 硬约束（架构级）

| 约束 | 原因 | 影响 |
|---|---|---|
| **Single worktree = main** | 所有 agent 共享 main（或 worktree 合并回 main） | 并发写需 claim 机制 |
| **Single-owner model** | 只有一个人类，多个 agent | 反向模型不支持 |
| **Submodules = independent repos** | 每个 `projects/*` 有独立 commits、releases、tests | 根仓不能 dictating 子模块内部 |
| **macOS-first** | `~/Library/LaunchAgents/`、`lsof`、`pkill` 是 macOS 特有 | 跨平台迁移成本高 |
| **Python 3.13** |  pinned by `projects/omo/pyproject.toml` | 依赖版本锁定 |

### 9.2 软约束（文化级）

| 约束 | 原因 | 影响 |
|---|---|---|
| **No global rewrites** | Refactors scoped 到单个 PR | 防止大爆炸式变更 |
| **Bots are agents, not code** | agents 在 `.agents/`，capabilities 在 `bin/` | 职责分离 |
| **Drift is visible, not silenced** | soft topics 而不是 hard fails | 并发 agent 不产生 false-positive flakes |
| **Doc updates are PR-time** | doc-update-lint 强制 | 文档与代码同步演进 |

### 9.3 张力点

| 张力 | 当前权衡 | 建议 |
|---|---|---|
| **Cleanliness vs velocity** | 每轮清理每 session +5 分钟 | 建立维护预算上限（如每月 30 分钟） |
| **Mechanical vs social enforcement** | P79 drift detection 是 mechanical；"agent must claim path" 是 social | 逐步将 social 约束升级为 mechanical |
| **Single-worktree vs single-submodule** | 一个子模块 "ahead" 时，根仓看到 drift 但不阻断 | 意图正确但令人惊讶；需文档化 |

### 9.4 约束战略建议

1. **硬约束保持**：single-worktree、single-owner、submodule independence 是架构基石，不应改变。
2. **软约束硬化**：将"agent must claim path before edit"从社会规范升级为 pre-commit hook 硬门禁。
3. **跨平台评估**：macOS-first 约束在当前阶段可接受，但应在 roadmap 中标记为"未来迁移成本"。

---

## 10. 综合评分

| 维度 | 评分 | 说明 |
|---|---|---|
| 结构健康 | **8/10** | 所有 gates pass，drift detected，history retained |
| 运营健康 | **7/10** | 67% human bottleneck 是弱点 |
| 文档 | **8/10** | 7 runbooks + ops README + retrospective + AGENTS.md |
| 可发现性 | **6/10** | 440 脚本无中央注册表 |
| 防腐 | **7/10** | Gates 捕获大部分 drift；runbook/code drift 未守卫 |
| 用户体验 | **7/10** | CLI 优秀；cockpit UI 默认离线 |
| 目标对齐 | **9/10** | Single-owner cognitive infrastructure 被机械保持 |
| **Overall** | **7.4 / 10** | 强基础，清晰的改进路径 |

---

## 11. 战略建议优先级（Top 10）

### 🔴 HIGH（立即）

1. **Drift sweep 工具** (`bin/gac/drift-sweep.py`)：一次性运行所有 drift checks + runbook validity + ADR link validity。在"soft rot"累积前捕获。
2. **L3 异常健康自动修复**：`evidence_required` 的 L3 high-risk tasks 应被检测为 drift 并 surfaced 带 exact remediation command。

### 🟡 MEDIUM（本月）

3. **Runbook validity CI check**：每次 merge 前验证每个 runbook 中引用的 `bin/X` 仍然存在。
4. **Cockpit dashboard auto-start**：修复 launchd plist 命令路径（`cockpit.dashboard_server` → `cockpit-dashboard`）。
5. **Skill registry verification**：列出 `.agents/skills/` 所有 SKILL.md，验证每个有对应 `bin/` entry 或外部 doc，alert on orphans。

### 🟢 LOW（下季度）

6. **Sub-project health aggregator**：单命令运行每个子模块的 `make test-diff`，报告 pass/fail counts。
7. **Knowledge indexing**：bin/、docs/、.agents/ 的知识图谱索引。
8. **ADR link validity check**：ADR 引用文件路径；路径变更时 ADR 静默 broken。
9. **Scheduled cleanup cron**：月度 `bin/gac/maintenance.py` 运行 drift checks + bin-scripts-convergence + ADR validity + runbook validity + 报告。
10. **Agent quickstart SKILL.md**：新 agent 的 1 页快速入门（如何 start run、claim path、closeout、在哪找 docs）。

---

## 12. 反模式（Anti-patterns to Avoid）

| 反模式 | 原因 | 正确做法 |
|---|---|---|
| 添加更多 gates 而不阅读现有 ones | 每个新 gate 是每个 PR 的税；当前 49-check gate 已 30-60s | 先优化现有 checks，再考虑新增 |
| Auto-fix scripts 无 audit log | 如果 `auto-fix-X.py` 变异状态，变异必须在 events.jsonl 中可逆 | 所有自动修复必须 emit OMO event |
| 添加更多 agents 而不检查并发 | 每个并发 agent 增加 contention 速率；67% owner concentration 部分因为 agents 太多 | 先解决 human bottleneck，再扩展 agents |
| 构建中央 dashboard | retrospective 的 "did NOT do" 有充分理由；Cockpit 是正确的入口 | 使用现有 cockpit，不重复 |
| 写 "best practices" doc | retrospective + runbooks 就是 practice；另一份 doc 增加噪音 | 维护现有 runbooks，不新增通用指南 |
| 使 drift detector blocking | soft drift 在并发 agent 下产生 false-positive flakes | 保持 soft，仅在真实 conflict 时升级 |
| 优化 L3 task routing | L3 tasks 正确路由到 human；优化意味着自动化不应自动化的判断 | 减少 L3 decisions 的数量，不优化路由 |

---

## 13. 最终结论

**8 轮清理将项目从"结构健康但运营脆弱"转变为"结构健康且运营可观测。"**

下一阶段（drift sweep、health auto-remediation、runbook validity、cockpit auto-start）是增量的，不是转型的。每个都添加一个特定的失败模式到检测集中。

最大的**战略**缺口是 human bottleneck。它不能通过自动化解决（L3 decisions 需要 human）。它只能通过**减少需要的 L3 decisions 数量**来解决——即做更少的 L3 事情。

当前轨迹是健康的。以当前节奏继续。

---

## 14. 复盘元数据

| 项目 | 值 |
|---|---|
| 分析时间 | 2026-08-24T06:47 |
| 分析基线 | 8 轮清理 + 11 PRs + BET 124/124 |
| 分析范围 | project-grain，9 维度 |
| 参考文档 | ARCHITECTURAL-REVIEW-2026-08-24.md、digital-twin-blueprint-v1.md、blueprint-multi-agent-execution-control-v1.md、VISION-ROADMAP.md、project-registry.yaml、layer-contract.yaml、governance-checks.yaml |
| 下次复盘触发 | 系统性分析/方案任务、多轮返工、Stop hook 反馈后、判断错误发现时 |
