---
status: active
lifecycle: retrospective
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../decisions/0126-s2-final-analysis.md
  - ../../.omo/_knowledge/decisions/0126-s2-final-analysis.md
---

# Code Review: S2 阶段主仓 PR + 后续 (2026-07-03)

## 1. 范围

**主仓 PR (148 commit 窗口, 2026-07-01 ~ 2026-07-03)**:
- PR #55-#59 (S2 续 + F-14 治本)
- PR #52-#54 (X-Plane P0 修复: ruff F841/F541)
- PR #49-#50 (P0 CI Quality Checks)
- PR #44-#48 (X-Plane P1 修复: dead-path-refs LEGACY_OK_DIRS)
- PR #34-#43 (X-Plane S2 阶段 dashboard 合并 + agent-workflow 体系)
- PR #25 (S2 F-2 + ADR-0115 Phase 2/4)
- PR #20 (S1 复盘)
- PR #17-#19 (S1 follow-up)

**新增文件 / 大改**:
- `bin/agent-workflow.py` (2327 行, X-Plane 大改)
- `bin/governance-evolution.py` (892 行, X-Plane 大改)
- `bin/mcp-server-kos.py` (294 行, X-Plane 新增)
- `bin/test-mcp-kos.py` (123 行, X-Plane 新增)
- `bin/state-freshness-check.py` (本会话新增)
- 6 个 SKILL.md (X-Plane 新增)
- 12 个 ADR (X-Plane + 本会话)

## 2. 整体评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构 | A | 健康度 100/100, GaC 体系闭环生效 |
| 一致性 | B+ | 1 个真 bug (executor_enum drift) + 1 个文档 drift (SYSTEM-ININDEX 数字) |
| 安全性 | C+ | 1 个 **P1 安全风险** (mcp-server-kos `query_custom_sql`) |
| 可维护性 | A- | 工具数 130+, 命名归一, lane 守门 |
| 测试覆盖 | B | 大文件 (agent-workflow 2327 行) 缺单测, KOS MCP 单测有 (123 行) |
| 文档 | A | 84 ADR + 6 SKILL + SYSTEM-INDEX 导航, 完整 |
| 跨仓协调 | C | F-8/F-13/F-7 仍跨仓, 留 P2/P3 |

## 3. Critical Findings (P1 阻塞)

### Finding 3.1: `mcp-server-kos` 的 `query_custom_sql` 端点是安全风险

**位置**: `bin/mcp-server-kos.py:79-101` (handle_query_custom_sql)

**问题**:
```python
"query_custom_sql": {
    "description": "对 KOS 索引数据库执行底层的只读 SQL 查询",
    "inputSchema": {"sql": {"type": "string", "description": "只读 SQL..."}},
}

# 实际实现:
forbidden_keywords = {"insert", "update", "delete", "drop", "alter", "create", "replace", "vacuum"}
for kw in forbidden_keywords:
    if kw in sql_lower:
        return ... "Security violation"
cursor.execute(sql)
```

**风险**:
1. **关键词黑名单可绕过**:
   - `INSERT/**/INTO` (SQL 注释绕过)
   - 启用 PRAGMA / ATTACH DATABASE / 写入 ATTACH 后的 DB
   - 函数调用: `SELECT load_extension('/path/to/malicious.so')`
   - `SELECT writefile('/etc/cron.d/...', '...')` (SQLite extension)
   - `SELECT readfile('/etc/passwd')` (读敏感文件)
   - 触发器 (trigger) 隐式写
2. **"只读" 假设不成立**: `connect(... mode=ro)` 阻止 SQLite 写事务, 但不阻止:
   - 读 OS 文件 (`readfile`)
   - 加载扩展 (`load_extension`)
   - 通过 ATTACH 切换到写
3. **MCP 端点暴露**: 这个工具注册到 MCP server (`bin/mcp-server-kos.py:280+`), 任何 MCP client (Cockpit, Kiro, Claude) 都可以调用

**影响**: High. 任何 MCP agent 拿到这个端点, 就能通过构造 SQL 读 OS 任意文件 / 加载恶意扩展.

**建议修法 (按优先级)**:
1. **删端点** (最安全): `query_custom_sql` 不应存在, KOS 用专用 endpoint (search_kos, get_document, list_entities) 已够
2. **若必须保留**, 改用 `sqlite3` 解析 SQL AST 而非关键词黑名单:
   - 用 `sqlparse` 库解析 SQL
   - 仅允许多语句 (multi-statement disabled by default in sqlite3)
   - 拒绝任何非 SELECT 开头的语句
   - 拒绝 PRAGMA / ATTACH / 函数调用
