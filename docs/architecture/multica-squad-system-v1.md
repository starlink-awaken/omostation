---
status: draft
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-05
title: multica Squad System v1 — 日常工程协作轨道
type: doc
---

# multica Squad System v1 — 日常工程协作轨道

> 文档 SSOT：本文档是 multica 日常协作轨道的**功能规格文档**（stable architecture contract）。
> 配额观察数据 → `.agents/skills/multica-squad-ops/quota-ledger.yaml`（运行时台账，非本文档维护）。
> 操作手册 → `.agents/skills/multica-squad-ops/SKILL.md`。
> multica 官方概念参考 → `multica <command> --help`（workspace/agent/squad/issue/autopilot/runtime）。
> 创建：2026-09-05 · Owner: governance-team

## 1. 定位与红线（必须先读）

`multica` 在本仓库已有一条**既有窄路径**：`projects/omo/src/omo/resident/executor.py::_execute_multica`
把它硬编码限定为 **R3 高危动作专用后端**（`deploy_production`/`delete_data`/`push_main`），
默认执行 agent 固定为 `Mika`（`execute.py:32`，`runtime_mode=local`）。**这条路径本文档不修改、不复用。**

本文档定义的是**第二条、物理隔离的使用轨道**：直接使用 multica 自身的
workspace/squad/issue/autopilot 概念做**日常工程协作**（批量编辑、跨厂商复核、调研、监控），
不经过 resident executor。两条轨道靠"不同 agent、不同职责边界"隔离，不共用 `Mika` 这个执行体。

**红线（对齐 `docs/plans/2026-09-04-architecture-analysis-and-requirements-consolidation.md` 的裁定）**：

1. multica 侧任何 issue 的自动执行，前置条件必须是 ADR-0203 已完成
   `bin/agent-workflow.py start --bet ... && claim`；autopilot job 第一步校验 claim token
   存在，不存在直接 fail-fast。**不允许 multica squad 自主发起工作、绕过 workflow claim。**
2. multica squad **不是**第二个控制面。它是 workflow governance + resident runtime + BOS route
   这个统一控制面下的一个**执行适配层**（与 local/pi-worker/orca 并列），职责边界见
   `docs/plans/2026-09-04-architecture-analysis-and-requirements-consolidation.md` §6。
3. `~/.claude/agents`（PAI 自定义 agent：Forge/Anvil/Cato 等）与本文档定义的 multica squad
   **分层独立，不打通**：PAI agents 仅在 Claude Code 单会话内通过 Agent 工具调用；
   multica squad 专管跨工具、跨会话的异步自动化。二者概念对齐（命名/角色类比）但配置不合并。

## 2. 能力分层（Tier）—— 不是"一个工具一个固定角色"

固定角色矩阵（如 BDSK 四角）适合"治理决策"场景——角色本身就是治理语义，不该变。
但 15+ 个 CLI 工具做日常工程协作时，工具背后的模型会变、同层里有多个候选、
谁来做应该看当前谁有空/谁没超额度，而不是写死。因此本轨道把"角色"拆成两层：

- **能力分层（Tier，相对稳定）**：见下表。
- **分派评分（运行时算）**：见 §3 配额动态策略。

