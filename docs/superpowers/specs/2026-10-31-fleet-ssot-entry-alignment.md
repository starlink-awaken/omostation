---
schema_version: specification/v1
spec_version: 1.0.0
title: 同机双根决策与入口文档对齐
bet_id: BET-Y2Q4-T10-278
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-31
---

# 同机双根决策与入口文档对齐

## 问题与范围

完整文件名 `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` 的当前状态为 ACCEPTED，其收官段记录历史切道及读侧限制；`AGENTS.md` 仍称该文件 PROPOSED，`ARCHITECTURE.md` 仍将安装位和 profile ledger 叙述为批次 1 时的状态。此变更仅使两处入口引用现有契约和实例化时刻的检查方法，不将历史验收当作所有当前进程、所有节点或全局唯一 writer 的证明。

## KOS 先例

KOS `kos::default::0456-dev-runtime-profile-root.md` 返回旧版 PROPOSED 快照，更新于 2026-10-08；当前检出的完整文件名及其 2026-10-29 addendum 为本次修订的直接来源。KOS `kos::default::BET-Y2Q4-T10-206.md` 是服务注册现实检查的历史复盘，不能代替本机现测。

## 必须满足

1. AGENTS 依据完整文件名明确两份同编号 ADR 的区别及各自的状态。
2. ARCHITECTURE 将安装根指向解析器和原决策，保留服务实际加载代码、依赖需逐项实测的边界。
3. ARCHITECTURE 将账本定位指向对应进程环境的 `event_ledger_path()`，区分活动账本与带 provenance 的非权威快照，不凭目录名推断 writer。
4. 完成现有 lane 检查、文档门禁和差异检查；未运行及失败项如实报告。

## 非目标

不变更 0456 决策的历史正文或状态；不改 runtime、服务注册、节点登记、数据库、生产配置与启动项；不执行生产切换、网络配置修改、清理、提交、推送或发布。不因本项修文就声明开发/生产隔离、健康或唯一 writer 已在现场全面验证。

## 失败与恢复

若当前权威文件、工作流准入或作用域与本契约冲突，停止本范围并保留证据；不绕过门禁。此文档补丁可通过逆向差异恢复，不能把 Git reset 应用于共享主树。
