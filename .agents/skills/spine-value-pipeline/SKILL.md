---
name: spine-value-pipeline
description: omostation (eCOS v6) 主干真值流与署名自进化技能包。指导 AI Agent 如何通过标准 bos:// 服务感知外部信号、驱动 Journey 状态机、调用本地主权算力生成草稿、在 Cockpit 呈递待办并捕获夏明星署名修改的 Diff 进行自适应学习。
type: ssot
owner: agent-skills-team
last_updated: 2026-09-03
---

# 主干真值流与署名自进化技能 (Spine Value Pipeline Skill)

> **北极星愿景**：「织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。」

## 1. 核心生命周期规范 (5 步真值流)

当 Agent 需要处理任何业务需求、邮件公文、健康数据或日程待办时，必须严格遵循以下 5 步真值流：

```text
[1. 信号感知] ──► [2. LECP 分诊] ──► [3. 智能草稿生成] ──► [4. Cockpit 审阅署名] ──► [5. Diff 记忆沉淀]
```

### 步骤 1：信号感知 (Ingress)
* **日历事项**：调用 `bos://ingress/calendar` (或执行 `python3 bin/ingress/calendar_reader.py`) 获取日程。
* **文件待办**：调用 `bos://ingress/inbox` (或执行 `python3 bin/ingress/inbox_watcher.py`) 扫描待办文件。

### 步骤 2：LECP 实体组装与分诊 (Triage)
* 按照 `protocols/lecp-schema.yaml` 格式组装实体：
  * `domain`: `p0_work` (工作) / `p1_health` (健康) / `p2_family` (家庭) / `p3_mind` (心智) / `p4_research` (科研)
  * `privacy_level`: `public` / `internal` / `secret` (健康数据必须标记为 `secret`)

### 步骤 3：本地算力草稿拟定 (Drafting)
* 调用 `bos://compute/omlxc/infer`：
  * 健康场景：强制 100% 本地离线 Metal 推理；
  * 公文场景：复用静态 Prompt 前缀缓存 (0ms TTFT)，生成结构化回信/清单草稿。

### 步骤 4：呈递 Cockpit 审阅与一键署名 (HITL Sign)
* 调用 Cockpit API (`POST /api/inbox/sign`) 或在 Web 界面呈现待办卡片；
* 绝不代替夏明星直接对外发送未经审阅的内容，必须由本人确认署名。

### 步骤 5：Diff 捕获与自适应记忆沉淀 (Feedback & Continuous LoRA Adaptation)
* 调用 `bos://memory/mos/diff` 或使用 CLI `cockpit spine sign --original <草稿> --signed <定稿>`；
* 自动提取用词/修辞偏好追加至 `~/Documents/_entities/facts/preferences.md`；
* 样本自动同步至 `.omo/state/lora-replay-buffer.jsonl`，在 Mac mini M4 闲时触发 LoRA 在线增量微调（30% 历史经验回放防遗忘）。

## 2. 标准 BOS 服务契约速查

| 协议 URI | 传输模式 | 职责 |
| :--- | :--- | :--- |
| `bos://ingress/calendar` | stdio | 获取本地系统日历 |
| `bos://ingress/inbox` | stdio | 获取 ~/Documents/_inbox 待办 |
| `bos://compute/aetherforge/infer` | stdio / http | 本地 0ms TTFT 主权大模型推理 (27B/70B) |
| `bos://compute/omlxc/dma` | stdio | 雷雳 5 120Gbps P2P 零拷贝 DMA 跨机总线 |
| `bos://compute/omlxc/lora` | stdio | 夏明星专属署名 Diff 闲时在线 LoRA 蒸馏 |
| `bos://memory/mos/diff` | stdio | 提取署名 Diff 并更新偏好库 |
| `bos://ops/health` | stdio | 全仓健康度巡检 |

## 3. Cockpit Spine CLI 常用操作

```bash
# 1. 请求本地主权模型草稿
cockpit spine draft --prompt "请拟定下周架构演进计划"

# 2. 审议修改后一键提交署名 Diff 并记录价值
cockpit spine sign --original "草稿文本" --signed "定稿文本" --domain "architecture"

# 3. 查看署名 Diff 经验回放池状态
cockpit spine diff
cockpit spine replay

# 4. 触发 Mac mini M4 闲时 LoRA 增量蒸馏
cockpit spine distill --domain "architecture" --epochs 3

# 5. 查看实时 DMA 链路与显存遥测
cockpit spine status
```

