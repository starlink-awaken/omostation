# P33 北极星 — 战役 2 起步 2 Domain（Memory + Governance）

> 2026-06-06 | 用户已审批 A1 方案
> 前置: P32 收官 (audit 100.0 A+ 极限, agora 12/12 满分级, ruff 0 errors)
> Phase 33 唯一的 P0 决策任务
> 历史北极星决策输入 / reference only。本文记录 P33 时点的域划分与起步判断，不是当前 BOS 域实现状态、当前健康分或当前审批结论 SSOT。
> 当前事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前治理审计与交付证据。

---

## 一、5 Domain 边界定义

5 Domain 是 BOS URI 命名空间的根目录, 对应"知、魂、行"三态映射到 5 个神圣领域。每个 Domain 在 `bos://` 之后占据第一段路径, 决定后续包归类与能力语义。

### 1. Memory（知 — 知识存储与摄取）

| 属性 | 内容 |
|------|------|
| 语义 | 知识图谱、向量存储、记忆摄取、检索 |
| 起步 kairon 包 | `kos`, `kronos` |
| 后做包 (W2) | `eidos` 的 schemas/校验部分 |
| 关键操作 | search / ingest / recall / vectorize / index |
| 价值 | omostation 知识脑 (gbrain + kos) 的 URI 抽象入口 |

### 2. Governance（魂 — 治理门控与协议）

| 属性 | 内容 |
|------|------|
| 语义 | 治理规则、门控、SSOT 协议、审批流 |
| 起步 kairon 包 | `omo`, `metaos`, `protocols-layer` (含 `sot-bridge` 的 `ssot`) |
| 后做包 (W2) | `engine-core` 的治理规则部分 |
| 关键操作 | audit / register / trigger / gate / validate / resolve |
| 价值 | 治理下沉到 URI 层, 大模型可语义寻址治理端点 |

### 3. Analysis（行 — 推演与研报）

| 属性 | 内容 |
|------|------|
| 语义 | 推演、研报、代码分析、智库 |
| 起步 kairon 包 | **W2 后做** |
| 后做包 | `minerva`, `ontoderive`, `codeanalyze`, `iris` |
| 关键操作 | derive / report / analyze / research |

### 4. Persona（魂 — 数字人与桥接）

| 属性 | 内容 |
|------|------|
| 语义 | 数字人、桥接外部 brain、人物画像 |
| 起步 kairon 包 | **W2 后做** |
| 后做包 | `sharedbrain-bridge`, `core-models`, `health-profile` |
| 关键操作 | bridge / profile / sync / persona |

### 5. Capability（行 — 工具与能力）

| 属性 | 内容 |
|------|------|
| 语义 | 工具市场、能力注册、运行时 |
| 起步 kairon 包 | **W2 后做** |
| 后做包 | `forge`, `agent-runtime` (在 `projects/runtime/`) |
| 关键操作 | execute / load / register / invoke |

### 为什么 W1 起步只做 2 个 Domain

| 理由 | 说明 |
|------|------|
| **可立刻注册** | kos/kronos/omo/metaos/protocols-layer 5 个包代码已稳定, 无需大规模重构 |
| **核心价值** | Memory + Governance 是 omostation 治理底座, 给"已有 19 活跃包"加 URI 抽象即可见价值 |
| **低风险** | 不动 agora 核心, 不改 agora-routes.json, 纯加 BOS 注册层 |
| **可验收** | 5 包注册 + 5 单测 + KOS 持久化 = 3-4 天可完成 |
| **可后扩** | 余 3 Domain 在 W2 走相同模板, 路径已清晰 |

---

## 二、BOS URI 命名约定

### 模式

```
bos://<domain>/<package>/<action>
```

### 三段式语义

| 段 | 取值 | 语义 |
|----|------|------|
| `domain` | `memory` / `governance` / `analysis` / `persona` / `capability` | 5 个固定, 决定命名空间 |
| `package` | kebab-case (小写 + 连字符) | 实际承载 URI 的 kairon 包, 与物理目录一致 |
| `action` | 动词 (search/ingest/register/...) | 具体端点能力, 通常与现有 CLI 子命令对齐 |

### 约束

- 域名空间: 5 个**固定不可扩展** (新能力归到已有 Domain, 不增加第 6 个)
- 包名: 必须 kebab-case (禁止 camelCase, snake_case, 大写)
- 动作: 动词优先, 名词只用于"实体列举类" (如 `list`, `get`, `describe`)
- 协议头: 严格 `bos://` 三字符, 禁止 `bos:` 双字符或 `b://`

### 起步 URI 清单 (W1 战役 2 必交付 5 条)

| URI | Domain | Package | Action | 对应能力 |
|-----|--------|---------|--------|----------|
| `bos://memory/kos/search` | memory | kos | search | 知识图谱检索 |
| `bos://memory/kronos/ingest` | memory | kronos | ingest | 记忆摄取 |
| `bos://governance/omo/audit` | governance | omo | audit | 治理审计 |
| `bos://governance/sot-bridge/register` | governance | sot-bridge | register | SSOT 注册 |
| `bos://governance/protocols-layer/trigger` | governance | protocols-layer | trigger | 协议触发器 |
| `bos://governance/metaos/gate` | governance | metaos | gate | 免疫门控 |

