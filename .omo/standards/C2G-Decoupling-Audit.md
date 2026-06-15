# 全链路深度审计与 C2G 独立化可行性评估报告

> **日期**: 2026-06-15
> **视角**: 产品架构师 (Sage) & 风控官 (Devil)
> **核心议题**: C2G 管线现状审计、接口统一方案、以及“需求管控系统”的独立化分拆评估。

---

## 🔍 一、 全链路现状深度审计 (The Audit)

从 5+4+1+1 的架构视角，对当前“从需求到执行”链路进行穿透式审计，我们发现系统逻辑跑通了，但**工程耦合度**和**用户体验**存在严重隐患。

### 1. 架构违和感 (Architectural Smells)
*   **OMO 的职能膨胀**：OMO 本应是纯粹的“交警”与“纪委”（管合规、管债务、管基线）。但现在，我们把 `omo_bridge.py`（需求转化）和 `omo_strategy.py`（战略雷达）强行塞给了它。OMO 既当裁判又当教练，严重违背了微内核的单一职责原则。
*   **L3 接口破碎**：虽然有 `workspace iterate` 作为宏观入口，但底层动作 (`omo bridge`, `omo strategy audit`) 暴露得太深，缺乏一个领域级（Domain-level）的统一下游命令。

### 2. 链路健壮性评估
*   ✅ **强壮点**：X1-X4 约束通过 `L0-constraints.yaml` 硬编码，M0 元模型（Pitch Template）保证了源头数据的结构化，这部分的基座坚如磐石。
*   ❌ **脆弱点**：`mof-extract` 回写机制与 Sandbox 目录强绑定，如果未来需求载体变成数据库（比如 gbrain），目前的 Python 脚本处理纯文本的逻辑将面临重构。

---

## 🛠️ 二、 对外能力接口统一解决方案 (The Unified UX)

为了抹平底层的撕裂感，我们必须在 L3 (`cockpit`) 层，提供一套完全屏蔽 5+4+1+1 复杂度的“需求与战略专属”控制台指令簇。

**建议废弃零散的 `omo` 调用，统合为 `workspace compass` (战略罗盘) 命名空间：**

```bash
# 1. 提案生成 (V2P) -> 触发 MetaOS 发散
workspace compass brainstorm "我想要一个自动发推的功能"

# 2. 定标下注 (C2G) -> 触发 Bridge，经过 OMO 门控，落入 CARDS
workspace compass bet runtime/sandbox/pitches/Pitch-AutoTweet.md

# 3. 战略扫描 (AGC) -> 触发大盘向量审计
workspace compass radar

# 4. 熵减清理 (AGC) -> 触发沙箱 GC
workspace compass gc --dry-run
```
**体验收益**：用户只需记住 `compass`（罗盘），就掌握了整个战略中枢。所有的 L0 校验、I0 路由都在这四个命令背后无声执行。

---

## 🚀 三、 “需求引擎”独立化可行性评估 (Standalone Project Evaluation)

**核心命题**：将 C2G 这一套“战略与需求”链路，从 `omo` 中整体剥离，甚至从 eCOS 内部闭环中剥离，使其成为一个独立项目（如 `projects/compass` 或面向外界的开源工具）。

### 1. 剥离的可行性：★★★★★ (极度可行且必要)
在领域驱动设计（DDD）中，“战略规划 (Strategy/Pitch)” 与 “系统治理 (Governance/OMO)” 是完全正交的两个限界上下文。
*   **目前**：Pitch 和 Bet 的逻辑寄生在 `projects/omo/` 下。
*   **重构后**：新建 `projects/compass/` (或 `c2g-engine`)。该引擎专注于将 Markdown 转化为目标任务。当它需要校验合法性时，通过 `bos://governance/omo/...` 向 OMO 发起请示，而不是把 OMO 的代码和自己的写在一起。

### 2. 独立架构边界划分
如果独立，系统职责将变得异常清晰：
*   **`projects/compass` (新项目 - 战略中枢)**：
    *   负责解析 `Pitch.md` 的语法树（Appetite, No-Gos）。
    *   负责管理 `runtime/sandbox/pitches/` 的生命周期。
    *   负责计算战略偏离度矩阵。
*   **`projects/omo` (老项目 - 纯粹的交警)**：
    *   只负责接收 Compass 传来的验证请求。
    *   回答 Yes/No，并记录 Audit 日志和 OMO Debt。

### 3. 面向外部市场的商业化潜力 (Commercial SaaS / CLI)
这套包含 **"V2P -> C2G -> BMAD -> OSC -> TTY -> SWR"** 的思想，完全可以打包成一个**面向 Indie Hacker 和小型敏捷团队的独立开源命令行工具**（例如命名为 `c2g-cli`）。
*   **痛点切入**：现在市面上的工具（Jira太重，Linear太浅，Notion太散），没有一个能强制将“愿景、边界(Appetite)、代码产出”在 Git 层面对齐的。
*   **产品形态**：一个零依赖的 Rust/Go 编写的二进制文件，或者 Python 包。开发者在项目根目录执行 `c2g init`，就可以获得本地的 Sandbox 和目标流转门禁。
*   **结论**：它不仅能作为本系统内部的一个子引擎独立，甚至具备剥离出当前 Workspace，成为独立生产力工具的巨大潜力。

---

## ⚖️ 决断建议 (Next Actions)

作为架构师，我**强烈建议执行内部拆分**。

1. **短期 (Phase 43)**：在 `projects/cockpit/` 中实现 `workspace compass` 命令簇，统一目前的零散体验。
2. **中期 (Phase 44)**：将 `omo_bridge.py` 和 `omo_strategy.py` 从 `projects/omo` 抽离，建立新的 `projects/compass` 引擎。
3. **远期**：将 `compass` 的逻辑剥离对 eCOS 其他组件的强依赖，打造成通用的 Markdown-to-Goal 本地管理框架，对外开源。
