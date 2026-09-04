---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Submodule 治理整合方案（2026-08-08）
type: doc
---
# Submodule 治理整合方案（2026-08-08）

> 基于 2026-08-08 会话的完整问题链（agora CI 双通道、reachability gate 全局冻结、
> submodule bump 传播断裂）沉淀的系统性治理整合。目标：从机制上消除同类病，而非逐次打补丁。

## 一、问题全景（8 个现象 → 3 条根因主线）

| # | 现象 | 表面原因 | 根因主线 |
|---|---|---|---|
| 1 | agora 独立 CI 全红 10+ runs | 8 个 path 依赖独立 runner 不存在 | A: 依赖可达性无预检 |
| 2 | test_forge_loader 硬编码本机路径 | 环境路径写死 | A: 环境性依赖无识别 |
| 3 | agora 修复合入但通道验证旧代码 | gitlink 停在旧版 | B: submodule 更新无反向传播 |
| 4 | 直接改 gitlink 被 hook 拒绝 | GAC 治理 | （合理，入口不清） |
| 5 | push 被 13 个无关 submodule 拦截 | reachability gate 全仓检查 | C: 门禁粒度太粗 |
| 6 | worktree origin 指向 agora | 配置继承错误 | C: 工具成熟度 |
| 7 | 双 CI 通道无人声明权威 | 历史遗留 | A: CI 所有权缺失 |
| 8 | 永远红的 CI 掩盖真实 bug | 狼来了 | A: 无 CI 健康度监控 |

## 二、根因主线与机制解法

### 主线 A：依赖可达性无预检 → 结构性错配静默存在
- agora 声明 8 个 `{path = "../kairon/packages/*"}` 依赖，无任何机制在配置层验证"独立 checkout 能否构建"
- 失败发生在 `uv sync` 运行时，且因"永远失败"被正常化
- **已落地**：PR #18 废弃 agora 独立 ci.yml（错误被正常化的源头消除）
- **待落地**：依赖可达性预检（CI 加构建前置断言）

### 主线 B：submodule 更新无自动化传播 → 修复代码永远迟到
- agora 合并 #16/#17/#18 → agora main 推进 → omostation gitlink 不自动跟进 → 通道验证旧代码
- **已落地**：PR #1202 bump agora → 44091bc1（走 GAC bump-pointer 治理流程）
- **待落地**：自动 bump 告警（CI 检测 gitlink 落后）

### 主线 C：reachability gate 全仓检查 → 任何 agent 中途状态冻结所有人
- pre-push hook 检查**全部 17 子模块** gitlink 可达性，一个 agent 的本地 commit 未推送即全局 push 失败
- **待落地（本方案核心）**：增量检查——只验证本次 diff 实际变化的 submodule

## 三、核心改进：reachability gate 增量检查

### 现状（bin/ssot/submodule-reachability-gate.py, 169 行）
```python
def check(source, *, fetch, skip_paths=None):
    for path in submodule_paths():  # 遍历全部 17 个
        if skip_paths and path in skip_paths:
            skipped += 1
            continue
        sha = gitlink_sha(path, source)
        ok, detail = remote_contains(path, sha, fetch=fetch)
        findings.append(...)
    failures = [item for item in findings if not item["ok"]]
    return {"ok": not failures, ...}
```
- 已含 G1 (P79) partial worktree 降级、shallow unshallow、GIT_DIR pop（治本 followup E）
- **缺口**：`submodule_paths()` 无条件全量，无"本次变更过滤"参数

### Patch：`--changed-from <base>` 增量模式
```python
# 新增: 提取本次 diff 涉及的 submodule
def changed_submodule_paths(base: str) -> set[str]:
    """git diff <base>..HEAD 中发生 gitlink 变化的 submodule 路径集合."""
    result = run(["git", "diff", "--name-only", base, "HEAD", "--", ".gitmodules", "projects/*"])
    changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    # .gitmodules 自身变化 → 全量检查（防御）
    if ".gitmodules" in changed:
        return set(submodule_paths())
    return {p for p in changed if p != ".gitmodules"}

# check() 签名扩展
def check(source, *, fetch, skip_paths=None, only_paths=None):
    paths = submodule_paths()
    if only_paths is not None:
        paths = [p for p in paths if p in only_paths]  # 只检查本次变更
        if not paths:
            return {"ok": True, "source": source, "checked": 0, "skipped": 0,
                    "failures": [], "findings": [], "mode": "incremental-empty"}
    # ...原逻辑
```

