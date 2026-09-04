---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
bet: BET-Y1Q3-T10-19
---

# 治理体系现状报告（Governance System Status）

> 日期：2026-09-03（UTC，只读快照）
> run-id：`20260903T060034Z-governance-audit-875927c6`
> profile：`governance-agent`
> bet：`BET-Y1Q3-T10-19`
> worktree：`/Users/xiamingxing/ws-gov-report-0903`，分支 `work/gov-report-0903`
> 作者：scribe（build orchestrator 委派，隔离 worktree 内撰写，未改主仓、未 commit）
> SSOT 指针声明：本报告所有规则/数量均引用 SSOT 指针（路径 + `::key`），不粘贴全量规则；凡涉运行时数字处均已标注“截至 2026-09-03 只读快照”，以区别于 SSOT 稳态契约（详见 Documentation SSOT Contract：`.omo/standards/doc-ssot-contract.md`）。

---

## §1 总览判断

**一句话成熟度判断（截至 2026-09-03 只读快照）：治理体系已达“强门禁 + 可观测 + 沉默治理”成熟态，但价值维（X3）偏薄、能力所有权与脚本基线存在可偿还的接线债。**

| 指标（截至 2026-09-03 只读快照） | 值 | 来源指针 |
|---|---|---|
| 健康分 | 81.7（09-01 快照） | `runtime` 健康看板快照（本报告仅转述快照值，非 SSOT 稳态值） |
| phase | 29 | `.omo/_truth/registry/phase-verdict.yaml`（快照转述） |
| active（进行中治理项） | 0 | 同上（快照转述） |
| SFOP 槽位检查 | ok | `bin/gac/check-sfop-slots.py`（CR-SFOP-01/02，截至 2026-09-03 只读快照） |
| gac-validate | 通过 | `bin/gac/gac-validate.py --gate`（截至 2026-09-03 只读快照） |

> 合规提醒：上表 phase/health/active 均为快照转述，不得作为 SSOT 写入任何 Markdown 契约；运行时真相以 `omo state sync` / `make omo-status` 为准。

---

## §2 X1–X4 四维（截至 2026-09-03 只读快照）

SSOT：`.omo/_truth/x1-governance-policies.yaml`、`x2-freshness-rules.yaml`、`x3-value-stack.yaml`、`x4-consistency-rules.yaml`。

### X1 审计边界（8 policy）

- 8 条审计/边界策略，覆盖准入、越权、审计留痕与双平面（Workspace × Documents）约束。
- 联动：`ecos-constraint explain/audit/eval/drift`（ADR-0190），`ecos-constraint documents audit/guardrail`（ADR-0191）。
- GaC 映射维度计数中 X1 占 29 条（见 §3，截至 2026-09-03 只读快照）。

### X2 保鲜（15 rule，多阈值）

- 15 条 freshness rules，多阈值分级（文档/状态/记忆体的保鲜期与巡检节律不同）。
- 联动：`make hygiene-patrol`（ADR-0192，`_entities/facts/*.yaml` 14 天新鲜度）。
- GaC 映射维度计数中 X2 占 19 条（截至 2026-09-03 只读快照）。

### X3 价值栈（薄）

- 规则仅 5 条（GaC dimension X3-5，截至 2026-09-03 只读快照），为四维中最薄一维。
- Vault X3 缺口：价值实证资产沉淀不足，需补强 `value-tracker` → 北极星度量闭环。
- P43 闭环实证：`.omo/_knowledge/patterns/p43-closed-loop-pattern.md` 证明“信号→旅程→价值记录→进化反馈”可跑通，但覆盖面窄，需从个案推广为常态（见 §7 TOP3）。

### X4 一致性（6 rule）

- 6 条一致性规则，覆盖跨平面命名、契约、投影一致性。
- GaC 映射维度计数中 X4 占 32 条（四维中最多，截至 2026-09-03 只读快照），说明一致性检查已深度嵌入各门禁。

---

## §3 GaC 门禁（截至 2026-09-03 只读快照）

SSOT：`.omo/_truth/registry/governance-checks.yaml::gac.rules`；生成摘要 `docs/generated/agent-gac-rules.md`；校验 `python3 bin/gac/gac-validate.py --gate`；漂移 `python3 bin/gac/gac-drift.py`；导出 `python3 bin/gac/gac-export-agents.py`。

| 切面（截至 2026-09-03 只读快照） | 值 |
|---|---|
| 规则总数 | 85（active 82 / removed 3） |
| enforcement 分级 | advisory 45 / required 30（余量为信息/历史保留位，详见 registry） |
| dimension 分布 | X4-32 / X1-29 / X2-19 / X3-5（合计 85，与总数自洽；X3 最薄） |
| layer 分布 | 以 Workspace 治理面为主，Documents 内容面与协议面（MOF/ECOS）为辅（明细见 `governance-checks.yaml::gac.rules[].layer`） |

