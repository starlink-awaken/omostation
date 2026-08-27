---
title: 战略-治理收敛 · 剩余工作派工指令
status: draft
type: agent-dispatch-brief
owner: 夏明星
created: 2026-08-17
lifecycle: plan
builds-on:
  - docs/STRATEGY-CONVERGENCE-MASTER-2026-08.md
  - docs/STRATEGY-CONVERGENCE-LANDING-PACKAGE-2026-08.md
  - .omo/_knowledge/decisions/0410-strategy-mainline-plan-supersedes-panorama.md
  - .omo/_knowledge/retros/BET-Y1Q1-T6-01.md
  - .omo/_knowledge/retros/BET-Y1Q1-T6-02.md
  - docs/architecture/wave-gate-bet-map.md
track: T6-SUBTRACT（exclusive，认领前先 `python3 bin/plan/bet-ledger.py status` 确认没有其他 T6 bet 在跑）
---

# 给接手 Agent 的话（先读这一段，再动手）

前面两轮（BET-Y1Q1-T6-01、BET-Y1Q1-T6-02）已经把《战略-治理-场景全域收敛总纲》里能立刻拍板的部分做完了：三年战略主线定了（ADR-0410，Plan 为主线，Panorama superseded）、`research-pipeline` 的 ID 碰撞解决了、Wave/Gate 和 BET 台账的映射表和硬门禁（`chain-bind-check.py`）也上线并合入 main 了。**这一轮不是重新分析，是把总纲里当时明确"还没人拍板"或"还没排期"的部分继续做完**。开工前请把上面 `builds-on` 列的几份文档（尤其是两份 retro）通读一遍——里面记录了上一轮踩过的坑，不要重踩。

**这一轮最容易踩的坑，提前说清楚**：BET-Y1Q1-T6-02 复盘里明确写了"台账写 done 的时候，main 上其实还没有这条链"——这个仓库里"声明先于事实"这个病，两周前刚被总纲当成头号问题分析过，上一轮修它的人自己又犯了一次。所以这一轮的 D0-D5 铁律、grill 流程、closeout 前必须真的 merge 到 main 再置 done，**不是形式，是这个仓库最近两周唯二两次真实事故的直接教训**，请照字面执行，不要图快。

---

# 剩余工作清单（按优先级）

## 1. D3：gbrain + kairon 是否合并（需要真人 grill，不要替他做决定）

总纲 §11 D3、ADR-0410 里都明确写着"本轮未开"。`STRATEGY-3YEAR-PLAN-2026H2-2029.md` §3.2 把这个合并标注为"不可逆"，锁定在 Y1Q3。

**这个 bet 的正确产出不是"合并 gbrain 和 kairon"，而是一份 grill 决策文档**，结构照抄 `ADR-0410` 的格式（WHY / WHAT / REJECTED ALTERNATIVES / CONSEQUENCES），核心问题清单：
- 现在是不是已经到了 Y1Q3（如果还没到，这个 bet 的正确产出可能是"确认暂不启动，记录触发条件"，而不是强行拍板）；
- 合并的真实收益（`STRATEGY-3YEAR-PLAN-2026H2-2029.md` §1.3 提到的"知识层双头"重复度）有没有新证据支持，还是仍停留在 2026-08-06 那次诊断；
- "不可逆"这个判断本身要不要在 grill 里重新确认，还是维持原判。

**done_when**：产出一份新 ADR（`.omo/_knowledge/decisions/04XX-gbrain-kairon-merge-*.md`），无论结论是"批准合并"还是"暂缓，记录触发条件"，都算完成——**这个 bet 不强制要求做出"合并"这个结论**。

## 2. D5：ADR-0247 与 ADR-0225/0226 的物理多机张力

总纲原文发现：ADR-0247（2026-07-26，多 Agent 协作优先、物理多机 deferred）和 ADR-0225/0226（2026-07-19，比 0247 早一周，把物理多机四机互联定为 G-DEL.1/G-DEL.3 的官方 caliber、fail-closed）之间存在没被后续任何 ADR 明确协调过的矛盾。同时 `.omo/_truth/registry/phase-scope.yaml`/`phase-verdict.yaml` 显示 G-DEL.1 至今仍 BLOCKED（reachable_physical_hosts=2 < min_physical_hosts=4）。

