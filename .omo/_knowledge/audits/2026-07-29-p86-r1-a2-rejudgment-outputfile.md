---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---

# P86 R1: A2 结论作废 + output_file 等量重判

> 📌 **本文件是 5.4x 作废 / 纯 text 重判的证据源**。  
> 现行 A2 定论地图: [2026-07-29-p86-a2-collaboration-gain-map.md](2026-07-29-p86-a2-collaboration-gain-map.md)（3 类型真 dispatch + shortfall）。  
> 勿把本文件中的历史中间结论当现行 SSOT。


> 🔴 P73 诚实纠错 (二次反转): 本文档初版用 output_file **byte** 对比得出"协作 3-4x 优势",
> **该结论错误** — byte 含 transcript 噪音 (工具调用/读文件输出).
> 提取**纯 assistant text** (去噪音) 后反转: 协作 **0.5-0.6x** (单 agent 产出更多更深).
> 下方"byte 3-4x"段落保留作历史 (标注误导), **结论以纯 text 为准 (本文档末尾"真实结论")**.

> 上位: goal R1 (最高优先, C 波送卡依赖)
> 🔴 红线 (R1): 用 result 下质量结论 = 违规 (已证不可信) · 非等量比较当对照 = 违规
> 🔴 **原 A2 收益地图作废** (基于 result 空 + 不等量墙钟, 双重违规)

## 作废声明

> **原 A2 协作收益地图 (`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md` 等)
> 全部作废**, 不得作为任何决策依据. 原因:
> 1. 质量基于 result 字段 (Q2 已证 harness 回收 bug, 不可信)
> 2. 墙钟非等量比较 (协作 3 份产出 vs 单 agent 1 份, 产出量不同, 墙钟不可直比)

## 等量重判 (output_file 口径, 产出量折算)

### batch3 (coupled+write 方案设计)
| 模式 | 墙钟 | output_file 产出 | 单位产出 (s/KB) |
|------|------|----------------|---------------|
| 协作 (3 haiku) | 115s | **544688 bytes (3 份)** | 0.211 |
| 单 agent | 140s | 180717 bytes (1 份) | 0.775 |
| **对比** | 协作优 18% | **协作优 3.0x** | **协作优 3.7x** |

→ batch3 **协作双优** (墙钟 + 产出量). 原"协作墙钟优 18% 但质量劣 (1/3 有效)"**作废**
(result 空是 bug, output_file 3 份都有产出).

### batch4 (independent+write check 设计)
| 模式 | 墙钟 | output_file 产出 | 单位产出 (s/KB) |
|------|------|----------------|---------------|
| 协作 (3 haiku) | 190s | **674399 bytes (3 份)** | 0.282 |
| 单 agent | 110s | 170233 bytes (1 份) | 0.647 |
| **对比** | 协作劣 73% (木桶) | **协作优 4.0x** | **协作优 2.3x** |

→ batch4 协作墙钟劣 (木桶 agent3=190s), 但**产出 4x**, 单位产出**优 2.3x**.
原"协作劣 73% + 全空"**作废** (result 空是 bug, output_file 3 份完整方案).

### 重判核心结论 (反转)
> **协作产出量优势明显 (3-4x), 单位产出 (s/KB) 优 2.3-3.7x.**
> 原"协作不适用思考性任务"结论 **完全错误** — 基于结果 (result bug) + 不等量墙钟 (没算产出量).
> 真相: 协作墙钟可能劣 (木桶), 但**产出量远超单 agent** (3 agent 各产 1 份 vs 单 agent 1 份).

## batch1 复查 (5.4x 是否受 result bug 影响)

batch1 (independent+none 简单批量, 6 INTERFACE as_of):
- 简单任务 result 字段可能有输出 (不像思考性任务 result 空)
- 但需复查 batch1 的 result 是否完整 (同 Q2 标准查 output_file)
- 方向可能相反: 若 batch1 result 也空, 5.4x 也是假的; 若 result 完整, 5.4x 可信
- ⬜ 待复查 (batch1 output_file 在更早 session, 可能已删)

## batch2 复查 (劣 1.7x)

batch2 (ordered+read 失败归因, 协作 223s vs 单 128s):
- ⬜ 待复查 output_file (K4 批次2 在更早 session, output_file 可能已删)
- 若 output_file 显示协作产出更多 (3 份归因), 原"劣 1.7x"可能也作废

## caveat (诚实)

output_file byte 含 **transcript 噪音** (工具调用/中间思考/读文件输出), 非纯方案文本.
精确产出量需提取 assistant 最终 message text (去 transcript 噪音).
当前 byte 量是**近似** (协作产出量优势 3-4x 即使扣噪音仍显著, 但精确倍数需提取复验).

**严谨结论**: 协作产出量明显大于单 agent (3-4x, 即便含噪音), 单位产出优.
但精确倍数 (2.3x / 3.7x) 需提取纯 assistant text 复验, 当前是 byte 近似.

## 新 A2 地图 (基于 output_file 等量, 替代作废版)

| 批次 | 类型 | 协作墙钟 | 协作产出 | 单位产出 | 重判 |
|------|------|---------|---------|---------|------|
| 3 | coupled+write (方案) | 优 18% | **3.0x** | **优 3.7x** | 协作强优 |
| 4 | independent+write (设计) | 劣 73% | **4.0x** | **优 2.3x** | 协作优 (单位产出) |