| Tier | 定位 | 成员（本机已确认模型，2026-09-05 核实） |
|---|---|---|
| T0 重推理/长上下文架构层 | 复杂设计、跨文件影响判断 | claude（Sonnet 5/Opus）、codex（gpt-5.3-codex-spark，128万 token）、**agy**（Google Antigravity，Squad E 灾备——`agy models` 显示 Gemini 3.8/3.7/3.6 Flash + Gemini 3.1 Pro，还能切 Claude Sonnet/Opus 4.6(thinking) 和 gpt-oss-120b，本身是个多模型网关） |
| T1 快速批量机械编辑层 | 大面积规则性改动、格式化、样板代码 | codebuddy（deepseek-v4-flash/kimi-k3，multica-native）、reasonix（deepseek-v4-flash，multica-native）、opencode 的 `build` agent（deepseek-v4-flash，multica-native）、**droid**（多模型池，**direct-cli**，见 §4a）、**copilot**（GPT-5.6 Luna via GitHub Copilot CLI，Squad E 灾备，独立 quota 池）、**hermes**（deepseek-v4-flash via opencode-go，Squad E 灾备，独立 quota 池） |
| T2 跨厂商对抗复核层 | 复刻 Cato"跨厂商盲点"设计动机，专挑与实现者不同厂商 | grok（xAI grok-4.6，multica-native）、kimi（Moonshot，multica-native）、**crush**（智谱 GLM，**direct-cli**，见 §4a）、**qoderclicn**（阿里 Qwen3.8-Max/Flash，Squad E 灾备——2026-09-05 实测已触发一次"credit usage limit"，是本方案第一笔真实配额观测数据） |
| T3 本地/隐私计算层 | 敏感内容不出网，走 omlxc 网关 | oh-my-pi（omp）、pi、opencode 的 `omlxc-local` agent（均 multica-native） |
| T4 只读观察层 | 状态监控，绑定 `external-readonly-agent` 画像，禁止写 | 现有 Codex Observer + Codebuddy Observer（multica-native）。crush 无 multica-native runtime，其健康状态走 quota-ledger 的 direct-cli 观测，不设专门 Observer agent（此前设想的"新增 Crush Observer"已更正为不可行） |
| T5 人工 GUI 层（明确排除自动化） | 无 CLI surface 或协议不兼容，不接入 squad/autopilot | traesolo（仅 GUI App）、zcode（GUI + 独立 CLI 运行时目录未入 PATH） |
| 搁置/待修复 | kilocode 有 ACP server 但用户不特别在意，2026-09-05 决定不再主动推进；qwen 认证过期(`401 invalid access token`)，需用户重新登录后才能定级 | kilocode（`role: unclassified`）、qwen（认证失效） |

**两种接入方式并存**：`multica-native` 的 runtime 走 multica 自身的 issue/agent/squad 状态机
（GUI 里看得到）；`direct-cli` 的工具不经过 multica，由 Squad leader 直接 subprocess 调用其
自己的非交互命令（GUI 里看不到这类任务，只在本地 orchestration 日志里可见）——两者的治理约束
（claim 前置、worktree 隔离、per-commit 身份）完全一致，只是"谁来发起调用"不同。

## 3. 动态配额策略

15+ 个 runtime 背后是不同订阅/账号（Anthropic、xAI、Moonshot、火山方舟等），限额类型不统一
（次数/token/并发），且大部分不通过 aetherforge 网关，不能整体复用网关的 quota engine。分两条腿走：

- **能自动探测的**（走 omlxc/aetherforge 网关代理的 runtime：oh-my-pi/pi/opencode 的
  `omlxc-local` agent）：直接复用 `projects/aetherforge/packages/gateway/src/llm_gateway/`
  里已有的 quota/budget/熔断模块，不新写代码。
- **不能自动探测的**（多数直连 vendor API 的 CLI）：`.agents/skills/multica-squad-ops/quota-ledger.yaml`
  记录观察到的额度耗尽信号，熔断降级规则见该文件内注释。台账由 T4 观察层在任务失败/异常时
  半自动回写，不要求一开始穷举官方限额（多数订阅制工具没有公开 quota API）。
- **分派评分权重**：借鉴 `projects/aetherforge/src/aetherforge/route/policies/RP-BALANCED.yaml`
  （cost 0.35/speed 0.25/quota 0.25/affinity 0.15），本场景多数工具订阅制而非按 token 计费，
  quota 信号比 cost 更关键：`quota 0.35 / capability-affinity 0.30 / speed 0.20 / cost 0.15`。

## 4. Runtime 协议兼容性核实（2026-09-05 实测）