**先做只读复核，不要直接下结论**：
1. 用 `python3 bin/plan/bet-ledger.py status` 或读最新 `.omo/_truth/goals/current.yaml`，确认 G-DEL.1 现在的真实状态有没有变化（可能两周里已经有其他 bet 动过物理多机）；
2. 如果状态没变，产出一份 ADR，二选一：(a) 正式确认"物理多机 caliber 随 ADR-0247 一并 deferred"，同步降级 G-DEL.1 的 fail-closed 严格度或明确其在 deferred 期间的处理方式；(b) 正式确认"G-DEL.1 caliber 不受 0247 影响，多 Agent 优先只是资源投入优先级问题，不改变验收标准"。哪个都行，但**必须有一份 ADR 把这两条并存的规则的关系写清楚**，不能继续让它们互不引用地悬着。

**done_when**：新 ADR 产出，且 `phase-scope.yaml` 或 `ADR-0247`/`ADR-0225`/`ADR-0226` 任一方的 `related:` 字段回填指向新 ADR。

## 3. D7 + 总纲 §9 剩余文档处置：治理基建链（第二代文档）内容级重读

总纲发现这批文档大多数 `review-state: metadata-only`——即只有 frontmatter 在 2026-07-31 被批量迁移过，正文从未真正重新审阅。这一批不需要 grill 决策，是纯粹的内容核查工作，逐个产出"仍然准确/需要更新/建议归档"的判断：

- `docs/PANORAMA.md`（内容定格 06-30，但 frontmatter 声称 07-31 已复核——先确认这份文档现在还有没有人在读，如果 `SYSTEM-INDEX.md`/`README.md` 仍然引用它作为"系统全景"入口，就必须真的重读一遍内容是否仍准确，不能只是再打一次 metadata-only 标记）
- `docs/FUNCTIONAL-CAPABILITY-MAP.md`（已知具体缺陷：§11 "BOS URI 域映射"列出 9 个域 `memory/governance/analysis/persona/capability/meta/omo/swarm/system`，与 `ARCHITECTURE.md`/`LAYER-INDEX.md`/`PANORAMA.md` 三处一致声明的 5 个规范域矛盾——这一条不需要 grill，直接核实真实域数量后订正其中一边即可）
- `docs/USER-JOURNEY-SOP.md`（2026-06-12 内容，和 08 月之后的场景卡/journey-spec 体系完全没打通——判断这份文档还要不要保留，如果保留需要至少加一条指向 `docs/scene-cards/`/`docs/journey-specs/` 的交叉引用）
- `docs/SYSTEM-INDEX-DESIGN.md`（自相矛盾：顶部声称"已实施：1 个纯指针文件、0 个新数据源"，但下文 700 行仍在详述一个更复杂的 5 文件生成器方案——需要先去确认 `INDEX-PROJECTS.md`/`INDEX-TOOLS.md`/`INDEX-KNOWLEDGE.md`/`INDEX-AGENTS.md` 这几个文件实际存不存在，再决定这份文档该精简成"已实施"版本还是把顶部状态改回"设计中"）
- `docs/STRATEGY-INDEX.md`（已知问题：其"核心文档"表仍未纳入 08-03 之后新增的至少 4 份文档，且"主方案"标注虽然 T6-01 那轮已经改指向 Plan，但整张表需要一次完整校验，确认没有其他遗漏）
- `docs/project-registry.yaml`（已知的 BOS service 计数内部不一致：文件内部同时出现 200 / 196 两个数字；T6-01 复盘里进一步发现 2026-08-15 实测 `bos-services.yaml` 是 223 [active 191]——需要重新核实当前真实数字，把文件里的多处计数改成一致）

**done_when**：以上 6 份文档逐个更新 `last-reviewed` 日期为真实复核日期（不是 metadata-only 迁移日期），并在 retro 里逐条写明"这次真的重读了正文，具体改了什么/为什么判断不需要改"。

## 4. 跟进 BET-Y1Q1-T6-02 复盘里自己记录的已知缺口

这几条不是新发现，是上一轮 agent 自己在复盘里明确写出来、留给下一个人的：

