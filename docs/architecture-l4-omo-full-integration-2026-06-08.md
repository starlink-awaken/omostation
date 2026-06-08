# L4 Kernel · 全层 OMO 强制流程 + 项目入口协议

**2026-06-08 · 全面治理闭环 · L0-L4+I0+X1-X4 + 所有项目入口**

---

## 一、各层 OMO 强制规则

### 1.1 层级映射

```
层    项目         OMO Phase  OMO Task   OMO Debt   OMO Audit
───────────────────────────────────────────────────────────
L4    l4-kernel    ✅          ✅          ✅          ✅
L4    21域数据     —           ✅ (CARDS)  ✅ (CARDS)  ✅ (signals)
L3    cockpit      ✅          —           —           —
I0    agora        —           —           ✅ (circuit) ✅ (events)
L2    kairon       ✅          ✅          ✅          ✅
L2    omo          中枢        中枢        中枢        中枢
L2    metaos       ✅          —           ✅ (immune) ✅ (gate)
L2    gbrain       —           —           ✅          —
L1    runtime      —           —           ✅ (matrix) ✅ (KEI)
L0    ecos         —           —           ✅ (mof)    ✅ (SSB)
X1-X4 治理轴       ✅          ✅          ✅          ✅
```

### 1.2 每层强制规则

```
L4 · l4-kernel:
  - 域创建 → Phase milestone
  - Schema violation → Debt 注册
  - 新鲜度告警 → Debt 注册
  - 所有写操作 → Audit 记录
  - 信号 🔴 >48h → Debt 升级

L4 · 21域数据:
  - CARDS 状态变更 → Task 同步
  - 控制面修改 → signals 记录
  - STATUS ALERT → Debt 注册
  - 域迁移 → Phase milestone

L3 · cockpit:
  - research 执行 → Phase context 注入
  - health --full → 检查所有域 Debt
  - 所有写操作 → cards_check

I0 · agora:
  - 服务离线 → Debt 注册 (circuit open)
  - 服务注册/注销 → Audit 记录
  - 代理调用失败 → Debt 注册

L2 · kairon:
  - minerva 研究 → Task 跟踪
  - 知识摄入 → Audit 记录
  - 包更新 → Phase milestone

L2 · omo:
  - 治理中枢: Phase/Task/Debt/Audit 全部管理

L2 · metaos:
  - 决策门控 → Audit 记录
  - 免疫告警 → Debt 注册
  - Agent prompt → Phase context 注入

L1 · runtime:
  - 服务健康异常 → Debt 注册 (matrix)
  - KEI 拦截 → Audit 记录
  - cron 任务失败 → Debt 注册

L0 · ecos:
  - MOF 模型变更 → Audit 记录
  - M1 节点漂移 → Debt 注册
  - SSB 签名异常 → Debt 注册
  - L0-registry 变更 → Phase milestone
```

---

## 二、所有项目入口协议更新

### 2.1 需要更新的文件

```
项目          文件                    更新内容
─────────────────────────────────────────────────────────
workspace     AGENTS.md               OMO 强制流程声明
workspace     CLAUDE.md               OMO 强制流程声明
agora         CLAUDE.md               I0 层 OMO 规则
cockpit       CLAUDE.md               L3 层 OMO 规则
ecos          CLAUDE.md               L0 层 OMO 规则
kairon        CLAUDE.md               L2 层 OMO 规则
l4-kernel     CLAUDE.md               L4 层 OMO 规则
metaos        CLAUDE.md               L2 层 OMO 规则
omo           CLAUDE.md               治理中枢声明
runtime       CLAUDE.md               L1 层 OMO 规则
```

### 2.2 OMO 强制流程声明模板

每个项目的 CLAUDE.md 必须包含以下章节:

```markdown
## OMO 强制流程

本项目所有操作必须通过 OMO 治理机制:

### 操作前 (Pre-operation)
1. **Phase 检查**: 确认操作与当前 Phase 目标对齐
2. **CARDS 检查**: `cockpit cards --check` 确认无冲突
3. **约束检查**: 确认不违反 X1-X4 约束

### 操作后 (Post-operation)
1. **Audit 记录**: 所有变更写入 OMO Audit 日志
2. **Task 同步**: 如涉及 CARDS, 同步 Task 状态
3. **Debt 注册**: 如发现异常/违规, 注册 OMO Debt
4. **Signal 发射**: 通过 l4-kernel SignalBus 发射操作信号

### 违规处理
- Schema violation → 立即修复 + Debt 注册
- 新鲜度告警 → 48h 内响应
- 信号 🔴 → 立即响应 + Debt 注册
- CARDS 阻塞 → 升级优先级 + 通知相关域
```

---

## 三、实施

现在开始实施。先更新 AGENTS.md 和所有项目的 CLAUDE.md。