`multica runtime profile create --protocol-family` 支持的枚举（实测取得，非文档推测）：

```
claude, codebuddy, codex, copilot, opencode, codearts, deveco, openclaw, hermes,
pi, cursor, kimi, reasonix, dsh, kiro, antigravity, qoder, qoderclicn, traecli,
grok, qwen, qwenpaw, mcode, dim, zeroclaw
```

对照本机三个待接入工具：

| 工具 | 自身协议探测结果 | 结论 |
|---|---|---|
| `kilocode` | `kilo acp` 子命令明确提供 ACP (Agent Client Protocol) server；底层引擎与 opencode 同源 | **可能兼容**，但 multica 枚举里没有名为 "kilocode" 的 family，需要用某个未识别 family（如 `openclaw`/`zeroclaw`/`dsh`/`mcode`/`dim`，本次未能确认其真实含义）做实际路由测试才能验证，测试本身会产生一次真实调用（可能消耗额度），本轮未执行 |
| `crush` | 顶层 `--help` 未见 ACP/agent-protocol 相关子命令；`crush server` 是自有 socket 服务，非确认的 ACP | **未发现兼容路径**，不建议现在接入 |
| `droid` | 顶层 `--help` 未见 ACP/agent-protocol 相关子命令 | **未发现兼容路径**，不建议现在接入 |

**结论**：droid/crush 没有找到与 multica 协议枚举匹配的证据，**不勉强凑协议**，改走 §4a
"direct-cli 兜底通道"——直接用它们自己的非交互命令，不经过 multica 的 runtime 抽象层。
`multica runtime profile create` 本身只做本地元数据校验（协议名合法即可创建成功），**不会**
在创建时验证目标命令是否真的说得通对应协议——所以"创建成功"不等于"能用"，本方案不采用
"硬凑协议名"这条路。

## 4a. Direct-CLI 兜底通道（droid / crush / kilocode 实测确认可用）

三个工具都有成熟的非交互执行模式，2026-09-05 实测 `--help` 确认：

| 工具 | 非交互命令 | 关键参数 | 风险闸门 |
|---|---|---|---|
| `droid` | `droid exec [--auto <level>] --model <id> "<prompt>"` | `--auto low\|medium\|high`、`-w/--worktree [name]`（**原生支持自动建 git worktree**）、`--output-format json` | **只允许 `--auto low` 或 `--auto medium`**；`--auto high`（含 git push/生产变更）和 `--skip-permissions-unsafe` 禁止使用——那是 R3 executor 的地盘，不归本轨道 |
| `crush` | `crush run --model <id> "<prompt>"` | `--yolo`（自动批准全部权限，用于非交互跑通）、`--cwd <path>` | 仅用于**只读复核类** prompt（Squad A/B 的 T2 角色），prompt 里显式要求"只给意见不改文件"；不依赖技术层面的写权限拦截，靠任务边界约束 |
| `kilocode` | `kilo run --format json --model <provider/model> "<message>"` | `--auto`（布尔，"危险"批准全部权限）、`--dir <path>` | 暂不设 `--auto`（宁可交互卡住也不无脑放权）；仅用于 T0 实验性只读探测，不进生产 squad |

调用方（Squad leader，当前即 Claude Code 本 session）通过 `Bash` 直接 subprocess 调用这些命令，
把 stdout 结果当作该 Tier worker 的产出，纳入 Squad A 的批量编辑/复核流程；隔离与身份规则同
§1 红线（worktree 隔离、per-commit 身份、claim 前置），与是否经过 multica 无关。

## 5. 七个 Squad

**已在真实 multica workspace（天狼星）创建（2026-09-05；Squad E 为同日追加，Squad F/G 为同日第三轮追加）：**

