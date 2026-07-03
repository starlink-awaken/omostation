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

## 11. 多维度评审与修订建议

对 ADR-0129 进行了 OMO/C2G/GaC/MOF 边界、fresh-clone/CI/onboarding、ES/CQRS 第一性原理、替代方案、子模块/worktree/并发/回滚审计、MVP 与风险六个维度的深度评审。核心结论：**方向正确，但当前方案不是最优解，需要修订后才能落地。**

### 11.1 当前方案的根本缺陷

#### 11.1.1 选址 `runtime/omo/state/` 与既有治理定义冲突

- `.gitignore:46` 已忽略整个 `runtime/omo/`。把 canonical 投影面放在被 gitignore 的目录，意味着新 clone/CI 默认看不到这些文件，与“projection 需要被 dashboard/cockpit/CLI 读取”矛盾。
- `AGENTS.md` §4 明确定义 `runtime/` 为 “Runtime execution logs, sandbox, server.log. Do not edit manually.” 把需要 OMO broker 写入、被服务读取的状态投影放进执行日志面，会造成 runtime/ 职责扩散。

#### 11.1.2 `system.yaml` 残留导致 state-sync 仍无法单 lane

当前 `omo_ingress_state.py:sync_state_projection` 仍会写 `.omo/state/system.yaml`（`projects/omo/src/omo/omo_ingress_state.py:241-262`），而 `system.yaml` 按规划保留为 `governance_state`。因此即便其他文件都迁到 `runtime/omo/state/`，一次 state-sync commit 仍会同时包含 `runtime_snapshot` 和 `governance_state`，lane check 继续失败。这是方案自述目标（`allowed_lanes: [runtime_snapshot]`）与实际路径之间的矛盾。

#### 11.1.3 `omo state refresh` 未纳入 broker

`projects/omo/src/omo/omo_state.py:cmd_state_refresh`（line 101、172-174）直接写 `.omo/state/system_health.yaml`，既不走 `omo_ingress_state.py`，也无文件锁。RPP 若把 `system_health.yaml` 纳入统一面，必须先改造这个入口，否则会出现双写者/双路径。

#### 11.1.4 Registry 与 profile 未同步

- `agent-workflows.yaml:158` 的 `state-sync-agent` 的 `can_write_lanes` 只有 `[governance_state]`，缺少 `runtime_snapshot`；
- `agent-workflows.yaml:1036-1040` 的 `state-sync` workflow `surfaces.write` 仍列旧路径；
- `mutation-surfaces.yaml:236` 的 `omo-state-sync-projection` `mutation_target` 仍列旧路径；
- `projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-OMO-STATE.yaml` 的 M1 政策范围未更新。

#### 11.1.5 `BRIEF.md` 人类入口风险

`BRIEF.md` 是 `CLAUDE.md:16` 启动协议中的“注意力漏斗”。直接迁到 `runtime/omo/state/brief.md` 会破坏 onboarding 体验。需要保留根目录入口（symlink 或生成后复制），直到启动协议迁移完成。

### 11.2 替代方案评估

| 方案 | 描述 | 优势 | 劣势 | 适用阶段 |
|---|---|---|---|---|
| A. 修复 `change-lane-check.py` 的 `allowed_lanes` 优先级 | 把 `allowed_lanes` 子集检查提前到硬编码隔离规则之前 | 改动最小，保留路径，立即解决 lane 冲突 | 给 state-sync 开了跨 lane 先例，若滥用会侵蚀 discipline | **MVP 止血首选** |
| B. Gitignore 现有路径 | 不迁路径，直接 ignore | 零路径迁移 | 不解决原子 commit，新 clone 缺文件，入口断裂 | 不推荐 |
| C. RPP（当前） | 迁到 `runtime/omo/state/` | 统一 lane，与既有 runtime 面对齐 | 与 `.gitignore`/`AGENTS.md` 定义冲突，`system.yaml` 残留 | 需修订 |
| D. **`.omo/state/runtime/` 投影面（推荐修订）** | 在 `.omo/state/` 内新建 `runtime/` 子目录作为投影面 | 不离开 OMO state plane，路径前缀稳定，lane 只需新增 `.omo/state/runtime/ -> runtime_snapshot` | 仍在 `.omo/` 下，需要 MOF 政策更新 | **长期根治首选** |
| E. 按 lane 拆多个 workflow | health/system/governance-data 一个 workflow，BRIEF 一个，system_health 一个 | 严格 lane | 失去原子性，碎片化 | 不推荐 |

### 11.3 修订后的推荐方案：`.omo/state/runtime/` 投影面 + `allowed_lanes` 修复

综合评审，推荐把当前 RPP 的落点从 `runtime/omo/state/` 改为 **`.omo/state/runtime/`**，并同步修复 lane check。

#### 11.3.1 为什么 `.omo/state/runtime/` 优于 `runtime/omo/state/`

