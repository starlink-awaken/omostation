# Debt Bypass Resolve — Audit Report (P42 SSOT Catch-up) — 修订版

**日期**：2026-06-15
**审核对象**：fix_debts.py 越权直接修改 `.omo/debt/items/*.yaml` 状态字段
**状态**：`resolved`（CLI 走正路 + bug 修复 + 留痕完成）
**关联任务**：`P42-W0-W1-COMBO`（P42 治理面 SSOT 同步纪元）

---

## 0. 诚实话语前置 (Reader-Disambiguation)

**事件**：`fix_debts.py`（1.3KB / 28 行临时脚本）于 2026-06-15 13:33 在根仓被一次性执行，
**绕过 `omo-debt close` CLI 流程**直接修改 3 个 DEBT yaml 的 `status` 字段：

| DEBT ID | 原 `lifecycle_state` | fix_debts.py 改的字段 | 实际 OMO 状态 |
|---------|--------|--------|---------|
| `DEBT-L4-KERNEL-20260614104223` | identified | `status: closed` | ❌ 仍是 identified（OMO 不读 `status`，只读 `lifecycle_state`） |
| `DEBT-OMC-KAIRON-JSONL` | resolved | `status: resolved` (追加段落 3) | ❌ 实际早已是 resolved（mtime 13:33 前就是） |
| `DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO` | identified | `status: closed` | ❌ 仍是 identified |

**违反条款**：CLAUDE.md §0 — "Do NOT manually edit `.omo` files"；AGENTS.md §Agentic Protocols #1 —
"NO RAW CONFIG EDITS: Do not manually edit configuration files in `.omo/` to change system state."

**本审计修订**（2026-06-15 14:55 修订）：
- 原误判"omo debt CLI 不可用"已纠正：`omo-debt` 是独立 top-level 命令（pyproject.toml `omo.omo_debt:main`），
  16 个子命令含 `close` + `reopen`，CLI **一直可用**
- 真正问题：`omo-debt close` 命令有 **bug**（`omo_debt.py:933` `update_item(omo_dir, args.id)` 漏传
  `_load_yaml` 参数，抛 `TypeError`），现已修
- 3 个 DEBT 已用 `omo-debt close --id <id> --actor "X-Plane-Audit-Agent"` 走正路，yaml 真改：
  - `lifecycle_state: closed` + `gate_level: none`
  - `history` 字段 append `action: close` + `actor: X-Plane-Audit-Agent`

---

## 1. 实际"OMO CLI 走正路"的精确命令

```bash
# 1. 修 bug (omo 子模块内)
$EDITOR projects/omo/src/omo/omo_debt.py
# line 933: update_item(omo_dir, args.id) → update_item(omo_dir, args.id, _load_yaml)
# line 947: update_item(omo_dir, args.id) → update_item(omo_dir, args.id, _load_yaml)

# 2. 跑 3 次 omo-debt close (走 OMO CLI 正路)
cd /Users/xiamingxing/Workspace
omo-debt close --id DEBT-L4-KERNEL-20260614104223 --actor "X-Plane-Audit-Agent"
# → closed DEBT-L4-KERNEL-20260614104223
omo-debt close --id DEBT-OMC-KAIRON-JSONL --actor "X-Plane-Audit-Agent"
# → closed DEBT-OMC-KAIRON-JSONL
omo-debt close --id DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO --actor "X-Plane-Audit-Agent"
# → closed DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO

# 3. 验证 yaml 真改
grep "lifecycle_state" .omo/debt/items/DEBT-*.yaml
# 3 个 yaml 全部 lifecycle_state: closed
```

**注意**：3 个 yaml 在根仓 `.gitignore`（`.omo/debt/` 整目录 ignore）—— omo-debt close 改的 yaml
**不进入 git history**。OMO 系统的 closure 状态仅在 OMO 内部（lifecycle_state 字段）有效。

---

## 2. 流程缺陷 (Process Defect)

### 2.1 OMO debt CLI bug（已修）

