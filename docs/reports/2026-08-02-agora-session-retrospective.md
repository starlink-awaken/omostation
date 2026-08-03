# agora×toolbox 深度修复与治理清理 复盘报告

> **创建时间**：2026-08-02
> **范围**：本次会话全链路（调研 → 安全修复 → MCP 协议评估 → 全面优化 → god module 拆分 → worktree/分支清理）
> **关联**：[`2026-08-02-agora-toolbox-deep-audit.md`](2026-08-02-agora-toolbox-deep-audit.md) · [`2026-08-02-agora-optimization-report.md`](2026-08-02-agora-optimization-report.md)

---

## 1. 会话全貌

| 阶段 | 交付 | 状态 |
|---|---|---|
| 深度调研 | 4 路并行 Agent：路由/安全/实例/集成 | ✅ |
| F-01~F-14 安全修复 | PR #782 + #790 + #797 | ✅ 合并 |
| MCP 协议 2026-07-28 评估 | 升级实验验证 + 报告落盘 | ✅ 保持稳定版 |
| 全面优化 P0/P1/P2 | PR #811（依赖/路径/死代码/异常/升级/env） | ✅ 合并 |
| tools_bos god module 拆分 | PR #843（1626 行 → 子包 + shim） | ✅ 合并 |
| worktree 清理 | 主仓 32→3、kairon 31→2 | ✅ |
| 分支清理 | 主仓 109→9、13 子模块瘦身 | ✅ |

**总成果**：agora 1479 tests 全绿、0 硬编码路径、依赖 12→8、6 个 PR 全部合并、工作区从 32 worktree/109 分支精简到 3/9。

---

## 2. 做得好的（保持）

1. **安全修复系统化**：fail-closed 系列（认证/准入/agent-token）统一模式，`AGORA_*_MODE` 逃生舱设计合理
2. **每项修复全量回归**：1479 tests 是兼容性安全网，每次改动都验证，及时暴露回归
3. **实验先行**：mcp 2.0 升级先 dry-run 解析 + 实验分支验证可行性（改动仅 2 import），再决定不引入 beta
4. **文档同步**：调研/优化/MCP 报告及时落盘，SSOT 引用规范
5. **清理谨慎**：worktree/分支清理严格按"无独有 commit + 远端已删 + 无 dirty"三标准，保留活跃项
6. **架构级决策记录**：tools_bos 拆分先做依赖图分析（发现 bdsk 循环），shim 模式保持兼容

---

## 3. 踩坑与教训（本次重点）

### 3.1 分支切换丢未提交改动（P0 教训）

**现象**：在 `exp/mcp2-upgrade` 分支做 P0-2（路径 env 化）+ P1-4（异常修复）后 `git checkout work/f01-auth-fail-closed`，router.py/manager.py/api.py/mcp_bootstrap/registry.yaml 的改动**全部丢失**，需重新应用。

**根因**：实验分支的改动未 commit，checkout 切换时 git 丢弃了未提交改动（分支本身没 commit，改动无处安放）。

**规则**：**跨分支工作前先确认未提交改动状态**；实验分支的改动要么 commit 要么 stash，再切换。

### 3.2 删死代码误删 re-export（P0 教训）

**现象**：删 `mcp.py to_otel_json` 时，误删文件尾部 `from agora.server.tools_proxy import proxy_call...` 的 re-export（6 个测试 ImportError）。

**规则**：**删除死代码前检查文件尾部/全文件是否还有被测试依赖的 re-export 或符号**；删除后立即跑相关测试（collection 阶段能暴露 import 错误）。

### 3.3 函数内局部 import 遮蔽（P0 教训）

**现象**：manager.py 某函数内 `if` 块有 `from pathlib import Path`，导致同一函数另一处 `Path.home()` 抛 `UnboundLocalError`（局部 import 使整个函数把 Path 当局部变量）。

**规则**：**函数内条件 import 会遮蔽模块级 import 并影响整个函数作用域**；模块级已 import 的符号避免在函数内重复 import（或改用 `os.path.expanduser` 等替代）。

### 3.4 shim 模式测试 patch 目标（P1 教训）

**现象**：tools_bos 拆成 shim 后，测试 `monkeypatch.setattr(tools_bos, "_AGORA_API_KEY", "")` 不生效——shim 的属性修改不影响 `_helpers` 模块内部引用。

**规则**：**shim 拆包后，测试 patch/setattr 目标必须改到实际定义模块**（如 `tools_bos._helpers._AGORA_API_KEY`、`tools_bos.routing._bos_router`）。

### 3.5 gac-worktree submit 混入运行时文件（P1 教训，重复出现）

**现象**：`gac-worktree.sh submit` 的 wip commit 自动把 worktree 里未提交的 `.omo/_knowledge/workflow-mesh/events.jsonl` 带入 PR（PR #782/#811/#843 三次）。

**规则**：**submit 后必查 `gh pr view --json files`**，发现混入运行时文件则 soft reset + 移除 + force push。（memory 已有类似记录，本次再确认）

### 3.6 `.worktrees/` 目录可能是子模块 worktree（P1 教训）

**现象**：`.worktrees/` 下目录显示"无 .git 纯残留"，实际是子模块 worktree（gitdir 指向 `projects/<sub>/.git/worktrees/`），需用 `git -C <sub> worktree list` 查看。

**规则**：**清理 worktree 前先确认归属（主仓 vs 子模块）**；`.worktrees/` 目录可能是子模块 worktree，不能仅凭"未在主仓注册"判断废弃。

### 3.7 squash 合并分支的清理判断（P1 教训）

**现象**：分支 tip 不在 main 祖先链（squash 合并），`git merge-base --is-ancestor` 误判"未合并"。

**规则**：**squash 合并残留分支用 `git log <branch> --not main` 判断**（无独有 commit = 已合并可删）；不能用 merge-base 祖先判断。

---

## 4. 后续待办（技术债）

| 项 | 说明 | 优先级 |
|---|---|---|
| kairon/runtime 剩余 worktree | ws-kairon-kems-final、ws-runtime-kems-final（detached，HEAD 未判定） | P2 |
| cockpit-fix-mesh | 远端分支存在但内容已入 main，待 PR 合并后清理 | P2 |
| 主仓 5 个实质工作分支 | p82-plan 等（200+ 未 push commit），需确认归属后处理 | P2 |
| mcp 2.0 升级触发条件 | TS SDK 2.x 或 fastmcp 4.0 stable 时执行 | P2 |

---

## 5. 固化

- 教训 3.1-3.7 已写入 agent 私有 memory（feedback 类型）
- 本报告落盘 docs/reports/ 供后续会话参考