**required 硬门举例（指针，不贴全文）：**

- 主树直改拦截 / worktree+PR 强制（分支保护 + `gac-worktree.sh claim/submit/merge`）。
- SFOP 槽位唯一性（CR-SFOP-01/02，`COMP-WS-omo` 为唯一 `S` 槽）。
- 执行链覆盖（CR-EXEC-CHAIN-01，`check-execution-chain.py`）。
- 需求迭代门（ADR-0204，staged 需求面路径无 active run 则 halt）。
- 子模块指针事务（`bin/ssot/submodule-pointer-transaction.sh`）。

**减法配额债（ADR-0431 D2）：**

- `subtraction-quota.yaml` 减法配额机制中 D2（待补理由说明）仍欠一条 justification 记录。
- 性质：文档债，非门禁失效；`gac-validate` 仍通过，但 `gate-known-debt.yaml` 应登记该已知债并限期补理由（见 §7 TOP6、§8 漂移清单）。

---

## §4 三平面 + 投影 + CI + Harness（截至 2026-09-03 只读快照）

### 4.1 OMO 治理面：3 平面 47 资产

- SSOT：`.omo/_truth/registry/omo-governance-surfaces.yaml`。
- 3 平面（治理内核 / 策略入口 / 协议与记忆投影）共 47 项治理资产（截至 2026-09-03 只读快照）。
- 用途：`omo lint projection-guard`（P74）、治理面资产增删必须走 registry 登记。

### 4.2 运行时投影：10 投影

- SSOT：`.omo/_truth/registry/runtime-projections.yaml`。
- 10 个运行时投影（截至 2026-09-03 只读快照），由 `omo-state-projection-guard.py`（P74）强制“投影只能读 SSOT、不得自立真相”。

### 4.3 CI 平面：150+ surface + 60 triggers

- SSOT：`.omo/_truth/registry/ci-surfaces.yaml`。
- 150+ CI 检查 surface、60 个触发器（截至 2026-09-03 只读快照）；接线检查 `python3 bin/gac/check-ci-surfaces.py`（ADR-0379）。
- 注意漂移：`Makefile` 缺 `ci-local` 目标（见 §8），本地一键全部门入口名与文档存在名实差，需对齐。

### 4.4 Harness 策略 v1.0

- SSOT：`.omo/_truth/registry/harness-policy.yaml`（v1.0，截至 2026-09-03 只读快照）。
- S 槽唯一：`COMP-WS-omo` 为 Mesh 唯一活跃 `S` slot（对应 `check-sfop-slots.py` CR-SFOP-01/02）。
- 8 阶段 DAG：`admission → spec → grill → dispatch → execute → verify → audit → accept`。
- 分级门：
  - Admission / Spec / Execution / Verify：blocking 9 + advisory 5；
  - Audit / Accept：分级放行（审计留痕 + 人工/自动接受）。
  （以上计数截至 2026-09-03 只读快照，明细见 `harness-policy.yaml::phases`。）
- 7 探针：心跳/活性探针矩阵见 `.omo/_truth/registry/probe-heartbeat-matrix.yaml`（M3 仪式，`probe-heartbeat-monitor.py --status`）。
- known_debt：`shrink_only`——已知债只允许收敛、不允许扩张；新增债必须登记理由与偿还期限。

---

## §5 SFOP/DFSQ + 执行链 + 能力所有权实测（截至 2026-09-03 只读快照）

| 检查 | 结果（截至 2026-09-03 只读快照） | 说明 |
|---|---|---|
| `check-sfop-slots.py --json` | ok，0 err / 1 warn | S 槽唯一且为 `COMP-WS-omo`；1 warn 为非阻塞性提示（详见 §8 输出摘要） |
| `check-execution-chain.py --json` | ok，0 err / 437 warn | 无合法触发器债（warn 多为“未接线/待登记”类提示，非错误；需持续收敛，见 §7 TOP2） |
| `gac-validate --gate` | 通过 | 但脚本数 574 > 基线 568（+6），基线需同步（见 §7 TOP4、§8） |
| `check-capability-ownership.py` | 582 孤儿（info 级） | 能力无主：需补登 `capability-providers.yaml` / `mof-capabilities.yaml`（见 §7 TOP1） |

要点：

- SFOP/DFSQ：`docs/architecture/dao-fa-shu-qi.md`（理论）+ `docs/architecture/os-operating-pattern-v1.md`（运行时槽位）；不得新增第二调度器/第五本体/顶层入口。
- 执行链 437 warn 不是失败，而是“接线覆盖率”的工作清单；策略是 shrink_only：只收敛不扩张。
- 能力 582 孤儿为 info 级，不阻塞门禁，但长期放任会侵蚀“能力→所有者→门禁”的可追溯性，优先级列 TOP1。

