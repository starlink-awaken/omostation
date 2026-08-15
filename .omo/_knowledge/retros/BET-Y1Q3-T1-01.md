---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-09
---
# BET-Y1Q3-T1-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成 registry/help_map 补全 + 弃用标注 + 测试（约 1 小时 vs appetite 2 天），未超出。
主要耗时在确认 SSOT 漂移实际范围（部分命令已被并发修复，需实测） + PASW 子模块提交流程。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| COMMAND_CATALOG 补充 bdsk/journey/panorama/project 四个缺失命令 | ✅ registry.py 补 4 个 (69→73), 双覆盖测试验证 |
| help_map.py GROUPS 补充 bdsk/journey/panorama/project/quickstart-check 五个缺失命令 | ✅ help_map GROUPS 补 5 个 (含 quickstart-check 到入门组) |
| 已弃用的 ssb 和 model-driven 从 _subcommands.py 移除注册（或明确标注 [DEPRECATED]） | ✅ 选"标注"路径: registry + help_map 均标 [DEPRECATED] (保留注册保兼容, 执行时已拒绝工作) |
| cockpit help 输出包含所有 73 个注册命令 | ✅ help 输出实测含 bdsk/journey/panorama/project/quickstart-check + ssb/model-driven 弃用标注 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **证据 E1/E2 部分过时**: 台账证据说 _subcommands.py 已注册 73 个但 registry/help_map 缺失 —— 实测 journey/project/quickstart-check 已在 registry (quickstart-check 在 registry L109), 真正缺失的是 bdsk/journey/panorama/project (registry) + bdsk/journey/panorama/project/quickstart-check (help_map)。**以实测为准而非证据文档**。
2. **help 输出是富文本产品地图**: `cockpit help` 是 help_map.py GROUPS 渲染的 rich 表格, 非 argparse usage。验证命令覆盖须检查 help_map GROUPS, 不能 grep argparse 输出。
3. **ssb/model-driven 选择"标注"而非"移除"**: done_when 允许二选一。实测两命令执行时已拒绝 (ssb rc=1 提示弃用, model-driven rc=2 拒绝除非 MODEL_DRIVEN_CLI_LEGACY=1), 故保留注册 + 标注 [DEPRECATED] 是最小改动, 符合非目标"修改命令实现逻辑"。
4. **SSOT 测试已有先例**: test_help_discover_ssot.py 已含"catalog ⊆ cli parsers"SSOT 校验, 在其上追加回归测试。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（cockpit 子模块 commit ef5ac8a）:
- `src/cockpit/commands/registry.py` +16 行: 补 4 个 CommandMeta + 2 个弃用标注
- `src/cockpit/commands/help_map.py` +12 行: 补 5 个 CmdRow + 2 个弃用标注
- `src/cockpit/tests/test_help_discover_ssot.py` +35 行: 2 个回归测试 (SSOT 双覆盖 + 弃用标注)

无新增 GaC 规则 / ADR / bin 脚本。净增 ~63 行 (测试为主)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **SSOT 三件套**: cockpit 命令的权威注册在 `_subcommands.py` (parser) + `registry.py COMMAND_CATALOG` (元数据) + `help_map.py GROUPS` (产品地图)。新增命令须三处同步, 缺一即漂移。
2. **测试先例**: `test_help_discover_ssot.py::test_catalog_commands_are_registered_in_cli` 校验 help_map catalog ⊆ cli parsers —— 加命令后跑此测试防漂移。
3. **PASW 子模块提交流程**: `projects/cockpit` (detached) 提交 → `.subtrees/cockpit` checkout -f + branch -f agent 分支 → push --force → bump-pointer。
4. **affected-hash 必填**: claim 命令须 `--affected-hash` (并发 0deecdd4 引入), 生成 = `affected-graph.py --changed-projects <proj> --json | shasum`。
5. **弃用命令策略**: 标 [DEPRECATED] 而非移除 (保留兼容), 执行层已拒绝 (ssb/model-driven 均 rc 非 0)。
6. **待办**: panorama/panorama 实际执行命令在 `panorama` parser (make panorama), 已标注可观测组; 无遗留。

---

## 独立核实记录（2026-08-15，台账信任修复轮）

> 本节由核实 agent 追加，原 retro（2026-08-09）保留不动。核实背景：台账信任修复轮要求 done 状态必须有可复核证据。

**逐条实测（worktree @ 最新 cockpit 子树）**：

| done_when | 判定 | 实测证据 |
|---|---|---|
| ① registry 补 bdsk/journey/panorama/project | ✅ | `len(COMMAND_CATALOG)=73`，四命令逐一 `in C`=Y |
| ② help_map 补五命令 | ✅ | `all_command_names()`=73；双向差集 `H−C=[]`、`C−H=[]` 零漂移 |
| ③ ssb/model-driven 标注弃用 | ✅ | `_subcommands.py:379/:407` help 带 `[DEPRECATED]`；`cockpit help` 实跑输出 `ssb [DEPRECATED]`、`model-driven [DEPRECATED]` |
| ④ help 含全部 73 命令 | ✅ | registry=73 = help_map=73，差集空；grep 五命令命中 6 行 |

台账 verify 三条实跑全过（help grep 命中 / ssb、model-driven 弃用标注在 help 系统 + registry 元数据可见；子命令 `--help` usage 头不带描述为 argparse 默认行为，弃用信息以 help 系统为准）。

**核实结论**：done_when 四条全部客观满足（由 2026-08-09 会话实现，本节独立复核确认），准予收口 status → done。发现两点台账债（不改，记录）：WS 前缀 `src/cockpit/` 与真实路径 `projects/cockpit/src/cockpit/` 不符；candidate 已完成却未及时置 done 属记账滞后。