(batch1/2 待 output_file 复查, 暂不入地图)

## R3 harness bug (阻断精确重判)

Agent 工具 result 回收缺陷 (Q2 已证) **是平台层 bug**, agent 无法自修:
- result 只回收摘要, 完整产出在 output_file (JSONL transcript)
- 精确重判需解析 output_file JSONL 提取 assistant text (去 transcript 噪音)
- 建议 (送卡): Claude Code 平台修 result 回收完整 output

**R3 状态**: 平台 bug, agent 绕过 (用 output_file), 精确复验需平台修复或 JSONL 解析工具.

## R4: C 波送卡延后 (合规)

🔴 C 波送卡 (`.omo/_knowledge/audits/2026-07-29-p86-c-wave-escalation.md`) 原基于作废地图.
**R4 延后**: R1 重判后, 协作"产出量优势 3-4x"是**新结论**, 与原"适用面窄"相反.
C 波送卡须基于新地图 (R1 完成后), agent 不代批.

## 待办
- ⬜ batch1/2 output_file 复查 (若已删需重跑)
- ⬜ output_file JSONL 提取纯 assistant text (精确产出量, 去 transcript 噪音)
- ⬜ R1 完成后 → C 波新送卡 (基于等量产出地图)
- ⬜ R3 harness 平台修复 (送卡人类)

## ✅ 真实结论 (纯 assistant text, P73 二次纠错, 2026-07-29)

提取纯 assistant message text (去 transcript 噪音):

| 批次 | 协作总 text (3 份) | 单 agent text (1 份) | 协作/单 |
|------|-------------------|---------------------|---------|
| batch3 | 5039 chars | **7819 chars** | **0.6x** |
| batch4 | 6948 chars | **12793 chars** | **0.5x** |

**反转**: 纯 text 协作 **0.5-0.6x** (单 agent 产出更多). 上文"byte 3-4x 优势"是 **transcript
噪音假象** (output_file 含工具调用/读文件输出, 非 pure 产出).

### 单位时间产出 (纯 text)
- batch3: 协作 115s/5039 = 0.0228 s/char, 单 140s/7819 = 0.0179 s/char → **单优 1.3x**
- batch4: 协作 190s/6948 = 0.0273 s/char, 单 110s/12793 = 0.0086 s/char → **单优 3.2x**

### 真实重判结论 (替代上方 byte 误导段)
> **协作纯产出量 0.5-0.6x 单 agent, 单位时间产出单 agent 优 1.3-3.2x.**
> 协作"3 份达标即止" (各 ~1700-2300 chars, 浅), 单 agent"1 份深入超标" (7819-12793 chars,
> 含源码定位/Q4 gap/方案对比).
> → **协作产出不优于单 agent (思考性任务)**. 原 A2 方向 (协作不适用思考性) 成立,
> 但证据改为纯 text (非 result 空 — result 空是 bug, 但纯 text 也证协作产出少).

### 新 A2 地图 (纯 text, 最终)
| 批次 | 类型 | 协作墙钟 | 协作纯 text | 单位时间 | 重判 |
|------|------|---------|-----------|---------|------|
| 3 | coupled+write | 优 18% | 0.6x | 单优 1.3x | **单 agent 优** (产出深) |
| 4 | independent+write | 劣 73% | 0.5x | 单优 3.2x | **单 agent 强优** |

**最终**: 思考性任务 (方案设计/check 设计) **单 agent 优** (产出更深 + 单位时间高效).
协作产出量少 (各 agent 达标即止, 不深入). 原"协作不适用思考性"结论成立 (纯 text 证据).

### batch1/2 复查

**batch1 复查结论 (2026-07-29, 已做)**:
- batch1 = **P81 真实任务** (PR #483, 12 remediation trails 如 REMEDIATE-AGENTMESH-ARCHIVE),
  **非 P84 dispatch 对照实验**, 无协作/单 agent output_file
- "5.4x" 是早期估算 (W1 任务#1 DOC_CLAIMS_SCOPE 并行 vs 单顺序), **无严谨墙钟对照 + 无 output_file**
- 系统已把 "5.4x" 匿名化成 "n" (多文档), 暗示数字不可信
- → **5.4x 无严谨证据, 从 A2 地图剔除**. batch1 不入新地图 (无对照数据).
- 方向: 简单批量协作**可能**优 (并行达标), 但需真 dispatch 等量对照重跑才有定论

**batch2 (K4 真 dispatch, 协作 223s vs 单 128s, 劣 1.7x)**:
- 在更早 session, output_file 可能已删 (无法纯 text 复查)
- 墙钟数据是真 dispatch 计时 (可信), 但产出量未纯 text 复查
- 若 output_file 已删, 需重跑 (R1 无法对已删数据补纯 text 分析)
- 暂按墙钟劣 1.7x 保留 (真 dispatch 计时可信), 产出量标"未复验"

### C 波送卡 (R4, 基于 R1 纯 text 结论)
- 协作产出不优于单 agent (思考性任务, 纯 text 证据)
- 简单批量待 batch1 复查 (可能协作优, 达标即可)
- agent 不代批, 送人类按任务类型分层决策
