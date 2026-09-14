---
title: omostation 2026-09-03 至 2026-09-14 治理交付轮深度复盘
status: completed
lifecycle: ephemeral
owner: governance-team
last-reviewed: 2026-09-14
type: ephemeral
---

# omostation 2026-09-03 至 2026-09-14 治理交付轮深度复盘

> 来源说明：母会话仅下发了骨架（frontmatter + 章节约定 §0–§7），未附“上一轮 general
> 兜底稿”全文，worktree 内亦检索不到该草稿。为不虚构原文，本文件由落盘 subagent
> 按 git 证据重建撰写，不冒充“原样写入”。证据命令与时间戳见 §0。
> 上一轮复盘发起时间戳（母会话提供）：2026-09-14T02:17:20Z。

## §0 范围与口径

- 时间窗：2026-09-03 → 2026-09-14（UTC）。
- 证据命令（在隔离 worktree 内执行，已 `git fetch origin main`）：
  - `git log origin/main --since="2026-09-03" --until="2026-09-15" --oneline`
  - `git log origin/main --since="2026-09-03" --until="2026-09-15" --oneline | wc -l`
- 文档约定：相对链接，不硬编码健康分/测试数/端口等易变数值；PR 编号仅作可验证指针，
  详情以 `gh pr view <号>` 为准。
- 归档位置约定：`type: ephemeral + status: completed` 的一次性文档归档到
  `.omo/_knowledge/design/plans/archive/`，顶层不再留存。

## §1 目标 vs 实际

- 本轮是多轨道并发交付轮：BET 台账 closeout、panorama 全景驾驶舱、scene/keeper
  保活、A2A 委派、aetherforge/记忆管线、子模块与远端卫生，均有合入。
- 实际：证据窗内 `origin/main` 新增约三 dozen 个提交（含 PR 合并与 ledger/pointer
  直接合入），无整轮级目标落空的可观测信号；收尾以 ledger `→ done` 条目批量落地。
- 偏差：部分“修复”提交是对并发协作副作用的自愈（如远端污染、指针漂移），属于
  计划外但必要的治理成本，见 §3。

## §2 分轨道交付

- **BET closeout 轨**：T4-07（SMTP 凭据模板 + retro）、T6-25、T6-27（Entity-Aware
  Chunking + SHACL）、T7-03、T7-07（continual-harness-refine）、T10-163、T10-165
  （Role registry + Capsule）、T5-05（candidate→done，DecisionGraphViewer）等多
  条目经 ledger 进入 `done`，见 `git log --grep="chore(ledger)"`。
- **Panorama 轨**：Phase A（经验建模）→ A+B（技能清单）→ C（经验图谱遍历）→
  v4（20 采集器）→ v5（采集器全覆盖）→ strategic overview drill-down，迭代节奏密，
  属本轮最连贯的功能线。
- **Scene/保活轨**：`service-keeper.py`（Agora/Cockpit/KOS 保活）、signal-poller
  watermark 修复、scene→personal_episode 内核桥接、applenotes connector 接入。
- ** Mesh/记忆/推理轨**：T8-22（TinyBOS P2P mesh codec）、T6-28（四级认知阶梯 +
  Radix 热缓存）、T6-29（Bionic 双相记忆巩固）、T8-23（Resident Flight Deck
  L1–L4 授权网关）。
- **协议轨**：T5-03 A2A 双向任务委派 + Observatory BOS 服务接入；BOS orphan
  清理 + verifier hardening。
- **指针/子模块轨**：cockpit-ui 多次 bump（DecisionGraphViewer、i18n + WCAG）、
  omo pointer bump（批次 33/34）、omlxc 注册 gpt-oss:20b。

## §3 阻塞链与根因修复

- **远端污染链**：主仓 origin 曾被改写为子模块 URL（并发会话串联覆盖），一切
  origin/main 验证静默失效。根因定位到旧 bash 版 `fix-remotes.sh`
  （worktree 下 `[ -d .git ]` 恒 false；未初始化子模块 `git -C` 上解析写主仓
  config）。已 Python 重写（`fix-remotes.py`，sh 为 shim），并固化三层约束：
  post-checkout 自愈 + pre-push 阻断 + cron 巡检。详见 `AGENTS.md` § worktree
  子模块与 remote 完整性。
