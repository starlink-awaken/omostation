---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Agora CI 运维经验（2026-08-08 会话沉淀）
type: doc
---
# Agora CI 运维经验（2026-08-08 会话沉淀）

> 本文沉淀 2026-08-08 会话中关于 agora 仓库 CI 的完整调查结论与修复记录，供后续运维复用，避免重复调查。

## 1. agora 仓库定位（关键认知）

agora 是 **omostation monorepo 的 git submodule**（`projects/agora`，remote `starlink-awaken/omostation-agora.git`）。

- **无分支保护**：agora main 可 PR 直合（与 omostation 需 phase-gate 不同），PR 合并走 `gh pr merge --merge` 即可
- **结构性依赖**：`pyproject.toml [tool.uv.sources]` 声明 8 个本地 path 依赖（`kos`/`bus-foundation`/`eidos`/`minerva`/`core-models`/`ecos`/`metaos`），指向 `../kairon/packages/*` 和 sibling 目录
- 这些包是 omostation 的 submodule —— **独立 runner 上永远不存在**

## 2. 双 CI 结构与决策（PR #18）

历史存在两个 CI：

| 通道 | 状态 | 结论 |
|---|---|---|
| agora 独立 `ci.yml` | 结构性损坏（uv sync 因 8 个 path 依赖失败，10+ runs 全红） | **已删除**（PR #18） |
| omostation `agora-ci.yml` | 有效（`projects/agora/**` 触发，submodule 完整 checkout，test + deploy-smoke） | **唯一通道** |

**教训**：永远红的 CI 是负资产（噪音 + 掩盖真实问题）。monorepo 子模块的独立 CI 本质不可行，应移交 monorepo 通道。

## 3. 环境性测试模式（PR #17）

`test_forge_loader.py` 曾硬编码本机绝对路径插入 sys.path → CI collection error。

修复模式（对齐 `test_bos_registry_contract.py` 的 broken 白名单机制）：

```python
# forge 是环境性外部包 (来自 kairon 独立仓库): CI 中不可用 → 跳过本模块
forge_market = pytest.importorskip(
    "forge.market", reason="forge 不可用 (kairon 独立仓库, 非 agora 依赖)"
)
```

**规则**：测试不得硬编码本机路径；环境性外部包用 `importorskip` / 白名单跳过，缺失不视为代码缺陷。

## 4. submodule gitlink bump 治理（未完成事项）

**关键状态**：omostation main 的 agora gitlink 停在旧版 `4c775439`，agora 仓库 3 项修复（#16 god-module 拆分、#17 forge 修复、#18 CI 废弃）在 agora 远程 `44091bc1`，但 **omostation 侧未 bump** → omostation 的 agora-ci 通道验证的是旧代码。

**治理约束**：omostation 有 `submodule-guard` hook，拒绝直接改 gitlink。正确流程（见 `docs/SUBMODULE-PR-STRATEGY.md`）：

```bash
bash bin/gac/gac-worktree.sh claim <session>     # 起治理 worktree
git submodule update --init projects/agora       # worktree 默认不 init
cd projects/agora && git checkout main           # init 后 detached
# ... 改子模块 commit ...
cd ../.. && git add projects/agora && git commit # bump pointer
bash bin/gac/gac-worktree.sh submit <session>    # pre-push 触发 sync-submodules → 子模块 direct push
bash bin/gac/gac-worktree.sh merge <session>
```

**待办**：将 agora gitlink 从 `4c775439` bump 到 `44091bc1`（含 #16/#17/#18），使 omostation agora-ci 通道验证修复代码。由于 `44091bc1` 已在 agora 远程，此 bump 是纯 gitlink 更新，无需子模块 commit。

## 5. 快速参考

```bash
# agora 无保护直合
gh --repo starlink-awaken/omostation-agora pr merge <n> --merge --delete-branch

# 检查 omostation 侧 agora gitlink
git ls-tree main projects/agora | awk '{print $3}'

# 检查 agora CI 通道状态
gh run list --workflow agora-ci.yml --limit 5

# agora 本地 path 依赖清单
grep -E "= \{ path|path =" projects/agora/pyproject.toml
```
