---
name: multica-squad-ops
description: "用 multica CLI 落地日常工程协作 4 个 squad（交付流水线/架构评审/研究情报/运维监控）+ 配额动态分派台账。与 R3-executor 的 multica 后端物理隔离，不替代 ADR-0203 workflow。"
last-reviewed: 2026-09-05
type: ssot
owner: governance-team
---

# multica Squad Ops

## 1. 何时使用

以下任务使用本技能：

- 需要把一个工程任务分派给 multica 侧某个 CLI runtime（跨工具协作）；
- 需要判断某个 runtime 是否配额耗尽、该换哪个同 Tier 备选；
- 需要新建/调整 multica squad、agent、autopilot。

本技能不替代 `bin/agent-workflow.py` 的 ADR-0203 流程、GaC/SSOT gate、独立 review 或
`.omo/standards/multi-agent-worktree-collaboration.md` 的 worktree 隔离纪律。

完整架构裁定见 `docs/architecture/multica-squad-system-v1.md`（Tier 分层、红线、Squad 定义）。

## 2. 前置校验（不可跳过）

在通过 multica 分派任何"会写文件"的 issue 之前：

```bash
python3 bin/agent-workflow.py bootstrap
python3 bin/agent-workflow.py start --bet <bet-id>
python3 bin/agent-workflow.py claim --bet <bet-id>
```

只有 claim 成功后才允许创建/触发对应的 multica issue 或 autopilot。只读观察类 issue
（Squad D）不受此约束。

## 3. Tier → Runtime 速查

| Tier | 场景 | 主力 runtime | Squad E 灾备（配额溢出改派） |
|---|---|---|---|
| T0 | 架构设计、跨文件影响判断 | claude、codex | agy（Gemini/Claude/gpt-oss 多模型网关） |
| T1 | 批量机械编辑 | codebuddy、reasonix、opencode(build)、droid(direct-cli) | copilot（GPT-5.6 Luna）、hermes（deepseek-v4-flash） |
| T2 | 跨厂商复核 | grok、kimi、crush(direct-cli) | qoderclicn（阿里 Qwen3.8） |
| T3 | 本地/隐私计算 | oh-my-pi、pi、opencode(omlxc-local) | — |
| T4 | 只读监控 | Codex Observer、Codebuddy Observer | — |

droid/crush 走 direct-cli 兜底通道（不经过 multica 协议），用 `droid-batch.sh`/`crush-review.sh`
(见 §3a) 调用；kilocode 用户不特别在意，已搁置不再推进；qwen 认证过期(`401`)，需重新登录才能定级。
详见架构文档 §2/§4a/§5(Squad E)。分派原则：Squad A/B 主力优先；某 runtime 在 `quota-ledger.yaml`
里 `last_exhausted_at` 命中冷却期，改派同 Tier 的 Squad E 成员，而不是干等或报错。

## 3a. Direct-CLI 兜底调用（droid / crush / kilocode）

droid/crush 优先用焊死了正确参数的 wrapper，不要手写裸命令（2026-09-05 SOP 演练踩过坑，
默认模型/flag 都不对）：

```bash
# droid — T1 批量编辑，只准 low/medium
.agents/skills/multica-squad-ops/droid-batch.sh low "<在隔离 worktree 内的具体编辑指令>"

# crush — T2 只读复核
.agents/skills/multica-squad-ops/crush-review.sh "<diff 或改动摘要>"

# kilocode — 仅实验性只读探测，不设 --auto，不进生产 squad（用户不特别在意，已搁置不推进）
kilo run --format json --model "<provider/model>" "<只读分析类 message>"
```

结果由 leader（Claude Code）读取 stdout，按正常 Squad A 流程走 Verifier(gate 脚本) →
人工 merge；不因为绕过了 multica 就跳过 worktree 隔离或 claim 前置。某 runtime 报错命中
`quota-ledger.yaml` 里的 `exhaustion_signals` 时，跑
`python3 .agents/skills/multica-squad-ops/record-quota-exhaustion.py <runtime> "<报错片段>"`
记一笔，连续 2 次自动标记熔断。

## 4. 分派决策（配额感知）

分派前查 `quota-ledger.yaml`：

1. 读该 Tier 候选列表；
2. 剔除 `last_exhausted_at` 在冷却期内（默认 24h）的 runtime；
3. 剩余候选按 `quota 0.35 / capability-affinity 0.30 / speed 0.20 / cost 0.15` 打分
   （无实测数据时按经验默认：T1 内 reasonix 略快于 codebuddy；T2 内 grok 速度优于 kimi）；
4. 选分最高的作为本次执行 runtime；次高作为失败重试的备选。

若某 runtime 本次任务返回的错误信息命中 `quota-ledger.yaml` 里该 runtime 的
`exhaustion_signals` 关键字，立即：
- 更新该 runtime 的 `last_exhausted_at` 为当前时间；
- 改派备选 runtime 重试一次；
- 若仍失败，上报给用户，不静默重试第三次。

## 4a. 七个 Squad 一览

A 交付流水线 / B 架构评审 / C 研究情报 / D 运维监控 / E 供应链多样性(灾备) /
F 文档与内容(纯文字场景，复用现有 agent) / G 个人隐私(family-hub/健康等敏感场景，
只准 T3 本地 agent，云端 vendor 一律不许)。完整定义、成员、ID 见架构文档 §5。
每个 agent/squad 在 multica 里都挂了完整 `--instructions`（不只是 description）：
身份+职责+能力边界+禁止事项+治理红线，改动系统提示时用
`multica agent update <id> --instructions "..."` / `multica squad update <id> --instructions "..."`。

## 5. Squad 操作命令参考

```bash
# 建 squad（leader 必须是已存在的 agent 名或 ID）
multica squad create --name "<squad-name>" --leader "<agent-name>" --description "<desc>"

# 建 leader agent（绑定某个 runtime-id，先用 multica runtime list --output json 查 id）
multica agent create --name "<name>" --runtime-id "<runtime-id>" --model "<model>" \
  --instructions "<role instructions>" --permission-mode private

# 加成员
multica squad member add --squad "<squad-id>" --agent "<agent-id>" --role "<role>"

# 建 autopilot（仅 Squad A 允许，且先 dry-run 验证 claim 校验生效）
multica autopilot create ...
multica autopilot trigger <autopilot-id>
```

具体参数以当次 `multica <command> <subcommand> --help` 实测为准，不要凭记忆硬编码旧参数。

## 6. 禁止事项

- 禁止让 multica squad/autopilot 绕过 `start --bet` + `claim` 自主发起写操作；
- 禁止把 multica 侧新 squad 的执行 agent 复用 R3-executor 里固定的 `Mika`
  （`projects/omo/src/omo/resident/execute.py:32`）——两条轨道必须用不同 agent；
- 禁止在没有实际路由测试验证的情况下，把 droid/crush/kilocode 当作"已接入生产"对待；
- 禁止把 BDSK 唯一可执行链（cockpit → BOS → Agora → AetherForge）的产出与 Squad B
  的"补充意见"混为一谈——后者不产生 `proof_state=proven`。

## 相关

- 架构：`docs/architecture/multica-squad-system-v1.md`
- 复用范式：`.agents/skills/bdsk-virtual-board/SKILL.md`、`.agents/skills/a2a-coordination/SKILL.md`
- 并发纪律：`.omo/standards/multi-agent-worktree-collaboration.md`
- 权限画像：`.agents/profiles/external-agent-profiles.fragment.yaml`