### 行为矩阵
| 模式 | 触发 | 检查范围 | 冻结影响 |
|---|---|---|---|
| 全量（默认，CI） | `--source head --fetch`（evidence-smoke-gate） | 全部 17 | CI 是最终守门员（合理） |
| 增量（本地 pre-push） | `--changed-from <base>` | 仅本次变更 | 并行 agent 中途状态零影响 |

### 为什么安全
1. **CI 不变**：evidence-smoke-gate 仍全量检查，main 合并后的完整性由 CI 守门
2. **本地增量**：只检查自己改的 gitlink，他人漂移不再阻塞我的 push
3. **.gitmodules 变化防御**：改 .gitmodules 本身触发全量（结构变更高风险）

## 四、配套机制（本次一并落地）

### 4.1 CI 所有权声明（docs/operations/CI-OWNERSHIP.md）
每个仓库声明唯一权威 CI 通道：
| 仓库 | 权威通道 | 独立通道处置 |
|---|---|---|
| agora | omostation agora-ci.yml | ✅ 已废弃（PR #18） |
| kairon/ecos/cockpit/family-hub | 各自 CI | 待审计 |

### 4.2 submodule 漂移告警（CI job 新增）
`check-submodule-pointer-drift.py`（已有，BET-Y1Q2-T1-05）纳入 governance-check 定时告警：
- gitlink 落后于子模块 origin/main → 提示 bump
- 连续 N 天无 bump → 告警（防"修复代码迟到"）

### 4.3 依赖可达性预检（CI 步骤新增）
agora-ci.yml 增加构建前置断言：`uv sync` 前检查 path 依赖目录存在，缺失则明确报
"此仓库不能独立构建，必须作为 omostation 子模块开发"，替代静默失败。

## 五、落地清单

| 优先级 | 项 | 状态 | 载体 |
|---|---|---|---|
| P0 | reachability gate 增量检查 | **本次落地** | bin/ssot/submodule-reachability-gate.py |
| P0 | pre-push 调用增量模式 | **本次落地** | .git/hooks/pre-push（治本 D 后接增量调用） |
| P0 | CI 所有权声明 | 本次文档 | docs/operations/CI-OWNERSHIP.md |
| P1 | agora gitlink bump | ✅ 已落地 | PR #1202 |
| P1 | agora 独立 ci.yml 废弃 | ✅ 已落地 | PR #18 |
| P1 | forge 环境性测试修复 | ✅ 已落地 | PR #17 |
| P1 | submodule 漂移告警 | 后续 | governance-check.yml |
| P1 | 依赖可达性预检 | 后续 | agora-ci.yml |

## 六、监督与判断规则（速查）

### push 被 gate 拦截时
1. 看拦截的 submodule 是否在本次 diff 中？
   - 不在 → 增量模式已跳过（若仍被全量拦，说明 pre-push 未走增量，修 hook）
   - 在 → 先推 submodule commit 再 push 主仓库（GAC 顺序：子模块 → gitlink → 主仓）

### CI 红时
1. 失败阶段？`uv sync`（依赖/结构）vs pytest（代码）→ 分别修机制/修代码
2. 唯一通道还是重复通道？重复 → 查 CI-OWNERSHIP 废弃或修复

### 合并 submodule bump 前
1. gitlink 指向 commit 在子模块远程存在？（`git ls-remote` 验证）
2. 合并后 CI `submodules: recursive` 能拉到？拉不到 = 合并即全红

### escape hatch 使用
- 用 `CI_LOCAL_SKIP=1` + `SWARM_ESCAPE_ID=<id>`（需在 swarm-coordination.yaml 登记）
- **不用**裸 `--no-verify`（会被观测窗计为 escape_hatch_abuse）