3. **退一步**: 加 `connect(... mode=ro, uri=True)` 基础上, 用 `set_authorizer` callback 拦截 (sqlite3 自带)

**触发优先级**: P1 (安全风险, 立即修)

### Finding 3.2: `executor_enum` 漏 `gac_local_gate` (F-14 治本 PR #59 未根治)

**位置**: `.omo/_truth/registry/governance-checks.yaml:402-405` (schema.executor_enum)

**问题**:
- 3 个规则 (CR-X2-GOVERNANCE-SEMANTIC-GATE / CR-L0-MATRIX-PORT-CONSISTENCY / CR-L0-MATRIX-LAUNCHD-COVERAGE) 声明 `executor: [ci_gate, gac_local_gate]`
- 但 `executor_enum` 是 10 项 (缺 `gac_local_gate`)
- `bin/gac-bootstrap.py` 自举层 5 报 ❌ (我用 `gac-bootstrap.py` 跑实测, 3 个 false positive 仍存在)
- `bin/gac-executor.py` 走 `EXECUTOR_PRESENCE` (我自己映射表, 已 PASS)

**根因**: PR #17 S1 follow-up 落地时, X-Plane 跨边界加 `gac_local_gate` 到 schema enum 漏了 (PR #20 #8344ccd3 治本 CR-X2-GOVERNANCE-SEMANTIC-GATE 规则补 SSOT 登记, 但 enum 未同步). 后续 PR #59 (`09c00321`) 我修了 `EXECUTOR_PRESENCE` 映射表, 但 **enum 本身没补** — 所以 gac-bootstrap 仍 fail.

