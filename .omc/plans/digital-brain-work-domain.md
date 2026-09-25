---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---
type: ssot

# 数字大脑 — 工作域邮件Agent全链路方案

> 创建: 2026-08-09 | 基于: 数字大脑愿景审查 + 技术验证
> 范围: 工作域邮件感知→理解→规划→执行→追踪 完整9步闭环
> 前置: 基础设施已就绪 (agent host + AetherForge LLM + scene/journey 框架)

---

## Context

用户的"数字大脑"愿景：常驻 agent 基于心智模型和 LifeOS，主动管理工作/家庭/健康/教育全生活域。
当前系统基础设施层 ~70% 就绪（agent框架、LLM算力、治理、场景/旅程），但应用层 ~5%（零个生活域 agent 在工作）。

本方案聚焦**工作域邮件 agent**——第一个打通的"肌肉"层。从邮件感知到任务执行的全链路，验证"数字大脑"概念。

### 技术验证结论

| 信号源 | 可读? | 数据量 | 读取方式 |
|--------|-------|--------|---------|
| Apple Mail | ✅ | 66,772封 | SQLite `Envelope Index` (subjects/addresses/messages) + .emlx 文件 |
| 网易邮箱大师 (工作) | ✅ | 239封 + 313附件 | `mail.db` (MailMeta) + `content.db` (MailContent, 纯文本可读) + `search.db` (FTS) |
| 网易邮箱大师 (个人) | ✅ | 3个账户 | 同上，不同 DataPath |

工作邮箱 `ws-xxk@bjfsh.gov.cn` 实测样本：`"市返回数据 请阅附件 谢谢"` — 纯文本，可直接 LLM 处理。

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    数字大脑 — 工作域架构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── 感知层 (Perception) ──────────────────────────────────┐  │
│  │  mail-reader.py                                           │  │
│  │  ├─ AppleMailReader: SQLite subjects + addresses + emlx  │  │
│  │  ├─ NetEaseReader: mail.db + content.db + search.db      │  │
│  │  └─ 统一格式: {source, subject, from, to, date, body,    │  │
│  │                attachments, unread, account}              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌─── 认知层 (Cognition) ───────────────────────────────────┐  │
│  │  mail-agent.py                                            │  │
│  │  ├─ LLM 分类: 通知/任务/参考/垃圾/个人 (AetherForge)     │  │
│  │  ├─ 任务提取: 截止时间/责任人/所需动作/优先级            │  │
│  │  ├─ 日报生成: "今日3封需处理" + LLM 摘要 + 建议          │  │
│  │  └─ 写入: ~/Documents/_inbox/<date>-mail-briefing.md     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌─── 规划层 (Planning) ───────────────────────────────────┐  │
│  │  task-planner.py                                          │  │
│  │  ├─ 匹配 journey spec (admin-notification-workflow)      │  │
│  │  ├─ LLM 分解: 通知→转发→收集→报告→审阅→提交             │  │
│  │  ├─ 生成执行计划: 每步骤 + 截止时间 + 所需文档           │  │
│  │  └─ 写入: ~/Documents/_inbox/<date>-task-plan.md         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌─── 行动层 (Action) ─────────────────────────────────────┐  │
│  │  doc-generator.py + mail-sender.py                        │  │
│  │  ├─ 公文生成: 通知/表格/报告 (从模板 + LLM 填充)         │  │
│  │  ├─ 邮件草稿: 转发通知/催收数据/提交报告 (SMTP)          │  │
│  │  ├─ 附件打包: 自动整理附件目录                           │  │
│  │  └─ 写入: ~/Documents/@工作文档/卫健委/_drafts/          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌─── 追踪层 (Tracking) ───────────────────────────────────┐  │
│  │  deadline-tracker.py                                      │  │
│  │  ├─ 定时检查: 邮件回复/审阅状态变化                      │  │
│  │  ├─ 超时告警: "距截止还有2小时，尚未收到3个科室回复"      │  │
│  │  ├─ 自动汇总: 收到的回复 → 整理为报告                    │  │
│  │  └─ 迭代触发: 领导回复意见 → 触发修改→重新提交           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─── 调度层 (Orchestration) ──────────────────────────────┐  │
│  │  mail-daemon (LaunchAgent, 每30min)                       │  │
│  │  ├─ 1. mail-reader: 读新邮件                              │  │
│  │  ├─ 2. mail-agent: LLM 分类 + 任务提取                    │  │
│  │  ├─ 3. task-planner: 对任务类邮件生成执行计划             │  │
│  │  ├─ 4. doc-generator: 生成文档草稿                        │  │
│  │  └─ 5. 输出到 Documents/_inbox/ (人审批后执行)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  算力: AetherForge ModelGateway → omlx reasoning (GLM-4.7-Flash)│
│  存储: ~/Documents/_inbox/ (日报/计划) + @工作文档/ (文档)      │
│  安全: 所有"行动"先生成草稿, 人类确认后执行                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 模块清单

