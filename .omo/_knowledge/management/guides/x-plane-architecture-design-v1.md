---
category: guides
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: x-plane-architecture-design-v1.md
deprecated-since: 2026-06-23

---

# X-Plane 治理控制平面架构设计 (X-Plane Governance Control Plane)

> **定位**: Phase 28 地基蓝图 · 2026-06-08 起草 · 解决 X1-X4 散落失控问题
> **承载决策**: 强化 **omo**(治理面 L2)为 X-Plane 控制面,**metaos**(编排面 L2)为执行面 —— **不新建项目**
> **与现有文档关系** (SSOT 指针,不复制):
> - 原则定义 → `LAYER-INDEX.md` §X1-X4
> - 实现注册(待升级) → `x-axis-implementation-registry.md`
> - 整合现状(aspirational) → `x-axis-consolidation-v1.md`
> - 强制五层防线(偏 X4) → `governance-enforcement-v1.md`
> - 一致性检查 → `x4-governance-consistency-design.md`
> **属性**: 历史控制平面设计提案 / reference only，不是当前 X1-X4 实装状态、当前健康分构成或当前控制面执行真相 SSOT。
> **当前事实**: 请回看 `/.omo/standards/omo-governance-surfaces.md`、`/.omo/state/system.yaml`、`/.omo/_truth/` 与当前治理检查结果。

---

## §1 问题陈述:声明与现实的分裂

### 1.1 活体标本:同一天的两套账本

| 来源(均 2026-06-06) | 对 X1/X2/X3 的陈述 |
|---|---|
| `x-axis-consolidation-v1.md` | X1 实现率 **100%** · X2 **100%** · KEI 沙箱"✅ 文件/网络/子进程拦截" · 审计"✅ JSONL" |
| `.omo/state/system.yaml`(blockers) | `X1-SANDBOX_INERT`(audit hook 从未激活) · `P2-KEI_AUDIT_EMPTY`(记录静默丢弃) · `X2-NO_FRESHNESS` · `X3-NO_COSTING`(零实现) |

同一天、对同一批机制,给出了完全矛盾的两套现实。`consolidation` 是"希望态(aspirational)",`system.yaml` 是"实际态(actual)",**两者之间没有任何自动校验把它们钉在一起**。

### 1.2 根因(三层)

1. **声明式治理的天花板**:核心治理权威是 markdown(registry / charter / consolidation)。markdown 既会漂移(不是事实)又不能执行(无法强制),违背 SSOT 铁律"事实只有一个权威位置"。
2. **五层防线结构性只服务 X4**:`governance-enforcement-v1.md` 的五层防线(CLAUDE.md §0 / CI / cards_check / 周常 health / Phase gate)检查的全是接口/端口/依赖/合规/Phase score —— **全部是 X4(静态一致性)范畴**。X1/X2/X3 这三个**需要运行时存在**的切面,从未接入强制体系。
3. **健康分与真相脱钩**:`health_score=100` 只算"测试通过率(产物质量)",不算"治理机制是否在运行(过程有效性)"。引擎在烧,仪表盘绿灯。

### 1.3 失控判定

散落实现 + markdown 注册表 + 无单一 owner + 强制体系只覆盖 X4 —— 在此模式下,声明与现实的漂移**无人察觉、无人负责、无法阻断**。失控不是风险,是数学必然,且**已经发生**(system.yaml 的 X1/X2/X3 blockers 即证据)。

---

## §2 设计目标与非目标

### 2.1 目标

| # | 目标 | 验收 |
|---|---|---|
| G1 | 让失控**可见** | 真实 X 分数进 `health_score`,僵尸机制当场暴露为 DEAD |
| G2 | 让失控**可控** | 新机制不注册→CI RED;声明与探活漂移→自动 drift 报告 |
| G3 | 单一 owner | omo 正式 own X 轴的注册/聚合/强制/演进 |
| G4 | 复用而非重造 | 站在五层防线上**只补运行时探活层**;收编现有 `omo_audit`/`omo_cost`/`omo_health` |

### 2.2 非目标(明确不做,YAGNI)