| Squad | ID | Leader | Members |
|---|---|---|---|
| 交付流水线小队 | `1fb3f53f-f39e-49c9-8468-98c9a2b106ce` | Claude Lead | Codebuddy Batch(t1-batch-primary)、Reasonix Batch(t1-batch-fallback)、Opencode Batch(t1-batch-alt)、Pi Local(t3-local-batch)、OMP Local(t3-local-batch-alt)、Grok Devil(t2-cross-review)、Kimi CrossReview(t2-cross-review-alt) |
| 架构评审小队 | `b75cae0f-14cd-4587-b085-427d2ce026be` | Claude Lead | Codex Sage(sage)、Grok Devil(devil)、Kimi CrossReview(keeper-alt) |
| 研究情报小队 | `cc996379-5f57-4c0d-8492-43adeb49deaa` | Claude Lead | Kimi CrossReview(researcher)、Codex Sage(researcher-longctx) |
| 运维监控小队 | `17860295-eb32-448b-a573-c4bc235c458a` | Claude Lead | Codex Observer(observer)、Codebuddy Observer(observer，均复用已有 agent) |
| 供应链多样性小队 | `ddf35bb1-ed92-43b8-adb7-309e9aec61db` | Claude Lead | Agy Architect(t0-backup)、Copilot Batch(t1-backup)、Hermes Batch(t1-backup)、Qoder CrossReview(t2-backup) |
| **文档与内容小队**（新） | `767c6633-b06c-4bfb-bed8-7d66452b8f28` | Claude Lead | Codebuddy Batch(drafter)、Kimi CrossReview(proofreader，均复用已有 agent) |
| **个人隐私小队**（新） | `c823dda0-b886-45c2-93ee-0600af73222e` | Claude Lead | Pi Local(primary)、OMP Local(fallback，均复用已有 agent) |

Agent ID: Claude Lead `eb03768b-c602-4d0d-8bc2-e50a9bbbf569`、Codex Sage `2f61218c-a46e-4ba4-95df-66f0b753a989`、
Grok Devil `c3436490-1d2d-466b-9516-2168f4c53ff2`、Kimi CrossReview `57cfed41-b3b4-488e-8b55-fff6d91a00ab`、
Codebuddy Batch `2ae6b24f-e2b9-4fcf-b453-22cc2f56cc74`、Reasonix Batch `be4110e3-59ca-423e-a3b7-39adcfad198b`、
Opencode Batch `60452951-1905-4ddc-8c7a-4e70aa6d8b9f`、Pi Local `9b7c543b-1726-4c40-9a66-54d940c4fe9a`、
OMP Local `f7487e6e-f690-4798-9fb4-84804c093c48`、Agy Architect `d3778597-a940-42f9-a741-5557626716ee`、
Copilot Batch `29d528e7-9540-40ca-95a0-8726e1228414`、Hermes Batch `8c7c7ccc-dd68-495b-9be7-4c5edd50a966`、
Qoder CrossReview `42092e81-1490-46c4-9de2-2061ad71e51d`。
均为 `permission-mode: private`，只能被 leader/squad 内部调用，不对外公开；全部挂了 `multica-squad-ops` skill，
7 个直接干活的 agent（Leader/Sage/Devil/CrossReview/三个原生 Batch worker）额外挂了 codebase-memory-mcp/gitnexus/serena，
Squad E 的 4 个灾备 agent 挂了 codebase-memory-mcp/gitnexus。

**Squad A · 交付流水线小队（第一阶段上线，唯一允许 autopilot）**
- Leader: 新建 agent，绑定 `claude` runtime（persona 命名 "Claude Lead"）
- Members: T1 当值 1-2 个（按配额台账动态选）→ T2 任选 1 个跨厂商复核 →
  Verifier（非 LLM，直接调 `make gac-local-gate` 等既有 gate 脚本）→ Closer: Claude（写 ADR/closeout）
- 强制前置：issue 必须已 `start --bet` + `claim`；autopilot job 第一步校验 claim token
- 强制隔离：改动在独立 worktree 内完成（`.omo/standards/multi-agent-worktree-collaboration.md`
  四步流程），per-commit `git -c user.name="squad-<runtime>"`，不改全局 git config
