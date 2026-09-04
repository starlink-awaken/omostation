---
type: ephemeral
created: 2026-09-03
---

# Documents 内容主权面迁移台账

日期：2026-08-11

`captured_at: 2026-08-11T11:24:26+08:00`

状态：Phase 0 收敛已实施，物理迁移待消费者清零

审计入口：`cockpit kems scan` → `l4-kernel content audit`

## 1. 裁决

Documents 是内容主权面，只持有数据、资料、信息、知识、文档、方法、领域宪法、声明式契约、人工决策和已接受证据。

KEMS 运行能力归 Workspace：

- KEMS 数据模型、图存储、检索与验证：`projects/knowledge/kairon/packages/kos/src/kos/kems/`
- 执行授权与编排：OMO + Workflow Mesh
- 运行适配、调度、状态、缓存和派生物：`projects/runtime/`
- 人类入口：Cockpit
- L4 Kernel：只负责内容契约、路径策略和 T0—T8 Harness，不直接执行 skill/workflow

本轮不删除 Documents 历史文件；先阻止新增运行态，再以消费者证据逐批迁移。

## 2. 分类契约

| 类型 | Documents 是否允许 | 权威 owner | 当前动作 |
|------|--------------------|------------|----------|
| `content` | 是 | Documents 业务域 | 保留 |
| `contract` | 是 | Documents 业务域 / L4 契约 | 保留并验证 |
| `runtime` | 否 | Kairon/KOS、OMO、Runtime 或其他 Workspace 项目 | 建立消费者清单后迁移 |
| `projection` | 非权威副本可暂存 | Workspace 运行态；Documents 仅作可重建视图 | 标记为非 SSOT，后续外移 |
| `cache` | 否 | Workspace 本地 state/cache | 清理或重建，不迁作内容 |
| `bridge` | 临时允许 | 实现仍归 Workspace | 消费者清零后退役 |

分类器按路径、扩展名、缓存目录和桥标记做确定性初筛；它不递归目录符号链接，但会把文件符号链接作为原路径下的独立资产审计。它会把资料中的源代码样本也列为 `runtime` 候选，因此 T8 在 Phase 0 仅 opt-in；迁移前仍需结合消费者和内容意图复核。

## 3. 2026-08-11 全量基线

命令：

```bash
uv run --directory ".subtrees/l4-kernel" --group dev \
  python -m l4_kernel.cli content audit "/Users/xiamingxing/Documents" --json
```

扫描 321,786 个普通文件或文件符号链接：

| 分类 | 数量 |
|------|-----:|
| content | 276,649 |
| contract | 420 |
| runtime | 7,650 |
| projection | 188 |
| cache | 36,878 |
| bridge | 1 |

Fail-closed 违规总数为 44,528（`runtime + cache`）。当前 `ok=false` 是真实存量债务，不是扫描失败。

### 3.1 主要域分布

| 域/根目录 | runtime | cache | projection | content | contract | 说明 |
|-----------|--------:|------:|-----------:|--------:|---------:|------|
| `@家庭生活` | 1,437 | 36,395 | 4 | 4,700 | 24 | 缓存占绝对多数，优先识别嵌套工程与虚拟环境 |
| `@学习进化` | 2,737 | 19 | 8 | 227,410 | 204 | 代码型学习资料与真实执行器混合，必须语义复核 |
| `@个人` | 2,553 | 48 | 4 | 28,939 | 8 | 个人代码资料与运行面混合 |
| `Zotero` | 755 | 1 | 0 | 36 | 0 | 多为应用资源，不应直接按业务执行器搬迁 |
| `@工作文档` | 90 | 398 | 15 | 14,291 | 102 | 先迁明确工具，再处理缓存 |
| `@公共` | 59 | 13 | 3 | 106 | 10 | 跨域公共执行器，优先级高；已有 1 个薄桥 |
| `@驾驶舱` | 9 | 2 | 141 | 352 | 15 | 生成视图集中，应继续明确非 SSOT |
| `_inbox` | 3 | 1 | 0 | 68 | 0 | 收件箱不应长期持有执行器 |

## 4. KEMS 专项迁移清单

按完整相对路径包含 `kems` 统计，仍有 46 个 `runtime` 候选；不含 `validate-concept-card.py` 等名称未带 KEMS 的关联执行器，因此这是下界，不是完整执行面规模。

### 4.1 P0：明确 legacy execution surface

| Documents 路径族 | 已见资产 | 目标 owner | 处置 |
|------------------|---------:|------------|------|
| `@学习进化/_control/executors/` | 10 个执行文件 | OMO / Runtime / 对应 Workspace 项目 | 禁止扩展；逐项建立调用方和替代入口 |
| `@学习进化/_knowledge/10-systems/KEMS/.kems/_scripts/` | 10 个脚本 | Kairon/KOS；编排走 OMO | 方法与契约留 Documents，脚本迁出 |
| `@公共/_runtime/kems-v2/` | 12 个 Python 脚本，另有缓存 | Kairon/KOS 或 Runtime | 合并重复实现，缓存直接重建 |
| `@公共/_runtime/check-kems-update.py`、`kems-toolkit.py` | 2 个脚本 | Cockpit / Kairon/KOS | 复核功能后桥接或退役 |
| `@工作文档/_control/tools/kems_*.py`、`卫健委/_runtime/check-kems-health.py` | 3 个脚本 | 对应 Workspace adapter | 保留业务输入，迁走执行逻辑 |
| `.kems-repair-backups/`、`_inbox/2026-08-03-kems-repair.py` | 2 个脚本候选 | 证据归档或删除队列 | 先判定是否仅为历史证据 |

代表性候选：

- `@学习进化/_control/executors/kems`
- `@学习进化/_control/executors/kems-mcp`
- `@学习进化/_control/executors/validate-concept-card.py`
- `@学习进化/_knowledge/10-systems/KEMS/.kems/_scripts/kems-cli.py`
- `@学习进化/_knowledge/10-systems/KEMS/.kems/_scripts/kems-mcp.py`
- `@公共/_runtime/kems-v2/graph-query.py`
- `@公共/_runtime/kems-v2/model-ask.py`
- `@公共/_runtime/kems-v2/refresh-indexes.py`

### 4.2 已完成的首个薄桥

`@公共/_runtime/kems-materialize.py` 原实现与 `projects/runtime/scripts/kems-materialize.py` 字节完全一致：

```text
SHA-256 208fb9e5d5d1da320eef3b3da26e2d504eb2d3a51a1dec63eb71829a0a65e1b5
```

Documents 副本已替换为带 `l4-content-plane: workspace-bridge` 标记的薄桥，通过 `BOS_WORKSPACE_ROOT` 定位 Workspace owner；`--help` 委派验证通过。现有消费者 `@公共/_runtime/bos-neural-mesh-runner.py` 使用 Python 解释器调用旧路径，因此兼容链未中断。

在同一份资产快照内，这次替换会把该文件从 `runtime` 转为 `bridge`，即 `runtime -1`、`bridge +1`、违规数 `-1`。上面的全量数字包含文件符号链接覆盖和审计期间 Documents 的实时变化，因此不拿旧快照总数冒充严格前后对照。

## 5. 迁移波次与退出条件

1. **Wave 0（本轮）**：L4 内容面分类/T8、旧执行入口 fail-close、Cockpit 扫描入口、首个重复实现薄桥。
2. **Wave 1（KEMS）**：为上述 P0 路径建立 `consumer → Workspace replacement → evidence` 映射；每次只迁一个闭环。
3. **Wave 2（公共运行态）**：处理 `@公共/_runtime/`、根目录脚本和 `_inbox` 执行器；把状态库、缓存和生成物移至 Workspace state root。
4. **Wave 3（域级清理）**：按域区分“代码资料”与“实际执行器”，先 `@家庭生活` 缓存，再 `@学习进化`、`@个人` 的代码型内容。
5. **Wave 4（强制门禁）**：单域债务清零后启用 T8；所有域清零后再把 T8 纳入默认 Phase 0 profile。

单个 legacy surface 的退出条件：

- 已识别全部调用方；
- Workspace replacement 有测试与可追溯 owner；
- 兼容桥通过回归验证且有 sunset 日期；
- 连续观测期无旧路径调用；
- 删除前另行获得明确确认。

## 6. 当前风险

- Documents 仍有大量嵌套缓存和应用资源，不能把 44,528 个候选机械地批量移动。
- KEMS README 中的历史版本、规模和“已部署”宣称只代表历史记录，不再证明当前运行有效。
- `projection` 目前只告警；在生成链和恢复路径稳定前，不应把 Documents 视图直接删掉。
- Phase 0 的重点是先停止架构债继续增长；物理清理必须以消费者证据为准。