- ❌ 不新建独立 X 轴项目(缺的是 owner+强制+可观测,不是项目)
- ❌ 不把 X 机制实现集中(X1 沙箱必须在 runtime 进程内,X4 检查必须在 CI;实现保持分布/就近)
- ❌ 不推翻五层防线(它对 X4 有效,只补它缺的那层)

---

## §3 核心架构:Control / Data Plane 分离 + 探活层

```
┌──────────── X-Plane 控制面 @ omo (单一 owner) ────────────────────────┐
│  omo_xplane.py 门面:                                                  │
│    register()  机器可读注册(YAML 契约,替代 markdown)               │
│    probe_all() 运行时探活 ← ★ 新增的第六层防线                        │
│    aggregate() 聚合 X1-X4 真实分数(收编 omo_audit/omo_cost/omo_health)│
│    enforce()   CI + Phase gate 强制                                    │
│    audit_drift() 声明 vs 探活漂移检测(演进/反熵)                    │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ 标准探针契约 (XProbeResult)
        ┌────────────────────────┼─────────────────────────┐
   Data Plane(实现保持分布 · 就近最优 · 每机制暴露 probe)
   X1@runtime沙箱   X2@runtime健康   X3@llm-gateway成本   X4@CI/scripts
                                 │
                                 ▼ 运行时强制
┌──────────── X-Plane 执行面 @ metaos ──────────────────────────────────┐
│  l2_controller / 免疫监控 接入:预算熔断(X3)· 沙箱 inert 告警(X1) │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.1 防线全景:补齐第六层

| 防线 | 触发 | 阻断力 | 覆盖(现状) | X-Plane 后 |
|---|---|---|---|---|
| L0 CLAUDE.md §0 | Agent 启动 | 软 | X4 | X4 |
| L1 CI scripts | git push | 硬 | X4 | X4 + **新机制未注册 RED** |
| L2 cards_check | 操作前 | 中 | X4 | X4 |
| L3 周常 health | cron | 软 | X4 | X4 |
| L4 Phase gate | Phase 末 | 硬 | X4 score | **min(X1..X4) score** |
| **L5 运行时探活** ★新增 | probe 周期 | 中→硬 | **X1/X2/X3** | **X1/X2/X3 真实存活** |

**核心增量一句话**:五层防线给 X4(静态一致性)用,X-Plane 补的 L5 探活层给 X1/X2/X3(运行时存在)用。

---

## §4 关键设计① 机器可读注册表(替代 markdown)

**位置**: `protocols/x-axis-registry.yaml`(L0 协议层,SSOT 唯一权威)
**作废**: `x-axis-implementation-registry.md` 降级为"人类可读视图",由 YAML 自动生成,**不再手工维护**。

```yaml
# protocols/x-axis-registry.yaml
version: 2
mechanisms:
  - id: X1/K1
    axis: X1
    name: KEI 安全沙箱
    owner: runtime
    impl: projects/runtime/.../kei_sandbox.py
    probe:
      kind: counter            # command|http|jsonl_freshness|counter
      run: "uv run --package runtime python -m runtime.kei_probe --count-24h"
      expect: ">0"             # 24h 捕获事件数为 0 → DEAD
      timeout_s: 5
    sla: { max_silence_h: 1 }
    blocks: "X1 score < 80 → Phase gate 阻断"

  - id: X1/K2
    axis: X1
    name: KEI 审计日志
    owner: runtime
    impl: runtime/data/kei_audit.jsonl
    probe:
      kind: jsonl_freshness    # 检查最后一条记录时间戳
      path: "~/.runtime/data/kei_audit.jsonl"
      expect: "last_record_age < max_silence_h"   # 文件空或陈旧 → DEAD
    sla: { max_silence_h: 24 }
    blocks: "X1 score 扣分"