---

## §6 Resident / BCOS / P74 / ADR-0203

### 6.1 Resident 常驻 Agent（5 角色 + 20 路由）

- 规格：`docs/architecture/resident-agent-system-v1.md`（ADR-0396）。
- 路由表 SSOT：`projects/omo/src/omo/resident/resident-routes.yaml`；角色 SSOT：`projects/omo/src/omo/resident/roles.py`；BOS：`bos://resident/*`。
- 5 角色（心眼脑忆手，截至 2026-09-03 只读快照）：感知（眼）/ 意图（心）/ 决策（脑）/ 记忆（忆）/ 执行（手）。
- 20 路由中 `execute` 为唯一非 safe 路由（截至 2026-09-03 只读快照），即唯一允许写副作用的出口，其余均为 safe/只读。
- 运维：`make resident-status && make resident-roles && make resident-daemon`。

### 6.2 BCOS 业务域系统（存在性说明）

- 规格：`docs/architecture/bcos-system-v1.md`（W1~W4：信号路由 → 进化引擎 → 北极星价值度量）。
- 入口：`make bcos-evolve && make bcos-signals && make bcos-north-star`；`python3 bin/bc-os/evolution_engine.py --json`。
- 本报告仅做存在性说明：BCOS 为业务闭环层，不与 Mesh（`COMP-WS-omo`）争 `S` 槽；其价值度量输出应回流 X3（当前 X3 薄，见 §2/§7）。

### 6.3 P74 沉默治理（三层 A1/A2）

- SSOT：`agent-workflows/::silent_workflow_policy`；`governance-checks.yaml`（4 条 CR-P74-* rules）。
- 三层：A1（运行时沉默检测）/ A2（投影守卫 `omo-state-projection-guard.py` + `omo lint projection-guard`）/ 常态化复盘固化（详见 ADR-0130 `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`）。
- 工具：`agent-workflow.py suggest --from-diff --profile <agent>`、`agent-workflow.py compliance --json`；Skill：`.agents/skills/workflow-silence-detection/SKILL.md`。
- 若 `p74_solidification.warn_count > 0`，禁止投机启动 workflow。

### 6.4 ADR-0203 红线（需求迭代强制 Workflow）

- SSOT：`.omo/_truth/registry/agent-workflows/::requirement_iteration_policy`；契约 `.omo/standards/agent-workflow-contract.md §3.1`。
- 强制链：`bootstrap → start --profile --bet --objective → claim --path → verify --from-diff --execute → closeout`。
- 可执行闸门（ADR-0204）：`compliance` / `status` 对已 stage 需求面路径检查 active run；无 run 则 halt（exit 1）；旁路 `AGCP_REQUIREMENT_ITERATION_GATE=0` 仅限明确豁免。
- 窄豁免：纯只读问答、`observer-audit`、用户书面 waiver；“先改完再补 workflow”一律禁止。

---

## §7 风险排序 TOP6 与建议（截至 2026-09-03 只读快照）

| 排名 | 风险 | 现状（快照） | 建议 |
|---|---|---|---|
| TOP1 | 能力孤儿 | 582 孤儿（info） | 补登 `capability-providers.yaml` + `mof-capabilities.yaml`；`check-capability-ownership.py` 收敛到 0；新增能力必须声明 owner 否则 CI 提示 |
| TOP2 | 执行链接线 | 437 warn（0 err） | 按 `check-execution-chain.py` 输出逐类接线（script-registry × ci-surfaces × cron × capability-registry × agent-workflows × skills × githooks）；shrink_only，每轮收敛数不得反弹 |
| TOP3 | X3 价值栈薄 | 规则仅 5，Vault X3 缺口 | `value-tracker --record/--update-north-star` 常态化；P43 闭环从个案推广为周度仪式；BCOS 度量回流 X3 |
| TOP4 | 脚本基线漂移 | 脚本 574 > 基线 568（+6） | 同步 `dependency-baseline.yaml` / 相关 `baseline-*.txt`，或清理多余脚本后重设基线；`gac-validate` 通过不代表基线已同步 |
| TOP5 | orphan 脚本 | registry 登记覆盖待补 | `bin/README.md` 工具目录与 `rule-gate-mapping.yaml` 对齐；`command-discovery.py` 降噪（命令密度/重复/易混淆） |
| TOP6 | justification 债 | ADR-0431 D2 待补理由 | 在 `gate-known-debt.yaml` 登记并限期补 justification；`subtraction-quota.yaml` 配额解释完备后关闭该债 |

