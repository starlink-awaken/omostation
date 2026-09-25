# cockpit deep audit — closeout retrospective

> Date: 2026-09-25  
> Owner: governance-agent  
> Scope: P0–P3 cockpit audit + commit + push  

---

## 1. 变更摘要

| 项 | 值 |
|----|----|
| commits | 2 (`095380b38` + `a5736a2f5`) |
| files changed | 51 |
| insertions | 496 |
| deletions | 550 |
| touched projects | `projects/cockpit` (submodule) |
| tests | 176 passed, 1 xfailed |

### P0
- cockpit `main` clean, tests pass

### P1
- 新增 `src/cockpit/commands/delegation_guard.py`, preflight 接入 governance/mesh/runtime/omo/spine
- `router_health.py` 增加 `CRITICAL_ROUTERS`, `dashboard_server.py` 区分 `critical_unavailable`/`degraded`

### P2
- 新增 `src/cockpit/omo_write_guard.py` (append_jsonl/write_text/write_json + atomic lock)
- `bos_invoker.py` metrics 接入 `omo_write_guard`
- 移除 6 个 deprecated commands + 注册 + 测试
- 修复 `test_dashboard_server.py` 预存失败

### P3
- 移除 `web/api_outcomes.py` + `commands/workplace.py` 中不必要的 `sys.path` 注入

### 收尾
- 解决 `docs/plans/3y-bet-ledger.yaml` merge conflict
- 从 index 移除嵌入式 git 仓库 `projects/knowledge/kairon-security`
- `.crush/` 大文件（747MB）加入 `.gitignore` 并从 commit 中剔除
- `projects/omlxc` submodule 推送至 `omostation-omlxc` 远程 `main`

---

## 2. P78 诊断前置 4 问

### 2.1 反证找了吗
- 证据支持：本地 tests 176 passed, 1 xfailed；submodule `omlxc` 推送成功
- 反证：`.crush/` 大文件在 amend 前已入仓，amend 后历史记录中仍有引用（`git ls-tree HEAD -- .crush/` 已清除）

### 2.2 查运行时实证了吗
- cockpit tests 在本地全量运行通过
- `omlxc` submodule 推送至 `omostation-omlxc` 远程 `main`（`ec48f56..6763927`）

### 2.3 读相关 ADR 了吗
- `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md` 已读
- P78 模式参考：`.omo/_knowledge/patterns/p78-triple-axis-diagnostic-pattern.md`

### 2.4 扫了工具链吗
- `bin/ssot` + `.github/workflows` 确认 deprecated commands 已从 registry/CLI dispatch/tests 全链路清除
- `projects/cockpit/tests/` 全量通过

---

## 3. 三层固化

| 层 | 操作 | 状态 |
|----|------|------|
| 记忆层 | 写 retro → `.omo/_knowledge/retros/` | ✅ 本文档 |
| 协议层 | 更新 AGENTS.md/CLAUDE.md | ⏭ 无需更新 |
| Harness 层 | 更新 hook/check | ⏭ 无需更新 |

---

## 4. 复盘结论

### 做得好的
1. **收尾完整** — P0–P3 全部 action items 闭环，tests pass
2. **及时清理** — 发现 `.crush/` 大文件问题后立即 amend，避免污染历史
3. **submodule 推送** — `omlxc` 在检测到 unreachable 后及时推送至其专用 remote

### 可以改进的
1. **git add 时机** — 多次 `git add -A` 导致嵌入式 git 仓库反复进入 index，应在首次 add 后立即检查
2. **大文件前置检查** — `.crush/` 应更早加入 `.gitignore`，避免在 commit 阶段才处理
3. **submodule remote 配置** — `omlxc` 的 remote 在 push 时才被发现不匹配，应在 audit 阶段就验证

### 下次行动
1. audit 阶段加入 `git ls-files | grep -E "\.(db|sqlite3)$" | xargs du -sh` 检查大文件
2. 首次 `git add` 后立即 `git status --short | grep "adding embedded"` 检查嵌入式仓库
3. submodule audit 时加入 `git remote -v` 验证 remote URL 匹配

---

## 5. 证据

- commits: `095380b38` + `a5736a2f5`
- tests: `projects/cockpit/tests/` 176 passed, 1 xfailed
- submodule push: `ec48f56..6763927` → `github.com:starlink-awaken/omostation-omlxc.git`
- `.crush/` amend: `git show --stat HEAD` 确认 `.crush/crush.db` 已清除
