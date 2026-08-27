# C2G v4 Pitch: The Cybernetic Strategy Engine (控制论战略引擎)

> **Upstream**: ECOS-V5-ARCHITECTURE (系统底座演进)

---

## 1. 核心叙事 (The Narrative)
我们要将 OMO 从一个“低维任务执行器”升级为“高维战略导航仪”。通过引入“战略即代码 (Strategy-as-Code)”的强约束机制，把枯燥的 Markdown 愿景转化为可编译、可拦截的 L0 防线，从根源上消灭 Agent 瞎忙和技术债务堆积，实现系统的永续熵减。

## 2. 待解痛点 (The Problem)
目前 OMO 的 `current.yaml` 是扁平化的任务列表，就像一张失去地图的坐标清单。
1. **战略漂移**：执行层（Agent 或人类）写代码时，早已忘了最初的愿景，导致做出一堆精美但无用的功能。
2. **文档腐败**：顶层的 `VISION.md` 和 `ROADMAP.md` 写完就吃灰，与代码脱节。
3. **缺乏孤儿防范**：拍脑袋想出的需求可以直接流入开发管线，导致 Backlog 膨胀。

## 3. 资源胃口 (The Appetite)
> **Appetite:** 3 Days (极限压缩的 MVP 周期，防过度工程)

## 4. 粗粒度方案 (The Solution / Fat Marker Sketch)
1. **建立战略实体拓扑 (The Ontology)**
   - 在 `.omo/_knowledge/strategy/` 中设立 `01-VISION.md` (顶层愿景) 与 `ROADMAP.md` (蓝图)。
   - 在 `milestones/` 中定义具体的阶段目标。
2. **引力链锚定机制 (Upstream Anchors)**
   - 规定所有的 Pitch 必须在头部挂载 `Target Milestone: MS-XXX`。
   - `omo_bridge` 在转化 Pitch 时，强制校验该 Milestone 是否在 `ROADMAP.md` 的 Active Epoch 中。如果脱节，拦截！
3. **向量对齐与审计 (Vector Alignment)**
   - 愿景提炼为 3 个 Vector（如 V1: 高效, V2: 自治）。
   - 所有的 Pitch 下注时，必须携带 Vector 权重。
   - 开发 `omo strategy audit` 工具，一键扫描全盘，输出当前投入在各 Vector 上的占比，发现偏离即报警。
4. **熵减闭环 (Compaction & Decay)**
   - Sandbox 中的 Pitch 超过 4 周未下注，自动挪入 `decayed/` 归档。

## 5. 兔子洞防范 (Rabbit Holes)
- **复杂的语义分析**：不要试图用 LLM 去“理解”长篇大论的愿景文档，那极不稳定。必须要求愿景和 Pitch 提供明确的 YAML 前置元数据（Frontmatter）供 Python 代码进行强校验。
- **重构现有任务系统**：不要推翻现有的 `.omo/tasks/`。所有的改造只发生在 `omo_bridge` 和前置审查环节。

## 6. 绝对不做的边界 (No-Gos)
- **不做任何大盘可视化（Dashboard / Web UI）**：全系基于纯文本 Markdown、Frontmatter 和 CLI 输出。
- **不做复杂的 OKR 嵌套**：只保留 Vision -> Roadmap -> Milestone -> Pitch 四个层级，坚决不引入任何复杂的企业级多级树。

---
*状态区 (System Auto-Updates)*
**Bet Status**: `Draft`
**Context URI**: `bos://memory/sandbox/pitches/Pitch-Cybernetic-Strategy.md`
**Write-back Logs**:
