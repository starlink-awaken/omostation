# Phase 0 回顾：发现的问题与改进方向

> 日期: 2026-05-26 | 基于实际运行数据的回顾

---

## 一、确认正确的部分

| 设计决策 | 验证结果 | 
|---------|---------|
| 双轨制（代码硬门禁 + LLM 软推理） | ✅ 两边输出互补，不冲突 |
| 三个 CLI 脚本分开独立 | ✅ 可单独使用也可组合调用 |
| 元模型 6 类型 + 8 知识类型分离 | ✅ 未出现类型混淆 |
| conservative prompt（温度 0.1 + max_tokens 4096） | ✅ 输出结构稳定 |
| 不阻塞原则（reason 失败不阻止注册） | ✅ 容错 |
| Phase 0 3 天 | ✅ 按时完成 |

## 二、发现的问题

### 🔴 1. PROCESSOR/AGENT 类型边界需要收紧

LLM Reasoner 两次输出对这个节点分类有分歧：一次 PROCESSOR (0.90)，一次 AGENT (0.85)。根因是 Agent Runtime 同时具备"任务执行"和"LLM 对话"两种特征，两种类型的判定标准在当前宪法中没有**排他性规则**。

**修复方向**：在宪法中增加"如果一个节点同时满足 A 和 B 类型特征，优先选择 X"的排序规则。

### 🔴 2. governance log 泄露文件系统路径

当前 log 记录 `yaml_path: "/Users/xiamingxing/.hermes/architecture/arch_nodes/agent-runtime.yaml"`——完整路径。虽然这是在本地运行，但治理数据如果将来被共享（报告、备份）就泄露了文件系统结构。

**修复方向**：log 中只记录相对路径（如 `arch_nodes/agent-runtime.yaml`）。

### 🟡 3. 没有"节点更新"流程

一个节点注册后，如果它的 ARCH_NODE.yaml 变了（比如增加了 provides），目前没有 `agora update-node` 命令。需要重新 register（会产生重复的 governance log 条目，Agora registry 也会 update）。

**修复方向**：Phase 1 中增加 `agora update-node` 命令，支持版本升级和字段变更。

### 🟡 4. `arcnode reason` 的 O2/O4 操作未实现

宪法定义的五项本体论操作，Phase 0 只实现了 O1（分类）、O3（依赖）、O5（承诺）。O2（分体论/COMPOSE 关系）和 O4（同一性/版本变化）还未实现。

**修复方向**：Phase 1 中扩展 prompt 覆盖 O2（需要上下文中有 COMPOSE 关系定义）和 O4（需要比较旧版和新版 YAML）。

### 🟢 5. 缺少 `--help` 文档

三个 CLI 脚本的 usage 信息太简略。`arcnode validate --help` 只有一行。

**修复方向**：Phase 1 中统一 CLI 的 argparse help。

### 🟢 6. 宪法引用的 schema 文件路径是"相对路径"

`meta_types.md`、`interface_contract.md`、`constraints.md` 在宪法中用相对路径 `schema/` 引用。但如果 move 了文件，引用就断了。

**修复方向**：明确约定文件位置的绝对规则（相对于 `~/.hermes/architecture/`）。

## 三、改进方向确认

| 优先级 | 问题 | 在哪个 Phase 修 | 工作量 |
|--------|------|----------------|--------|
| P0 | PROCESSOR/AGENT 边界规则 | Phase 1.2 — 现在做 | ~15min |
| P0 | log 路径脱敏 | Phase 1.3 — 现在做 | ~5min |
| P1 | update-node 命令 | Phase 2 | ~2h |
| P1 | O2/O4 操作 | Phase 1.3 | ~1h |
| P2 | CLI --help | Phase 1.4 | ~30min |
| P2 | 引用路径规则 | Phase 1.1 | ~10min |
