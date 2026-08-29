---
title: OMO extracted delivery consumer contract repair evidence
date: 2026-08-29
status: verified
---

# OMO 拆分后 delivery consumer 契约修复证据

## Child delivery

- child repository: `starlink-awaken/omostation-omo`
- child PR: https://github.com/starlink-awaken/omostation-omo/pull/112
- merged child main: `f82f7627ab228991c283ac1effa5582feeee459d`
- delivery tag: `delivery/omo-validator-contracts-20260829-v2`

## Verification

在 child main 的 PR CI 中：

- `CI/lint`: pass
- `CI/test`: pass
- `CI/test-cov`: pass
- focused engineering-delivery, projection, validator、external consumer suite：63 passed
- `py_compile`：pass

## Repaired contracts

本次修复恢复了 SRP 拆分遗漏的 canonical `_utc_now` 导出、qualified
`scene_binding`、projection receipt writer/validator schema、MOS outcome 参数
契约，并保留 shadow observer 的路径别名兼容与最终文件/root symlink 拒绝。

## Scope boundary

该报告证明 child 代码和测试已合入 child main；根仓 gitlink 仍须单独验证。
不证明 T1-12 durable OMO admission，也不修改宿主机运行态。
