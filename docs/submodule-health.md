# 子模块健康度报告

> 生成时间: {{GENERATED_AT}}
> 自动生成: `bin/gac/submodule-cleanup.sh --json`

## 概览

| 指标 | 数值 |
|------|------:|
| 子模块总数 | {{SUBMODULE_COUNT}} |
| 远程分支总数 | {{REMOTE_BRANCH_COUNT}} |
| Tags 总数 | {{TAG_COUNT}} |
| 指针漂移 | {{DRIFT_COUNT}} |
| 未初始化 | {{UNINITIALIZED_COUNT}} |

## 子模块详情

| 子模块 | 远程分支 | Tags | 指针状态 | 最后同步 |
|--------|----------|------|----------|----------|
| {{SUBMODULE_ROWS}}

## 过期分支 (已合入 main, >30天)

{{EXPIRED_BRANCHES}}

## 过期 Tags (超过保留数量)

{{EXPIRED_TAGS}}

## 建议

- 定期清理已合入 main 的远程分支
- 清理过期 tags，保留最近 20 个
- 同步子模块指针到最新 origin/main
- 清理悬空 tracking 分支

---

*本报告由 `bin/gac/submodule-cleanup.sh` 自动生成.*