- 不自动 merge：PR 需人工审批

**Squad B · 架构评审小队（复用/升级 BDSK，仅建议不写代码）**
- Builder=Claude、Devil=Grok（跨厂商制造结构性质疑）、Sage=Codex（长上下文）、Keeper=Claude 或 Kimi
- 不替换、不新增第二条执行链：BDSK 现有唯一可执行链原样保留，本 squad 输出标记"补充意见"，
  不产生 `proof_state=proven`

**Squad C · 研究情报小队（只读并行调研，无写权限）**
- 借鉴 PAI Researcher 模式扩展到 multica 侧对应 runtime（kimi/codebuddy 等）
- 用 A2A 协议"并行扇出"模式（`a2a_send_task` 批量发起 + 轮询收集）汇聚结果

**Squad D · 运维监控小队（纯监控，扩展现有 2 个 Observer）**
- 现有 Codex Observer + Codebuddy Observer，绑定 `external-readonly-agent` 画像
  （`allowed_workflows: [observer-audit, handoff-resume, mof-state-bridge-audit]`，`can_write_lanes: []`）
- 并入 `multica-status.sh`（独立旁路脚本，见 §7），承担配额台账半自动回写

**Squad E · 供应链多样性小队（灾备/配额溢出候补，2026-09-05 新增）**
- 定位：不是又一个"干活"squad，是 Squad A/B 的**跨厂商备胎池**——当主力 runtime 触发
  `quota-ledger.yaml` 熔断规则（连续 2 次 exhaustion_signals）时，leader 按 tier 就近改派
  给本 squad 对应成员，同时天然提供第 3/4/5 家供应商的独立视角。
- Agy Architect（T0 备份，Google Gemini 家族，兼容 Claude/gpt-oss 多模型切换）
- Copilot Batch（T1 备份，GPT-5.6 Luna via GitHub Copilot CLI，与 codex 同为 OpenAI 家族但走
  独立 quota 池）
- Hermes Batch（T1 备份，deepseek-v4-flash via opencode-go，与其它 T1 worker 模型同源但
  quota 池独立，纯用于分流不换视角）
- Qoder CrossReview（T2 备份，阿里 Qwen3.8 家族，与 grok/kimi/crush 均不同源）——**2026-09-05
  实测已真实触发一次 `You've reached your credit usage limit`**，是本方案上线以来第一笔
  真实配额观测数据，已用 `record-quota-exhaustion.py` 记入台账（1/2，未到熔断阈值）
- 不自带 autopilot，只接受 leader 的溢出改派，不独立接单

**Squad F · 文档与内容小队（纯文字场景，2026-09-05 第三轮新增）**
- 定位：与 Squad A 的"改代码"场景区分开——README/ADR叙事/PR描述/changelog/知识库沉淀初稿
  这类纯文字任务，不需要 T1/T2 全套流水线，复用现有 agent 组一个轻量小队即可，不新建 agent。
- Drafter=Codebuddy Batch（复用）、Proofreader=Kimi CrossReview（复用）
- 涉及正式治理文档(.omo/standards、ADR)时仍需过 `doc-ssot-lint`，不因为"纯文档"跳过治理门禁

**Squad G · 个人隐私小队（个人/家庭/健康敏感场景，2026-09-05 第三轮新增）**
- 定位：与工程交付场景物理隔离——涉及 `family-hub`/健康/个人日志等个人敏感信息的任务，
  硬性规定只能用 T3 本地/隐私计算角色，禁止分派给任何云端 vendor 工具（不论
  multica-native 还是 direct-cli），哪怕是同类"批量编辑"任务
- Primary=Pi Local（复用）、Fallback=OMP Local（复用）
- 全程走 omlxc 本地网关，不联外网大模型 API

## 6. 落地状态（本轮实际执行情况）

