---
title: 运维基础设施与双平面治理 · 派工指令
status: draft
type: agent-dispatch-brief
owner: 夏明星
created: 2026-08-17
lifecycle: plan
builds-on:
  - docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md（本指令的分析依据，接手前必读）
  - docs/STRATEGY-CONVERGENCE-MASTER-2026-08.md
  - docs/architecture/wave-gate-bet-map.md
  - .omo/_knowledge/retros/BET-Y1Q1-T6-01.md
  - .omo/_knowledge/retros/BET-Y1Q1-T6-02.md
track: T6-SUBTRACT（exclusive，认领前先 `python3 bin/plan/bet-ledger.py status` 确认没有其他 T6 bet 在跑）
---

# 给接手 Agent 的话（先读，再动手）

这一轮延续 T6-01/T6-02 的方法论，但工作对象不一样：**这次要核实的东西，一部分在 git 仓库里，一部分只存在于宿主机本机（`~/.hermes/`、真实 `crontab -l`、`~/Library/LaunchAgents/`）**。如果你是在云端沙箱/隔离容器里跑的 Agent，只能碰到挂载进来的 Workspace 仓库，**碰不到宿主机本机的这三处路径**——这一点在《OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md》起草时已经验证过一次（云端沙箱访问这些路径会直接报"No such file or directory"/"Permission denied"，不是它们不存在，是够不着）。**任务 1-3 里涉及宿主机核实的部分，必须由能直接操作这台 Mac 终端的 Agent 或人类本人来做**；如果你只有仓库访问权限，请只做仓库侧能核实的部分（比如脚本文件是否存在），host 侧的部分明确标注"需要本机终端权限，本轮未核实"，不要编造结果。

这四项任务优先级不同，`appetite` 各自独立，建议拆成 3-4 个独立 bet，不要合并。

---

# 任务 1（最高优先级）：核实 MOF E-DOC-001~005 的真实生效状态

**背景**：`docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md` §1.3 发现，材料没有说清楚 E-DOC-001~005 这五条 Documents 边界约束规则，究竟是"已经在 ADR-0190（MOF Dynamic Constraint Governance，已确认真实合入 main，PR #1626）落地的规则集里强制生效"，还是"仍是设计阶段、尚未接线"。

**要做的事**：
1. 找到 ADR-0190 落地的那批规则的实际注册位置（大概率在 `.omo/_truth/registry/` 下某个 governance-checks 或类似的 yaml 里，具体路径需要你自己核实，不要假设）。
2. 逐条核对 E-DOC-001（禁止在 Documents 创建可执行脚本）、E-DOC-002（Documents 只读工具集）、E-DOC-003（防逃逸脚本执行）、E-DOC-004（事实保鲜门禁）、E-DOC-005（BOS 单一入口）这五条规则，是否每一条都能在实际规则文件里找到对应的、真正会被 CI/Agent Preflight 拦截的实现（不是只在某份 Markdown 里描述过）。
3. 如果找不到对应实现，**不要假装它存在**，如实记录"设计阶段，未接线"。
4. 如果找到了，尝试构造一个最小的违规样本（比如在 Documents 侧的一个测试子目录里试着放一个 `.py` 文件，走一遍会不会被拦截——注意这一步要在隔离环境/沙箱里做，不要在真实 Documents 目录里实测，避免污染真实文件）。

**done_when**：产出一份核实报告（建议放在 `.omo/_knowledge/audits/` 下），逐条列出 E-DOC-001~005 各自的真实状态（已强制/部分接线/仅设计），附证据（规则文件路径或"未找到"的搜索记录）。**这个 bet 不要求把未接线的规则补齐实现**——那是下一轮的事，这一轮只要求把"设计 vs 事实"这条线画清楚。

---

# 任务 2：核实并修复 §1.2 发现的三处调度重叠

**背景**：蓝图 §1.2 发现三处具体重叠，需要逐一到宿主机上核实：

1. **治理审计三重复**：Hermes cron 07:00「omo-governance-audit」+ 宿主机 crontab 09:05/09:10「governance-evolution.py status/packages」+ launchd `com.omostation.governance-scanner.plist`（每小时）——三者是否真的在做同一件事、产出是否冲突过。
2. **漂移检测两重复**：Hermes cron 05:00「omo-drift-detection」+ 宿主机 crontab 周一 10:05「`bin/mof-drift`」——检查两者的检测范围是否完全重叠还是各有侧重。
3. **`bin/gac/cron-daily-dashboard.sh` 疑似缺失**：宿主机 crontab 08:30 声称在跑这个脚本生成 GaC 治理快照，但云端这边核实仓库里**没有这个文件**。**这一条请优先核实**——如果脚本真的不存在，这条每日节奏可能已经静默失败了一段时间，需要确认宿主机上这个 cron job 最近的执行日志/退出码，看看失败了多久、有没有人发现过。

