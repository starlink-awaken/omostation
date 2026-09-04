---
title: eCOS 下一阶段独立 Agent 任务包
type: execution-plan
owner: 夏明星
created: 2026-08-01
updated: 2026-08-01
lifecycle: plan
strategy_ref: docs/STRATEGY-3YEAR-PANORAMA.md
last_updated: 2026-08-18
---

# eCOS 下一阶段独立 Agent 任务包

## 1. 目标

把战略 Stage A 与 Stage B 的第一批工作拆成三个可独立实施、独立测试、独立 PR 的任务包。
三个 Agent 可以并行执行，不共享 worktree，不修改相同的主要文件，不依赖对方的未合并代码。

共同原则：

- 每个 Agent 从真正的根仓 `omostation-root/main` 创建独立 worktree。
- 在根仓默认 remote 修复合并前，不得用当前 `gac-worktree.sh claim` 创建 worktree。
- 每个 Agent 必须运行 Agent Workflow，先 claim 路径再编辑。
- 不得修改主工作区 `/Users/xiamingxing/Workspace` 的脏文件。
- 不得直接写 `.omo` 治理状态；必须使用 OMO/C2G broker。
- 子模块修改必须先在子模块分支提交并推送，再提交根仓指针。
- 每个任务一个 PR；不得顺手重构其他项目。

## 2. 并行边界

| 任务包 | 目标 | 主要写入面 | 不得触碰 |
|---|---|---|---|
| A | 根仓身份与 worktree/PR 远端修复 | `bin/gac/gac-worktree.sh`、相关测试和 worktree 运维文档 | `.omo/goals`、project registry、Cockpit 子模块 |
| B | SSOT 与当前状态时间线归一 | project registry/generator、目标 broker、相关治理测试 | worktree 脚本、Cockpit UI/后端 |
| C | 工程交付黄金旅程产品面 | cockpit、cockpit-ui、专属 journey 集成测试、根仓子模块指针 | worktree 脚本、project registry、`.omo` 真相文件 |

合并顺序建议：A -> B -> C。三个 Agent 可以并行开发，但 C 在最终 rebase 时必须吸收 A 的远端修复。

## 3. 统一启动模板

在任务 A 合并前，三个 Agent 均使用以下方式创建 worktree：

```bash
cd "/Users/xiamingxing/Workspace"
git fetch "omostation-root" main
git worktree add "/Users/xiamingxing/ws-<agent-slug>" \
  -b "codex/<agent-slug>" "omostation-root/main"
cd "/Users/xiamingxing/ws-<agent-slug>"
git submodule update --init projects/ecos projects/omo projects/cockpit projects/agora scripts
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
```

推送与 PR 必须显式指定根仓：

```bash
git push -u "omostation-root" "codex/<agent-slug>"
gh pr create --repo "starlink-awaken/omostation" \
  --base main --head "codex/<agent-slug>"
```

## 4. 任务包 A：根仓身份与 Worktree/PR 远端修复

### 4.1 业务结果

无论本地 `origin` 指向什么仓库，根仓 worktree、push、PR 和 merge 都只能针对
`starlink-awaken/omostation`。发现远端身份不匹配时必须 fail closed，不得继续创建错误基线。

### 4.2 建议分支

`codex/root-remote-worktree-identity`

### 4.3 允许写入

- `bin/gac/gac-worktree.sh`
- `bin/gac/` 下新建的远端身份解析辅助脚本
- `tests/` 下专属 worktree remote 测试
- `docs/operations/worktree-hygiene.md`
- 必要时更新 `AGENTS.md` 中的命令示例，但不改动架构或任务状态

### 4.4 设计要求

1. 定义 canonical root remote 解析顺序：显式参数或环境变量 -> 配置项 -> URL 匹配 -> fail closed。
2. URL 必须匹配 `starlink-awaken/omostation`，不能把 `omostation-runtime` 当根仓。
3. `claim`、`submit`、`merge` 使用同一个解析结果，不能各自推断。
4. 输出中显示实际 remote、URL、base ref 和目标仓库。
5. 为“origin 错、omostation-root 对”“只有正确 origin”“没有正确 remote”建立测试。
6. 不自动修改用户 git remote 配置；只做显式解析和阻断。

### 4.5 Agent Workflow

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" start project-code-change \
  --profile engineering-agent \
  --objective "修复根仓 worktree/PR 对 canonical remote 的错误假设并 fail closed"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "bin/gac/gac-worktree.sh"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "tests"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "docs/operations/worktree-hygiene.md"
```

### 4.6 验收

- 错误 `origin=omostation-runtime` 时解析到正确根仓 remote，或明确失败。
- 不再出现从 runtime `origin/main` 创建根仓 worktree。
- 测试覆盖三种 remote 拓扑。
- `make gac-local-gate` 通过。
- Agent Workflow verify/closeout 完成。

### 4.7 可直接交给 Agent 的指令

```text
你负责 eCOS 任务包 A：根仓身份与 Worktree/PR 远端修复。

