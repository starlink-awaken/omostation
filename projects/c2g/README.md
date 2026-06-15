# C2G Engine (Concept-to-Goal)

> 🧭 **The Strategic Compass for Indie Hackers & Startups**

C2G 引擎是一个**独立的战略需求管控框架**。它致力于解决独立开发者和小型团队在产品演进中常见的“点子乱飞”、“缺乏边界”、“难以收敛落地”的技术债务问题。

它负责接收未经雕琢的原始意图（Pitch），验证其合规性与边界（Appetite），并将其降维、转换、下注为系统可追踪、可执行的战略目标（Bet & Task）。

## 🌟 核心特性 (Features)

1. **V2P (Vision-to-Pitch)**: 协助将模糊愿景转化为包含边界的结构化提案（沙箱阶段）。
2. **C2G (Concept-to-Goal)**: 在门控的强力监督下，将合规的 Pitch 实例化为具体执行目标。
3. **AGC (Audit & Garbage-Collection)**:
   - **战略雷达 (Radar)**: 审计全盘活跃目标的愿景偏离度（如 V1 效率维度 vs V2 自治维度）。
   - **熵减清理 (GC)**: 回收 Sandbox 中长期未下注的僵尸提案。
4. **适配器架构 (Ports & Adapters)**: 核心层不依赖任何第三方业务代码。你可以通过注入 Adapter 来对接你自己的存储层或门控逻辑。

## 📦 安装 (Installation)

```bash
# 通用版 (基于本地文件系统的存储与基础门控)
pip install c2g

# 增强版 (如果你身处 eCOS OMOstation 体系)
pip install c2g[ecos]
```

## 🛠️ 快速开始 (Quickstart)

C2G 默认支持双引擎驱动：通用本地版 (`local`) 与 深度定制版 (`ecos`)。

```bash
# 1. 尝试将你的 Pitch 转化为可执行 Bet (使用默认本地适配器)
c2g --adapter local bet ./pitches/MyGreatIdea.md

# 2. 启动战略雷达，审查当前的 Bet 偏离度
c2g --adapter local radar

# 3. 运行熵减 GC，清理过期的无用点子
c2g --adapter local gc --dry-run
```

## 🏗️ 架构解析 (Architecture)

本项目采用严格的 **IOC (控制反转)** 原则进行设计。
核心引擎 (`c2g.engine` / `c2g.bridge` / `c2g.strategy`) 不知道数据存在哪里，也不知道由谁来拦截不合规的提案。它只认两个 `Protocol`:

- `IGovernanceProvider`: 你的团队对“提案”和“任务”有什么底线要求？（通过它注入）
- `IStorageProvider`: 你的“提案库”和“目标库”存在哪里？是 Github Issues，还是本地 YAML，或是 Notion？（通过它注入）

自带了以下两种开箱即用的 Adapter：
*   **`local`**: 适合个人独立开发者。所有数据存储在 `.c2g_data/` 下。简单轻量。
*   **`ecos`**: 为星链觉醒 OMO 体系深度定制。它会自动与 `projects/omo` 对接，调用 L0 的 X1-X4 约束法则进行强制拦截。

---
*Built with ❤️ by the eCOS Agentic Team.*