**done_when**：三项各自产出"实测结论 + 处理建议"。第 3 项如果确认脚本确实缺失且任务确实在失败，需要额外标注"这条静默失败从什么时候开始"（如果 crontab 日志能查到的话），并给出是补回脚本还是移除这条 cron job 的建议——**不要求你直接决定并执行，写清楚现状交给人类判断即可**。

---

# 任务 3：产出「Hermes 治理边界声明」

**背景**：蓝图 §2.2 指出 Hermes 的 12 个内置任务完全脱离 Workspace 的 ADR-0203/bet-ledger 治理框架，没有任何机制约束或记录它的变更。

**要做的事**：不要求把 Hermes 12 个任务全部收编进 BET 台账（那是过度设计），只要求产出一份简短、明确的边界声明文档，回答三个问题：
1. Hermes 由谁负责维护（如果答案是"就是这台机器上装的，没人专门管"，如实写出来，这也是一种真实状态）；
2. Hermes 任务如果失败或被静默禁用，有没有任何告警机制会让人知道（如果没有，如实写出来）；
3. 以后如果要新增/修改 Hermes 任务，需不需要走审批（建议至少要求：涉及会写 Workspace 仓库文件的 Hermes 任务，变更前要过一次 grill 或至少知会一声；纯本机运维类的任务不强制）。

**done_when**：产出 `docs/operations/hermes-governance-boundary.md`（或类似路径，具体位置你可以按仓库惯例调整），三个问题都有明确答案，不留"待定"。

---

# 任务 4（优先级最低，可以往后排）：单机灾难恢复清单

**背景**：蓝图 §2.1 指出，launchd/crontab/Hermes 三套调度系统全部单点绑定在这台 Mac 上，ADR-0247 已经明确物理多机 deferred，但目前没有任何"这台机器彻底不可用时会丢什么"的盘点。

**要做的事**：列一份清单——如果这台 Mac 硬盘明天彻底损坏，以下几类东西各自有没有异地备份/能不能重建：
- Hermes 的调度定义（`~/.hermes/` 下的配置）
- crontab 的定义（`crontab -l` 的内容本身）
- launchd 的 23 个 plist 文件
- 本地跑着但没同步到任何 git 仓库的运行时状态（如果有的话）

**done_when**：产出一份清单，每一类标注"有备份/无备份，若无备份的恢复难度"，**不要求这一轮就把备份做好**，只要求把风险敞口写清楚，供后续排期。

---

# 执行方式（复用 T6-01/T6-02 已验证流程）

```bash
# 0. 先确认 T6 轨道没人在跑
python3 bin/plan/bet-ledger.py status

# 1. 登记新 bet（建议 BET-Y1Q1-T6-03 起，任务 1/2/3/4 各自独立登记，appetite 参考：
#    任务1 = 3天，任务2 = 2天，任务3 = 1天，任务4 = 2天）

# 2. 认领隔离 worktree
bash bin/gac/gac-worktree.sh claim <bet-id 小写>

# 3. 起 workflow，必须带 --bet（T6-02 上线的硬门禁）
uv run --with pyyaml python bin/agent-workflow.py start governance-state-mutation \
  --profile governance-agent --bet <BET-ID> \
  --objective "<对应任务的一句话目标>"

# 4. claim 写面、执行，每写完一个文件立刻 git add（D0）

# 5. 收尾：verify + agent-workflow verify + closeout，
#    确认 PR 真的 merge 到 origin/main 再把台账置 done（T6-01 的教训）
python3 bin/plan/bet-ledger.py verify <BET-ID> --execute
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# 6. 写复盘（.omo/_knowledge/retros/<BET-ID>.md），Q1-Q5 + 打假一段，格式照抄 T6-01/T6-02

# 7. tag 并确认真的推到了 origin（T6-02 吃过的亏）
git push origin <tag>
git ls-remote --tags origin | grep <bet-id>

# 8. 提交
bash bin/gac/gac-worktree.sh submit <bet-id 小写>
```

# 非目标

- 任务 1-4 都不要求"顺手把发现的问题都修好"——这一轮的产出是**核实报告 + 处理建议**，不是全量修复。修复是否要做、什么时候做，交给人类看完报告后再排期。
- 不要在没有本机终端权限的前提下，编造 Hermes/crontab/launchd 的"核实结果"——没权限就如实写"未核实"，这正是这套治理体系最看重的一条纪律。
- 不要新开第五套编号或第二套台账，所有发现和结论都落在现有的 BET/retro/audits 体系里。