### M1: `bin/ssot/mail-reader.py` (新建, ~120行)

**职责**: 统一读取 Apple Mail + 网易邮箱大师, 输出标准化邮件列表

**核心函数**:
```python
def read_apple_mail(limit=20, unread_only=True) -> list[Mail]:
    """读 Apple Mail: SQLite subjects + addresses + messages"""

def read_netease_mail(account: str, limit=20, unread_only=True) -> list[Mail]:
    """读网易邮箱大师: mail.db MailMeta + content.db MailContent"""

@dataclass
class Mail:
    source: str        # "apple_mail" | "netease_work" | "netease_personal"
    subject: str
    sender: str
    recipient: str
    date: str          # ISO-8601
    body: str          # 纯文本正文
    attachments: list[str]
    unread: bool
    account: str       # 邮箱地址
```

**复用**: `_shared.py` (ROOT, utc_now)
**数据源**:
- Apple Mail: `~/Library/Mail/V10/MailData/Envelope Index` (SQLite)
- 网易工作: `~/Library/Containers/com.netease.macmail/Data/Library/Application Support/data/ws-xxk@bjfsh.gov.cn_2160/`
- 网易个人: 同上, `xia_mingxing@163.com_6928` 和 `fshxxk@163.com_8688`

**DoD**: `python3 bin/ssot/mail-reader.py --json` 输出最近10封邮件的标准化 JSON

### M2: `bin/ssot/mail-agent.py` (新建, ~150行)

**职责**: LLM 分类邮件 + 任务提取 + 日报生成

**核心函数**:
```python
def classify_mail(mail: Mail) -> dict:
    """LLM 分类: 通知/任务/参考/垃圾/个人"""
    # 调用 _llm_helper.llm_ask()

def extract_task(mail: Mail) -> dict | None:
    """从邮件提取任务: 截止时间/责任人/所需动作/优先级"""

def generate_briefing(mails: list[Mail]) -> str:
    """生成今日邮件简报 Markdown"""
    # 输出到 ~/Documents/_inbox/<date>-mail-briefing.md
```

**复用**: `_llm_helper.py` (llm_ask), AetherForge ModelGateway
**分类 prompt 示例**:
```
你是邮件分类助手。请将以下邮件分类为:
- 通知 (上级通知/政策文件/会议通知)
- 任务 (需要你执行的动作: 收集数据/提交报告/转发文件)
- 参考 (行业资讯/学术文章/参考信息)
- 垃圾 (广告/推广/无关)
- 个人 (私人邮件)

邮件: {subject} from {sender}
正文: {body[:500]}

输出 JSON: {"category": "...", "priority": "high/medium/low", "summary": "...", "action_needed": "..."}
```

**DoD**: `python3 bin/ssot/mail-agent.py` 在 `~/Documents/_inbox/` 生成今日邮件简报

### M3: `bin/ssot/doc-generator.py` (新建, ~100行)

**职责**: 从模板 + LLM 生成公文/表格/报告

