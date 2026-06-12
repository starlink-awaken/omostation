# Memθ (Mem-Theta) 记忆算子体系与接口规范设计

**日期**: 2026-06-13
**设计方**: 织星 Agent 架构组
**状态**: Approved (Phase 1.2)

## 1. 背景与理论支撑

在 eCOS 演进到 v6.1 战略时，单纯的 Append-only 记忆链（如 `kairon/kos/memory_card.py` 的切片）因碎片化率高达 100% 且无法自我合并，注定会在长期运行中崩溃。基于《十大记忆架构评测》与 Memθ 理论，记忆不能仅仅被“检索”，必须被“治理”。

本体系旨在为系统引入具备自洁能力的三维算子：**Merge**, **Update**, **Filter**。它们将作为 `agora` 记忆路由和 `gbrain` 存储底座的标准通讯协议。

---

## 2. 算子定义 (Operators)

所有算子通过 MCP `bos://memory/operator/{action}` 端点对外暴露。

### 2.1 Update 算子 (状态覆盖)
**语义**：当实体或事物的确定性状态发生变更（如任务完成、代码被重构）时，覆盖其旧状态，而非追加新日志。
**输入签名**：
```typescript
interface UpdateOperation {
  target_id: string;          // 目标对象（如 OMO Task ID 或 gbrain node id）
  context: string;            // 新的上文
  confidence: number;         // 置信度 (0.0 - 1.0)，低于阈值的更新将被驳回
  trigger_source: string;     // 溯源标记
}
```
**行为**：
1. 锁定对象。
2. 覆写 payload 与 `updated_at` 时间戳。
3. 如果 `gbrain` 支持，追加版本历史 (Version History)，但不参与主流检索。

### 2.2 Merge 算子 (语义蒸馏与收敛)
**语义**：针对同一主题下的多篇碎片化 Memory Cards，调用 Base LLM 进行逻辑蒸馏，将其融合为一篇更高信息密度的摘要节点。
**输入签名**：
```typescript
interface MergeOperation {
  query_topic: string;        // 融合主题
  source_ids: string[];       // 待合并的切片 ID 列表
  model_override?: string;    // 指定提取摘要的模型，如使用强逻辑模型
}
```
**行为**：
1. `kos` 提取全部 `source_ids` 的内容。
2. 通过 LLM 抽象出 “当前事实”、“推演结论”、“过期假设”。
3. 在 `gbrain` 中插入新的 Meta-Node（元节点）。
4. 对原 `source_ids` 节点标记 `archived = true`，从主流向量检索视野中隐身。

### 2.3 Filter 算子 (三维淘汰/遗忘机制)
**语义**：根据 [时间衰减] + [访问频率] + [语义冗余度] 对记忆图谱进行裁剪。
**输入签名**：
```typescript
interface FilterOperation {
  domain: string;             // 清理域
  decay_days: number;         // 判定为“冷数据”的天数阈值
  access_threshold: number;   // 最低检索命中次数
  dry_run?: boolean;          // 是否仅输出报告
}
```
**行为**：
计算记忆节点的活性分数 (Vitality Score)：
`Score = (AccessCount * W1) - (DaysSinceLastAccess * W2)`
- 对于分数低于截断值的节点，自动下沉至归档存储（不进入上下文窗口）。

---

## 3. 双轨写入管线 (Dual-Track Pipeline) 接口草案

为了不破坏现有的容错能力，系统实施“双轨并行”原则：

- **Raw Track (原始轨迹)**：一切交互仍保留完整的日志并保存在廉价持久层（`.omo/_log`）。
- **Theta Track (提炼轨迹)**：Agent 在反思阶段，强制调用 `Merge` 算子，将 Raw Track 的多轮碎片归纳为状态描述，并通过 `Update` 写入 `gbrain` 事实库。

### 3.1 Gbrain 库表适配
为支持上述算子，`gbrain` Schema 需要至少扩充以下感知能力：
1. `access_count` INT DEFAULT 0 (每次检索命中时递增)
2. `last_accessed_at` TIMESTAMPTZ
3. `confidence_score` FLOAT DEFAULT 1.0

---

## 4. 后续落地计划
- **Phase 1.3**: 落实此规范至 `gbrain` 适配层与 `kos` 调度模块中。
- **Phase 1.4**: 实现 Filter 淘汰机制并挂载至 `opc_closeout_crontab` 作为夜间作业。