```

**probe.kind 四型探活**(对症四种僵尸):
| kind | 探活方式 | 专治 |
|---|---|---|
| `command` | 跑命令,exit 0 = alive | 沙箱是否真注册了 hook |
| `http` | 打健康端点 | 服务是否真在监听 |
| `jsonl_freshness` | 查日志最后记录时间戳 | `KEI_AUDIT_EMPTY`(空/陈旧→DEAD) |
| `counter` | 读计数器(如 24h 事件数) | `SANDBOX_INERT`(0 事件→DEAD) |

---

## §5 关键设计② Probe 探针契约(灵魂)

每个 X 机制必须回答三问:**我在吗?(alive)我健康吗?(healthy)证据呢?(evidence)**

```python
@dataclass
class XProbeResult:
    mechanism_id: str          # "X1/K1"
    status: str                # GREEN | YELLOW | RED | DEAD
    alive: bool                # 机制是否真在运行(不是代码是否存在)
    evidence: dict             # {type, value, observed_at} —— 证据,非声明
    last_active: str | None    # 最后一次真实活动时间戳
    detail: str                # "audit hook registered, 1432 events/24h"
```

**`status=DEAD` 是本设计的核心武器**:专为"声明存在但实际 inert"而生。
注册表说有 → probe 探不到活动证据 → **DEAD**。这一个状态当场抓出 `X1-SANDBOX_INERT`、`P2-KEI_AUDIT_EMPTY` 这类僵尸——**不再靠人某天偶然翻 system.yaml 才发现**。

| status | 含义 |
|---|---|
| GREEN | 在运行 + 有新鲜活动证据 |
| YELLOW | 在运行但接近 SLA 边界(如 silence 接近 max) |
| RED | 探活失败/报错(机制坏了) |
| **DEAD** | 注册表声明存在,但探不到任何活动证据(声明/现实分裂) |

---

## §6 关键设计③ omo_xplane 门面模块

**位置**: `projects/omo/src/omo/omo_xplane.py`
**原则**: 门面(facade),**收编**现有散落件,不重写。

```python
class XPlane:
    """X 轴治理控制面。omo 作为单一 owner。"""

    def register(self, m: XMechanism) -> None:
        """注册机制 → 写 protocols/x-axis-registry.yaml。重复/无 probe → 拒绝。"""

    def probe_all(self) -> dict[str, XProbeResult]:
        """L5 探活层:遍历注册表,逐机制执行 probe。★新增能力。"""

    def aggregate(self) -> XScore:
        """聚合 X1-X4 真实分数。收编:
           X1 ← omo_audit.summary() + probe(沙箱/审计)
           X2 ← omo_health + probe(freshness)
           X3 ← omo_cost(llm_cost.jsonl) + probe(预算)
           X4 ← 现有 scripts/check-*.py(复用,不动)
        """

    def enforce(self, context: str) -> list[Violation]:
        """CI / Phase gate 调用。未注册机制、DEAD 机制、score 不达标 → Violation。"""

    def audit_drift(self) -> list[Drift]:
        """反熵:对比注册表声明 status vs probe 实际 status。
           不一致 → Drift → 自动 omo debt register(标 X2 保鲜维度)。
           ★ 这是防止'consolidation 100% vs system.yaml inert'再次发生的根本机制。
        """
```

**收编映射**(DRY,现有件各归其位):
| 现有件 | 归入 |
|---|---|
| `omo_audit.py`(record/query/summary + run_governance_audit 6 检查) | X1 聚合源 |
| `omo_cost.py`(llm_cost.jsonl 解析) | X3 聚合源 |
| `omo_health.py` / `omo_metrics.py` | X2 聚合源 |
| `scripts/check-interfaces.py` / `check-cross-deps.py` | X4 聚合源(原地复用) |

---

## §7 关键设计④ 真实 X 分数进 health_score(戳破 100)

**接入点**: `omo_state.py` / `omo_state_schema.py` / `scripts/sync_omo_state.py`(现 health_score 计算源)。

```python
# 改造前: health_score 仅反映测试通过率(产物质量)
# 改造后:
health_score = w_quality * quality_score + w_xplane * xplane_score

