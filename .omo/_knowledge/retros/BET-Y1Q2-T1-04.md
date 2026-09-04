---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-04 复盘
type: retro
---
# BET-Y1Q2-T1-04 复盘

## Q1 实际耗时 vs appetite？超出比例？

appetite 2 天；实现收尾在独立注册工作之后的单个 session 内约 1.5 小时完成，远低于 appetite，未超出。
耗时主要不在功能编码，而在契约对齐（可执行 SSOT 前缀/版本语义）、负例补强与跨角色聚合缺陷的对抗性发现。

## Q2 done_when 是否全部通过？哪条没过，为什么？

| done_when | 状态与证据 |
|---|---|
| 严格 ID 前缀（principal:/role:/responsibility:/assignment:）与单调递增版本，同一 ID 每次变更版本 +1 | ✅ 目标 sovereignty 套件 96 通过；登记 CLI smoke 中 `sovereignty-query --principal-id principal:alice` 返回 count=2 且 role_ids 恰含 family-steward/professional、不含 learner（Principal 隔离 count=2） |
| assign / revoke / replace 为合法状态转换；对已失效或旧版本号写入被拒绝，版本号禁止倒退 | ✅ 事件溯源重放 + 乐观并发按 principal 作用域强制版本单调；主隔离/旧版本写入负例覆盖 |
| 所有写只经 LedgerBroker.append，无绕过 broker 的直接 SQL 或文件写 | ✅ append 唯一写路径；event-ledger 回归 223 通过 / 5 skipped |
| 每个 Principal 数据互相隔离：查询与重放按 principal_id 过滤，跨 Principal 不泄漏 | ✅ 登记 CLI smoke：`sovereignty-query --principal-id principal:alice` 返回 count=2，全部返回 assignment 均属于 Alice，Bob 的 role:learner 缺席（跨 Principal 不泄漏） |
| 删除派生查询状态后可由事件日志重建，不涉及 W2-04 投影 | ✅ strict replay 通过（OpenCode Go 加固引入），派生状态可重建；对抗性共享责任场景重放合法 6 事件链，全部读模型将 responsibility:shared 解析到 New version 2（同 Principal 聚合语义证据，非跨 Principal 隔离证据） |
| 目标 pytest 通过；真实 CLI smoke（sovereignty-assign / sovereignty-query / ledger verify）exit 0 | ✅ OMO PR #26 合并 SHA `6d13f487990ddd656483e8bf046b25b883a04c49`；根仓 PR #1335 合并 SHA `f2b82b5fe8720e1c752bd620e0d918a1db99b5cd`；登记 smoke 硬断言（jq）通过 |

未过项：无。

## Q3 过程中发现的与 plan 不符的事实（打假）

1. **初始执行器发明了错误的 `pri_`/`rol_`/`rsp_`/`rasg_` 前缀**：台账 done_when 明写 `principal:/role:/responsibility:/assignment:`，执行器未先读可执行 SSOT 而自造短前缀。以台账为准修正为可执行 SSOT 前缀后才与登记契约一致。
2. **首位 reviewer 在强制比对精确 BET 前错误批准**：凭表面印象 approve，协调器要求其逐条对照 exact BET 文本后才发现前缀/语义偏离并改判。
3. **自洽测试不足以捕获契约失配**：自测全绿仍与登记 smoke 的精确断言不符；只有真实登记的 CLI smoke（含 `verify total=3` 与 Principal 隔离 count=2 的 jq 硬断言）才暴露 mismatch。
4. **CodeBuddy 用 bypassPermissions 产出大量修正编辑，但 API 在 worker_done 前以 Tencent 502 终止**：修正编辑本身是可用的，但 worker_done 前的 API 终止使协调器无法信任完成声明；恢复的 diff 经独立检查与测试后，再由 OpenCode Go 加固（strict replay + principal 作用域乐观并发）。
5. **OpenCode Go 加固**：补入 strict replay 与 principal 作用域乐观并发（版本号禁止倒退、旧版本写入拒绝），把 Q2 的单调性/重建 done_when 落到实处。
6. **两轮 review 仍漏掉跨角色共享 Responsibility 聚合 bug**：共享责任（responsibility:shared 由多个 Role 关联）的聚合语义仅靠静态 review 未发现，最终由对抗性交互场景重放合法 6 事件链暴露——全部读模型必须解析到 New version 2。
7. **CI 使用本地项目 Ruff 配置缺失的独立 import/format 规则**：本地 `ruff check` 通过而 CI 首轮失败，需第二 CI 轮用 CI 等价规则对齐后全绿。
8. **uv.lock 与 run-continuation / governance 投影为重复 scope 泄漏**：多次把不应入面/入仓的派生文件带进变更，均被恢复或以可恢复方式移出；最终 OMO diff 不含任何此类泄漏。
9. **closeout 自动结晶生成错误信念 "Unverified workflow closeout"**：尽管 verify 与 observe 均通过，自动结晶仍产出该假信念，该输出被拒绝；以真实 verify/observe 证据为准。
10. **bet-ledger D0 guard 无法透视子模块内部文件**：根仓 `git ls-files` 将已合并进 OMO 的 write surface 误判为未跟踪；但 OMO 合并 SHA 与远端 D0 tags 均可达，D0 证据成立，故受控使用 `--force`。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

