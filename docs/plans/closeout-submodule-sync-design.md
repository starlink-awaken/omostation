---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# 子模块漂移治理 — 深度设计方案

> 版本: 2026-08-08  
> 状态: 设计稿  
> 关联: ADR-0371 (PASW), PR#1166 (closeout insights), BET-Y1Q2-T1-05

## 1. 现状分析

### 已有机制
| 机制 | 位置 | 能力 |
|------|------|------|
| 漂移检测 | `bin/gac/check-submodule-pointer-drift.py` | 检测 DIVERGED/stale/ahead |
| 未推同步 | `bin/ssot/sync-submodules-push.sh` | pre-push 时 push 子模块未推 commit |
| PASW 隔离 | `bin/gac/gac-worktree.sh` + `lib/pasw-core.sh` | 高冲突子模块 per-agent worktree |
| 债务种子 | `bin/gac/debt-auto-seed-drift.py` | 漂移自动写入 `.omo/debt/` |
| CI 日清 | `Makefile ci-local-fast` | ruff + pyright + drift + debt-seed |

###  gaps
1. **无 stale 自动 pull**: pre-push 只 push 未推 commit，不 pull 过期子模块
2. **PASW 漂移检测盲区**: drift check 只读 `projects/<sub>`，不读 `.subtrees/<sub>`
3. **CI 无 auto-fix**: CI 检测到 drift 只报错，不自动修复
4. **submit 未集成 sync**: `gac-worktree.sh submit` 不自动同步子模块

## 2. 深度设计方案

### 2.1 Enhanced sync: `sync-submodules-push.sh --pull`

**目标**: pre-push 时不仅 push 未推 commit，还 pull 过期子模块

**实现**:
```bash
# 新增 --pull 模式
sync-submodules-push.sh --pull    # pull stale + push unpushed
sync-submodules-push.sh           # 仅 push (原有行为)
```

**逻辑**:
1. 遍历所有子模块
2. 检查 `origin/main` vs 本地 HEAD
3. 如果本地落后 (stale) 且非 PASW 子模块:
   - `git checkout main && git pull`
4. 如果本地领先 (unpushed):
   - `git push --no-verify origin HEAD`
5. PASW 子模块 (.subtrees/) 跳过 pull (由 bump-pointer 管理)

**复用**: 复用现有 `sync-submodules-push.sh` 的遍历逻辑，新增 pull 分支

### 2.2 PASW-aware drift detection

**目标**: drift check 同时检查共享区和 PASW 隔离区

**实现**: 增强 `check-submodule-pointer-drift.py`:
```python
# 新增: 检查 .subtrees/ 状态
PASW_SUBTREE_DIR = ".subtrees"
PASW_ISOLATED_SUBS = ["projects/knowledge/gbrain", "projects/cockpit", "projects/agora"]

def check_pasw_drift(sub_name: str) -> dict:
    """检查 .subtrees/<sub> 的漂移状态"""
    sub_wt = REPO_ROOT / PASW_SUBTREE_DIR / sub_name
    if not sub_wt.exists():
        return {"status": "skip", "reason": "no pasw worktree"}
    
    # 检查 .subtrees/<sub> HEAD vs origin/<session>-<sub>
    # 检查 projects/<sub> gitlink vs .subtrees/<sub> HEAD
    ...
```

**输出**:
```json
{
  "results": [
    {"submodule": "projects/agora", "status": "aligned", ...},
    {"submodule": ".subtrees/agora", "status": "ahead", "detail": "PASW worktree has unpushed commits"}
  ]
}
```

### 2.3 CI auto-fix

**目标**: CI 检测到可自动修复的 drift 时自动修复

**实现**: 新增 `Makefile` target:
```makefile
.PHONY: submodule-sync-auto
submodule-sync-auto:
	@echo "── submodule auto-sync (pull stale + push unpushed) ──"
	bash bin/ssot/sync-submodules-push.sh --pull 2>&1 | sed 's/^/[sync] /'
	python3 bin/gac/check-submodule-pointer-drift.py --json 2>&1 | \
		python3 -c "import sys,json; d=json.load(sys.stdin); ..."
```

**CI 集成**:
```yaml
# .github/workflows/governance-check.yml
- name: Submodule sync
  run: make submodule-sync-auto
```

### 2.4 Agent workflow integration

**目标**: `gac-worktree.sh submit` 自动同步子模块

**实现**: 在 `submit` 命令中增加:
```bash
# 提交前自动同步子模块
echo "⚡ 自动同步子模块..."
bash "$(dirname "$0")/../sync-submodules-push.sh --pull" 2>&1 | tail -5
```

**时机**: 
- `submit` 时自动运行 (pre-push 之前)
- 确保子模块 commit 已推送，gitlink 可达

## 3. 架构衔接

### 复用现有组件
| 组件 | 复用方式 |
|------|----------|
| `sync-submodules-push.sh` | 新增 `--pull` flag，复用遍历逻辑 |
| `check-submodule-pointer-drift.py` | 新增 PASW 检查函数 |
| `debt-auto-seed-drift.py` | 已实现，直接调用 |
| `gac-worktree.sh` | submit 命令集成 auto-sync |
| `pasw-core.sh` | PASW worktree 检测复用 |

### 与 PASW 的边界
- **PASW 子模块** (gbrain/cockpit/agora): 
  - 不自动 pull (由 bump-pointer 管理)
  - 漂移检测检查 `.subtrees/<sub>` 状态
  - 未推检测检查 `.subtrees/<sub>` 和 `projects/<sub>` 两端
- **非 PASW 子模块** (其余 14 个):
  - 自动 pull + push
  - 漂移检测只检查 `projects/<sub>`

## 4. 实施计划

### Phase 1: Enhanced sync (1-2h)
1. 修改 `sync-submodules-push.sh`: 新增 `--pull` 模式
2. 测试: `make ci-local-fast` 验证

### Phase 2: PASW-aware drift (1-2h)
1. 修改 `check-submodule-pointer-drift.py`: 新增 PASW 检查
2. 更新 `pre-push` hook: 调用增强版 drift check
3. 测试: 在 PASW worktree 中验证

### Phase 3: CI integration (30min)
1. 新增 `Makefile submodule-sync-auto` target
2. 更新 CI workflow (如需)
3. 测试: `make submodule-sync-auto`

### Phase 4: Agent workflow integration (30min)
1. 修改 `gac-worktree.sh submit`: 增加 auto-sync
2. 测试: claim → work → submit 流程

## 5. 风险评估

| 风险 | 缓解 |
|------|------|
| auto-pull 覆盖本地改动 | 仅 pull 无本地改动的子模块 (检查 `git diff --quiet`) |
| PASW 子模块误 pull | PASW 子模块跳过 pull，由 bump-pointer 显式管理 |
| CI 时间增加 | auto-sync 仅在有 drift 时执行，平时 skip |
| 并发冲突 | PASW 已隔离高冲突子模块，auto-sync 只操作非 PASW |

## 6. 验收标准

- [ ] `sync-submodules-push.sh --pull` 通过 `make ci-local-fast`
- [ ] `check-submodule-pointer-drift.py` 输出包含 PASW 状态
- [ ] `make submodule-sync-auto` 修复 stale 子模块
- [ ] `gac-worktree.sh submit` 自动同步子模块
- [ ] PR CI 全绿 (除预存债务)
