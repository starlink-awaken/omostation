---
status: proposed
lifecycle: architecture
owner: governance-team
last-reviewed: 2026-07-03
related:
  - 0128-state-generation-concurrency.md
  - ../../.omo/standards/omo-governance-surfaces.md
  - ../../.omo/standards/agent-workflow-contract.md
  - ../../bin/change-lane-check.py
  - ../../projects/omo/src/omo/omo_ingress_state.py
  - ../../projects/omo/src/omo/omo_state.py
---

# ADR-0129: 运行时投影面分离（ADR-0128 Phase 3 治本设计）

## 1. 背景与问题再定位

ADR-0128 已经把状态生成从“推模式 + 异步副作用”改造为“事件总线 + OMO broker 单写者 + 内容指纹”。但在落地 baseline PR 时发现一个更底层的冲突：

**OMO state-sync broker 在语义上是单次原子操作，却被 git 变更车道规则拆成多个 lane。**

具体表现为：

| 文件 | 当前路径 | 当前 lane | 是否可重算 | 生成工具 |
|---|---|---|---|---|
| health.yaml | `.omo/state/health.yaml` | governance_state | 是 | `omo state sync` / `compass_radar.py` |
| system.yaml | `.omo/state/system.yaml` | governance_state | 部分（投影字段可重算，phase/debt 字段为指针） | `omo state sync` / `omo state sync-tasks` |
| system_health.yaml | `.omo/state/system_health.yaml` | runtime_snapshot | 是 | `omo state refresh` / cron-service |
| governance-data.json | `.omo/_control/governance-data.json` | governance_state | 是 | `omo state sync` |
| BRIEF.md | `BRIEF.md` | docs | 是 | `omo state sync` / `generate-brief.py` |

`bin/change-lane-check.py` 的硬编码规则：
- `runtime_snapshot` 不能和任何其他 lane 混合；
- `governance_state` 不能和任何其他 lane 混合；
- `docs` 只能和 `governance_code`/`config` 组合（`ALLOWED_COMBOS`）。

结果是：即便 `state-sync` workflow 声明 `allowed_lanes: [governance_state, docs, runtime_snapshot]`，只要一次 commit 包含 `system_health.yaml`，lane check 就会失败。这导致 ADR-0128 设想的“单次原子 state-sync commit”实际上不可行，必须拆成 2-3 个 PR。

## 2. 根因分析

### 2.1 变更车道规则与数据语义错位

`.omo/state/health.yaml` 和 `.omo/state/system_health.yaml` 本质上都是**运行时扫描/计算后覆写的投影文件**，但一个被归为 `governance_state`，一个被归为 `runtime_snapshot`，只因为路径前缀不同。BRIEF.md 被归为 `docs` 则是因为它被列在“启动注意力文档”白名单里。

这种分类方式对**人类可读文档**和**源码**是合理的，但对**机器生成的运行时投影**造成了语义扭曲：
- 这些文件不是决策记录；
- 它们不包含需要人工 review 的语义变更；
- 它们都是“丢了可以重算”的缓存/投影。

### 2.2 单写者 broker 与多 lane commit 的冲突

ADR-0128 引入的 `omo_ingress_state.py:sync_state_projection` 是**单一原子写操作**，它同时更新 health.yaml、system.yaml、governance-data.json、BRIEF.md。逻辑上它们必须一致，但 lane check 却要求它们分属不同 commit。

分 commit 的代价：
- 产生 2-3 个微型 PR，审核成本高；
- 中间状态可能不一致（例如 system_health.yaml PR 先合，health.yaml PR 后合，dashboard 在窗口期内读到过期数据）；
- agent 需要手动拆分 staging，违背“单写者”简化并发的初衷。

### 2.3 Phase 3 之前的状态不可持续

即使引入内容指纹和单写者，只要投影文件仍分散在 `.omo/state/`、`BRIEF.md`、`.omo/_control/` 这些被不同 lane 管辖的位置，state-sync 就永远无法在一个 commit 内完成。这是架构层面的 tension，不是工具层面的 bug。

## 3. 设计目标

1. **保证 state-sync 的原子性**：一次同步产生的所有投影文件应在同一个 commit / 同一个 workflow 内完成。
2. **不削弱 lane discipline 对人类代码/文档的保护**：lane check 仍应防止无关代码、文档、子模块指针混交。
3. **可重算投影不再占用源码生命周期**：投影文件应明确为 runtime/cache，不纳入需要人工 review 的 git tracked 面，或至少不被 lane check 当作人类产物拆分。
4. **向后兼容**：现有消费者（cockpit API、CLI、dashboard、CI）不应在迁移期内失效。
5. **保持架构收敛**：不引入新的存储系统，复用已有的 `runtime/` 执行日志面和 OMO broker。

## 4. 方案对比