注: 起步 6 条覆盖 2 Domain 全部 5 个 kairon 包, 验收 5 条任一即可视为起步达标 (实际起算 5 包对应 5 条核心 URI, 第 6 条作为强化)。

### W2 扩展 URI 预览 (后做, 仅参考)

- `bos://analysis/minerva/research`
- `bos://analysis/codeanalyze/review`
- `bos://persona/sharedbrain-bridge/sync`
- `bos://capability/forge/execute`

---

## 三、为什么 Memory + Governance 起步

### 已有代码基

- **kos** (kairon/): 知识图谱检索 CLI 已稳定, 暴露 search 端点
- **kronos** (kairon/): 记忆摄取, 暴露 ingest 端点
- **omo** (kairon/omo): 治理 CLI (audit / register / gate 子命令已就绪)
- **metaos** (kairon/): 免疫门控, 暴露 gate 端点
- **protocols-layer** (含 sot-bridge ssot): 协议注册, 暴露 trigger / register 端点

### 风险曲线

| 风险维度 | W1 起步 | W2 余 3 Domain | 战役 1 动态注册 |
|----------|--------|---------------|----------------|
| 改 agora 核心 | 否 | 否 | **是** |
| 改 agora-routes.json | 否 | 否 | **是** |
| 引入新依赖 | 否 | 否 | **可能** |
| 重启 omo daemon | 否 | 否 | **是** |
| 健康分波动 | ±1 | ±2 | ±5 |

**W1 是 0 风险操作**, 仅在 omo `governance` CLI 加 `bos register` 子命令, KOS 新增 `zone=bos_registry` 索引。

### 业务耦合

- P32 audit 100.0 是当前极限, W1 不能回落
- agora 健康 12/12 满分级不能破坏
- ruff 0 errors 必须保持
- omo daemon 不能重启 (P32 已稳定运行)

---

## 四、实施优先级 (A1 方案)

| 阶段 | 战役 | 范围 | 估时 | 风险 | 状态 |
|------|------|------|------|------|------|
| **P33-W0** | 北极星 | 归档 + 本文档 | 1h | L0 | **当前 done** |
| **P33-W1** | 战役 2 起步 | **Memory + Governance** 2 Domain, 5 包注册 | 3-4 天 | L1 | 下一步 |
| **P33-W2** | 战役 2 余下 | Analysis + Persona + Capability 3 Domain | 5-7 天 | L1 | 后做 |
| **P33-W3** | 战役 1 | Agora Mesh 动态注册 (废硬编码 import) | 5-7 天 | L2 | P34+ 评估 |
| **P33-W4** | 战役 3 | Forge 集市 (market_load_tool) | 4-6 天 | L2 | P34+ 评估 |
| **P33-W5** | 验收 | 综合 audit + 健康分 ≥ 95 | 1 天 | L0 | 收官 |

### 战役 1 + 3 后置理由

| 战役 | 后置理由 |
|------|----------|
| 战役 1 (Agora 动态注册) | 需动 agora 核心, 风险 L2; W1 起步用静态声明 + KOS 索引可绕过动态注册 |
| 战役 3 (Forge 集市) | 需 marketplace 重启 + 大模型语义匹配, 风险 L2; 在 P34 评估与 WPS 集成一并做 |

### 与 P30-P32 关系

| 阶段 | 成果 | 与 P33 关系 |
|------|------|------------|
| P30 | 6 项目布局稳定 (kairon / gbrain / omo / metaos / cockpit / runtime) | 物理层已就位, P33 加协议层 |
| P31 | 3 组合并后 kairon 19 活跃包 | P33 给"19 包"加 URI 抽象, 不破坏合并成果 |
| P32 | audit 100.0, agora 12/12 满分级 | P33 起步不破坏 P32 极限 |

**关键不变量**: P33 战役 2 是"加法", 不动现状, 不破坏 P32 极限。

---

## 五、W1 战役 2 起步验收标准

### 8 条 Checklist (全部必须通过)

- [ ] **5 kairon 包注册 BOS URI**: `kos` / `kronos` / `omo` / `metaos` / `protocols-layer` 至少各 1 条
- [ ] **命名约定严格**: 全部 URI 符合 `bos://<domain>/<package>/<action>` 形式, kebab-case
- [ ] **omo CLI 注册命令**: 每个 URI 在 omo `governance` CLI 有 `omo bos register <uri>` 对应
- [ ] **持久化到 KOS**: 注册记录写到 KOS `zone=bos_registry` (可用 `kos query --zone bos_registry` 查)
- [ ] **单元测试 ≥ 5 个**: 每 Domain 至少 1 个, 覆盖 URI 解析 + 注册 + 查询
- [ ] **ruff 0 errors**: 全 kairon + agora + omo 包 ruff check 通过
- [ ] **audit 总分 ≥ 95**: 7 项检查总分不破 95 (P32 100.0 是上限, W1 不强求 100)
- [ ] **omo daemon 仍跑**: `launchctl list | grep com.omo.governance.daemon` 有 PID, 不重启