xplane_score = min(X1, X2, X3, X4)   # ★ 取短板,不取平均
```

**为什么 min 不 avg**:木桶效应。X3=0 时,avg 仍有 ~70 继续骗人;**取 min,X3=0 则 xplane_score=0,health_score 当场从 100 跌穿**,假象立破。这是 G1(让失控可见)的硬指标。

---

## §8 metaos 执行面:运行时熔断

metaos(编排面)的 `l2_controller` / 免疫监控接入 X-Plane,把"检查"升级为"运行时强制":

| 切面 | 运行时动作 |
|---|---|
| X3 预算 | Agent 累计成本超配额 → metaos 熔断该 Agent 的 LLM 调用 |
| X1 安全 | probe 报沙箱 DEAD → metaos 拒绝调度需沙箱的高危 KEI 任务 + 告警 |
| X2 保鲜 | 服务 silence 超 SLA → metaos 触发 autoheal 或降级 |

---

## §9 三档演进路线图

| | 档位① 止血 MVP(~1周) | 档位② 控制平面(~1月) | 档位③ 治理内核(季度,Phase 28+) |
|---|---|---|---|
| 注册表 | markdown→`x-axis-registry.yaml` + probe 字段 | 同① + CI 校验未注册机制 | 同② |
| 探活 | 写 `omo x-axis check` 聚合器跑一遍 | `omo_xplane.probe_all()` 周期化 | 探活即内核心跳 |
| 强制 | — | enforce() 接 CI + Phase gate | metaos 运行时熔断 |
| 可见 | X1/X2/X3 真相暴露到报告 | xplane_score 进 health_score | 蜂群级 X 仪表盘 |
| 演进 | 人工跑 | audit_drift() 自动 debt | 内核自愈 |
| **戳破的痛点** | 让失控**可见** | 让失控**可控** | 让失控**不可能** |
| ROI | 🔥🔥🔥 | 🔥🔥 | 🔥 战略 |

**强烈建议先做档位①**:投入最小,价值最大——把会骗人的 markdown 换成能跑的 YAML+探针,100 分仪表盘当场现原形。先让病灶可见,才谈得上治。

---

## §10 最终态愿景:X-Plane = 操作系统的内核态

omostation 自称 **Personal AI Operating System / 蜂群网络(Phase 27)**。用 OS 的眼光看:

```
   业务态(用户态)     kairon 25包 · gbrain 记忆 · 各业务 Agent
 ───────────────────────────────────────────────────────────────
   X-Plane(内核态)    X1=安全内核  X2=调度&自愈  X3=资源配额  X4=系统调用契约
```

一个没有内核态的 OS 跑不起来。当前内核态 X1 半死、X2 没有、X3 是零 = **没有权限管理、没有进程调度、没有内存配额的 OS**,单机看不出,**上蜂群(多 Agent 并发)立刻雪崩**:
- Agent 越多,X1 必须从"检查"变"运行时强制",否则裸奔
- 全局自愈(X2)需要全局状态感知,散落健康检查撑不起
- 成本(X3)在并发下指数爆炸,无预算熔断 = 烧钱无底洞

按 Meadows 杠杆点,X-Plane 处于"系统规则层",比调参数高数个量级;蜂群规模越大,这块地基杠杆越大。**X-Plane 不是锦上添花,是 Phase 28 必须补的地基。**

---

## §11 风险与权衡

| 风险 | 缓解 |
|---|---|
| omo 职责膨胀(已是大模块) | omo_xplane 仅做门面/聚合,实现仍在各 Data Plane;必要时拆 omo-xplane 子包 |
| probe 自身成为新的维护负担 | probe 是声明式 YAML + 四种通用 kind,新机制填表即可,无需写代码 |
| 取 min 导致 health_score 长期低分,打击士气 | 这是**特性不是 bug**——真实分数才有改进动力;可同时展示 quality/xplane 双轨 |
| probe 周期开销 | 探活轻量(读日志尾/计数器/exit code),周期可配(CI 时 + 周常 cron) |

---

## §12 落地清单(档位①,可直接执行)

1. 建 `protocols/x-axis-registry.yaml`,迁移现有 20 项,逐项补 `probe` 字段
2. 为 X1/X2/X3 僵疑机制写最小 probe:`kei_probe`(counter)、audit jsonl_freshness、cost counter
3. 写 `omo x-axis check` CLI:跑 probe_all + 打印 X1-X4 真实 status 表(含 DEAD 标红)
4. 把真实结果回填 `system.yaml`,核对与 `consolidation-v1.md` 的差距(预期大量 DEAD)
5. `x-axis-implementation-registry.md` 顶部加指针:实现以 YAML 为准,本文降级为生成视图

---

*起草: 2026-06-08 · 承载: omo(控制面) + metaos(执行面) · 不新建项目 · 待人类确认落地档位*