| 方案 | 描述 | 优点 | 缺点 | 是否符合目标 |
|---|---|---|---|---|
| A. 修改 lane check 允许 state-sync 跨 lane | 给 `runtime_snapshot` 或 `state-sync` workflow 开特例 | 改动最小，立即可用 | 特例会累积，lane discipline 被侵蚀 | 部分 |
| B. Gitignore 现有路径 | `.omo/state/*.yaml`、`BRIEF.md` 等加入 `.gitignore` | 无需改路径 | 新 clone/CI 缺文件，reader 需 fallback，state-freshness-check 会失败 | 否 |
| C. 运行时投影面分离（推荐） | 新建 `runtime/omo/state/` 作为投影文件 canonical 位置，`.omo/state/` 保留兼容 shim | 彻底解耦 lane 冲突，projection 统一为 runtime_snapshot，支持原子同步 | 路径迁移工作量大 | 是 |
| D. 按 lane 拆分成多个 workflow | health/system/governance-data 一个 workflow，BRIEF 一个，system_health 一个 | 严格 lane discipline | 失去原子性，同步碎片化 | 否 |
| E. 统一把 `.omo/state/` 全标 runtime_snapshot | health.yaml 也改为 runtime_snapshot | 路径不变，lane 统一 | system.yaml 含 phase/debt 指针，不完全是 runtime；需要大量 lane 例外 | 部分 |

## 5. 推荐方案：运行时投影面分离（C）

### 5.1 总体设计

创建一个新的运行时投影面目录：

```
runtime/omo/state/
├── health.yaml                 # 原 .omo/state/health.yaml
├── system_health.yaml          # 原 .omo/state/system_health.yaml
├── governance-data.json        # 原 .omo/_control/governance-data.json
└── brief.md                    # 原 BRIEF.md（保留 human-readable 命名）
```

保留 `.omo/state/system.yaml` 在原位置，但明确其角色：
- `.omo/state/system.yaml` 是**治理状态指针文件**，记录当前 phase、debt 指针、health_score_ref 等；
- `runtime/omo/state/` 下的文件是**可重算运行时投影**，由 broker 统一写入；
- `.omo/_control/` 只保留真正需要版本化的控制配置（如 `debt-dashboard/current.yaml`）。

### 5.2 路径迁移策略

**第一阶段（兼容期，4-8 周）**：
- 新增 `runtime/omo/state/` 作为 canonical 写入路径；
- `omo_ingress_state.py` 同时写入新路径，并保留向旧路径的同步（软链接或复制）；
- 消费者逐步迁移到新路径；
- lane check 将 `runtime/omo/state/` 统一识别为 `runtime_snapshot`。

**第二阶段（切换期）**：
- 更新所有消费者默认读取 `runtime/omo/state/`；
- 旧路径 `.omo/state/health.yaml`、`BRIEF.md` 等由兼容 shim 重定向；
- CI 在 checkout 后自动运行 `omo state sync` 生成投影。

**第三阶段（退役期）**：
- 移除旧路径写入；
- `.gitignore` 旧投影文件；
- 删除兼容 shim。

### 5.3 Lane 收敛

迁移完成后，state-sync 涉及的文件 lane 分布：

| 文件 | 新路径 | 新 lane | 说明 |
|---|---|---|---|
| health.yaml | `runtime/omo/state/health.yaml` | runtime_snapshot | 纯投影 |
| system_health.yaml | `runtime/omo/state/system_health.yaml` | runtime_snapshot | 纯投影 |
| governance-data.json | `runtime/omo/state/governance-data.json` | runtime_snapshot | 纯投影 |
| brief.md | `runtime/omo/state/brief.md` | runtime_snapshot | 纯投影 |
| system.yaml | `.omo/state/system.yaml` | governance_state | 治理指针文件，保留 tracked |

`state-sync` workflow 的 `allowed_lanes` 简化为 `[runtime_snapshot]`，一次 commit 即可包含所有投影文件，lane check 自然通过。

### 5.4 读取者迁移

通过 **路径注册表** 避免硬编码分散：

```yaml
# .omo/_truth/registry/runtime-projections.yaml
projections:
  health:
    canonical: runtime/omo/state/health.yaml
    legacy: .omo/state/health.yaml
    generator: omo state sync
  system_health:
    canonical: runtime/omo/state/system_health.yaml
    legacy: .omo/state/system_health.yaml
    generator: omo state refresh
  governance_data:
    canonical: runtime/omo/state/governance-data.json
    legacy: .omo/_control/governance-data.json
    generator: omo state sync
  brief:
    canonical: runtime/omo/state/brief.md
    legacy: BRIEF.md
    generator: omo state sync
```

新增工具函数 `omo.paths.projection_path(name)`，消费者统一调用：

```python
from omo.paths import projection_path
health_path = projection_path("health")  # 优先 canonical，fallback legacy
```

### 5.5 system.yaml 的特殊处理