**核心函数**:
```python
TEMPLATES = {
    "forward_notice": "~/Documents/@工作文档/卫健委/_templates/转发通知模板.md",
    "data_collection": "~/Documents/@工作文档/卫健委/_templates/数据收集表模板.md",
    "summary_report": "~/Documents/@工作文档/卫健委/_templates/汇总报告模板.md",
}

def generate_doc(template: str, context: dict) -> str:
    """LLM 填充模板, 生成文档草稿"""
    # 输出到 ~/Documents/@工作文档/卫健委/_drafts/
```

**DoD**: 给定模板和上下文, 生成可编辑的 Markdown 文档

### M4: `bin/ssot/mail-sender.py` (新建, ~80行)

**职责**: SMTP 发送邮件 (草稿模式 — 保存到草稿箱, 不直接发)

**核心函数**:
```python
def create_draft(to: str, subject: str, body: str, attachments: list[str]) -> str:
    """创建邮件草稿 (不直接发送, 人确认后发)"""
    # 写入 ~/Documents/@工作文档/卫健委/_drafts/<date>-email-*.eml

def send_email(to: str, subject: str, body: str, smtp_config: dict) -> bool:
    """SMTP 发送 (仅在人类确认后调用)"""
```

**安全**: 默认只创建草稿, `send_email()` 需要显式调用
**DoD**: 能生成 .eml 格式草稿文件

### M5: `bin/ssot/mail-daemon.py` (新建, ~60行)

**职责**: LaunchAgent 守护进程, 每30分钟执行完整流程

**流程**:
```python
def run_cycle():
    # 1. 读新邮件
    mails = read_all_sources(since_last_check=True)
    # 2. LLM 分类
    classified = [classify_mail(m) for m in mails]
    # 3. 任务提取
    tasks = [extract_task(m) for m in classified if m.category == "任务"]
    # 4. 日报生成
    briefing = generate_briefing(classified)
    # 5. 对高优先级任务, 生成执行计划+文档草稿
    for task in tasks:
        if task.priority == "high":
            plan = plan_execution(task)
            docs = [generate_doc(t, task.context) for t in plan.templates]
    # 输出到 Documents/_inbox/ (等人类审批)
```

**LaunchAgent**: `~/Library/LaunchAgents/com.omostation.mail-daemon.plist`
- StartInterval: 1800 (30min)
- Python: `/opt/homebrew/bin/python3`

**DoD**: LaunchAgent 注册并运行, 每30分钟在 _inbox/ 产出简报

### M6: 新建 Journey Spec — 行政通知处理流程

**文件**: `docs/journey-specs/admin-notification-workflow.yaml`

```yaml
journey_id: admin-notification-workflow
trigger: mail_classified_as_task
states:
  - name: received
    scene: unified-inbox
    transitions:
      - to: classified
        condition: mail.category == "任务"
  - name: classified
    scene: unified-inbox
    actions: [extract_task, determine_deadline]
    transitions:
      - to: forwarding
        condition: task.requires_forwarding
  - name: forwarding
    scene: document-generation
    actions: [generate_forward_notice, generate_form, send_to_subordinates]
    transitions:
      - to: collecting
        condition: emails_sent
  - name: collecting
    scene: deadline-tracking
    actions: [wait_for_replies, check_deadline]
    transitions:
      - to: compiling
        condition: deadline_reached OR all_replies_received
  - name: compiling
    scene: document-generation
    actions: [compile_report, generate_summary]
    transitions:
      - to: reviewing
        condition: report_compiled
  - name: reviewing
    scene: leadership-review
    actions: [send_to_leader, wait_for_feedback]
    transitions:
      - to: iterating
        condition: leader_has_feedback
      - to: submitted
        condition: leader_approved
  - name: iterating
    scene: document-generation
    actions: [incorporate_feedback, revise_report]
    transitions:
      - to: reviewing
        condition: revision_complete
  - name: submitted
    scene: final-submission
    actions: [submit_to_superior, archive]
    terminal: true
```

---

## 执行计划

### Phase 1: 感知+认知 (M1+M2, 先让系统"看懂"邮件)