- **指针漂移链**：worktree claim 默认全量 init 子模块；快速路径与直创路径由
  post-checkout 守卫兜底做本地无网络对齐（只动子模块工作树，不改根指针）。
- **rebase 风险链**：本地 commit 基于旧 main 时 `pull --rebase` 可能丢改动，
  约定 rebase 后用 `git reflog` 确认；动手前先查 main 是否已自愈
  （PITFALL-GAT-006），只用内容 diff 判等价。
- **ledger 插入链**：禁止按行号盲插（bets 序列被顶层键切断），统一用
  `ledger-safe-insert.py --dry-run` 先行校验。

## §4 CI 红与合规红

- 本复盘落盘时未拉取本轮 CI 全量红单（证据仅为 git log）；已知并已在仓内固化的
  高频红因（`AGENTS.md` §7 与实证）：
  - frontmatter `last-reviewed` 用非 UTC 当天/未来日期 → gac-gate FAIL。
  - `ci-surfaces` 自引用路径与 workflow `on.paths` 严格匹配问题。
  - `set -e` 静默中断、`uv.lock` 被忽略、缺模块等常规红（见 ci-red-triage skill）。
- 本文件 frontmatter 已按 UTC 当天（2026-09-14）填写，归档路径符合 T6-17 约定，
  落盘后以 `agent-workflow.py compliance`（至少）取证，红则停住报红、不强合。

## §5 流程债务

1. **并发自愈成本高**：远端/指针/hook 回退类问题反复出现（#3282 回退 #3277 类
   同名 BET 并行交付回退），说明“改 canonical 前先 `git fetch` 查 main 是否已含
   目标内容”仍靠人工自觉，需继续硬化为 hook/CI。
2. **manifest 全量扫描纪律**：改 hook 脚本路径必须扫描 manifest 全部 hook 段，
   历史上只改一段导致静默失效，需 checklist 化。
3. **元数据路径纪律**：worktree 下禁用 `--git-dir` 读 hooks 元数据，统一用
   `--git-common-dir`，已文档化但仍需新 agent onboarding 时强调。
4. **复盘交接断层**：本轮即实例——母会话引用“上一轮全文/兜底稿”但未随任务下发，
   子代理只能按证据重建。建议：复盘任务必须附全文或文件指针，禁止只传章节约定。
5. **数值硬编码**：文档 SSOT 合同已禁止在 Markdown 硬编码阶段/分数/计数/端口，
   本文件遵守；存量文档仍需巡检。

## §6 口径说明

- “交付数”口径 = 证据窗内 `origin/main` 提交数（含合并与直接合入），不等于 BET
  关闭数；BET 关闭以 ledger `→ done` 条目为准。
- PR 编号（如 #37xx 段）为 git log 可观测指针，不在此复述标题以外的断言；核验
  用 `gh pr view`。
- 时间口径均为 UTC；`last-reviewed` 取落盘当天（2026-09-14），满足 gac-gate
  “当天或更早”要求。
- 本复盘为一次性 `ephemeral/completed` 文档，归档后顶层不留存，引用方请用归档路径。

## §7 下一步

1. 复盘交接规范化：要求复盘任务携带全文或仓内指针（§5-4），可进 `AGENTS.md`
   Common Pitfalls 或 retro checklist。
2. 并行交付防回退：claim/start 前的 `git fetch + 内容 diff` 检查保持人工纪律，
   评估是否值得做成 `gac-worktree.sh claim` 的自动前置。
3. 远端卫生三层约束已落地，求观察一轮 cron 日志
  （`runtime/cron/remote-hygiene.log`）确认零污染后再降级为纯巡检。
4. panorama v5 之后的全景采集器覆盖率与 skill 清单消费方（cockpit/agora）对接，
   建议下一轮复盘单列一节。
5. 本文件 PR 合并后，母会话可按归档引用约定更新索引指针。
