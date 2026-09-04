---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-06 复盘
type: retro
---
# BET-Y1Q2-T1-06 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 9 小时墙钟时间（其中实现与返工约 2 小时），低于 2 days appetite，未超出。主要时间花在多 Agent 首轮返工、跨仓契约对齐、独立回归和 D0 远端可达性验证。

## Q2 done_when 是否全部通过？哪条没过，为什么？

按可信本地单用户的冻结范围，9/9 通过：ECOS 生成并校验同一组 `PolicyDecision` / `ActionReceipt` 契约；Agora 在公共 FastMCP 入口与 Proxy/MCP-stdio 终端适配器执行 PEP；OMO 使用真实 `MandateManager` 与 `LedgerBroker` 持久化 decision、started、terminal；失败路径保持 fail-closed；同进程 action/hash 重试不重复执行；只读路径不回归；未调用任何真实业务副作用。

证据：ECOS 81 个定向/编译测试通过；Agora 26 个 PEP 测试与 162 个 BOS/Proxy 回归测试通过；OMO 31 个新测试与 217 个 sovereignty 回归测试通过；跨仓真账本探针得到 `Decision.Policy.v1 → Action.Started.v1 → Action.Succeeded.v1`、provider 调用 1 次、hash chain `ok=true`；独立 reviewer 给出 APPROVE。

恶意同进程代码、跨主机、多进程并发 exactly-once、崩溃后自动 reconcile、后台/legacy 路由穷尽仍按 non_goals 延后，不计为本 BET 未通过。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. 单一 FastMCP hook 不能覆盖直接 Proxy/MCP-stdio 终端调用，最终采用“入口完成生命周期、终端适配器验证 ContextVar permit”的最小双层接线。
2. Agora 首轮实现曾在 provider 缺失时放行、复制本地模型并用内存事件冒充 Ledger；监督验收拒绝后才改为消费 ECOS 生成模型与 fail-closed 窄 SPI。说明 worker_done 不能替代独立 provider-call-count/ledger 证据。
3. 原台账写的是尚不存在的 Agora 测试路径，实际交付集中为 `tests/test_pep_integration.py`；closeout 前已回写 SSOT，避免 verify 命令假失败。
4. 子模块 commit/tag 仍不足以让根仓 D0 通过；`bump-pointer` 会校验 SHA 的远端可达性，因此必须先推独立子仓分支与 tag。
5. 外部 Agent 终端存在完成实现后继续高 CPU 空转、未收尾 commit 的情况；主控应以文件静止、测试证据和独立 review 为准，及时停止进程并接管提交。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

本 BET 三个子仓合计修改 19 个文件，源码/生成契约净增约 2,401 行，测试净增约 2,007 行，总净增约 4,408 行；GaC 规则 +0、ADR +0、脚本 +0。净增主要来自 MOF 多目标生成物、真实 Ledger 因果实现及负向/回归测试；未新建顶层项目或入口。

`bet-ledger.py surface` 的全仓 git-tracked 口径：

```text
src_loc      842,479 / baseline 726,412 / +116,067
test_loc     384,829 / baseline 350,854 / +33,975
src_files      3,692 / baseline   3,204 / +488
test_files     2,017 / baseline   1,827 / +190
adr_total        374 / baseline     344 / +30
gac_rules        136 / baseline     136 / +0
gac_required      26 / baseline      26 / +0
bin_scripts      446 / baseline     310 / +136
standards         55 / baseline      53 / +2
```

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. 下一技术波仍是 W2-04，但在启动前要先完成剩余 G-1 控制面复验；不要把 W2-03 的 receipt 当作 W2-04 projection 已完成。
2. Agora 的可信边界是注册公共路由，不是对任意同进程 Python import 的安全隔离。若未来进入多人/多租户部署，另立 BET 做凭据隔离、permit 强绑定、并发幂等和 crash reconcile。
3. 多 Agent 执行继续采用“ECOS 合同先行 → OMO 语义/账本 → Agora 物理接线 → 独立 reviewer + 主控跨仓探针”；主控对 worker_done 必须复跑测试并检查 provider 调用计数、事件顺序和 hash chain。
4. PASW 子仓先 push 分支/tag，再用 `gac-worktree.sh bump-pointer`；提交后将只读锚点更新到新 gitlink，避免根 worktree 长期显示 `MM`。