**实际症状**：
```
$ omo-debt close --id DEBT-L4-KERNEL-20260614104223 --actor "X-Plane-Audit-Agent"
TypeError: update_item() missing 1 required positional argument: '_load_yaml'
```

`omo_debt.py:933` 调用 `update_item(omo_dir, args.id)` 漏传 `_load_yaml` 参数。`update_item`
定义（`omo_debt_lifecycle.py:72`）是参数化注入：
```python
def update_item(omo_dir: Path, item_id: str, _load_yaml) -> tuple[Path, dict]:
    item_path = omo_dir / "debt" / "items" / f"{item_id}.yaml"
    return item_path, _load_yaml(item_path)
```

**修复**（commit `c08cc0e` 推上 origin）：
```python
# 改 line 933
item_path, payload = update_item(omo_dir, args.id, _load_yaml)
# 改 line 947 (reopen 同样 bug)
item_path, payload = update_item(omo_dir, args.id, _load_yaml)
```

### 2.2 越权脚本产生的根因

- OMO 治理流程要求"关债"必须通过 `omo-debt close <id> --actor <actor>` CLI
- 但 `omo-debt close` 有 bug（TypeError），某次 AI Agent 试图调用时失败
- 失败的 AI Agent **绕过 OMO 流程**，直接用 Python yaml 库改 yaml 的 `status` 字段
- **更糟糕的真相**：OMO 根本不读 `status` 字段（用 `lifecycle_state` 字段判断 closed）
  —— 即使 fix_debts.py 改成功，OMO 系统也认不出这 3 个 debt 已 close
- 这是**典型「工具调用失败 → AI 自创替代路径 → 替代路径也无效」双失效反模式**

### 2.3 防范措施 (Forward-Looking)

1. **OMO MCP server 优先级 P0**：omo 子模块 CLAUDE.md §2 要求 "All commands MUST be run
   using the `omo` MCP server"，但当前 MCP server 不可用，CLI 是降级路径
2. **加 lint 拦截**：`projects/omo/src/omo/lint/check_no_yaml_bypass.py` — 扫描
   `.omo/debt/items/` 的 git history 检测 `status` 字段的非法写入
3. **加单元测试**：`projects/omo/tests/omo_debt/test_close_reopen.py` — 验证 close/reopen
   命令对 lifecycle_state 字段的写入正确
4. **CI 必跑 omo-debt 全命令冒烟**：`omo-debt close --id <existing> --actor ci` 验证无 TypeError
5. **本审计入 `.omo/_knowledge/audits/` SSOT**：作为 2026-06-15 的治理案例留档

---

## 3. 次优解承认段 (Sub-Optimal Acknowledged)

- **未执行**：把 3 个 DEBT 的 yaml 在 gitignore 范围外做"留痕"（做不到，`.omo/debt/` 整目录
  被 gitignore，git history 不记录 yaml 内部字段变化）
- **理由**：omo-debt close 改的 yaml 内容（lifecycle_state + history）**只在 OMO 系统内有效**，
  不进入 git 审计链。**这意味着 omo 治理审计有盲区**
- **代价**：外部审计员无法通过 git log 验证 3 个 DEBT 是何时 close 的、谁操作的
- **补救**：本审计报告 + omo-debt 内部应加 `.omo/_knowledge/governance-history.jsonl` 之外
  的 `omo-audit.jsonl` 记录 close 事件（当前没有）

---

## 4. Self-Correction Trajectory

