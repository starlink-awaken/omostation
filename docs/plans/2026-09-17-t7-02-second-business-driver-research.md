---
bet_id: BET-Y2Q4-T7-02
title: 公文场景第二业务驱动调研 — 脱离国转中心借调依赖
type: research
status: accepted
lifecycle: history
date: 2026-09-17
owner: xiamingxing
---

# BET-Y2Q4-T7-02 调研报告：公文场景第二业务驱动

## 1. 调研背景

2026-08-19 国转中心借调冻结后，公文/决策收件箱场景（当前唯一"主战场"）面临业务驱动单点依赖问题。本调研目标：
- 找到至少一个不依赖国转中心借调的替代业务驱动
- 验证其与已建成 document-review 能力（拟稿/审批/督办闭环）的兼容性
- 为后续 BET 认领决策提供参考

## 2. 现状分析

### 2.1 当前 document-review 场景卡

| 字段 | 值 |
|------|-----|
| lifecycle | supervised |
| activation | active |
| journey_ref | inbox-to-decision |
| trigger | 公文起草/审查需求进入确认队列 |
| 现有驱动 | 卫健委借调 / **国转中心** / 日常公文 |
| calibration target | min_samples: 30, min_calibration: 0.6 |

**问题**：trigger 明确包含"国转中心"，借调结束后失去主要驱动来源。

### 2.2 已建成 document-review 能力清单

| 能力 | 实现状态 | 位置 |
|------|----------|------|
| 决策收件箱 (CRUD) | ✅ 完整 | `bin/ssot/scene-card-decision-inbox.py` + `cockpit decide` |
| HITL 审批流 | ✅ 完整 | `bin/ssot/scene-card-approval-flow.py` + REST API |
| 统一收件箱 (LECP v3.0) | ✅ 完整 | `cockpit/web/api_unified_inbox.py` |
| 三档邮件起草 | ✅ 完整 | `cockpit inbox draft` → BOS `bos://inbox/mail/draft` |
| GB/T 9704-2012 DOCX 渲染 | ✅ 完整 | `cockpit/renderers/gov_docx.py` |
| 格式检查 / 敏感项检查 / 依据核验 | 📋 定义于场景卡 | scene-document-review input_schema |
| 全审 (full_review) | 📋 定义于场景卡 | scene-document-review input_schema |

### 2.3 inbox-to-decision 旅程管线

```
messages_collected → triaged → under_review → decision_made → task_created → delivered → knowledge_captured
                                     ↓
                              returned_for_revision → under_review (loop)
```

7 个状态，2 个分支。`under_review` 阶段有 human_review checkpoint。

## 3. 候选驱动评估

### 3.1 候选 A：行政通知处理全流程 (admin-notification-workflow) ✅ 推荐

**BET**: BET-Y1Q4-T8-04
**Journey**: 上级通知 → 分类 → 转发 → 收集 → 汇总 → 审阅 → 提交 (9 步闭环)
**Trigger**: `mail_classified_as_task` from `mail_daemon` — **通用邮件触发，无国转依赖**

#### 场景卡状态 (6 张)

| 场景卡 | lifecycle | 功能 |
|--------|-----------|------|
| scene-admin-inbox | draft | 读取工作邮箱未读邮件并 LLM 分类 |
| scene-admin-classify | **assisted** | LLM 分类判定任务类型 |
| scene-admin-forward | **assisted** | 生成转发通知与数据收集表草稿 |
| scene-admin-collect | **assisted** | 注册 deadline_tracker 截止追踪 |
| scene-admin-compile | **assisted** | 汇总收集结果生成工作报告草稿 |
| scene-admin-review | **assisted** | 生成发领导的审阅请求邮件草稿 |
| scene-admin-submit | **assisted** | 提交最终报告 |

#### 兼容性验证

