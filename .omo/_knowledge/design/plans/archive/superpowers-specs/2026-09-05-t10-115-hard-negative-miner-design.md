---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T10-115
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-115 署名 Diff 语义反向萃取与负样本硬过滤设计

## 1. 目标

从 Experience Replay 水塘（lora-replay-buffer.jsonl，≥30 条真实署名样本）
逐样本解析夏明星的修改 Diff（删除/替换/补充），反向提炼负样本硬规则
（禁止空洞套话、行文偏好、格式习惯），沉淀为可机读规则库，并经 MOF
动态约束接入点对后续初稿实现 100% 拦截。

## 2. In scope

1. `projects/omlxc/src/omlxc/dataplane/hard_negative_miner.py`（新文件）：
   - `parse_signature_diff(instruction, output)`：difflib opcodes →
     结构化 hunk（op/删除段/新增段/位置）。
   - `classify_hunk`：规则启发式语义分类（banned_phrase 套话删除 /
     verbose_trim 冗长压缩 / terminology_replace 术语替换 /
     structure_reorder 结构调整 / fact_fix 事实修正）。
   - `mine_negatives(buffer_path)`：遍历 replay buffer，聚合同模式
     出现 ≥2 次的 hunk → `HardNegativeRule`（pattern/type/evidence/
     count），导出 JSONL 规则库（`.omo/state/hard-negative-rules.jsonl`）。
   - 真实数据验证：对现存 ≥32 条 document-review 样本全量跑通。
2. `projects/ecos/src/ecos/governance/diff_broker.py`（新文件）：
   - `check_draft(text, rules)` → `(allowed, violations)`：初稿生成侧的
     MOF 动态约束接入点——命中负样本硬规则的草稿返回 rejected 与违规
     明细（100% 拦截语义 = 规则命中即拒绝，无豁免通道）。
   - 参考既有 `dlp_broker.py` 的 broker 形态。
3. 测试：omlxc 侧 miner 单测（合成 diff + 真实 buffer 冒烟）；ecos 侧
   broker 拦截单测。

## 3. Out of scope

- 不训练模型、不改 LoRA 权重；不做生成式摘要。
- 不改 replay buffer 的写入路径（T10-105 已交付）。
- 规则库的人工复核界面不在本 bet（T10-116 工作台承接展示）。

## 4. 验收（对齐 ledger done_when）

1. 对 replay buffer 任一样本调用 miner 产出结构化 Diff 报告（含语义
   意图分类字段）。
2. 提炼的规则经 `check_draft` 对命中样本的原始初稿 100% 拒绝
   （violations 非空且 allowed=False）。
3. 单测全部通过。