| 步骤 | 任务 | 文件 | DoD |
|------|------|------|-----|
| 1.1 | mail-reader.py | `bin/ssot/mail-reader.py` | `--json` 输出最近10封标准化邮件 |
| 1.2 | Apple Mail reader | 同上 | 读 subjects + addresses + unread 状态 |
| 1.3 | 网易 reader | 同上 | 读 mail.db MailMeta + content.db MailContent |
| 1.4 | mail-agent.py | `bin/ssot/mail-agent.py` | LLM 分类5封测试邮件 |
| 1.5 | 日报生成 | 同上 | 输出 Markdown 到 _inbox/ |

**验证**: `python3 bin/ssot/mail-reader.py --json | python3 -m json.tool | head -20`
**验证**: `cat ~/Documents/_inbox/$(date +%Y-%m-%d)-mail-briefing.md`

### Phase 2: 规划+行动 (M3+M4, 让系统能"做事")

| 步骤 | 任务 | 文件 | DoD |
|------|------|------|-----|
| 2.1 | 文档模板 | `~/Documents/@工作文档/卫健委/_templates/` | 3个模板: 通知/表格/报告 |
| 2.2 | doc-generator.py | `bin/ssot/doc-generator.py` | 给定模板+上下文 → Markdown 草稿 |
| 2.3 | mail-sender.py | `bin/ssot/mail-sender.py` | 生成 .eml 草稿文件 |
| 2.4 | admin-notification journey | `docs/journey-specs/admin-notification-workflow.yaml` | dry-run 通过 |

**验证**: `python3 bin/ssot/journey-runner.py run --journey admin-notification-workflow --dry-run`

### Phase 3: 调度+追踪 (M5+M6, 让系统"自主运行")

| 步骤 | 任务 | 文件 | DoD |
|------|------|------|-----|
| 3.1 | mail-daemon.py | `bin/ssot/mail-daemon.py` | run_cycle() 完整执行 |
| 3.2 | LaunchAgent | `~/Library/LaunchAgents/com.omostation.mail-daemon.plist` | 每30min自动运行 |
| 3.3 | deadline-tracker | 集成在 mail-daemon 中 | 检测回复状态变化 |
| 3.4 | 端到端验证 | — | 给定一封测试邮件 → 完整流程产出 |

**验证**: `launchctl list | grep mail-daemon` (PID 非空)
**验证**: 检查 `~/Documents/_inbox/` 有当日简报

---

## 验收标准

| # | 标准 | 测试方法 |
|---|------|---------|
| AC1 | mail-reader 能读两个源的邮件 | `python3 bin/ssot/mail-reader.py --json` 输出≥1封 |
| AC2 | LLM 分类准确率 >80% | 人工检查5封分类结果 |
| AC3 | 日报在 _inbox/ 生成 | `ls ~/Documents/_inbox/*mail-briefing*` |
| AC4 | 文档草稿可编辑 | 生成的 Markdown 结构正确、内容相关 |
| AC5 | journey dry-run 通过 | `journey-runner.py run --journey admin-notification-workflow --dry-run` |
| AC6 | daemon 运行 | `launchctl list | grep mail-daemon` 有 PID |
| AC7 | 安全: 不自动发邮件 | 所有邮件操作只生成草稿, 需人工确认 |

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 邮件内容含敏感信息 | LLM 只处理摘要, 不传全文; 草稿存在本地 |
| 网易邮箱大师数据库格式变化 | reader 有 fallback: 先试 SQLite, 失败试 .eml 文件 |
| Apple Mail 进程锁 | SQLite 以只读模式打开 (`mode=ro`) |
| LLM 误分类 | 人工审批环节兜底; 分类有 confidence 分数 |
| 自动发邮件风险 | **所有邮件操作只生成草稿**, mail-sender 的 send_email() 需要显式确认 |
| 邮件编码问题 | 自动检测 charset, fallback base64 → GB2312 → UTF-8 |

---

## 后续扩展 (Phase 2, 不在本计划范围)

- OA 系统集成 (致远OA Web API)
- 微信/钉钉消息感知
- 家庭域 agent (家庭早报、教育规划)
- 健康域 agent (卫健委巡检自动化)
- 个人域 agent (知识管理、学习规划)
