---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q3-T10-118
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-118 三域 LoRA 蒸馏与动态热插拔管理器设计

## 1. 目标

按公文政务（Gov）/ 技术架构（Tech）/ 邮件简复（Email）三个垂直业务域
组织署名样本、蒸馏专精 LoRA 适配层（lora-gov-v1 / lora-tech-v1 /
lora-email-v1），并提供 Spine Draft 域路由的自动秒级热插拔。

## 2. In scope

1. `projects/omlxc/src/omlxc/dataplane/lora_manager.py`（新文件）：
   - `LoraAdapterManager`：适配器注册表（domain → adapter 目录/元数据）、
     `activate(domain)` / `deactivate(domain)` 热插拔、`list_adapters()`
     状态面（存在性/样本数/评估分）。
   - `partition_buffer_by_domain(buffer_path)`：replay buffer 样本按
     域关键词映射分片（gov=公文/政务/批复；tech=架构/ADR/评审；
     email=邮件/函复），样本不足的域诚实标记 `pending_samples`。
   - `distill_all()`：逐域调用 T10-105 的 `dispatch_distill`（复用既有
     三级诚实派发），产出可复现的权重包产物记录。
   - 评估框架：`evaluate(domain)` 复用 `evaluate_alignment`（ROUGE-L），
     base vs adapter 输出对比，结果入适配器元数据。
2. `projects/cockpit/src/cockpit/commands/spine.py`（增量）：
   - `cockpit spine lora --list-adapters [--eval]`：适配器状态与评估面。
   - Draft 域路由：draft 命令带 domain 时自动激活对应适配器（存在才
     挂载，缺失如实提示）。
3. `projects/omlxc/tests/unit/test_lora_manager.py`（新文件）：分片/
   注册表/热插拔/路由/评估框架单测。

## 3. Out of scope

- 不下载/不依赖特定大模型权重（训练后端可插拔：本地 MLX 可用则真实
  蒸馏，样本不足或后端缺失诚实报告 pending，不伪造权重包）。
- 不做 LoRA 权重的量化压缩与多机分发。
- 真实 M4 节点夜间调度属部署配置（本 bet 交付机制与本地验证）。

## 4. 验收（对齐 ledger done_when）

1. 三域适配层产物记录可复现生成（样本充足的域为真实 adapter 目录，
   不足的域为 pending 记录——不以合成权重冒充）。
2. `spine draft --domain X` 路由自动挂载已存在的适配层（秒级，无全量
   重载）。
3. 评估框架可产出 base vs adapter 的 ROUGE-L 对比（提升数字依赖真实
   训练结果，如实记录）。
4. `uv run python -m cockpit.cli spine lora --list-adapters --eval` exit 0。
