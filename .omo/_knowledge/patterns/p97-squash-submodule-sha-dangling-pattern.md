---
schema_version: pattern/v1
pattern_id: P97
title: squash-merge × submodule SHA 悬空模式
owner: governance-team
last_updated: 2026-09-04
type: ssot
---

# P97: squash-merge × submodule SHA 悬空模式

## 触发条件（任一即评估本模式）

1. 子仓 PR 用 **squash** 方式合并后，主仓 bump 了指向**原分支 SHA** 的 gitlink
2. CI 大面积 checkout 失败（"did not contain <sha>" / "not our ref"）但本地全绿
3. `git branch -r --contains <gitlink-sha>` 在子仓内为空

## 机理

```
子仓 fix 分支 commit (SHA-X)
  → PR squash 合并 → main 上是 新SHA-Y（X 的内容副本，非 X 本身）
  → SHA-X 不在任何远端分支 → gitlink 指 X = 指空气
  → 本地绿（对象库恰好有 X）/ CI 红（fetch 不到 X）
```

雷不即时炸：延迟到 CI checkout 才爆，且一个子仓悬空会炸掉全部 job。

## 4 秒自查法

```bash
python3 bin/ssot/submodule-reachability-gate.py --source index --fetch
# 或手动: cd <submodule> && git branch -r --contains <gitlink-sha>
```

注意判定标准：gate 认 `refs/remotes/origin/main`（严格），`branch -r --contains`
认任意远端分支（宽松）——bus-foundation 案例证明宽松标准会漏网。

## 合并方式选择规则

| 场景 | 用法 | 原因 |
|------|------|------|
| 主仓 gitlink 需指向子仓分支原 SHA | **merge-commit**（--merge）或 **fast-forward push** | squash/rebase 都会换 SHA |
| 子仓允许直接 push main 且分支领先 main | `git push origin HEAD:refs/heads/main`（ff） | 最干净，PR 自动判 merged |
| 只合内容、gitlink 之后 bump 到 main tip | squash 也行，但 bump 时**必须指向合并后 main** | 悬空只在"指旧 SHA"时发生 |

## 修复路径（已悬空时）

1. **保 SHA**（gitlink 不动）：把原 SHA 推上远端——分支 + merge-commit 合并（如 omo#139）
2. **重锚定**（gitlink 改）：指回子仓 origin/main tip（内容已 squash 进 main 时用）
3. 全量体检脚本扫所有 gitlink（ls-files -s + 严格 main 标准）

## 实战案例

- 2026-09-04 PR #3048：10 子仓悬空 → CI 11 job 全红 → 修复链 4 小时
- omo 保 SHA 走 merge-commit（#139）；bus-foundation 走 ff push；其余 9 仓重锚定 main tip
- family-hub 禁 merge-commit（仓保护）→ ff push 替代，PR 自动 merged

## 关联

- 机制化落地：pre-commit gitlink 可达性前置检查（bin/git-hooks/，见 P96 retro 机制清单）
- ADR-0450（cockpit-ui submodule 回归，第 15 子模块）
