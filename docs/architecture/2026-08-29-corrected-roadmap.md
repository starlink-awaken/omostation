---
status: active
lifecycle: plan
owner: architecture-team
last-reviewed: 2026-08-29
---
# 架构演进全景规划 — 从基础设施到价值交付

> **日期**: 2026-08-29
> **立场**: 基于 Phase 1-3 后架构评估，修正路线从"继续加连接"转向"引真实负载"。
> **前序**: [`2026-08-29-post-phase3-architecture-review.md`](2026-08-29-post-phase3-architecture-review.md)

---

## 一、现状诊断

### 1.1 已完成（Phase 1-3）

| 能力 | 状态 | 实跑 |
|------|------|------|
| 决策收件箱 | ✅ 已建成 | 🟢 |
| 防腐 G1/G2 接线 | ✅ 已建成 | 🟢 |
| 场景卡升级 | ✅ 机制存在 | 🟡 |
| 场景→Journey | ✅ 接线器存在 | 🟡 |
| 价值→进化 | ✅ 接线器存在 | 🟡 |
| 日历信号路由 | ✅ 已建成 | 🟢 |
| 三桥连接 | ⚠️ 骨架存在 | 🔴 |
| 探测器心跳矩阵 | ✅ 已建成 | 🟢 |

### 1.2 核心问题

```
问题: 体系"治理极厚、价值极薄"
根因: 桥已建但无车可通，无真实用户任务流入
证据: 任务邮件率 0.14%, 场景卡 3/17 active, 进化 0 采纳
```

---

## 二、修正路线总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    4 段式演进路线 (8-10 周)                              │
│                                                                         │
│  Phase 0           Phase 1           Phase 2           Phase 3         │
│  减法清淤    →     引真实负载   →     桥通车     →     价值闭环       │
│  (1 周)            (2-3 周)          (3 周+)           (持续)         │
│                                                                         │
│  · dormant 扫除    · 日历信号        · 三桥合一        · 价值证明     │
│  · 三桥合一        · 场景卡激活      · 委托逻辑        · 自进化       │
│  · claims 清理     · journey 实弹    · 提案 triage     · 北极星       │
│  · 提案池清淤      · 北极星真指标    · Goal 模式                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 三、Phase 0：减法清淤（1 周）

### 3.1 目标

- script_baseline 从 531 降至 <500
- 消除 dormant 代码负债
- 清理过期 claims 和提案池

### 3.2 具体步骤

#### 3.2.1 Dormant 代码判定

| 模块 | 路径 | 判定标准 | 建议 |
|------|------|----------|------|
| Agent Cell×10 | `projects/agora/projects/agent-cell/` | 6 个月无激活？ | 归档 |
| planner/verifier | `projects/omo/src/omo/resident/` | 无调用方？ | 归档 |
| Goal-4X | `projects/omo/src/omo/resident/goal*.py` | 无引用？ | 归档 |
| 三桥脚手架 | `bin/gac/*-bridge.py` | 功能重叠？ | 合并为 bridge-runtime |

**验证**: `script_baseline` 下降计数

#### 3.2.2 过期 Claims 清理

```bash
# 93 个过期 active claims (冻结于 2026-08-18)
python3 bin/gac/swarm-discipline-cli.py claims-cleanup --older-than 7d
```

**验证**: `claims` 表 active 计数归零或显著下降

#### 3.2.3 提案池清淤

```bash
# 964 个提案做质量分层
python3 bin/bc-os/evolution-proposal-triage.py \
  --quality-threshold 0.6 \
  --archive-low-quality
```

**验证**: 提案池从 964 降至 <100 高质量提案

#### 3.2.4 三桥合一

**现状**: 3 个几乎相同的委托框架（kernel-bridge, model-ecos-bridge, l4-memory-bridge）

**合并方案**:

```python
# bin/gac/bridge-runtime.py (统一运行时)
class BridgeRuntime:
    """统一桥接运行时 — 替代三个脚手架桥"""

    BRIDGES = {
        "metaos-omo": {
            "description": "MetaOS ↔ OMO 主权委托",
            "delegable": ["audit_log", "gate_decision"],
        },
        "model-ecos": {
            "description": "Model-Driven ↔ ECOS MOF 同步",
            "delegable": ["stage_tracking", "mof_sync"],
        },
        "l4-memory": {
            "description": "L4 ↔ OMO/MOS 记忆层",
            "delegable": ["domain_registration", "content_archive"],
        },
    }
```