1. **不离 OMO state plane**：`omo-governance-surfaces.md` 已把 `.omo/state/` 定义为 `runtime_ssot`，`runtime/` 子目录是其自然延伸，不破坏 `AGENTS.md` 对 `runtime/` 的边界定义。
2. **无需改动 `.gitignore`**：`.omo/state/runtime/` 不会被现有 gitignore 规则误伤，projection 文件仍可被 tracked（或后续 selectively gitignored）。
3. **路径迁移量更小**：消费者前缀仍是 `.omo/state/`，只需要把末尾 `health.yaml` 改为 `runtime/health.yaml`，回归测试面更小。
4. **lane 规则更内聚**：`change-lane-check.py` 只需新增一条 `path.startswith(".omo/state/runtime/") -> runtime_snapshot`，无需把整个 `runtime/` 目录都卷入状态投影语义。

#### 11.3.2 必须同步的 `change-lane-check.py` 修复

当前 `bin/change-lane-check.py:137-148` 中，硬编码隔离规则（line 140-141、146-147）在 `allowed_lanes` 子集检查（line 142）之前执行，导致 workflow 声明的 `allowed_lanes` 被架空。应调整为：

```python
def allowed_for(lanes: set[str], allowed_lanes: set[str]) -> bool:
    if len(lanes) <= 1:
        return True
    # workflow 显式授权优先
    if allowed_lanes and lanes <= allowed_lanes:
        return True
    if "runtime_snapshot" in lanes and len(lanes) > 1:
        return False
    if "submodule_pointer" in lanes and not any(lanes <= combo for combo in ALLOWED_COMBOS):
        return False
    if "governance_state" in lanes and len(lanes) > 1:
        return False
    return any(lanes <= combo for combo in ALLOWED_COMBOS)
```

这样 `state-sync` workflow 的 `[governance_state, docs, runtime_snapshot]` 才能真正生效，在 `.omo/state/runtime/` 迁移完成前也能让旧路径的 state-sync commit 通过。

#### 11.3.3 修订后的文件布局

```text
.omostate/
├── system.yaml                    # 治理指针文件，保留 governance_state
└── runtime/                       # 运行时投影面，统一 runtime_snapshot
    ├── health.yaml
    ├── system_health.yaml
    ├── governance-data.json
    └── brief.md
```

根目录 `BRIEF.md` 保留为 tracked symlink 或生成后复制，直到 `CLAUDE.md` 启动协议迁移完成。

### 11.4 修订后的 MVP

| 项 | 是否纳入 MVP | 说明 |
|---|---|---|
| 修复 `change-lane-check.py` allowed_lanes 优先级 | 是 | 立即解除 lane 冲突，作为过渡止血 |
| 创建 `.omo/state/runtime/` | 是 | 新的 canonical 投影面 |
| 迁 health / system_health / governance-data | 是 | 纯运行时投影 |
| 保留 `BRIEF.md` 根入口 | 是 | symlink/copy，不破坏启动协议 |
| `omo state refresh` 改造 | 是 | 必须纳入 broker 或统一写 canonical 路径 |
| 更新 `state-sync-agent` profile | 是 | `can_write_lanes` 增加 `runtime_snapshot` |
| 更新 mutation surfaces / workflow surfaces | 是 | 指向新路径 |
| 实现 `omo.paths.projection_path()` | 是 | 统一读取入口，fallback legacy |
| `system.yaml` 可重算字段拆分 | 否 | 作为 ADR-0130 跟踪 |
| gitignore 旧路径 | 否 | 等消费者全部迁移后再做 |

### 11.5 仍需后续 ADR 处理的问题

1. **`system.yaml` 拆分**：把 task counters、`health_score_ref`、`runtime_health_summary` 等可重算字段迁到 `.omo/state/runtime/system-projection.yaml`，让 `.omo/state/system.yaml` 只保留 phase/debt 指针。
2. **跨 worktree 锁**：当前 `fcntl_lock` 基于 `runtime/omo/_delivery/ingress/ingress.lock`，不同 worktree 不共享。建议把锁移到 `.git/omo-state.lock` 或明确每个 worktree 独立运行时状态。
3. **审计 artifact 归档**：`runtime/omo/` 下的 delivery artifact 被 gitignore，需要把关键 artifact 复制到 `.omo/_delivery/state-archive/` 或 CI 归档。
4. **fresh clone 生成契约**：明确 CI / Makefile / onboarding 文档中必须在读取前运行 `omo state sync`。

### 11.6 最终判断

- **ADR-0129 的目标（把可重算运行时投影与治理指针/人类文档解耦）是正确的。**
- **当前推荐的落点 `runtime/omo/state/` 不是最优**，因为它与 `.gitignore` 和 `AGENTS.md` 对 `runtime/` 的定义冲突，会把问题转化为新的边界混乱。
- **更优落点是 `.omo/state/runtime/`**，它不离 OMO state plane，lane 规则更内聚，迁移面更小。
- **必须同步修复 `change-lane-check.py` 的 `allowed_lanes` 优先级**，否则即使迁路径，`system.yaml` 残留和 workflow 声明仍会让 lane check 失败。
- **MVP 应收窄**：先迁 health/system_health/governance-data，保留 BRIEF.md 根入口，修复 lane check 和 registry；`system.yaml` 拆分和旧路径退役作为后续阶段。
