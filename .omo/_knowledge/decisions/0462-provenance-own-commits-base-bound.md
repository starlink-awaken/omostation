---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: architecture-governance
last-reviewed: 2026-10-02
type: ssot
id: ADR-0462
related: ADR-0460, ADR-0422
tags: [provenance, own-commits, platform-base, rev-list, regression]
---

# ADR-0462 — mainline 收窄不得丢弃 `identity_base` 下界

- **Status**: ACCEPTED（2026-10-02；修正 ADR-0460 收窄引入的回归，已实施）
- **Date**: 2026-10-02
- **Owner**: architecture-governance
- **Related**: ADR-0460（provenance 身份校验收窄到 clone 自身提交）

## 问题

ADR-0460 把「clone 自身提交」的界定从 `<base>..<head>` 改为
`rev-list <head> --not <mainline refs>`，以解决「并发活跃仓里他人合入 main 的提交
被误算成自身提交」。

但收窄后 `base_sha`（`identity_base`，取值为 `platform_base_sha` 或 `frozen_sha`）
这个**下界**被静默丢弃了 —— `commit_identities_match` 的两条分支是：

```python
if mainline_refs is not None:
    commit_shas = own_commit_shas(repo_root, head_sha, mainline_refs)   # base_sha 未用
else:
    commits = git(repo_root, "rev-list", f"{base_sha}..{head_sha}")     # 旧路径用 base_sha
```

后果：**只要平台在 agent 开工前自己推进过 base**，那些平台提交的作者不是 clone 身份，
于是落进「自身提交」集合 → `commit_identities_match` 判 False →
`clone_provenance_mismatch`。

该回归自 #4556 起存在，由三项用例持续报出（`test_platform_provenance_accepts_exact_github_merge_wrapper`
等），另连带四个 `test_retire_*` 失败（同一根因的下游）。**合计 7 个红测试。**

## 事实（实测，同一 fixture）

| 区间 | 提交 | 结果 |
|---|---|---|
| 旧：`platform_base..source_head` | 1 个（agent 的） | 通过 |
| 收窄后：`source_head --not <mainline>` | **2 个（含 platform 的）** | 身份不匹配 → 回归 |

## 修法

把 `identity_base` 作为**下界**重新纳入排除项：

```python
commit_shas = own_commit_shas(
    repo_root, head_sha, mainline_refs, exclude_shas=[base_sha]
)
```

**语义是收窄而非放宽。** 被排除的 `base_sha` 及其祖先在 agent 开工前就存在，
不可能是 clone 加的提交，本就不该按 clone 身份校验。平台路径下 `platform_base_sha`
已被「`frozen → base`」与「`base → head`」两处祖先校验约束在 `frozen..head` 之内，
故排除它不构成绕过。

非平台路径下 `base_sha = frozen_sha`，通常已是 main 的祖先，追加排除是冗余但无害的。

## 实现陷阱：`--not` 是切换，不是标志

`git rev-list` 的 `--not` 作用于**其后所有 rev 直到下一个 `--not`**：

```
A --not B C --not D
  = 包含 A、排除 B 与 C、**再切回包含 D**
```

因此排除项必须与 mainline refs **共用同一个 `--not`**：

```python
args = ["rev-list", head_sha, "--not", *mainline_refs, *(exclude_shas or [])]
```

修复初版误写成逐个追加 `--not`，结果把 `platform_base` **反向包含**进去，区间反而
变大 —— 3 个用例仍红。`tests/unit/test_clone_provenance_own_commits.py::
test_exclude_and_mainline_share_one_not_flag` 专门钉死这一点。

## 影响面

- 仅 `own_commit_shas` 增加 `exclude_shas` 关键字参数（默认 `None`，向后兼容）
- `commit_identities_match` 在 `mainline_refs` 分支传回 `base_sha`
- **不放宽任何 fail-closed 语义**：区间变小，校验更严
- ADR-0460 的收窄目标（排除并发合入 main 的他人提交）**仍然成立**

## 验收

| 用例 | 修复前 | 修复后 |
|---|---|---|
| `tests/test_clone_lifecycle.py` 全文件 | 7 failed | **0 failed**（107 passed） |
| `tests/unit/test_clone_provenance_own_commits.py` | 3 passed | 7 passed |

新增 3 项 focused 用例（平台 base 推进场景 + `--not` 切换语义护栏）。

## 证据

- 回归点：`bin/gac/agent-clone.py` `own_commit_shas` / `commit_identities_match`
- 用例：`tests/test_clone_lifecycle.py::test_platform_provenance_*`(3)、
  `test_retire_*`(4，同根因下游)
- focused：`tests/unit/test_clone_provenance_own_commits.py`
- 引入回归的提交：`60f9e3eb5`（#4556，ADR-0460 收窄）

## 决策记录

- **2026-10-02**: 定位并修正。收窄方向本身正确，缺陷是丢了下界。
  另记录实现陷阱：`--not` 的切换语义使「逐个追加排除项」成为反向操作。
