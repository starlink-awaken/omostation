# P1 三个早期项目分析报告

> Phase 1 历史分析快照，不再作为当前 phase 决策入口。

> 日期: 2026-05-20
> 审计: Sophia / Pallas / BOS-Skill-CLI

---

## 一、Sophia — 符号化研究范式引擎

| 维度 | 评估 |
|------|------|
| **代码** | 12 py / 1,077 行核心逻辑 + 27 tests |
| **架构** | 状态机驱动的范式编译器: 11 CLI + 8 MCP 工具 + TUI + Python API |
| **本质逻辑** | 研究范式从语言描述→可执行编译→结果验证的全流程 |
| **代码质量** | ✅ typing, 序列化, 安全校验, 零外部核心依赖 |
| **依赖者** | ✅ **Minerva** (`from sophia import compile_paradigm` — Web API + tests) |
| | ✅ **OntoDerive** ecosystem adapter |
| **健壮性** | Alpha 级但已有生产骨架 |

**结论: 🟢 保留并继续投入**

Sophia 是工作区内**唯一被其他项目代码级 import 的项目**，说明它的能力是真实被需要的。27 tests 覆盖了核心管线，但 `COMPILE` 和 `FORGE` 两条主线的边界用例可能还不够。

**建议**: 测试从 27 扩到 50+（主要补充 pipeline 错误路径和边界条件），然后可以考虑 v1.0。

---

## 二、Pallas — 知识工程统一入口

| 维度 | 评估 |
|------|------|
| **代码** | 3 py / 204 行 CLI + 15 行 `__init__` + 202 行 test |
| **本质逻辑** | 编排器/编排器: 一条 `pallas pipeline` 串起 ontoderive → pallas → agora → minerva |
| **依赖者** | ❌ 零。没有任何代码 import 它或 subprocess 调它 |
| **存在的唯一理由** | 跨项目一站式编排体验（手动场景） |
| **是否可持续** | ⚠️ 薄层设计的优势就是零维护成本 |

**结论: 🟡 保留薄层，不继续增肥**

Pallas 不需要变厚。它就是一个 `main()` + 几个 subprocess call，唯一的业务价值是"一条命令跑四个项目"。只要它还在用 setup.py 声明依赖关系，修好 `pip install -e` 即可。

注意: **setup.py 声明了 ontoderive/agora/sophia/minerva 作为可选依赖**，但实际在使用时不需要安装这些包 —— Pallas 用 subprocess 而不是 import 调用它们。依赖声明有误。

**建议**: 
- 修正 `pyproject.toml` 的可选依赖声明（当前声明了 ontoderive/agora 等包但 Pallas 并不 import 它们）
- 加一行 pipeline 完成后打印耗时
- 不增加新功能。当 Agora v2 Pipeline 成熟后可以自然退役。

---

## 三、BOS-Skill-CLI — 技能生命周期管理

| 维度 | 评估 |
|------|------|
| **代码** | 9 py / 3 commits / 15 tests / **70.78% 覆盖率** |
| **架构** | 三段式状态机: staged → promoted / rejected |
| | 3 路冲突策略 (replace/skip/rename) |
| | 3 源搜索 (filesystem, pip, github) |
| | TUI (Textual) + CLI (Typer) 双界面 |
| **与 SharedBrain 的关系** | **完全独立**。不依赖 BOS/Z-Core，自己管理 JSON 注册表 |
| **代码质量** | ✅ **工作区内最好之一** — 模块分离干净 (SkillReview state machine, Skills service layer, CLI, TUI), 测试覆盖 70%+ |
| **依赖者** | ❌ 零代码耦合。仅与 Agora discovery 做软耦合 |
| **成熟度** | MVP 骨架: 3 个 commit, 核心链路基本完整, 部分 feature 待做 |

**结论: 🟢 保留，值得投入资源完成**

这是工作区内设计最干净的项目之一。SkillReview 状态机 + 3-way conflict policy + 3-source search 的组合是真正有用的基础设施。问题是它还差几个 feature 才到"可用"状态。

**建议目标**: 完成以下 3 个 pending features 后发布 v1.0:
1. `github:` download 源（目前只有 filesystem 和 pip）
2. URL zip download 源
3. 技能模板（`init` 命令一键脚手架）
4. 补到 20+ tests

---

## 四、综合定位图

```
依赖关系:

Agents (外部) ──── BOS-Skill-CLI (技能生命周期)
     │
     ├─── Sophia (范式引擎) ←── Minerva (import)
     │                              │
     ├─── Pallas (编排桥) ────── CLI→ ontoderive / agora / minerva / sophia
     │
     └─── other MCPs (kos, gateway...)
```

| 项目 | 角色 | 建议 | 努力量 |
|------|------|------|--------|
| Sophia | 能力输出者 (被 import) | 🟢 加固 | 补 30+ tests (~半天) |
| Pallas | CLI 编排器 (被手动调) | 🟡 维持薄层 | 修可选的依赖声明 (~半小时) |
| BOS-Skill-CLI | 独立基础设施 | 🟢 完成 MVP | 3 个 feature (~1-2天) |