工作区根目录是 /Users/xiamingxing/Workspace。先阅读根 AGENTS.md、CLAUDE.md、
docs/proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md 的任务包 A。

重要事实：当前根仓 origin 指向 omostation-runtime，真正根仓 remote 是 omostation-root。
不要使用现有 gac-worktree.sh claim 创建 worktree；从 omostation-root/main 手工创建
/Users/xiamingxing/ws-root-remote-worktree-identity，分支 codex/root-remote-worktree-identity。

严格执行 bootstrap -> status -> start project-code-change -> claim -> edit/test -> verify -> closeout。
只修改任务包 A 允许的文件。实现 canonical root remote 解析、URL 身份校验和 fail-closed，
确保 claim/submit/merge 使用同一 remote。不要自动改用户 git config。

补充可重复测试，运行 targeted tests、make gac-local-gate。提交后显式 push 到
omostation-root，并为 starlink-awaken/omostation 创建 PR。报告 commit、PR、测试和残余风险。
不要合并其他 Agent 的分支，不要修改 Cockpit、project registry 或 .omo goals。
```

## 5. 任务包 B：SSOT 与当前状态时间线归一

### 5.1 业务结果

项目注册、当前目标、当前 Phase、任务 registry 和派生文档共享同一时间线。动态数量不再依赖
长期手抄；当 current goals 与 system state 不一致时，门禁能发现并给出修复路径。

### 5.2 建议分支

`codex/ssot-current-state-convergence`

### 5.3 允许写入

- `docs/project-registry.yaml`
- `bin/mof/gen-project-registry.py`
- `bin/ssot/` 下直接相关的 registry/doc SSOT 校验器
- `.omo/_truth/registry/` 下必要的生成规则或 schema
- `projects/omo/` 中目标/状态 broker 与测试
- 通过 broker 产生的 `.omo/goals/current.yaml`、task registry 或审计证据
- 专属测试与最小运维文档

### 5.4 设计要求

1. 区分项目、子模块、内置实现和外部 capability，不再用一个总数表达不同对象。
2. BOS、工具、项目等动态数量由生成器读取权威源并校验，Markdown 继续只放指针。
3. 建立 current goals 与 current phase 的一致性检查。
4. 已完成的历史 Bet 不得继续伪装成 current active goal。
5. 没有 active task 时应明确进入 waiting-for-scenario/next-bet 状态，而不是保留陈旧目标。
6. 所有 `.omo` 变更必须通过 OMO/C2G broker；没有 broker 时先补 broker 和审计测试。
7. 不把本战略中的阶段计划直接手抄成运行事实；只登记已批准且有 owner 的近期工作。

### 5.5 Agent Workflow

该任务涉及治理状态，应使用 `governance-state-mutation`：

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" start governance-state-mutation \
  --profile governance-agent \
  --objective "归一项目注册、current goals、current phase 与任务 registry 时间线"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "docs/project-registry.yaml"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "bin/mof/gen-project-registry.py"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "projects/omo"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path ".omo/goals/current.yaml"
```

### 5.6 验收

- project registry 的分类和生成结果与物理仓库、内置实现和 capability registry 一致。
- current goals 不再以旧完成项作为当前执行计划。
- current phase、active task、current goal 的不一致会使检查失败。
- OMO broker 有审计证据，未出现 direct `.omo` write 违规。
- `doc-ssot-lint`、`ssot-guardian`、targeted tests、`make gac-local-gate` 通过。

### 5.7 可直接交给 Agent 的指令

```text
你负责 eCOS 任务包 B：SSOT 与当前状态时间线归一。

先阅读 /Users/xiamingxing/Workspace/AGENTS.md、CLAUDE.md、ARCHITECTURE.md，
以及 docs/proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md 的任务包 B。

从 omostation-root/main 手工创建独立 worktree
/Users/xiamingxing/ws-ssot-current-state-convergence，分支
codex/ssot-current-state-convergence。不要使用尚未修复的 gac-worktree.sh claim。

执行 bootstrap -> status -> start governance-state-mutation --profile governance-agent -> claim。
先核验再修改：区分 project/submodule/implemented-in-bin/toolbox capability，追踪
project-registry、system.yaml、goals/current.yaml 和 task registry 的真实生成链。

禁止直接编辑 .omo 状态来改数字。必须使用已有 OMO/C2G broker；若没有满足需求的 broker，
先在 projects/omo 补最小 broker、审计和测试，再通过 broker 生成变更。

增加 current goal/current phase/active task 一致性门禁，清除历史完成项伪装 current goal 的问题。
只修改任务包 B 的允许路径，不碰 worktree 脚本和 Cockpit。

运行 doc-ssot-lint、ssot-guardian、相关单测和 make gac-local-gate，完成 verify/closeout。
提交后 push 到 omostation-root，为 starlink-awaken/omostation 创建独立 PR，并报告证据。
```

