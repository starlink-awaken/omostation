---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-09-16
type: ssot
---
# P104 — Ledger Closeout Reuse-Existing-Work Pattern

> **2026-09-16 ledger 99.3% 完成 (416/419) 沉淀** · 来源: 本会话 5 个 closeout PR 实证
> 适用: BET done 之后, ledger status flip + retro 新增 + lint 通过

## TL;DR

ledger closeout 时**优先复用已合入主仓的实现**, 不要为了"任务完成感"硬重写.
T3-02 / T2Q3-T7-01 都是依赖 `git log --grep "<bet-id>"` 找到已有 commit,
直接做 ledger status flip + retro frontmatter 更新, 0 行新代码.

## 三步法

```bash
# Step 1: 查实现是否已在主仓
git log --all --oneline --grep "<BET-ID>"

# Step 2: 若已实现, 写最小 closeout
- docs/plans/3y-bet-ledger.yaml: status flip + done_at
- .omo/_knowledge/retros/<BET-ID>.md: retro 4 段

# Step 3: 验证 + push
python3 bin/plan/bet-ledger.py lint  # OK
git push
gh pr create --admin --squash --delete-branch
```

## 何时重写 vs 复用

| 场景 | 决策 |
|------|------|
| 实现已合入, 测试已 pass | **复用**, closeout 即可 |
| 实现存在但缺少测试 | 加测试, 再 closeout |
| 部分实现, 关键路径缺 | 重写 (但要小范围) |
| 完全没实现 | 拒 closeout, 认领实施 PR |

## 陷阱

1. **混淆 closeout 与实施 PR**: 两者必须分开, closeout 写代码会触发 lint 报错
2. **忘记 retro**: done 状态 BET 必带 retro, 否则 next-bet-execution 取舍无证据
3. **忘记 done_at**: 不写 done_at 会被 lint 拒绝
4. **忘记补 write_surfaces**: done 状态 BET 必填齐 write_surfaces, 否则 SSOT 不完整

## 教训来源

- T3-02 (#3805): LoRA 矩阵 + 测试 + 实施都已合入, 本 PR 仅做 ledger flip + retro 状态更新
- T2Q3-T7-01 (#3823): 家庭资产审计在 family-hub 子模块, 0 行新代码
- T7-05 (#3715): Scene Lifecycle Cruiser 在 omo 子模块, 0 行新代码
- T6-28 (#3766): 4-Tier cognitive hierarchy 在 aetherforge 子模块, 0 行新代码

**4/4 closeout PR 在本会话遵循此 pattern**, 总耗时从 1-2 天降到 5-15 分钟.
EOF
