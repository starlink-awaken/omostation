---
title: "卫健委控制器影子迁移阶段复盘"
date: 2026-08-14
status: in_progress
scope: "Runtime 影子作业、Cockpit 只读投影、Workspace Documents binding"
---

# 卫健委控制器影子迁移阶段复盘

## 本阶段结论

卫健委既有 `controller.py` 保持原位、原行为不变。本阶段没有修改 Documents 内容、
没有改动 crontab，也没有把域内 `_runtime` 重新定义为执行入口。

Workspace Runtime 新增手动 `documents-weijian-controller-shadow` 作业：它只读六个
既有平面，生成 Runtime state 内的有界收据。其结果固定为
`shadow_incomplete` 且非零退出；这不是失败被掩盖，而是“仍不能切换 legacy”的明确
证据。Cockpit CLI 和两个只读 MCP surface 只读取该收据，因此 Claude Desktop、Codex、
Zed/ZCode 等客户端可通过同一个 Workspace MCP 看见相同状态，而不执行 Documents
内的脚本。

## 已覆盖与未迁移的边界

| Legacy rule family | 当前状态 | 本阶段输出 |
|---|---|---|
| CR01 红色 signals、CR02 warning 积压 | shadowed | 仅聚合计数 |
| CR03 新鲜度、CR05 超过 60 天实体审查 | shadowed | 仅聚合计数 |
| CR08 不可读/断链、CR23 OCR、CR24 模型、CR25 关键路径、CR26 文档治理、CR29 项目阶段、CR30 材料核对 | unmigrated | 明确列入收据，不伪造 parity |

收据不包含 Documents 相对路径、正文或生成报告；Runtime 仅写入其 state root。实时
smoke 证实作业返回 `exit_code=1`，但 `evidence_error=null`，并给出 4 项已覆盖和 7 项
未迁移规则。随后 Cockpit `controller-shadow work-weijian --json` 与
`domain_controller_shadow_status(work-weijian)` 都返回同一 `shadow_incomplete` 状态。

## SSOT 与客户端路径

- 域身份继续只认 L4 Domain Registry 与 `DOMAIN.yaml`；
- 作业声明、允许读取范围和 MCP tool 绑定只认 Workspace
  `documents-domain-projects.yaml`；
- 运行收据只认 Runtime state；
- Cockpit 只组合上述来源，不回写 Documents；
- Documents 域网关继续要求客户端先取 `domain_context`，并通过新增的
  `domain_controller_shadow_status` 查询本阶段状态。

这使“每个 Documents 域可作为独立项目接入同一 Cockpit MCP”的模型保持一致，同时避免
为卫健委创建第二个域级 KEMS/Runtime。

## 验证与已知限制

- Runtime 聚焦测试：36 passed；Runtime 静态检查与格式检查通过；
- Cockpit adapter、CLI、MCP 聚焦测试：79 passed；静态检查与格式检查通过；
- Workspace Documents binding checker：68 passed；对真实 12 域注册表返回
  `ok=true`、零错误；
- 实际 Runtime 作业和 Cockpit/MCP 端到端 smoke 均已运行，状态均为
  `shadow_incomplete`，没有把未迁移的规则报告成完成。

曾尝试以完整 Runtime suite 做额外验证；该 suite 在既有缺失/不一致的 workspace
依赖解析下无法自然结束，因此本阶段以覆盖变更面和真实作业 smoke 为发布证据，不把该
环境问题归因于影子作业。

## 下一迭代与切换门

下一项应从 CR08 的无跟随/不可读摘要开始，或从 CR25/CR26/CR29/CR30 中选择一个已有
明确 owner、可只读且可复现的检查器。每一项都先扩展 Runtime 收据，再以 Cockpit
投影展示；只有所有 11 个规则均具备 fixture parity、实际作业 evidence、回滚演练与
crontab manual-run 验证后，才可请求切换旧 controller 的消费者。

在那之前：旧 controller 和定时调用继续是唯一生效路径；影子作业只用于发现和证据。