---

## §8 附录

### A. 检查命令与输出摘要（截至 2026-09-03 只读快照）

```bash
python3 bin/gac/check-sfop-slots.py --json
# ok，0 err / 1 warn；S 槽唯一为 COMP-WS-omo（快照转述）

python3 bin/gac/check-execution-chain.py --json
# ok，0 err / 437 warn；无合法触发器债，warn 为待接线清单（快照转述）

python3 bin/gac/gac-validate.py --gate
# 通过；脚本 574 > 基线 568（+6，基线待同步，快照转述）

python3 bin/gac/check-capability-ownership.py
# 582 孤儿（info 级，需补登，快照转述）

python3 bin/gac/check-ci-surfaces.py
# CI 平面接线检查（ADR-0379），surface 150+ / triggers 60（快照转述）

make gac-local-gate
# 全量治理-as-Code 门禁（常态化守护，要求 ALL GREEN PASS）
```

> 注：本表为审计输入方提供的输出摘要转述（截至 2026-09-03 只读快照），非本 scribe 在主仓执行所得；如需复核，请在 worktree 内重跑上表命令并以 `verify` 链（§结尾）确认。

### B. SSOT 文件指针列表

- X1：`.omo/_truth/x1-governance-policies.yaml`
- X2：`.omo/_truth/x2-freshness-rules.yaml`
- X3：`.omo/_truth/x3-value-stack.yaml`
- X4：`.omo/_truth/x4-consistency-rules.yaml`
- GaC：`.omo/_truth/registry/governance-checks.yaml::gac.rules`
- 三平面：`.omo/_truth/registry/omo-governance-surfaces.yaml`
- 投影：`.omo/_truth/registry/runtime-projections.yaml`
- CI：`.omo/_truth/registry/ci-surfaces.yaml`
- Harness：`.omo/_truth/registry/harness-policy.yaml`
- 探针：`.omo/_truth/registry/probe-heartbeat-matrix.yaml`
- 需求迭代：`.omo/_truth/registry/agent-workflows/::requirement_iteration_policy`
- 契约：`.omo/standards/agent-workflow-contract.md`、` `.omo/standards/doc-ssot-contract.md`
- SFOP：`docs/architecture/dao-fa-shu-qi.md`、`docs/architecture/os-operating-pattern-v1.md`
- Resident：`projects/omo/src/omo/resident/resident-routes.yaml`、`projects/omo/src/omo/resident/roles.py`
- BCOS：`docs/architecture/bcos-system-v1.md`
- P74：ADR-0130 `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`
- 能力：`.omo/_truth/registry/capability-providers.yaml`、`.omo/_truth/registry/mof-capabilities.yaml`
- 已知债：`.omo/_truth/registry/gate-known-debt.yaml`、`.omo/_truth/registry/subtraction-quota.yaml`

### C. 漂移清单（截至 2026-09-03 只读快照）

1. registry 18 vs 16：某 registry 计数 18 与文档记载 16 不一致（名实差，需以 registry 为准并修正派生文档）。
2. ledger 149 vs 277：bet ledger 两处计数 149 与 277 不一致（快照转述；以 `docs/plans/3y-bet-ledger.yaml` SSOT + `bin/plan/bet-ledger.py status` 为准）。
3. PANORAMA 过期：`docs/PANORAMA.md` 全景导航落后于运行时状态（需重生成/对齐 `.omo/state/system.yaml`）。
4. Makefile 无 `ci-local`：文档引用的 `make ci-local` 在 Makefile 中缺失（需补目标或修正文档引用为实际存在的本地门禁入口）。

---

## 下一步 + verify 指引

**下一步（建议顺序）：**

1. 补登：TOP1 能力孤儿补 owner（`capability-providers.yaml` / `mof-capabilities.yaml`）。
2. 接线：TOP2 执行链 437 warn 收敛（shrink_only，按类分批）。
3. X3 补强：value-tracker 常态化 + BCOS 回流 + P43 推广。
4. 基线同步：脚本 574 vs 568 基线对齐 + 漂移清单 4 项关闭（registry/ledger/PANORAMA/Makefile）。

**verify 指引（在 worktree 内执行，不碰主仓）：**

```bash
cd /Users/xiamingxing/ws-gov-report-0903
uv run --with "pyyaml" python "bin/agent-workflow.py" verify 20260903T060034Z-governance-audit-875927c6 --from-diff --execute
make gac-local-gate
python3 bin/gac/check-sfop-slots.py --json
python3 bin/gac/check-execution-chain.py --json
python3 bin/gac/gac-validate.py --gate
```

*报告完。本文件为隔离 worktree 内新增的唯一文件，未修改其他文件，未 commit。*