**验证**: 3 个文件 → 1 个文件，功能等价

---

## 四、Phase 1：引真实负载（2-3 周）

### 4.1 目标

- 真实任务信号 ≥1/周
- 场景卡 active 从 3 → 8
- Journey 实际执行 ≥1

### 4.2 具体步骤

#### 4.2.1 日历信号源接入

**为何先日历**: 本地可读、无单位网络依赖、个人/工作事件全覆盖

```python
# bin/bc-os/signal_router.py 扩展
class CalendarSource:
    """macOS 日历事件源"""

    def __init__(self):
        self.source_type = "calendar"
        self.priority = "P1"

    def fetch_events(self, since: datetime) -> list[dict]:
        """从 macOS Calendar.app 读取事件"""
        # 使用 osascript 或 icalendar 库
        pass

    def route(self, event: dict) -> str:
        """路由到对应场景"""
        title = event.get("title", "")
        if re.search(r"会议|meeting", title):
            return "meeting-supervision"
        elif re.search(r"deadline|截止", title):
            return "task-reminder"
        return "knowledge-ingest"
```

**验证**: 日历事件能触发场景路由

#### 4.2.2 场景卡激活

**当前**: 3 active / 17 total

**目标**: 8 active

| 优先级 | 场景卡 | 激活条件 |
|--------|--------|----------|
| P0 | admin-inbox | 已有 active，扩展至 unified-inbox |
| P0 | document-review | 公文审查需求进入收件箱 |
| P1 | meeting-supervision | 日历会议触发 |
| P1 | research-pipeline | 深度研究需求 |
| P1 | knowledge-curation | 知识沉淀需求 |

**验证**: `scene-card-lifecycle.py --report` active 计数

#### 4.2.3 Journey 实弹

**当前**: 1 active / 12 specs

**方案**:
1. 选 admin-inbox 对应的 `inbox-to-decision` journey
2. 手动触发首次执行（真实邮件或模拟）
3. 验证全链路：intake → review → deliver → close

**验证**: Journey 状态机完整走通 1 次

#### 4.2.4 北极星真指标接入

**当前**: B 轴 20/100（决策吞吐低）

**方案**:
- 工作交付：接入 mail-journey 产出
- 知识消费：接入 gbrain 查询计数
- 时间节省：接入执行日志的 est_minutes

**验证**: B 轴从 20 → ≥40

---

## 五、Phase 2：桥通车（3 周+）

### 5.1 目标

- 三桥合一后实现真实委托逻辑
- 提案采纳率 0 → 5（真提案口径）
- Goal 模式最小启动（1 轨道）

### 5.2 具体步骤

#### 5.2.1 统一 Bridge Runtime 实现

```python
# bin/gac/bridge-runtime.py
class BridgeRuntime:
    def delegate(self, bridge_id: str, function: str, *args, **kwargs):
        """统一委托入口"""
        bridge = self.BRIDGES.get(bridge_id)
        if not bridge:
            raise ValueError(f"Unknown bridge: {bridge_id}")
        if function not in bridge["delegable"]:
            raise ValueError(f"Function {function} not delegatable via {bridge_id}")

        # 实际委托逻辑
        if bridge_id == "metaos-omo":
            return self._delegate_to_omo(function, *args, **kwargs)
        elif bridge_id == "model-ecos":
            return self._delegate_to_ecos(function, *args, **kwargs)
        elif bridge_id == "l4-memory":
            return self._delegate_to_mos(function, *args, **kwargs)
```

**验证**: 真实调用成功（如 audit_log 写入 OMO）

#### 5.2.2 提案 Triage + BCOS 四阶段

**当前**: 964 提案，0 采纳

**方案**:
1. 质量分层：机器流水账归档，<100 真提案保留
2. BCOS 四阶段仅对保留提案运行
3. 首批 5 个高置信提案自动 approve

**验证**: adoption_count ≥ 5

#### 5.2.3 Goal 模式最小启动

**当前**: 6/6 heartbeat, 0 messages

**方案**:
1. 选 1 轨道（建议 T1-05 文档审查）
2. 配置 Goal agent profile
3. 通过 BET claim → verify → closeout 流程验证

**验证**: Goal agent 至少完成 1 个 BET 闭环

---

## 六、Phase 3：价值闭环（持续）

### 6.1 目标

- 北极星 composite_score ≥ 80
- 周任务处理量 ≥ 5
- 自进化提案采纳 ≥ 10%