**真实状态**:
- `bin/gac-executor.py` (PR #59 治本): ✅ PASS (走 EXECUTOR_PRESENCE)
- `bin/gac-bootstrap.py` (PR #59 治本 不彻底): ❌ FAIL (走 schema.executor_enum)

**验证**:
```bash
$ uv run --with pyyaml python bin/gac-bootstrap.py
▶ 层5 执行有效: ❌ 非法/无 executor=3
    ❌ CR-X2-GOVERNANCE-SEMANTIC-GATE: 非法 executor: ['gac_local_gate']
```

**修法** (单 commit, 1 行):
```yaml
executor_enum: [hook_pre_edit, hook_post, ci_gate, omo_audit, mcp_tool, mof_validate, mof_audit, evidence_smoke, radar_cron, gc_cron, gac_local_gate]
```

**触发优先级**: P1 (gaC 自举 fail, F-14 半治本)

### Finding 3.3: `check_type_enum` 漏 `ssot_lint` (类似 3.2)

**位置**: `.omo/_truth/registry/governance-checks.yaml:check_type_enum`

**问题**:
- 3+ 规则声明 `check_type: ssot_lint`
- 但 `check_type_enum` 28 项中无 `ssot_lint`
- 任何检查 `check_type` 在 enum 内的工具会报 ssot_lint 非法

**修法** (1 行): 在 `check_type_enum` 末尾加 `, ssot_lint`

**触发优先级**: P1 (同 3.2)

## 4. High Findings (P2)

### Finding 4.1: `bin/agent-workflow.py` (2327 行) 缺单测

**问题**: 大文件单测覆盖薄弱. X-Plane 加了 `tests/test_agent_workflow.py` (423 行), 覆盖不全.

**建议**:
- 拆分 agent-workflow.py 为多个 module (profile / runner / cli / state)
- 提单测覆盖率至 ≥80% (尤其 profile 加载 / state transition / cli 入口)

**触发优先级**: P2 (技术债, 不阻塞)

### Finding 4.2: `bin/mcp-server-kos.py` 用 `except Exception as e` 宽捕获 (4 处)

**位置**: `bin/mcp-server-kos.py:55, 80, 100, 130` (大致行数)

**问题**: 4 处 `except Exception as e` 宽捕获, 隐藏真实错误. 例如 `except Exception as e: return {"content": [{"type": "text", "text": f"Database error: {str(e)}"}]}` 暴露 raw error 给 MCP client, 可能是内部 schema leak.

**建议**: 改 `except (sqlite3.Error, json.JSONDecodeError)` 等具体异常; 对未知异常 log + 返通用错误.

**触发优先级**: P2 (错误处理不佳, 不阻塞)

### Finding 4.3: `bin/agent-workflow.py` 大文件 + 缺 docstring (X-Plane 大改)

**问题**: agent-workflow.py 2327 行, X-Plane 大改后部分函数缺 docstring. `tests/test_agent_workflow.py` 仅 423 行, 覆盖率低.

**建议**:
- 拆分为 4-5 个 module
- 关键函数补 docstring
- 提测试覆盖率

**触发优先级**: P2 (技术债, 不阻塞)

### Finding 4.4: SYSTEM-INDEX.md 数字 stale (P2 文档 drift)

**问题**: 文档说 139 GaC 规则, 实际 147. 文档说 89 ADR, 实际 84.

**修法** (1 commit, 文档):
- 把数字改对
- 或加注释 "数字为 approximate, 详见 SSOT 源"
- 或加 auto-gen script (在 brief 流程跑)

**触发优先级**: P2 (文档 drift)

## 5. Medium Findings (P3)

### Finding 5.1: X-Plane 跨边界工作的 drift (历史 148 commit 中多次)

**症状**: 跨仓协调多次发现 "声明了 X, 但 Y 没同步" (gac_local_gate, ssot_lint, M2 enum 扩). X-Plane 加规则时漏同步 enum.

**建议**: 在 `bin/gac-m1-sync.py` 加 cross-schema validation: 加规则时自动 diff enum, 若声明的 executor/check_type 不在 enum 报错.

**触发优先级**: P3 (流程改进)

### Finding 5.2: F-8 / F-13 / F-7 仍跨仓

ADR-0122 路线图明确 "❌ 跨仓 F-7/F-8/F-13 不属主仓 scope". X-Plane 持续推进, 但这 3 项仍未触发跨仓协调 PR.

**建议**: 单独 PR 触发各 owner 仓:
- F-8: 6 个 BOS 域 (cockpit / l4-kernel / runtime / meta / swarm / omo) 加 kind
- F-13: omo-debt 收编 cockpit
- F-7: BOS 3 处越界 (P2 长期)

**触发优先级**: P3 (跨仓, 不属主仓)

### Finding 5.3: 6 个 SKILL.md 落地未跑 distillation pass

X-Plane 加 6 个 SKILL (system-index-distill, trajectory-distill, design-self-critique, ecos-test-cycle, omo-audit-baseline, worktree-ci-isolate). 新 skill 落地应跑一次 distillation pass 验证可用.

**建议**: X-Plane 跑一次 (或下一次使用时跑).

**触发优先级**: P3 (skill 验证)

## 6. 优秀实践 (赞)

### 6.1: lane 守门严格生效
6 commit lane 守门全 PASS (governance_code × 3, governance_state × 2, docs × 1). 跨 lane 混合 commit 被 hook 拦.

### 6.2: ADR 流程成熟
84 ADR 维护, status/lifecycle 字段一致, INDEX.md 持续更新. 复盘 ADR 0124/0125/0126 落地及时.

### 6.3: 健康度 100/100 闭环
X-Plane 持续推进 service 启 daemon + state sync, health_score 70/100 → 100/100. GaC healthcheck 全绿.

### 6.4: PR 流程规范
Phase 2c 强制 worktree + PR (我已遵守). squash merge + delete branch. PR message 含 root cause + 治本动机 + 验证 + 链接.

### 6.5: 自动化 test 覆盖
148 commit 窗口内, X-Plane 持续加 `tests/test_*.py` (test_agent_workflow 423 行, test_mcp_kos 123 行, test_governance_evolution 405 行). 测试金字塔向上.

### 6.6: SKILL workflow 模式
6 个 SKILL 提供 "distilled workflow" 入口. 复用价值高. `system-index-distill` 特别有用 (workspace 30 秒理解入口).

## 7. 总结

### 7.1 必须立即修 (P1)

1. **Finding 3.1** (mcp-server-kos `query_custom_sql` 安全风险) — 删端点或用 AST 解析 (1 commit)
2. **Finding 3.2** (`executor_enum` 漏 `gac_local_gate`) — 1 行 enum 补全 (1 commit)
3. **Finding 3.3** (`check_type_enum` 漏 `ssot_lint`) — 1 行 enum 补全 (1 commit)

3 commit 估时 1.5h, ROI 极高.

### 7.2 建议改进 (P2-P3)

- 大文件拆分 (agent-workflow 2327 行) — 留 follow-up
- mcp-server-kos 异常处理 — P2
- SYSTEM-INDEX 数字刷新 — P2
- 跨仓 F-7/F-8/F-13 — 留 P3

### 7.3 整体判断

**主仓代码质量: 良好 (B+).** 1 个 P1 安全风险, 2 个 P1 治本不彻底 (enum drift), 整体架构和流程成熟.

**建议: 立即修 3 个 P1 (估 1.5h), 后续可优化 P2 项, 跨仓项留 P3.**

## 8. 链接

- ADR-0126 S2 阶段深度分析
- P72 follow-up-completion-pattern
- 148 commit 窗口 (X-Plane + 人)
- PR #11 (P0) / #15 (S0) / #17-#20 (S1) / #25 (S2 首日) / #34-#59 (X-Plane + S2 续)

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