本 bet 在 OMO 子模块的精确归因（相对 `b14c463b`）：**5 个文件、2976 行插入** — 源码 1186 行、测试 1790 行。无新增 GaC 规则、ADR、脚本、项目、DDL、MOF、Agora/BOS/MCP 面、远程写面或外部副作用。根仓侧变更仅为**一个子模块指针**（指向 OMO PR #26 合并 SHA `6d13f487990ddd656483e8bf046b25b883a04c49`）。

`bet-ledger.py surface` 的仓库全景观察量（全局变化为观察量，非全部由本 bet 贡献）：

```text
src_loc              837,887         726,412  +111,475(+15%)
test_loc             379,747         350,854   +28,893(+8%)   不得下降
src_files              3,683           3,204      +479(+15%)
test_files             1,997           1,827      +170(+9%)
adr_total                372             344       +28(+8%)
gac_rules                136             136        +0(+0%)
gac_required              26              26        +0(+0%)
bin_scripts              449             310      +139(+45%)
standards                 55              53        +2(+4%)
collab_scenarios           5             221      -216(-98%)
```

注意：以上为 git tracked 全仓口径（含子模块）的观察量，累积自多个归并 bet 的去重量；本 bet 自身仅贡献上文的 5 文件 / 2976 行插入（源码 1186 + 测试 1790），且 gac_required +0。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **先读可执行 SSOT，再写代码**：ID 前缀/版本语义在台账 done_when 已明写，不要自造 `pri_`/`rol_` 等变体；契约以台账 + 登记 smoke 的 jq 断言为准，自洽测试不替代登记 smoke。
2. **登记 CLI smoke 是契约锚点**：`uv run --frozen omo ledger sovereignty-assign / sovereignty-query / verify`，用 `jq -e` 硬断言（verify total=3、Principal 隔离 count=2）。
3. **跨角色共享 Responsibility 是聚合陷阱**：responsibility:shared 由多 Role 关联时，读模型必须稳定解析到单一 New 版本；静态 review 会漏，务必用对抗性交互场景（合法多事件链重放）验证。
4. **CI Ruff 规则与本地配置可能不同步**：本地 `ruff check` 绿不代表 CI 绿；提交前用 CI 等价命令（含 import/format 规则）自检，避免第二 CI 轮。
5. **scope 泄漏高发点**：uv.lock、run-continuation / governance 投影等派生文件反复越界；交付前核对 write_surfaces，泄漏项恢复或移出，保持 OMO diff 仅含源码+测试。
6. **D0 证据在子模块内**：bet-ledger D0 guard 用根仓 `git ls-files` 看不到子模块内部文件，会误报未跟踪；以 OMO 合并 SHA（`6d13f487990ddd656483e8bf046b25b883a04c49`）+ 远端 D0 tags + 根指针三层证据为准，必要时受控 `--force`。
7. **旁路/API 终止使交付信号不可信**：bypassPermissions 或外部工具 API 在 worker_done 前终止（如 Tencent 502）时，完成声明不可信；恢复的文件编辑在独立 diff review + 测试 + 回到受管 workflow 之后方可接受。