- `chain-bind-check.py` 的硬门目前只包住了 `bin/agent-workflow.py` 这个根仓 wrapper，绕过它直接调 `cockpit agent start` 或 `python -m omo.workflow` 仍然可以不带 `--bet` 开工——需要把硬门下沉到更底层的入口，或者至少在 cockpit/omo 的对应 CLI 里也接上同一个 `chain_bind` 检查。
- `bootstrap`/`status` 在没有 active run 时会把"已经正常关闭、且当时确实绑定了 bet"的历史记录显示成 `missing-bet`——这是 `perception_fields` 只扫描 `status==active` 的 run 导致的误报，需要修正扫描范围或调整展示逻辑，避免下一个人看到 `missing-bet` 就误以为链条从未生效。
- D0 铁律"commit 了就安全"在这个仓库已经被证伪两次（一次是最早的 601 行代码丢失事故，一次是 T6-02 自己的本地 tag 没推到 origin）——建议这个 bet 顺手把"tag 必须验证已推送到 origin 才算 D0 完成"这条，从 T6-02 retro 里的个案教训，提升为写进 `docs/plans/3Y-BET-LEDGER.md` 或 `docs/plans/AGENT-BRIEF.md` 的正式铁律条款（可以是 D0 的补充说明，不需要新开一个 D6）。

**done_when**：上述三项各自要么修复、要么产出一份说明"为什么这次不修，留给下一轮"的记录，不能沉默地跳过。

---

# 执行方式（照抄 T6-01/T6-02 已验证过的流程，不要另起一套）

```bash
# 0. 先确认 T6 轨道没人在跑（T6-SUBTRACT 是 exclusive）
python3 bin/plan/bet-ledger.py status

# 1. 在 3y-bet-ledger.yaml 里登记新 bet（建议 BET-Y1Q1-T6-03 起，具体号看 ledger 里下一个可用号）
#    appetite 建议：D3+D5 各自独立一个 bet（涉及真实决策，可能要等人确认，appetite 放宽到 1 周）；
#    第 3 项（文档重读）可以单独一个 bet（appetite 3-5 天，纯核查工作量可预估）；
#    第 4 项（chain-bind 补漏）单独一个 bet（appetite 3 天，参照 T6-02 的量级）

# 2. 认领隔离 worktree
bash bin/gac/gac-worktree.sh claim <bet-id 小写>

# 3. 起 ADR-0203 workflow，注意这次必须带 --bet（T6-02 刚上线的硬门禁）
uv run --with pyyaml python bin/agent-workflow.py start governance-state-mutation \
  --profile governance-agent --bet <BET-ID> \
  --objective "<对应上面第几项工作的一句话目标>"

# 4. claim 写面、执行、每写完一个文件立刻 git add（D0）

# 5. 收尾：verify + agent-workflow verify + closeout，
#    closeout 前务必确认 PR 已经真的 merge 到 origin/main 再把台账置 done
#    （T6-01/T6-02 的教训：不要把"台账写 done"和"main 上真的有这条链"当成一回事）
python3 bin/plan/bet-ledger.py verify <BET-ID> --execute
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# 6. 写复盘（.omo/_knowledge/retros/<BET-ID>.md），格式照抄 T6-01/T6-02 那两份，
#    Q1-Q5 五问 + 一段"打假"（本轮发现的、和计划不符的事实），不要省略打假这一段

# 7. git tag 并确认真的推到了 origin（T6-02 吃过这个亏）
git push origin <tag>
git ls-remote --tags origin | grep <bet-id>   # 确认远端真的有

# 8. 提交
bash bin/gac/gac-worktree.sh submit <bet-id 小写>
```

# 非目标（这一轮不要做的事）

- 不要替人类拍板 D3（gbrain+kairon 是否合并）——只产出 grill 决策文档草稿，最终 ADR 状态建议先设为 `PROPOSED`，等人类确认后再改 `ACCEPTED`（除非你能拿到夏明星本人在当前会话里的明确书面确认）。
- 不要在同一个 bet 里同时动 D3/D5/文档重读/chain-bind 补漏——按上面建议拆成 3-4 个独立 bet，避免像总纲最早建议的那样把所有事塞进一个大 PR。
- 不要碰共享 Workspace 主目录之外的写操作；不要动 `.omo/state/`、`runtime/`、`kos/`、Orca 协调状态——这些红线在两周前的交接手册里说得很清楚，这一轮工作范围全部在 `docs/` 和少量 `bin/plan/`、`.omo/_knowledge/` 之内，不需要碰这些。