`system.yaml` 留在 `.omo/state/system.yaml`，因为它包含两类内容：
- **可重算投影字段**：task 计数、health_score_ref、runtime_health_summary；
- **治理指针字段**：current_phase、phase*_status、debt_weight_items。

对于可重算字段，建议逐步拆出到 `runtime/omo/state/system-projection.yaml`，让 `system.yaml` 只保留治理指针。但这是一项更大的重构，可以在 RPP 迁移稳定后再做。

在 RPP 第一阶段，`system.yaml` 仍由 `omo state sync-tasks` 和 `omo state sync` 更新，保留 `governance_state` lane。

## 6. 与 ADR-0128 的关系

ADR-0128 解决的是**“谁写、怎么写、何时写”**的问题：
- 单写者 broker；
- 事件总线触发；
- 内容指纹避免无意义刷新。

ADR-0129 解决的是**“写到哪里、按什么生命周期管理”**的问题：
- 投影文件集中到 runtime 面；
- lane 统一为 runtime_snapshot；
- state-sync 恢复原子 commit。

两者是递进关系：ADR-0128 止血并建立单写者秩序；ADR-0129 治本完成 runtime/governance 面分离。

## 7. 落地路线图

### Phase 1：注册表 + 双写（2-3 周）

1. 创建 `.omo/_truth/registry/runtime-projections.yaml`；
2. 实现 `omo.paths.projection_path()` 工具函数；
3. 修改 `omo_ingress_state.py` 双写：先写 `runtime/omo/state/`，再写 legacy 路径；
4. 修改 `omo state refresh` 双写 `system_health.yaml`；
5. 更新 `state-sync` workflow 的 write surface 为新路径；
6. 添加兼容 shim：旧路径文件不存在时自动从 canonical 复制；
7. 更新 `bin/change-lane-check.py`：将 `runtime/omo/state/` 识别为 `runtime_snapshot`。

### Phase 2：读取者迁移（4-6 周）

1. 逐个迁移消费者：
   - `bin/compass_radar.py`
   - `bin/generate-brief.py`
   - `bin/state-freshness-check.py`
   - `bin/governance-readiness.py`
   - `bin/omo-health.py`
   - `projects/cockpit/src/cockpit/web/api_omos.py`
   - `projects/cockpit/src/cockpit/commands/status.py`
   - `.github/workflows/c2g-radar-daily.yml`
2. 更新测试 fixtures；
3. 更新 `AGENTS.md`、`ARCHITECTURE.md` 等文档中的路径引用；
4. CI checkout 后自动跑 `omo state sync`。

### Phase 3：旧路径退役（2-4 周）

1. `omo_ingress_state.py` 停止写入 legacy 路径；
2. `.gitignore` 中添加：
   ```
   .omo/state/health.yaml
   .omo/state/system_health.yaml
   .omo/_control/governance-data.json
   BRIEF.md
   ```
3. 移除兼容 shim；
4. 更新 `state-freshness-check.py` 等工具：canonical 路径缺失时视为需要 sync，而不是 failure；
5. 发布 closeout / 迁移完成审计。

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 大量硬编码路径迁移遗漏 | 提供 `omo.paths.projection_path()` 单一入口；lint 检测直接拼接 `.omo/state/health.yaml` 的代码 |
| 新 clone 缺少投影文件 | CI / Makefile 默认运行 `omo state sync`；工具对 canonical 路径缺失给出友好提示而非崩溃 |
| cockpit/dashboard 读到过期 legacy 文件 | 双写期保证同步；切换期优先 canonical，legacy 作为 fallback |
| 外部脚本/AI 仍写旧路径 | pre-commit hook 检测旧路径写入并 warning；MOF drift 检查注册表一致性 |
| `system.yaml` 仍跨 lane | 保留其 governance_state 身份；可重算字段未来再拆 |

## 9. 待决策

1. 是否接受 `runtime/omo/state/brief.md` 替代根目录 `BRIEF.md`？这会影响 `CLAUDE.md` 启动协议和 human attention funnel。
2. 兼容期是否使用 symlink（`BRIEF.md -> runtime/omo/state/brief.md`）还是复制？symlink 对跨平台更友好，复制更简单。
3. `system.yaml` 的可重算字段是否在本次一并拆出，还是留给后续 ADR？
4. 是否同步把 `docs/generated/project-layer-index.md` 等已 gitignored 生成物也纳入 `runtime-projections.yaml` 统一注册？

## 10. 立即可做的最小验证

1. 创建 `runtime/omo/state/` 目录；
2. 修改 `omo_ingress_state.py` 双写，观察 `git status` 是否仅 `runtime/omo/state/` 变化；
3. 验证 lane check：同一 commit 包含 `runtime/omo/state/health.yaml` 和 `runtime/omo/state/brief.md` 时，lanes = {runtime_snapshot}，check PASS。
