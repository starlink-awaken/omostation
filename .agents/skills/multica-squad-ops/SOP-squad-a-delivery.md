# SOP: Squad A（交付流水线小队）实兑流程

> 2026-09-05 实测跑通一次，记录真实命令、真实报错和治本方式。后续真实交付照抄本流程，
> 遇到和这里不一致的报错，先怀疑是版本/环境变了，再怀疑是自己漏了一步。

## 0. 全流程一览

```
ADR-0203 claim → worktree 隔离 → T1 批量编辑(multica-native 或 direct-cli)
  → T2 跨厂商复核 → Verifier(gate 脚本) → 人工 merge 审批 → worktree 清理/closeout
```

## 1. ADR-0203 claim（写文件前必做，不可跳过）

```bash
# 1. 起一个 run（workflow_id 是位置参数，不是 --workflow）
uv run --with pyyaml python bin/agent-workflow.py start project-doc-change \
  --profile docs-agent \
  --bet <真实BET-ID，来自 docs/plans/3y-bet-ledger.yaml> \
  --objective "<一句话说明这次要做什么>" --json
# 返回 run_id，形如 20260905T030841Z-project-doc-change-2dc3f5be

# 2. claim 需要一份 affected-graph 收据，不能只给字符串占位
python3 bin/gac/affected-graph.py --changed-projects <project-name|workspace-root> \
  --output <receipt-path> --json
# 根级 docs/.agents 改动用 workspace-root；改某个子模块用该子模块名(如 omo/agora)

# 3. 正式 claim
uv run --with pyyaml python bin/agent-workflow.py claim <run_id> \
  --path "<要改的路径1>" --path "<要改的路径2>" \
  --actor "<身份，如 claude-lead>" --affected-hash "<receipt-path>" --json
```

**踩坑记录**：
- `start` 不带 `--profile` 会报 `project-doc-change requires --profile (docs-agent, governance-agent)`。
- `claim` 不带 `--affected-hash` 会报 `Missing or invalid affected-hash`；这不是占位字符串，
  是真的会校验收据内容和 claim 的 path 是否对得上（`validate_affected_graph_receipt`）。
- `--bet` 这一层门禁（`bin/plan/chain_bind.py::start_requires_bet`）只校验非空字符串，
  不校验 BET 是否真存在于 ledger——**但这不代表可以随便编一个假 BET**，真实交付必须用
  `docs/plans/3y-bet-ledger.yaml` 里真实存在的条目。唯一合法的"跳过"是
  `AGCP_REQUIREMENT_ITERATION_GATE=0`（测试套件自己也这么用），**仅限本 SOP 这种纯演练/
  自测场景**，真实交付绝不能长期这样跑。

## 2. Worktree 隔离（不得在主工作树直接改）

```bash
git fetch origin main
git worktree add .claude/worktrees/<name> -b <branch> origin/main
cd .claude/worktrees/<name>
```

**踩坑记录**：真实交付前必须 `git submodule update --init --recursive`，否则
`doc-ssot-lint.py` 会报"L0 约束源缺失"之类的假阳性（子模块目录是空 gitlink，不是真代码）。
本次演练是纯 scratch 文件、没碰子模块相关内容，跳过了 submodule init，遇到了这个已知假阳性，
确认无关后忽略；真实交付不能跳过这一步。

**并发风险实况**：本次演练过程中，主工作树 (`/Users/xiamingxing/Workspace`) 的 `git status`
里出现了 `D bin/gac/gates.py` / `hygiene.py` / `repo-health-metrics.py` 三个被 stage 的删除
——这不是本次演练造成的，是当时另有并发 agent 在主工作树上活动的实况痕迹（本仓库同时有
20+ 个 worktree 在跑不同 BET）。这正是"必须走 worktree 隔离、不能直接改主工作树"这条纪律
存在的理由——真实发生在你眼前。遇到类似情况：**不要碰、不要调查、不要 stage/unstage**，
那是别的 agent 的工作，继续走自己的隔离流程即可。

## 3. T1 批量编辑

### 3a. multica-native（codebuddy/reasonix/opencode）
通过 multica issue 分派给对应 agent（Codebuddy Batch / Reasonix Batch / Opencode Batch）。

### 3b. direct-cli（droid）—— 2026-09-05 实测

```bash
droid exec --auto low --model "custom:DeepSeek-V4-Flash---Anthropic-6" "<编辑指令>"
```

**踩坑记录（重要）**：默认模型 `gpt-5.6-sol` 在当前账号/地区策略下不可用，报
`HTTP 400: Provider not available in this region`（`droid doctor` 能诊断出这个具体
report，日常报错本身只说 `Exec failed`，看不出原因，必须跑 `droid doctor` 才知道是模型
区域限制而不是网络/鉴权问题）。**droid exec 必须显式 `--model custom:...-Anthropic-N`**
（或其它确认可用的模型），不能用默认值。`--auto low` 按预期只做了文件创建，未触碰其它内容。

## 4. T2 跨厂商复核

### 4a. multica-native（grok/kimi）
通过 multica issue 分派给 Grok Devil / Kimi CrossReview。

### 4b. direct-cli（crush）—— 2026-09-05 实测

```bash
crush run --model "zai/glm-5.3" --quiet "只复核以下改动是否有问题，不要修改任何文件：<diff>"
```

**踩坑记录**：
- `--yolo` / `-y`（--help 里写的自动批准权限参数）在当前安装的 crush v0.92.0 里**实测不可用**，
  报 `Unknown flag`/`Unknown shorthand flag`，无论放在 `run` 前后都一样——这是该版本的已知
  限制，不要在 SOP 里假设它能用。好在纯"只复核不改文件"的 prompt 本来就不会触发写权限确认，
  没有 `--yolo` 也能正常跑完。
- 模型参数必须是 `provider/model` 格式（如 `zai/glm-5.3`），裸模型名（如 `"glm"`）会报
  `Failed to override models: large model "glm" not found`；用 `crush models` 查真实标识。

## 5. Verifier（gate 脚本）

```bash
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
# 涉及代码/更广改动时按需加 ssot-guardian / gac-local-gate
```

只对本次 squad 产出的文件/目录跑，不要因为主工作树有无关并发改动就误判自己的产出有问题。

## 6. 人工 merge 审批

Squad A 不自动 merge。走到这一步后，产出（commit/diff）交给用户或独立 reviewer 决定是否
落地成真实 PR；这一步没有命令，是纪律，不是脚本。

## 7. 清理（演练/被拒绝的改动）

```bash
cd /Users/xiamingxing/Workspace
git worktree remove .claude/worktrees/<name> --force
git branch -D <branch>
```

## 8. Closeout

```bash
uv run --with pyyaml python bin/agent-workflow.py closeout <run_id> --status ok \
  --evidence "<一句话证据摘要>" --json
```

## 9. 结论

2026-09-05 完整跑通一次：claim 链路（start→affected-graph→claim）全部用真实命令验证通过；
T1(droid)/T2(crush) direct-cli 通道确认可用，但都有非默认参数的强制要求（见上）；worktree
隔离在有真实并发 agent 活动的情况下证明了其必要性；清理流程干净、无残留。
