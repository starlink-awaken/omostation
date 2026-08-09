---
status: archived
lifecycle: history
owner: xiamingxing
last-reviewed: 2026-08-09
---

# BET-Y1Q3-T6-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成 cockpit_mcp 残留 import 清理 + 测试（约 2 小时 vs appetite 3 天），未超出。
主要耗时在理解 cockpit_mcp.py 被删后 L4 读取功能的替代路径 + 逐文件迁移。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 所有 cockpit.scripts.cockpit_mcp 残留 import 已清理或替换为 Agora BOS 调用 | ✅ 新增 `commands/_l4_legacy.py` 迁移 L4 读取 (workspace_context/cards_status/cards_check/vault_search/domains_list), 7 个文件 (l4bridge/mcp/health/brief/kems/web/api_omos/dashboard/routes) 全部改为从 _l4_legacy 导入; 无残留 import (仅注释引用) |
| l4bridge.py 的 try/except 降级逻辑已移除（恢复为正常调用路径） | ✅ 移除 _HAS_L4 try/except, 直接 import _l4_legacy (模块常存) |
| audit worktree 子模块指针已同步到主 worktree 状态（c2g + bus-foundation） | ✅ 实测 c2g=350c567 + bus-foundation=900ca5f 与 main 一致, `git submodule status` 无空提交标记 |
| cockpit context/cards/vault/domains/health/mcp 无参运行返回正常 | ✅ 实测 6 命令 rc=0: context/cards --check/domains/health/mcp --list-tools (Agora BOS 80 服务); 不再有 "❌ L4 bridge 不可用" |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **cockpit_mcp.py 删除后 L4 读取无替代**: 5de9b5c 删除 cockpit_mcp.py (1197 行), commit message 说 "All MCP access routes through Agora (:7431)", 但 7 个调用方仍直接 import — 删除未配套迁移。真正缺口 = L4 读取逻辑 (读 .omo goals/constraints + 卡片扫描) 需重新落户。
2. **不做 shim 而做迁移**: non_goals 禁新增 cockpit_mcp shim。解法: 新建 `commands/_l4_legacy.py` 承载 L4 读取 (纯数据读), 复用 cards.py 的 `_iter_cards` 避免重复解析。这不是 shim (不暴露删除的 stdio API), 而是把读取逻辑正式迁移到 commands 层。
3. **mcp 命令 stdio/SSE 入口已死**: cmd_mcp 整个依赖已删的 `cockpit_mcp.mcp` (server 对象)。改法: `--list-tools` 直接走 `_list_agora_tools()` (HTTP 探测 :7431), stdio/SSE 启动改为提示 Phase 4 已移除。
4. **kems domains 契约不匹配**: 原代码从 workspace_context 读 `domains` 字段, 但该字段不存在 → 输出"共 0 个域"。改法: 直接用 `_l4_legacy.domains_list()` 数据。
5. **测试过时**: test_cli_mcp.py 模拟 stdio 启动 (mock cockpit_mcp.mcp.run), test_capability 模拟降级路径 — 均需更新为 Phase 4 后行为。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（cockpit 子模块 commit f423893）:
- 新文件 `src/cockpit/commands/_l4_legacy.py` (~230 行): L4 读取迁移
- 修改 7 文件 +~130/-160 行: 移除残留 import + try/except 降级
- 新测试 `tests/test_l4_legacy.py` (6 个) + 更新 test_cli_mcp (2) + test_capability (1)
- cockpit 1079 tests 全绿

净减 ~30 行 (移除降级逻辑 + 死代码)。无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **L4 读取入口**: `cockpit.commands._l4_legacy` 是 workspace context / CARDS / vault / domains 的读取源 (读 .omo + Documents/@域)。勿再 import `cockpit.scripts.cockpit_mcp` (已删除)。
2. **命令→替代映射**: workspace_context/cards_status/cards_check/vault_search/domains_list 全部在 _l4_legacy; `_scan_cards` 内部复用 cards.py `_iter_cards`。
3. **mcp 命令**: `--list-tools` 走 agora HTTP 探测; stdio/SSE server 启动已移除 (提示用 Agora :7431)。
4. **PASW 子模块提交流程**: `projects/cockpit` (detached) 提交 → `.subtrees/cockpit` checkout + branch -f agent 分支 → push --force → bump-pointer。
5. **测试锚点**: test_l4_legacy.py 覆盖读取契约; test_help_discover_ssot.py 覆盖 SSOT 三件套; 全量 1079 passed。
6. **待办**: agora 仅注册 `bos://cockpit/tools/cards_status`; 若要完整 BOS 化 L4 (context/cards_check/vault/domains 也走 bos://), 是 T6-02 的自然延伸, 已超出 done_when。