## 6. 任务包 C：工程交付黄金旅程产品面

### 6.1 业务结果

用户在 Cockpit 中能看到一次工程任务从意图、workflow、worktree、验证、PR、合并到 evidence 的
完整状态，并能区分 live、stale、failed、unavailable。UI 不再用随机或默认运行数据制造假绿。

### 6.2 建议分支

`codex/cockpit-delivery-golden-journey`

### 6.3 允许写入

- `projects/cockpit/`
- `projects/cockpit-ui/`
- `tests/integration/delivery_journey/`
- 根仓对应的两个子模块指针
- 与该旅程直接相关的 Cockpit 文档

### 6.4 设计要求

1. 定义统一 `DeliveryJourney` 只读投影，至少包含 intent/task/run/worktree/verification/PR/evidence。
2. 投影读取现有 OMO、Agent Workflow 和 Git/PR 证据，不创建第二套任务状态机。
3. Cockpit 提供 API 和 UI；AI 入口仍通过 Agora，不新增顶层 MCP server。
4. 数据必须携带 `source`、`freshness`、`status` 和 `last_updated`。
5. API 不可用时 UI 显示 unavailable，不保留随机 health/request/error 曲线作为真实数据。
6. 建立一个不会发起真实生产变更的端到端 fixture，覆盖 pending -> running -> verified -> merged。
7. 用户可从失败节点打开来源、证据或恢复动作，不写大段功能说明文字。

### 6.5 Agent Workflow 与子模块规则

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" start project-code-change \
  --profile engineering-agent \
  --objective "实现 Cockpit 工程交付黄金旅程只读投影、API、UI 与端到端验证"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "projects/cockpit"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "projects/cockpit-ui"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> \
  --path "tests/integration/delivery_journey"
```

在两个子模块中分别创建 `codex/cockpit-delivery-golden-journey` 分支，先提交和推送子模块，
再在根仓提交 gitlink 指针。不得在 detached HEAD 上留下不可达 commit。

### 6.6 验收

- API 能基于 fixture 返回一条完整旅程，且没有第二套任务状态。
- UI 能显示每个阶段、来源、新鲜度、失败原因和恢复入口。
- 后端不可用时没有伪造 live 指标。
- Cockpit targeted pytest、Cockpit UI lint/typecheck/build、journey integration test 通过。
- 根仓 submodule reachability、Agent Workflow verify/closeout、`make gac-local-gate` 通过。

### 6.7 可直接交给 Agent 的指令

```text
你负责 eCOS 任务包 C：工程交付黄金旅程产品面。

先阅读根 AGENTS.md、CLAUDE.md，projects/cockpit 与 projects/cockpit-ui 的 AGENTS.md，
以及 docs/proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md 的任务包 C。

从 omostation-root/main 手工创建根 worktree
/Users/xiamingxing/ws-cockpit-delivery-golden-journey，分支
codex/cockpit-delivery-golden-journey。初始化 cockpit、cockpit-ui、omo、agora 子模块。

执行 bootstrap -> status -> start project-code-change -> claim。分别在 cockpit 和 cockpit-ui
子模块创建同名 codex 分支，禁止在 detached HEAD 提交。

实现 DeliveryJourney 只读投影：复用 OMO、Agent Workflow、Git/PR 和 evidence 事实，
不要创建第二套任务数据库。提供 Cockpit API 与正式 UI，显示 source/freshness/status/last_updated。
后端不可用时显示 unavailable，删除或隔离随机/默认运行指标，禁止假绿。

增加 pending -> running -> verified -> merged 的安全 fixture E2E。只修改任务包 C 允许路径，
不碰 worktree 脚本、project registry 和 .omo 状态真相。

运行 Cockpit pytest、UI lint/typecheck/build、journey integration、submodule reachability 和
make gac-local-gate，完成 verify/closeout。先推两个子模块分支，再提交根仓指针，最后显式
push 到 omostation-root 并创建 starlink-awaken/omostation PR。报告三个 commit/PR、测试和风险。
```

## 7. 集成与合并检查

三个 PR 全部就绪后，由集成人执行：

1. 先合并 A，验证新 worktree 命令解析到 canonical root remote。
2. B、C 分别 rebase 最新 `omostation-root/main`，禁止在共享主工作区处理冲突。
3. 合并 B，运行 registry/current-state 一致性门禁。
4. 合并 C，运行 Cockpit、UI、journey E2E 和根仓全量门禁。
5. 核验 main 上的 submodule commit 全部远端可达。
6. 将三项真实结果回填 OMO evidence 和战略执行复盘，不手工修改健康分。

完成定义：三个 PR 均合并，主仓门禁通过，工作区没有不可达 submodule commit，Cockpit 能展示
一条真实或 fixture 化但事实一致的交付旅程，后续新 Agent 默认不会再从错误 remote 创建 worktree。
