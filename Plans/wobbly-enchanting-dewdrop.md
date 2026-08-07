# 下阶段推进 Plan — fabric 收官后的 4 项建议

> 创建: 2026-08-07 | 模式: Plan Mode | 前置: fabric 红线推进收官 (5 PR merged: #1051/#1055/#1058/#1062/#1071)
> 策略: 每项独立 worktree (基于 origin/main), D3 声明工作流, SWARM_ESCAPE_ID 逃生舱矩阵

---

## 0. Context

fabric 红线推进收官后（document-review 3/3 公文源 active + drift 根治 + god-module 部分解除），复盘识别出 5 个下阶段建议。本 plan 调研后**剔除 1 个过时项**（agora F821 已修），保留 4 项，按价值/风险/可控性排序。

**调研发现（truth-driven）**：
- seeyon_oa `list_items` **也用 `127.0.0.1`**（#1071 只修了 `is_available`）—— 这是 `iris list seeyon_oa` 返回 "no results" 的真根因（CDP 404 扫不到 tab）
- agora F821 已在 main 修复（`ruff check src/ --select F821` All passed）—— 剔除
- cockpit api_system_map_catalog.py 1565 行（god-module，结构待细看）

---

## 1. Roadmap（4 项优先级）

| 优先级 | 项 | 价值 | 风险 | 工程量 |
|--------|-----|------|------|--------|
| **P0** | seeyon_oa list_items localhost 修复 + Runtime.evaluate 增强 | 高（document-review 真能跑公文） | 低 | 中 |
| **P1** | cockpit api_system_map_catalog.py god-module 拆解 | 高（解除 PR 阻塞） | 中（ruff + 大文件） | 大 |
| **P2** | bos-registry drift 监控（验证 #1058） | 中（防复发观测） | 低（只读） | 小 |
| **P3** | engineering-delivery 激活证据链 | 中（业务前置） | —（客观证据） | —（等输入） |

---

## 2. P0: seeyon_oa list_items 修复 + Runtime.evaluate 增强

### 问题
- `list_items` 行 ~70 `urlopen("http://127.0.0.1:9222/json/list")` —— Chrome 111+ DNS rebinding 404（#1071 漏修）
- 边界注释：「定位 tab 级；DOM 深抓待办公文需后续 CDP Runtime.evaluate」—— 当前只返回 tab 元数据

### 方案（两步）

**Step 1: list_items localhost 修复**（1 行，同 #1071）
- 文件: `projects/kairon/packages/iris/src/iris/connectors/seeyon_oa.py`
- `127.0.0.1` → `localhost`
- 验证: `iris list seeyon_oa --limit 3` 返回 OA tab（CDP Chrome 开 + OA 登录后）

**Step 2: Runtime.evaluate 增强**（DOM 深抓待办公文）
- CDP WebSocket（tab 的 webSocketDebuggerUrl）发 `Runtime.evaluate` 执行 JS
- JS 抓 OA 待办列表 DOM，返回 Note[] 含公文标题/链接/时间
- 失败降级返回 tab 元数据（F14 错误隔离）

### 实施
1. kairon worktree: `git -C projects/kairon worktree add ws-seeyon-list -b work/seeyon-list-runtime-eval origin/main`
2. Edit list_items（127.0.0.1→localhost）
3. 加 `_fetch_pending_via_runtime`（CDP WebSocket + Runtime.evaluate）
4. list_items 调 _fetch_pending_via_runtime（失败降级）
5. `iris list seeyon_oa --limit 5` 验证
6. ruff format + commit + push --no-verify（既有 debt）+ Workspace 根 bump + PR + admin merge

### 风险
- OA DOM 结构未知 —— Step 2 先 CDP console 探选择器
- CDP WebSocket 客户端：看 kairon 是否已有 `websockets` 依赖

---

## 3. P1: cockpit api_system_map_catalog.py 拆解

### 问题
- 1565 行（god-module GATE FAIL 阻塞所有 PR）
- cockpit ruff format（老王栽过循环，careful）

### 方案（同 agora external_connections 模式）
1. 勘察结构: `grep -nE "^class |^def |^    def |^@" api_system_map_catalog.py`
2. 抽自包含段到新模块 + re-export（保 __all__ + 调用方兼容）
3. ruff format + cockpit 测试 + bump + PR

### 风险
- cockpit PASW（.subtrees/cockpit）+ ruff 全 repo 检查
- **建议**: 先勘察，quick win（抽一段减 <1500）则做，否则标专项

---

## 4. P2: bos-registry drift 监控（验证 #1058）

### 目的
验证 #1058 bump-pointer auto-sync 在真实 agora bump 时生效。

### 方案（只读观测）
- 等下次 agora bump（别人或老王触发）
- `make check-docs-drift` 看 drift=no（#1058 生效）
- drift 复发则定位 #1058 是否触发

---

## 5. P3: engineering-delivery 证据链（等业务）

5 个 activation_blockers（客观证据，非授权能解）：
- 老王能准备: sample_refs 骨架
- 等业务: business owner 确认 + result consumer + OMO admission
- **不硬激活**（红线）

---

## 6. worktree 策略（D3 + 逃生舱）

```bash
# 通用 worktree (手动, 避免 gac-worktree claim 超时)
git fetch origin main
git worktree add /Users/xiamingxing/ws-<task> -b work/<task> origin/main

# commit + push (逃生舱矩阵)
SWARM_ESCAPE_ID=write-owner-repair-draft bin/gac/swarm-git commit --no-verify -m "..."
SWARM_ESCAPE_ID=submodule-reachability-partial-worktree bin/gac/swarm-git push --no-verify -u origin work/<task>

# PR + admin merge
gh pr create --base main --head work/<task> --title "..." --body "..."
gh pr merge <pr> --squash --admin
```

submodule 改动（kairon/cockpit）：先 submodule 独立 worktree commit + push，再 Workspace 根 bump + PR。

---

## 7. 验证

| 项 | 命令 | 期望 |
|----|------|------|
| P0 Step1 | `iris list seeyon_oa --limit 3` | 返回 OA tab（非 no results） |
| P0 Step2 | `iris list seeyon_oa --limit 5` | Note[] 含 OA 待办公文 |
| P1 | `make gac-local-gate` | api_system_map_catalog <1500L |
| P2 | `make check-docs-drift`（agora bump 后） | drift=no |
| P3 | `cat engineering-delivery-dogfood.yaml` | 等 OMO admission + business |

---

## 8. 执行顺序建议

1. **P0 Step1 先**（1 行修复，立刻让 `iris list seeyon_oa` 工作，快赢）
2. **P2 观测**（被动，等 agora bump）
3. **P0 Step2**（Runtime.evaluate，勘察 OA DOM，中工程）
4. **P1**（cockpit god-module，先勘察再定 quick win vs 专项）
5. **P3**（等业务，不主动）

从 **P0 Step1** 起手，看 token/时间决定推进 P0 Step2 还是 P1。
