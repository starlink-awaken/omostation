---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-17 复盘
type: retro
---

# BET-Y1Q2-T1-17 复盘

## 交付与真实回执

本轮把 Codex 从 Orca 中容易卡审批框的交互式 TUI，收口为受治理的非交互 worker。正式入口固定为
`codex exec --approve-for-me --ephemeral --ignore-user-config --json`；它使用 Codex 的自动审批和
`workspace-write` 沙箱，没有使用 `--dangerously-bypass-approvals-and-sandbox`。OMO 仍拥有任务写面与
完成判定，Orca 只负责 Run/Task/Dispatch 运输。

Codex 不直接写真实独立 clone。adapter 先建立一次性 execution clone，在副本中运行并审计 commit、
ignored write、symlink、gitlink、全局禁止路径和任务 allowlist；通过审计的 binary patch 才事务式应用回
真实 clone。原 clone 的 HEAD、branch、index 与既有 dirty path 内容都有指纹保护。patch、复核或回执
发布失败时反向 patch，并且只有确认恢复基线后才返回受控失败。

真实无人值守 smoke 返回精确标记 `OMO_CODEX_UNATTENDED_OK:T1-17:FINAL`，退出码为 0，过程中没有人工
点击。脱敏回执位于本机临时目录，`status=succeeded`、`approval=approve-for-me`、`changed_paths=[]`，
回执摘要 `d61bbe0f9482a6f1f8ba8d2fe47735850ed9c1feb713a8099e521aead57e4177` 可复算。第一次最终 smoke 因
独立 reviewer 同时更新本机 ignored evidence/运行验证而触发 `workspace_changed_during_execution`；它没有
发布成功回执，也没有写回候选 patch，证明并发门禁没有假绿。审查结束后的静止重跑才成功。

Orca 运输证据为 Run `run_4b94c900d493`、成功 Task `task_e9dbdaef80a5` 与 Dispatch
`ctx_873fca3fc81b`；查询结果为 task completed、worker outcome succeeded、dispatch completed、
failure_count=0。这里的 `worker_done` 只证明运输完成，不替代 OMO reviewer。独立 reviewer 最终结论为
CLEAR/APPROVE，无 CRITICAL/HIGH/MEDIUM。

## Q1 实际耗时 vs appetite？

约一天，符合 1 day appetite。主要耗时在 execution-clone 隔离、原 clone 并发指纹、patch/回执事务
回滚、真实 submodule 负测，以及 Orca 实际运输与 Codex 真实模型 smoke，不在 adapter 的基础 argv。

## Q2 done_when 是否全部通过？

全部通过：

1. 共享、linked、symlink 或身份不匹配 workspace 在 Codex 启动前拒绝；
2. 固定 argv、`shell=False`、敏感环境剥离、超时 process-group TERM→KILL→wait 均有负测；
3. 任务写面、commit、ignored、symlink、gitlink、并发 dirty path 与回滚边界均有真实 Git 测试；
4. 真实 read-only Codex smoke 零人工确认，marker 与脱敏回执均可验；
5. Orca Run/Task/Dispatch 可重放查询，独立 reviewer 直接复测 57 条根测试、27 条 OMO 门禁测试；
6. 只有 Codex 晋升为 L1 admitted，其他候选 worker 继续 declared/disabled。

## Q3 与计划不符的事实

1. 最初设计让 Codex 直接在独立 clone 的 `workspace-write` 沙箱运行；审查指出这仍把任务边界交给 prompt。
   最终改为 execution clone + 审计 patch，真实 clone 只接收经验证的差异。
2. 第一版只比较 dirty path 名称，无法发现同一路径内容被并发改写；最终加入按文件类型和内容摘要的完整
   指纹，并在有 delta 和无 delta 两条路径都重检。
3. 第一版 patch 已应用后，如果 post-check 或 receipt 发布失败，可能留下部分写入；最终改为先暂存回执、
   再应用 patch、最后 exclusive 发布，失败时回滚并确认基线。
4. Orca wrapper 两次因 shell 中 `$outcome` 被外层提前展开而没有正确注入完成事件，需要按原样重发。
   后续 Orca/控制器适配应传结构化 argv/JSON，禁止把 worker 回执拼成脆弱 shell 文本。
5. Claude 独立 review 的首次 worker 选择遇到默认模型 unavailable，第二次安全 Sonnet 运行超时；系统没有把
   这些失败冒充 review 成功，最终改由独立只读 reviewer 直接复测并形成版本外 evidence。

## Q4 净增减与必要性

新增一个 Python bounded adapter、一个定向测试文件、一个 admitted worker registry 条目及最小协作标准。
没有修改 Orca/Codex 用户配置，没有新增 scheduler、task database、Workflow Mesh 状态机、Ledger DDL、
模型路由或 UI。execution clone、binary patch、指纹和两阶段回执是防止无人值守 worker 污染真实 clone 所需
的最小事务边界，不是为未来预留的抽象层。

## Q5 后续提示

下一步不要立即把全部云模型都自动准入。先让这一条 Codex transport 在 3–5 个 L1 小任务中 dogfood，
观测 timeout、审批自动审查延迟、patch 拒绝率与 review 成本；再把同一 adapter-neutral receipt 合同扩给
OpenCode/Pi/OMP。Orca 需优先修复 shell-ready/TUI-ready/worker-done 的状态分层和结构化注入，避免再用
终端可见或字符串拼接充当任务已接收。CodexBar 继续只做额度 observation，不能自动改变 worker admission。