- [x] 架构文档（本文档）
- [x] 操作手册 `.agents/skills/multica-squad-ops/SKILL.md`
- [x] 配额台账初始文件 `.agents/skills/multica-squad-ops/quota-ledger.yaml`
- [x] 4 个 squad 在真实 multica workspace 创建（用户已确认）
- [x] 各 squad leader/specialist agent（绑定各自 native runtime）创建
- [x] droid/crush/kilocode 确认为 direct-cli 兜底通道（不勉强凑 multica 协议），命令与风险闸门见 §4a
- [x] Squad A 端到端 dry-run 实测通过（2026-09-05）：ADR-0203 claim 链路（start→
      affected-graph→claim）、隔离 worktree、T1(droid direct-cli)、T2(crush direct-cli)、
      Verifier(doc-ssot-lint) 全部真实跑通一次，未落地（清理 worktree/分支，未 merge）。
      完整步骤、真实报错与解法见 `.agents/skills/multica-squad-ops/SOP-squad-a-delivery.md`。
- [ ] Squad A 真实 autopilot 接线（`multica autopilot create/trigger`）——本轮只验证了
      claim 链路本身，尚未把它接进 multica 的 autopilot 触发器；留待下一轮
- [x] Squad E 供应链多样性小队新增（2026-09-05 第二轮）：4 个新 agent 全部实测定级
- [x] 13 个 agent 全部换上完整的系统提示（身份/职责/边界/协作方式/治理红线），不再是
      一两句话的占位描述（2026-09-05 第三轮）
- [x] 7 个 squad 全部挂了 `instructions` 字段的工作准则（原先只有 `description`）
- [x] 新增 Squad F(文档与内容)、Squad G(个人隐私)，覆盖"纯文字"和"个人敏感信息"两个
      新场景边界；两队都复用已有 agent，未新建 CLI 工具接入
- [x] Squad E 供应链多样性小队新增（2026-09-05）：4 个新 agent（Agy Architect/Copilot
      Batch/Hermes Batch/Qoder CrossReview），全部实测定级、非猜测
- [x] copilot/hermes/agy/qoderclicn 完成真实定级探测；kilocode 决定搁置、qwen 认证过期待用户处理
- [x] `record-quota-exhaustion.py` 落地并用真实数据验证一次（qoderclicn 触发 credit
      usage limit，见 quota-ledger.yaml）
- [x] `droid-batch.sh` / `crush-review.sh` wrapper 脚本落地，焊死了 SOP 里踩出的正确
      模型参数
- [x] `multica-status.sh`（§7）落地，秒级查看 squad/agent/配额熔断状态（`make` 封装未落地，见 §7 说明）

## 7. multica-status —— 轻量旁路监控（不侵入 cockpit TUI）

`bin/omo-status`/`bin/omo-top` 的真实实现在 `projects/cockpit`（独立子仓，改它要走
子仓 PR/CI 流程，成本和"看一眼 squad 状态"这个需求不成比例）。因此新增
`.agents/skills/multica-squad-ops/multica-status.sh` 作为一个独立、轻量、只读的旁路
脚本，与 omo-status/omo-top **平级共存，不是替代品**：

```bash
bash .agents/skills/multica-squad-ops/multica-status.sh
```

输出 squad 列表+成员数、multica-squad-ops 相关 agent 状态、quota-ledger 熔断状态三段。

**`make multica-status` 这层封装暂未落地**：2026-09-05 曾往主工作树 `Makefile` 加过
一个 3 行 target，但主工作树当时有并发 agent 在活动（同一时段观察到 `bin/gac/gates.py`
等文件被并发改动），该编辑被后续覆写、静默丢失——这正是
`.omo/standards/multi-agent-worktree-collaboration.md` 警告的"文件回写拉锯"，问题出在
**直接改了共享文件却没走 worktree 隔离**，是本次操作自己的失误，不是并发 agent 的错。
没有跟着重打去抢这行 Makefile，脚本本身可直接运行，`make` 封装留给下一次走正式
worktree+PR 流程时顺手加上。
