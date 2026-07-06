# Submodule PR 反向 Review Guide (ADR-0150, Round 5e)

> **配套 ADR-0150** (R5e, 2026-07-06)
> **配套**: docs/MCPTOOL-ADDER-GUIDE.md (单 PR 模板规范), AGENTS.md §10 (round workflow)
> **状态**: 沉淀自 PR #131 (merged) / #102 (closed) / #136 (merged) / #137 (closed) 共 4 个 submodule PR 实战

---

## 0. TL;DR

过去 5 个 PR (#131, #102, #136, #137, PR #135 #134 #133 链) 模式显示:
- **3 个 PR 是 submodule "stale"**(creator push 后,主仓前进,子模块 SHA 不再最新)
- **3 个 closed** + **3 个 merged** 共 6 个 PR 中,比例 **50% close / 50% merge**
- 共同失败模式:**PR body 描述的 commit 哈希与 gitlink 实际不符**,**PR HEAD 落后 main HEAD**

本文档给出 submodule PR 提交者与 reviewer 的双向 review checklist:
- 提交者: 5 步自检
- Reviewer: 6 步守门

---

## 1. submodule PR 3 种模式 (历史实证)

| 模式 | 例子 | 原因 | 解法 |
|------|------|------|------|
| **A. 匹配主仓** (no-op) | PR #131 (R0..R5 主,18 子模块 bump 都 match main HEAD) | 提交者本地领先 main push 时 merge,但分支保留 | squash merge (no-op 仍把文档 + ADR 落地) |
| **B. 落后** (stale) | PR #102 (2 commit 落后)、PR #103 (已合即 PR #102 redundant)、PR #137 (gBrain reset 老 commit) | 提交者 push 后未与 main 同步 | **close,等主仓推进自然覆盖** |
| **C. 真正补** (missing fix) | PR #103 (4966.7d91 修复), #131 (M4 元模型) | 提交者 push 立即 + 重要修复 | merge (早合早治本) |

**Reviewer 首要任务**: 区分 PR 是 A (no-op 文档),B (过时),C (补漏)。

---

## 2. 提交者 5 步自检 (PR 提交前)

### Step 1: 同步主仓最新

```bash
git fetch origin main
git checkout main
git pull --rebase origin main   # 或 ff
```

### Step 2: 比较 PR 提议与当前 main 的 submodule SHA

```bash
# PR-准备分支相对 main HEAD 的 submodule diff
git fetch origin work/{your-branch}
git rev-list --left-right origin/main..origin/work/{your-branch} \
  -- projects/{each-submodule} | head

# 或直接看 gitlink 差异
for sub in projects/ecos projects/runtime projects/omo; do
  head_sha=$(git ls-tree HEAD $sub | awk '{print $3}')
  pr_sha=$(git ls-tree origin/work/{your-branch} $sub | awk '{print $3}')
  echo "$sub: HEAD=$head_sha PR=$pr_sha $([ "$head_sha" = "$pr_sha" ] && echo match || echo DIFF)"
done
```

**期望**: 所有 submodule status = `match`。如果 DIFF,需要 `git submodule update --remote {sub}`。

### Step 3: 验证 PR body commit SHA 与 gitlink 一致

```bash
gh pr view {your-num} --json body,files \
  --jq '.body' | grep -oE '[0-9a-f]{40}' > /tmp/pr-body-sha.txt
git ls-tree origin/work/{your-branch} | grep -oE '[0-9a-f]{40}' > /tmp/pr-gitlink-sha.txt
diff /tmp/pr-body-sha.txt /tmp/pr-gitlink-sha.txt
```

**期望**: 无差异。如果有差异, **修改 PR body** 让 SHA 与 gitlink 一致(否则 reviewer 关闭时标"不一致")。

### Step 4: 本地 5-check strict + 57 测试

```bash
uv run --with "pyyaml" python bin/mof-bootstrap.py all
uv run --with "pyyaml" python tests/integration/m4_metamodel/run_all.py
uv run --with "pyyaml" python bin/m4-health-score.py
```

**期望**: 5-check strict all 0 err, 57/57 PASS, Health Score 100/100。

### Step 5: 推 + 开 PR

```bash
git push origin work/{your-branch}
gh pr create --base main --head work/{your-branch}
```

---

## 3. Reviewer 6 步守门 (PR review 时)

### Step 1: 查 PR 创建时间 vs main HEAD 活动

```bash
gh pr view {num} --json createdAt,additions,deletions
echo "main HEAD last 10:"
git log --oneline main -10
```

**判定**: PR createdAt 距最新 main HEAD commit 时间 < 30 min → 高风险 stale(主仓推进非常活跃)。

### Step 2: 列出 PR 与 main HEAD 的 submodule SHA 对比表

```bash
gh_pr_num={num}
gh_pr_branch=$(gh pr view $gh_pr_num --json headRefName -q .headRefName)

echo "submodule | main HEAD | PR #${gh_pr_num}"
git submodule foreach --quiet --recursive 'echo "$sm_path $(git rev-parse HEAD) $(cat .gitmodules | ...)"' 2>/dev/null

# 简化版
for sub in $(git diff --name-only main origin/$gh_pr_branch | grep '^projects/' | cut -d/ -f1-2 | sort -u); do
  head_sha=$(git ls-tree HEAD $sub 2>/dev/null | awk '{print $3}')
  pr_sha=$(git ls-tree origin/$gh_pr_branch $sub 2>/dev/null | awk '{print $3}')
  echo "$sub | $head_sha | $pr_sha | $([ "$head_sha" = "$pr_sha" ] && echo match || echo DIFF)"
done
```

**判定**:
- 全 `match` → 模式 A (可以 squash merge, no-op 文档)
- 仅 1-2 个 `DIFF`(老 commit 落后) → 模式 B (close, 让主仓推进)
- `DIFF` 是新修复 (例如 `d8fdd8d` 后于 `1f62411bc`) → 模式 C (merge)

### Step 3: 验证 PR body SHA 与 gitlink 一致

```bash
gh pr view {num} --json body \
  --jq '.body' | grep -oE '[0-9a-f]{7,40}' | sort -u > /tmp/pr-body-sha.txt
gh pr view {num} --json files \
  --jq '.files[] | select(.path | startswith("projects/")) | .path' | \
  while read sub; do
    git ls-tree origin/$gh_pr_branch $sub 2>/dev/null
  done | grep -oE '[0-9a-f]{40}' | sort -u > /tmp/pr-gitlink-sha.txt
diff /tmp/pr-body-sha.txt /tmp/pr-gitlink-sha.txt
```

**判定**: 有 diff → reviewer 失败,要求作者更新 PR body / 重新 push 重同步。

### Step 4: M4 Health Score 影响预估

```bash
# 模拟 main + PR 合并后 score (本地)
git merge origin/$gh_pr_branch --no-commit --no-ff
uv run --with "pyyaml" python bin/m4-health-score.py
git merge --abort
```

**判定**:
- Health Score 不退化( ≥ 100/100 ) → 模式 A/C, merge OK
- Health Score 退化 → 模式 B, close (PR 是 stale)

### Step 5: 本地兼容性核查

```bash
git merge origin/$gh_pr_branch --no-commit --no-ff
git submodule update --init --recursive
uv run --with "pyyaml" python bin/mof-bootstrap.py all
uv run --with "pyyaml" python tests/integration/m4_metamodel/run_all.py
git merge --abort
```

**判定**: 全绿 → 兼容性 OK。

### Step 6: OMO cron 守门

PR 不动 `.omo/cron/*`, 不动 `.truth/registry/*` YAML, 不发 OMO state bus events(P74 governance boundary)。

```bash
gh pr diff {num} --name-only | grep -E "\.omo/(cron|truth|state)"
```

**判定**: 无输出 → P74 边界守住。

---

## 4. 决策矩阵

| 模式 | Step 2 判定 | Step 3 判定 | Step 4 判定 | 决策 |
|------|-------------|-------------|-------------|------|
| A. 匹配 (no-op) | 全 match | (空) | Health 持平 | squash merge |
| B. 落后 (stale) | 任一 DIFF 是老 commit | 无 diff | Health 退化 或 不退化但 lost refactor | **close** |
| C. 真补 (missing) | DIFF 是新 commit | 无 diff | Health 持平或升 | merge (squash 或 rebase) |

---

## 5. close 模板 (close 评论)

当判定为模式 B (stale), 用以下 close 评论:

```markdown
关闭原因: 内容已被主仓 #XXX / 后续 fix 覆盖, 当前是 obsolete。

## 关键证据

### 1. 模块 bump 落后主仓 HEAD

| submodule | main HEAD | 本 PR |
|-----------|----------|--------|
| projects/X | abc123 | def456 (老) |

### 2. PR body commit 描述与 gitlink 不一致 (如有)

PR body 描述 projects/X → abc789, 但实际 → def456.

### 3. 关闭理由

合并此 PR 会 reset submodule X 从 main HEAD 的 abc123 回到老 def456,
丢失后续 commit 集包括 [...特别重要 commit]。

### 建议后续

若需求有效, 基于 main HEAD 重开新 PR。
```

---

## 6. merge 评论模板 (合并后)

```markdown
[M4 Health Score]: {baseline} → {after-merge}
- 57/57 PASS → {still-pass}
- 5-check strict → {status}
- ADR 数目 → {new-count}

[squash / merge / rebase] 理由: 模式 A (no-op / match 主仓)
或: 模式 C (真补 - {修复名}).
```

---

## 7. 历史实证 (5 个 PR 案例归类)

| PR | 模式 | Step 2 判定 | 实际 outcome |
|----|------|-------------|---------------|
| #131 | A | 5-check 一致 / 18 submodule match main HEAD | MERGED (squash) ✅ |
| #102 | B | projects/ecos runtime omo 3 个落后 | CLOSED ⚠️ |
| #103 | C | 真正补 P110-A + 修复 | MERGED (squash) ✅ |
| #136 | A | 3 submodule match, adr-coverage fix | MERGED (squash) ✅ |
| #137 | B | 5/6 match, gBrain reset to 老 commit | CLOSED ⚠️ |

**distribution**: A=40%, B=40%, C=20% (样本量小,统计意义有限)

**observation**: **40% submodule PR 创建后即过时**, submit 5 步自检是必做。

---

## 8. 与 AGENTS.md §10 round-trip 的集成

AGENTS.md §10.1 Round 类型中加:

| Round 类型 | 标准 |
|-----------|------|
| R-submodule-bump | 5 步自检 + 6 步 reviewer 见 ADR-0150 |

---

## 9. 关联

- [ADR-0150](../.omo/_knowledge/decisions/0150-submodule-pr-reverse-review.md) (本 ADR)
- [ADR-0142](./M4-DECISIONS-INDEX.md) (决策速查)
- [ADR-0148](../.omo/_knowledge/decisions/0148-round-trip-playbook.md) (round-trip 7 步)
- [ADR-0147](../.omo/_knowledge/decisions/0147-mcptool-adder-guide.md) (单 PR 模板对应)
- [docs/MCPTOOL-ADDER-GUIDE.md](./MCPTOOL-ADDER-GUIDE.md) (单 yaml adder)