### 验收执行命令

```bash
# 1. 5 包 URI 计数
grep -r "bos://" /Users/xiamingxing/Workspace/projects/kairon/{kos,kronos,omo,metaos,protocols-layer}/ --include="*.py" | wc -l
# 应 >= 5

# 2. URI 命名规范
grep -rohE "bos://[a-z]+/[a-z][a-z0-9-]*/[a-z][a-z0-9-]*" /Users/xiamingxing/Workspace/projects/kairon/ | sort -u
# 应至少 5 条规范化 URI

# 3. omo bos register CLI 存在
ls /Users/xiamingxing/Workspace/projects/kairon/omo/src/omo/ | grep bos

# 4. KOS 持久化
python3 -c "from kos import registry; print(len([r for r in registry.query(zone='bos_registry')]))"
# 应 >= 5

# 5. 单测通过
cd /Users/xiamingxing/Workspace/projects/kairon && make test-fast 2>&1 | tail -5
# 应 0 failed

# 6. ruff 0
cd /Users/xiamingxing/Workspace/projects/kairon && ruff check . 2>&1 | tail -3
# 应 "All checks passed!"

# 7. audit 总分
python3 /Users/xiamingxing/Workspace/.omo/_delivery/governance-audit.py 2>&1 | tail -3
# 应 >= 95

# 8. omo daemon
launchctl list | grep com.omo.governance.daemon
# 应有 PID 行
```

---

## 六、不做的事 (W1 范围外)

| 不做项 | 理由 | 何时做 |
|--------|------|--------|
| agora Mesh 动态注册 | 改 agora 核心, 风险 L2 | 战役 1 (P34+ 评估) |
| forge 集市 | 需 marketplace 重启 | 战役 3 (P34+ 评估) |
| 修改 agora-routes.json | 起步阶段静态声明已够 | 战役 1 时统一改 |
| 改 agora 核心代码 | 0 容忍破坏 P32 极限 | 战役 1 才允许 |
| 重启 omo daemon | 验收标准第 8 条明令禁止 | 战役 1 才允许 |
| 新增 kairon 包 | 起步只加 URI 抽象 | W2+ 评估 |
| W2 三 Domain (Analysis/Persona/Capability) | 模板待 W1 验证后复用 | P33-W2 |
| X 侧链 + L0 锚定 (战役 4) | 待 P33 全部战役完成再启动 | P34+ |

---

## 七、与 P30-P32 关系

### 物理层就位 (P30 收官)

- 6 项目布局: kairon / gbrain / omo / metaos / cockpit / runtime
- L0-L4 物理拆包, X1-X3 跨切面已分

### 协议层就位 (P32 收官)

- agora 健康 12/12 满分级
- audit 100.0 (A+ 极限)
- ruff 0 errors
- 280 ruff errors 已归零 (P32-W1-RUFF-CLEANUP)
- 39 missing deliverables 已修正 (P32-W0-DELIVERABLES)
- 30 smoke test 已补 (P32-W0-SMOKE)

### 抽象层启动 (P33 战役 2)

- **加法操作**: 给 5 个 kairon 包 (kos/kronos/omo/metaos/protocols-layer) 加 BOS URI 抽象
- **不破坏现状**: 不改合并成果, 不动 agora 核心, 不重启 daemon
- **可回滚**: URI 注册在 KOS `bos_registry` zone, 一键 `omo bos deregister` 回滚

### P30→P31→P32→P33 演进曲线

```
P30: 物理拆包 (6 项目 + L0-L4)
     ↓
P31: 3 组合并 (kairon 19 活跃包)
     ↓
P32: 治理下沉 (audit 100.0, agora 12/12, ruff 0)
     ↓
P33: 协议抽象 (BOS URI + 5 Domain) ← 当前
     ↓
P34: 动态织层 (Agora Mesh) + 集市 (Forge)
```

---

## 参考

- [plan-phase33-bos-mesh-unification.md](./plan-phase33-bos-mesh-unification.md) — P33 整体战役规划
- [retrospective-2026-06-07-p32.md](./retrospective-2026-06-07-p32.md) — P32 收官复盘
- [5+3+1-layer-deep-architecture.md](./5+3+1-layer-deep-architecture.md) — 模块级精度架构
- ADR-0005 (kairon governance) — kairon 治理铁律
- ADR-0006 (kairon package merge) — kairon 合并策略

---

> 文档创建于 2026-06-06, 由 omostation 北极星撰写工程师生成
> 用户审批 A1 方案, 战役 2 起步 2 Domain
> 命名约定: `bos://<domain>/<package>/<action>` (kebab-case)
> 下一步: P33-W1-CAMPAIGN-2-PRECHECK