### 6.2 具体步骤

#### 6.2.1 价值证明闭环

```
执行完成 → 自动记录 est_minutes → north_star B 轴更新
         → 价值报告 → weekly-review 卡片
         → 主人签核 → retro 沉淀
```

#### 6.2.2 自进化闭环

```
proposals → triage → BCOS 四阶段 → approve → 执行
         → 效果评估 → retro → 新 proposals
```

#### 6.2.3 持续迭代机制

| 周期 | 活动 | 输出 |
|------|------|------|
| 每日 | heartbeat 检查 | probe 报告 |
| 每周 | weekly-review | 价值报告 + 决策收件箱 |
| 每月 | 架构健康检查 | 评估报告 |
| 每季 | BET 复盘 | 台账更新 |

---

## 七、Phase 间衔接机制

### 7.1 Phase 0 → Phase 1

| 条件 | 检查 |
|------|------|
| script_baseline < 500 | `gac-validate.py --gate` |
| active claims = 0 | `swarm-discipline-cli.py claims-report` |
| 三桥合一完成 | `bridge-runtime.py --status` |
| 高质量提案 < 100 | `evolution-proposal-triage.py --count` |

### 7.2 Phase 1 → Phase 2

| 条件 | 检查 |
|------|------|
| 日历信号路由成功 | `signal_router.py --calendar test.ics` |
| 场景卡 active ≥ 8 | `scene-card-lifecycle.py --report` |
| Journey 执行 ≥ 1 | `journey-runner.py --status` |
| 北极星 B 轴 ≥ 40 | `north_star_meter_v3.py --json` |

### 7.3 Phase 2 → Phase 3

| 条件 | 检查 |
|------|------|
| 桥委托调用成功 | `bridge-runtime.py --delegate test` |
| 提案采纳 ≥ 5 | `evolution_engine.py --json` |
| Goal 模式 1 轨道完成 | `bet-ledger.py status` |

---

## 八、验证门控

### 8.1 每个 Phase 结束验证

| Phase | 验证项 | 通过标准 |
|-------|--------|----------|
| Phase 0 | 减法计数 | script_baseline ↓ 30+ |
| Phase 1 | 真实负载 | 任务信号 ≥1/周 |
| Phase 2 | 桥通车 | 委托调用成功 |
| Phase 3 | 价值证明 | B 轴 ≥ 40 |

### 8.2 每周健康检查

```bash
# 全量治理门禁
make gac-local-gate

# 北极星指标
python3 bin/bc-os/north_star_meter_v3.py --json

# 探测器心跳
python3 bin/gac/probe-heartbeat-monitor.py --status

# 防腐管道
python3 bin/gac/corrosion-pipeline-connector.py --dry-run
```

---

## 九、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 用户不参与签核 | 高 | Phase 1-3 全阻塞 | 异步批处理 + 超时自动升级 |
| 日历信号噪声大 | 中 | 场景误触发 | 白名单 + 置信度门控 |
| 三桥合一引入回归 | 中 | MetaOS/Model-Driven/L4 故障 | 保留原接口为 fallback |
| 真实任务量不足 | 高 | 进化引擎空转 | 手动注入种子任务 |

---

## 十、给用户确认的决策点

### 决策 1: Dormant 判定权

**问题**: Cell×10/planner/verifier/Goal-4X 按"6 个月激活计划"判定归档？

**选项**:
- A. 接受"无近期计划=先归档可快速恢复"
- B. 保留全部，等待自然激活
- C. 自定义判定标准

**建议**: A（减少表面积，归档可恢复）

### 决策 2: 三桥合并

**问题**: kernel-bridge / model-ecos-bridge / l4-memory-bridge 合并为统一 `bridge-runtime`？

**选项**:
- A. 接受合并（减少表面积，保留接口）
- B. 保留三个独立桥（职责清晰）
- C. 先保留，等 Phase 2 再决定

**建议**: A（三个几乎相同的框架是表面积负债）

### 决策 3: 信号源优先级

**问题**: 日历 (本地可读, 快) vs OA (单位网络, 价值高) 先接哪个？

**选项**:
- A. 日历优先（快速验证信号链路）
- B. OA 优先（价值更高）
- C. 并行推进

**建议**: A（快速验证，OA 依赖单位网络环境）

---

*文档生成: 2026-08-29 · 基于 Phase 1-3 后架构评估*
