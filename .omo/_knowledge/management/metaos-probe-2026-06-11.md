---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# MetaOS AppendOnlyLog 探查报告

**探查人**: worker-4
**日期**: 2026-06-11
**分支**: 当前分支
**落位**: `.omo/_delivery/metaos-probe-2026-06-11.md`

---

## 1. 项目基本信息

| 字段 | 值 |
|------|-----|
| 项目路径 | `projects/metaos/` |
| 包名 | `metaos` (hatchling wheel, `src/metaos`) |
| Python | 3.13+ |
| 描述 | MetaOS — 编排/治理层: 决策门控、免疫监控、路由、数字资产引擎 |
| 状态 | 🟢 163 tests，活跃开发 |
| 从属关系 | 2026-06-06 从 `kairon/packages/metaos` 拆出为独立项目 |

---

## 2. `.omo/` 存在性

**结论：不存在。**

`projects/metaos/.omo/`目录不存在，metaos 无任何治理平面结构。

---

## 3. AppendOnlyLog 相关代码

**结论：完全不存在。**

- `AppendOnlyLog` — 0 处
- `ZTimestampModel` — 0 处
- `append_only_log` — 0 处
- 全库搜索无任何匹配

---

## 4. .jsonl 直接写入

**结论：不存在。**

源码（含 src/ 和 tests/，排除 .venv）中与 jsonl/json相关的引用全部为：

| 文件 | 用途 | 类型 |
|------|------|------|
| `onboard.py` | `~/.metaos/onboard.json` 用户配置 | 读/写 JSON |
| `gate.py` | `config/decision_matrix.json` 门控规则配置 | 读 JSON |
| `router.py` | `config/task_routes.json` 路由规则配置 | 读 JSON |
| `d_layer.py` | `{asset_id}.json` 数字资产生成 | 写 JSON |
| `m_layer.py` | HTTP API `r.json()` 响应解析 | 调用 `.json()` |
| `workflow_planner.py` | HTTP API `r.json()` 响应解析 | 调用 `.json()` |
| `task_manager.py` | `agora-tasks.json` 任务存储 | 读/写 JSON |

**无任何 `.jsonl` 文件直接写入操作。**

---

## 5. 数据持久化机制

| 模块 | 机制 | 文件 |
|------|------|------|
| D Layer（数字资产） | JSON 文件（每个 asset 一个 .json） | `layers/d_layer.py` |
| Workflow 断点续跑 | SQLite | `core/workflow_store.py` |
| A2A 任务管理 | JSON 文件 | `a2a/task_manager.py` |
| CLI onboard | JSON配置文件 | `onboard.py` |

---

## 6. 与 AppendOnlyLog 改造的距离

| 方面 | 现状 | 距离 AppendOnlyLog |
|------|------|-------------------|
| 时间戳日志 | 无 | 需新增 |
| append-only 语义 | 无 | 需新增 |
| ZTimestampModel | 无 | 需新增 |
| .jsonl 文件写入 | 无 | 需新增 |
| 审计/事件流 | 无 | 需新增 |
|治理平面 (.omo/) | 无 | 需新增 |

---

## 7. 下一步建议

1. **创建 `.omo/` 治理平面** — 参照 kairon/omo 模板
2. **选定日志注入点** — 建议优先在以下位置引入 AppendOnlyLog：
   - D Layer 的数字资产写入（`layers/d_layer.py`）
   - A2A 任务状态变更（`a2a/task_manager.py`）
   - Workflow 断点续跑状态变更（`core/workflow_store.py`）
3. **引入 omo AppendOnlyLog** — 从 `projects/omo/src/omo/core/append_only_log.py` 复用
4. **参考 omo 模式** — omo 已完成 AppendOnlyLog 改造，可直接参照

---

## 8. 参考文件

- `projects/metaos/CLAUDE.md` — 项目自述
- `projects/metaos/pyproject.toml` — 包配置
- `projects/omo/` — AppendOnlyLog 改造参考仓