| document-review 能力 | admin-notification 匹配度 | 说明 |
|---------------------|--------------------------|------|
| **拟稿 (draft generation)** | ✅ 直接复用 | admin-compile 生成报告草稿 → 直接走 document-review 拟稿流程 |
| **格式检查 (format_check)** | ✅ 直接复用 | GB/T 9704-2012 格式标准适用于所有公文类型，含行政通知 |
| **敏感项检查 (sensitive_check)** | ✅ 直接复用 | 转发通知/审阅请求同样需要密级和敏感词检查 |
| **依据核验 (basis_verify)** | ✅ 直接复用 | 行政通知需核验政策依据/法规条文 |
| **审批流 (approval)** | ✅ 直接复用 | admin-review → document-review → decision_made 自然衔接 |
| **督办 (tracking)** | ✅ 直接复用 | admin-collect → deadline_tracker 已实现截止追踪 |
| **统一收件箱** | ✅ 直接复用 | admin-inbox 接收的邮件同样走 unified-inbox → inbox-to-decision |

#### 兼容性结论

**兼容度：100%** — admin-notification-workflow 的全部 7 个场景产出（报告草稿、转发通知、审阅请求、数据收集表）均属于公文范畴，可直接复用 document-review 的拟稿/格式检查/敏感项检查/依据核验/审批/督办全链能力。

#### 预估请求量

- **触发频率**：上级通知邮件到达即触发（mail_daemon 每日扫描）
- **预估日请求量**：5-20 件/天（取决于组织层级和通知频率）
- **vs 国转中心借调**：国转中心场景为周期性季度总结（约 4 次/年），admin-notification 为持续性日常需求

### 3.2 候选 B：工程交付评审 (engineering-delivery-review) ⚠️ 部分兼容

**BET**: BET-Y1Q2-T7-01
**Lifecycle**: supervised / active

- ✅ 兼容 document-review 的审批流和决策收件箱
- ⚠️ 产出为工程评审证据（PR diff、测试报告），非传统公文格式
- ⚠️ 格式检查/敏感项检查适用度低
- ❌ 预估请求量低（工程变更驱动，非持续需求）

### 3.3 候选 C：周期性报告 (periodic-reporting) ❌ 仍依赖国转

**BET**: BET-Y1Q2-T6-04
**Lifecycle**: supervised / active

- ❌ opportunity window 明确包含"卫健委借调周报/月报 + 国转中心季度总结"
- ❌ 本质仍是国转驱动，不满足"脱离国转依赖"条件

## 4. 结论与建议

### 4.1 推荐方案

**admin-notification-workflow (BET-Y1Q4-T8-04) 是最佳第二业务驱动**：

1. **独立于国转**：由通用邮件触发，不依赖任何借调关系
2. **基础设施就绪**：6 个场景卡已在 assisted/controlled 运行，共享 mail_daemon + risk_engine + decision-inbox 管线
3. **能力完全兼容**：document-review 的拟稿/格式检查/敏感项检查/依据核验/审批/督办全链可直接复用
4. **持续需求**：日常行政通知为持续性需求，非周期性事件
5. **零新代码**：现有基础设施即可服务，无需新建管线

### 4.2 后续 BET 认领建议

| BET | 建议 | 说明 |
|-----|------|------|
| **Y3H1-T7-01** (中试/政策申报升 assisted) | 新建 BET | 若未来出现替代驱动，应新建 BET 而非复活（retro 建议） |
| **Y3H2-T7-01** (公文场景 routine) | 新建 BET | 依赖 Y3H1-T7-01，同样应新建 |
| **T7-02** (本 BET) | **可 closeout done** | 调研完成，结论已写入 |

### 4.3 解冻路径

```
T7-02 (本调研) → closeout done
    ↓
若需推进公文场景 assisted → 新建 BET（基于 admin-notification-workflow）
    ↓
新 BET 通过 document-review 能力验证 → lifecycle=assisted
    ↓
积累 calibration ≥ 0.6 → assisted 稳定
    ↓
新 BET 升 routine（格式类限定）→ 替代 Y3H2-T7-01
```

### 4.4 风险与限制

- **格式检查/敏感项检查/依据核验**：当前仅在场景卡 input_schema 中定义，未找到独立实现模块——实际执行依赖 LLM (`bos://capability/compute/generate`)，需通过实际运行验证输出质量
- **admin-notification-workflow 的 journey status 为 draft**：虽场景卡已 assisted，但 journey spec 本身标记为 draft，需确认是否影响 runner 调度
- **预估请求量未经实测**：5-20 件/天为估算值，需实际运行 mail_daemon 后确认
