---
title: "Closeout 模板（5 分钟）"
lifecycle: entry
owner: governance-team
last_updated: 2026-08-15
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# Closeout 模板（5 分钟）

## 使用说明
- 本文件可直接按项目类型使用：
  - 先填 `基础信息` 到 `风险与后续`，适用于文档、运维、流程等通用收口任务。
  - 若本次任务包含代码改动，继续补齐下方 `开发任务附录`。
- 标准流程：先完成通用块，再决定是否补充开发附录。

## 基础信息
- 日期：
- 任务/工作项：
- 责任人：
- 关联 PR / Commit：

## 目标与范围
- 本次目标：
- 触达范围（文件/模块）：

## 执行结果
- ✅ 已完成：
- ⚠️ 未完成/阻塞：

## 收口命令（必须执行）
```bash
cd /Users/xiamingxing/Workspace

git status --short
git status -sb
git submodule status
git status --short .omo/state
git status --short .omo/_truth/registry
```

## 变更/脏文件处理
- 已回退文件（如有）：
- 已保留变更文件（如有）：

## 状态确认
- 主仓是否干净：
- 子仓是否干净：
- 是否与预期提交一致：

## 风险与后续
- 风险：
- 下步动作：

## 备注
- 证据文件：

---

# 开发任务附录（5 分钟）

## 任务信息
- 日期：
- 任务 ID/名称：
- 负责人：
- 关联 PR / Commit：
- 运行时分支：

## 开发目标
- 目标一句话说明：
- 变更范围（模块/文件）：

## 变更明细
- 主要变更：
- 设计取舍（如有）：

## 验证与测试
- 影响面评估：
- 已执行命令：
```bash
# 填写实际命令
```
- 结果（PASS/FAIL）：
- 失败说明与缓解（如有）：

## 风险与回归
- 已回归场景：
- 已发现风险：
- 下一步跟进：

## 收口核验（必做）
```bash
cd /Users/xiamingxing/Workspace

git status --short
git status -sb
git submodule status
git diff --stat
```

- 是否有非预期脏文件：
- 是否有子模块脏状态：
- 是否与目标状态一致：

## 交付与证据
- 证据文件/日志：
- 复盘/验收链接：
