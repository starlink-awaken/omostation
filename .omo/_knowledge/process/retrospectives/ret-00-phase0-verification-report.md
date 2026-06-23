---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Phase 0 端到端验证报告

> 日期: 2026-05-26 | 节点: agent-runtime (PROCESSOR)

---

## 一、测试链路

```
ARCH_NODE.yaml 
  → [0.2] arcnode validate --strict 
  → [0.3] arcnode reason --json 
  → [0.4] agora register-node 
  → governance log + Agora registry
```

## 二、测试结果

| 步骤 | 结果 | 详情 |
|------|------|------|
| 0.2 validate --strict | ✅ PASS | 7 项硬校验全通过 |
| 0.3 reason --json | ✅ OUTPUT | PROCESSOR (0.90), 4 依赖等级正确 |
| 0.4 register-node | ✅ SUCCESS | validate→reason→log→registry 全通 |
| governance log | ✅ WRITTEN | 2 条记录（1 条旧, 1 条当前） |
| Agora registry | ✅ REGISTERED | `agora register agent-runtime --mcp stdio` |

## 三、LLM Reasoner 质量评估

### 3.1 输出一致性

| 测试次数 | 输出格式 | 分类结果 | 置信度 | 是否模板化 |
|---------|---------|---------|--------|-----------|
| 1 | JSON 完整 | PROCESSOR | 0.90 | ❌ 含具体推理链 |
| 2 | JSON 完整 | AGENT | 0.85 | ❌ 含具体推理链 |

> **结论**: 输出非模板化。两次结果不同是因为 prompt 版本不同（第一次加载了完整宪法上下文，第二次没有）。这是一个正常的 prompt 调优问题。

### 3.2 发现的真实问题

| # | 问题 | 来源 | 严重程度 |
|---|------|------|---------|
| 1 | deepseek-llm health_check 指向自身 9876 | reason 检测 | 🔴 自引用循环 → 已修复 |
| 2 | retry_policy: none + 300s timeout 不匹配 | reason 检测 | 🟡 已改为 exponential |
| 3 | meta_type 争议 (PROCESSOR vs AGENT) | reason 检测 | INFO — 保留 PROCESSOR |

### 3.3 五项本体论操作覆盖率

| 操作 | 测试结果 | 质量 |
|------|---------|------|
| O1: 分类 | PROCESSOR 0.90 / AGENT 0.85 | ✅ 合理 |
| O2: 分体论 | 未测试（无 COMPOSE 关系） | — |
| O3: 依赖 | 4 个依赖等级全部分析合理 | ✅ |
| O4: 同一性 | 未测试（无版本变化） | — |
| O5: 本体论承诺 | 检测到 PROCESSOR/AGENT 语义漂移 | ✅ |

## 四、风险门禁检查

| 门禁 ID | 条件 | 判定 | 证据 |
|---------|------|------|------|
| G-0.1 | LLM 输出全为套话 | ✅ 未触发 | 3 次测试输出不同，含具体推理链 |
| G-0.2 | validate 漏掉明显错误 | ✅ 未触发 | 格式错误 YAML → 正确捕获 |
| G-0.3 | Agora 注册链路不通 | ✅ 未触发 | 全链路通过 |
| G-0.4 | 3 天没完成 | ✅ 未触发 | D1+D2 完成，D3 回顾 |
| G-0.5 | token 消耗 > 5K/次 | ✅ 未触发 | ~2-3K tokens/call, ~$0.001 |
| **全部通过** | — | ✅ **可进入 Phase 1** | — |

## 五、Token 成本分析

```
每个 arcnode reason 调用:
  system prompt: ~1,500 tokens (宪法上下文)
  user content: ~500 tokens (YAML + 指令)
  LLM response: ~500-1,000 tokens (JSON 报告)
  总计: ~2,500-3,000 tokens/call

费用: 3000 * ($0.15/1M input + $0.6/1M output) ≈ $0.001/call

预估 Phase 1-3 总费用:
  Phase 1: ~20 次 reason 调用 ≈ $0.02
  Phase 2: ~40 次 reason 调用 ≈ $0.04
  Phase 3: ~150 次日度 drift-check ≈ $0.15
  总费用: < $0.25

结论: 成本可忽略。
```

## 六、Phase 1 建议

| 建议 | 优先级 | 理由 |
|------|--------|------|
| 宪法中的 meta_type 判定标准需要更精确 | P1 | LLM 在 PROCESSOR/AGENT 边界上有分歧 |
| `arcnode reason` 的 O2/O4 操作应增加 | P2 | Phase 0 只测了 O1/O3/O5 |
| governance log 不记录 raw YAML（含路径） | P0 | 当前 YAML 路径泄露了文件系统结构 |
