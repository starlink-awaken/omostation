---
type: ssot
name: nextgen-cognitive-mesh
description: "Master governance skill for OMOStation Next-Gen Cognitive Mesh V3.0 (ADR-0200~0203). Guides memory self-distillation, cryptographic Merkle action ledgering, zero-config local edge compute roaming, and domain cartridge capsule packaging."

last-reviewed: 2026-08-26
owner: governance-team
---

# 🧠 Next-Gen Cognitive Mesh V3.0 智能体感知与治理规范 (ADR-0200 ~ ADR-0203)

本规范为接入 `omostation` 的所有自主智能体 (Agents) 提供四大下一代核心主权认知与算力治理协议。

---

## 1. 🧠 记忆自蒸馏与冲突自愈 (Memory Distillation - ADR-0200)

- **定位**：在夜间低峰期利用 `omlxc P2` 算力，对 A2A 通信日志与笔记进行事实提纯与冲突消解。
- **调用方式**：
  ```bash
  # 触发知识与记忆自蒸馏分析
  cockpit memory distill
  # 自动应用高置信度黄金卡片合并
  cockpit memory distill --auto-apply
  ```
- **核心契约**：`KnowledgeDocument` 信任等级 (Trust Level 1~5) 与时间戳仲裁机制。

---

## 2. ⚡️ 密码学级操作审计凭证 (Merkle Action Ledger - ADR-0201)

- **定位**：任何向外部政企系统、生产接口或关键文件的写入动作，必须生成并校验 Merkle 包含证明。
- **调用方式**：
  ```bash
  # 查看审计账本状态与 Merkle Root Hash
  cockpit audit-ledger status
  # 校验指定操作的 Inclusion Proof 有效性
  cockpit audit verify-proof <action_id>
  ```
- **安全红线**：禁止绕过 Merkle 记录直接执行未经验签的高危变更操作。

---

## 3. 🧑‍💻 局域网边缘弹性算力网格 (Local Edge Compute Mesh - ADR-0202)

- **定位**：基于局域网节点自发现与显存/温度感知，实现任务跨设备的弹性溢出与 0ms 漫游。
- **调用方式**：
  ```bash
  # 查看局域网边缘算力拓扑与温度/显存状态
  omlxc fabric mesh list
  # 计算任务最佳放置与漫游决策
  omlxc fabric mesh route --model <model_id> --priority P0
  ```

---

## 4. 👁️ 领域卡带胶囊化与沙箱运行时 (Domain Cartridge Capsule - ADR-0203)

- **定位**：将特定领域的方法论、意图模式、合规红线与工具集打包为独立分发的 `.cartridge` 胶囊。
- **调用方式**：
  ```bash
  # 打包领域源目录为签名卡带
  cockpit cartridge pack <source_dir> --output <name>.cartridge
  # 检查卡带清单与合规要求
  cockpit cartridge inspect <name>.cartridge
  # 在隔离沙箱中安全执行卡带意图
  cockpit cartridge run <name>.cartridge --intent "良乡医院等保三级立项"
  ```
