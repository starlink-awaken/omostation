# 技术情报报告：2026 Q2 行业扫描 × omostation 迭代

> 日期: 2026-05-29 | 输入: 50+ GitHub + 30+ 公众号 + 30+ 知乎
> 深度读取: AI-Scientist-v2, OpenHuman, ContextHub

---

## 一、三个战略信号

### 信号 1: OpenHuman — omostation 的镜像竞品

OpenHuman (tinyhumansai, 25k+ stars) 是最接近 omostation 愿景的开源产品。

| 维度 | OpenHuman | omostation | 差距 |
|------|-----------|:---------:|:----:|
| GUI | 桌面应用 + 面部动画 | 无 | 🔴 |
| 记忆 | Memory Tree + Obsidian vault, 自动压缩 | KOS 10165→700 | 🔴 |
| 集成 | 118+ OAuth, 自动 20min sync | Hermes 10+ | 🟡 |
| Token 压缩 | TokenJuice (省 80%) | 无 | 🟡 |
| 合规/免疫 | 无 | EU+免疫+护栏 | ✅ 独有 |
| 架构 | Monorepo (Electron+Tauri+Rust) | 多仓库 | — |

**洞察**: OpenHuman 是"消费品级"的个人 AI OS，omostation 是"架构师级"的。omostation 的合规/免疫是护城河，但产品化差距大。**omostation 不需要变成 OpenHuman，但需要吸收其 Memory Tree + TokenJuice + 自动集成同步的思路。**

### 信号 2: AI-Scientist-v2 — 自主研究新标杆

SakanaAI 的 AI-Scientist-v2 展示了**代理树搜索(BFTS)**驱动的研究自动化：并行探索多条路径，动态剪枝，最终论文已被 workshop 接收。

**启示**: omostation 不需要做 ML 实验自动化，但 BFTS 方法论可直接融入 minerva 研究管线——"多个研究路径并行 + 动态评估 + 剪枝"。

### 信号 3: Agent Skills 爆炸

列表中发现 **8+ agent skills 项目**：awesome-agent-skills, agent-skills, scientific-agent-skills, nuwa-skill, wps-skills 等。验证 KOS self 的技能蒸馏方向正确。

---

## 二、情报分类

### 对 omostation 直接有用的

| Repo | 启示 | 融入位置 | 优先级 |
|------|------|---------|:-----:|
| **OpenHuman** Memory Tree + TokenJuice | gbrain 记忆增强 + 新 token 压缩层 | L2 新能力 | 🔴 P1 |
| **ContextHub** agent 自学习文档 | KOS self 知识积累 | KOS self | 🟡 P2 |
| **AI-Scientist-v2** 树搜索 | minerva 研究管线 BFTS | minerva | 🟡 P2 |
| **trustgraph** 信任知识图谱 | KOS index 可信度层 | KOS index | 🟡 P2 |
| **SkillRouter** 技能路由 | agentmesh Agent 技能选择 | agentmesh | 🟡 P2 |
| **scientific-agent-skills** 科学技能 | KOS self 技能模板 | KOS self | 🟡 P2 |

### 已知/已计划的

nuwa-skill, graphify, GitNexus, MinerU, wps-skills, wx-cli, deepseek-reasonix, DeepCode, ruflo, gbrain, gstack, notebooklm-py — 已在 SharedWork 或 Phase 2-3 计划中。

### 参考资料

ai-engineering-from-scratch, claude-howto, happy-llm, knowledge-work-plugins, ai-dev-kit, semle, needle, pi, pi-acp, deepwiki-open, claw-code, dory, ultramind, Agent-Reach, MiroThinker, multica — 参考设计/方法论。

---

## 三、架构迭代建议

### 新增包

| 包名 | 层 | 灵感来源 | 功能 |
|------|:--:|---------|------|
| **token-juicer** | L2 | OpenHuman | Token 智能压缩 (HTML→MD, 去重, 多字节保留) |
| **memory-tree** | L2 | OpenHuman | 分层摘要树 + Obsidian vault 同步 |
| **bf-search** | L2 | AI-Scientist-v2 | 代理树搜索 (并行探索+动态剪枝) |
| **trust-layer** | L3 | trustgraph | KOS index 可信度评分 |
| **skill-router** | L3 | SkillRouter | agentmesh Agent 技能智能路由 |

### 架构修正

1. **KOS index 修复后立即增加 Token 压缩层** — 降低索引和检索的 token 成本
2. **minerva 研究管线增加 BFTS 模式** — 并行探索多条研究路径
3. **gbrain 增加 Memory Tree 模式** — 分层摘要而非平铺记忆
4. **Phase 2 新增集成自动同步策略** — 参考 OpenHuman 的 20min auto-fetch

### 与现有路线图的整合

| 新能力 | 融入 Phase |
|---------|:---------:|
| Token 压缩层 | Phase 2 Sprint 1 (与 KOS 修复并行) |
| BFTS 研究模式 | Phase 2 Sprint 3 minerva 增强 |
| Memory Tree | Phase 3 gbrain 升级 |
| Skill 路由 | Phase 3 KOS self |
| 信任图谱 | Phase 2 Sprint 1 KOS index |

### 产品化差距（Phase 4+）

omostation 不需要做 GUI（与 OpenHuman 不同定位），但需要：
- install.sh 一键安装（已计划）
- Web Dashboard（Agora 已有基础）
- API 文档自动生成（已计划）
- 社区 Skill 市场（Phase ∞ 联邦学习）
