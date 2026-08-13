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
`shadow_observed` 且非零退出；这不是失败被掩盖，而是“已观测、仍不能切换 legacy”的明确
证据。Cockpit CLI 和两个只读 MCP surface 只读取该收据，因此 Claude Desktop、Codex、
Zed/ZCode 等客户端可通过同一个 Workspace MCP 看见相同状态，而不执行 Documents
内的脚本。

## 旧控制器的观测边界

| Legacy rule family | 当前状态 | 本阶段输出 |
|---|---|---|
| CR01 红色 signals、CR02 warning 积压 | observed | 仅聚合计数 |
| CR03 新鲜度、CR05 超过 60 天实体审查 | observed | 仅聚合计数 |
| CR08 断链、CR23 OCR、CR24 模型新鲜度 | unobserved | 只列入完整规则清单；不读取或执行其输入 |
| CR25 关键路径、CR26 文档治理、CR29 阶段骨架、CR30 材料完备性 | unobserved | 只列入完整规则清单；不调用域内检查脚本 |

2026-08-14 的复核校正了初版的错误分母：实际旧
`@工作文档/卫健委/_control/controller.py` 共实现 CR01、CR02、CR03、CR05、CR08、
CR23–CR26、CR29–CR30 十一条规则。v2 收据完整列出十一条 `legacy_rule_ids`，同时以
`observed_rule_ids` 明确标识本阶段安全观测到的四条，以 `unobserved_rule_ids` 明确标识
其余七条尚未接入 Workspace owner。它固定 `cutover_ready=false` 与
`legacy_controller_replaced=false`；旧 v1 收据会被 Runtime binding 和 Cockpit 拒绝，避免
客户端继续读取“4+7”的错误解释。

收据不包含 Documents 相对路径、正文或生成报告；Runtime 仅写入其 state root。实时
smoke 证实作业返回 `exit_code=1`，但 `evidence_error=null`，并给出完整十一条 legacy
规则清单及其中四条的只读观测。随后 Cockpit `controller-shadow work-weijian --json` 与
`domain_controller_shadow_status(work-weijian)` 都返回同一 `shadow_observed` 状态。

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

- Runtime 聚焦测试：30 passed；Runtime 静态检查与格式检查通过；
- Cockpit adapter、CLI、MCP 聚焦测试：79 passed；静态检查与格式检查通过；
- Workspace Documents binding 与隧道契约测试：76 passed；对真实 12 域注册表返回
  `ok=true`、零错误；
- 实际 Runtime 作业和 Cockpit/MCP 端到端 smoke 均已运行，状态均为
  `shadow_observed`；v2 以清单与观测状态区分完整旧控制器规则和本阶段已观测子集。

曾尝试以完整 Runtime suite 做额外验证；该 suite 在既有缺失/不一致的 workspace
依赖解析下无法自然结束，因此本阶段以覆盖变更面和真实作业 smoke 为发布证据，不把该
环境问题归因于影子作业。

## 下一迭代与切换门

下一项应先为 CR08、CR23–CR26、CR29–CR30 分别定义各自的 Workspace owner job，并保留
独立的 fixture parity、实际作业 evidence、回滚演练与 crontab manual-run 验证；CR04 若需
治理，也须作为独立控制规则处理。只有全部十一项具备这些证据后，才可请求切换旧
controller 的消费者。

在那之前：旧 controller 和定时调用继续是唯一生效路径；影子作业只用于发现和证据。

## 2026-08-14 CR24 独立 owner 绑定补记

CR24 模型新鲜度现已获得独立的 Workspace Runtime owner job：
`documents-weijian-model-freshness` 由 `runtime-control` 以手动、只读、fail-closed
方式执行，并由 Cockpit 的 `domain_model_freshness_status` 只读投影状态。Runtime 与
Cockpit 的独立 owner 实现已合并；Workspace 此处只绑定已合并 contract，不在
Documents 内执行或写入任何内容。

这仍不是 legacy cutover。controller-shadow v2 的 `unobserved_rule_ids` 保持生成当时的
历史语义，不因新增独立 owner 而回写或改释旧收据；旧 controller 与其定时调用继续是
唯一生效路径。CR24 的阶段完成状态只能在 Workspace 根变更合并且安装态 smoke 成功后
更新；本补记不声称 ChatGPT Secure MCP Tunnel 已安装或可用。