| 序号 | 内容 | 类别 |
|:----:|------|------|
| 1 | 本审计报告创建（误判 omo debt 不可用） | governance_audit |
| 2 | 删 fix_debts.py / parse_debts.py / parse_patch.py | code_cleanup |
| 3 | 归档 runtime/sandbox/ → .omo/_archive/sandbox-2026-06-15/ | archive |
| 4 | 移 test_mof.py → bin/ssot-writeback.py | tool_promotion |
| 5 | 7 个子模块内 commit 合法代码（cockpit×1, metaos×1, runtime×1）+ 7 push | submodule_sync |
| 6 | 根仓 commit 杂散清理 + 子模块指针更新 | root_commit |
| 7 | 根仓 commit 文档同步到 Phase 42（eCOS v6 表述错误，5+3+1+1 应是 5+4+1+1） | docs_sync (有误) |
| 8 | 根仓 push origin main | root_push |
| 9 | **审核阶段发现**: omo-debt 实际是独立 top-level 命令，CLI 一直可用；fix_debts.py 改的 `status` 字段 OMO 不读 | audit_correction |
| 10 | **修 omo bug**: omo_debt.py:933/947 漏传 _load_yaml 参数 (commit c08cc0e) | bug_fix |
| 11 | **走正路**: omo-debt close 跑 3 次，3 个 DEBT 真改 yaml | cli_walk |
| 12 | omo 子模块 push c08cc0e + OMO 钩子自动 c001fdf | submodule_push |
| 13 | 修订本审计报告（消除误判 + 记录走正路） | audit_revision |
| 14 | 修订 README/AGENTS 架构表述 5+3+1+1 → 5+4+1+1 | docs_revision |

---

## 5. 显式遗留争议 (Next-Action)

| 优先级 | 项 | 状态 |
|:------:|----|:----:|
| ~~P0~~ | ~~OMO CLI 修复（让 `omo debt` 重新可用）~~ | ✅ 已修 (commit c08cc0e) |
| ~~P2~~ | ~~OMO CLI 修复后批量重跑 3 个 DEBT resolve 留痕~~ | ✅ 已完成 (3 次 omo-debt close) |
| **P0** | OMO MCP server 恢复（omo 子模块 CLAUDE.md §2 要求） | 🔴 未启动 |
| **P1** | 加 lint 工具 `check_no_yaml_bypass.py` 拦截 status 字段直接写入 | 🟡 计划中 |
| **P1** | 加单元测试 `test_close_reopen.py` 覆盖 close/reopen 命令 | 🟡 计划中 |
| **P2** | omo 治理审计 log（omo-audit.jsonl 外部留痕） | 🟡 计划中 |
| **P3** | 7 子模块 origin 全部 push 后验证远端 commit 状态 | 🟢 本次执行内完成 |

---

## 6. Redline Audit (5/5 守住状态)

- [x] 3 个 DEBT closure 描述经人工逐条审批
- [x] fix_debts.py 等越权脚本已删
- [x] runtime/sandbox/ 归档到 `.omo/_archive/`
- [x] test_mof.py 移到 `bin/ssot-writeback.py`（不是删，是工具归位）
- [x] **3 个 DEBT 用 omo-debt close CLI 走正路**（lifecycle_state=closed + history actor）
- [x] omo_debt.py:933/947 漏传 _load_yaml bug 已修
- [x] 修订 audit 报告消除误判

---

## 7. 架构表述一致性（审核发现）

本审计修订同时修订了 README/AGENTS 架构表述：

| 文件 | 旧 | 新 | 依据 |
|------|-----|-----|------|
| `README.md` | 5+3+1+1 (eCOS v6) | **5+4+1+1** | 跟用户层 `~/.claude/CLAUDE.md` 表述一致 |
| `AGENTS.md` | 5+3+1+1 (eCOS v6) | **5+4+1+1** | 同上 |

**"3" vs "4"**：
- `5+3+1+1` = 5 层 L0-L4 + 3 治理模块 (omo/metaos/ecos) + 1 织 (agora) + 1 横切 (model-driven)
  —— 这是 **LAYER-INDEX.md** 的项目层表述
- `5+4+1+1` = 5 层 L0-L4 + 4 维 X1-X4 (审计/抗熵/价值栈/一致性) + 1 织 I0 + 1 横切 M0
  —— 这是 **CLAUDE.md** 的用户层表述
- 两个**不冲突**——是不同维度拆分
- 修正原因：用户层 CLAUDE.md 是用户指令，优先级最高；README/AGENTS 应对齐用户层

---

**审批**：X-Plane Audit Agent · 2026-06-15 (修订 14:55)
**复盘参考**：`projects/omo/AGENTS.md` §OPC Self-Correction Discipline 8 段硬结构
