# 路径A-C全面落地 — 深化执行 × 减法收敛 × 感知闭环

> 创建: 2026-08-07 | 前置: 四面一脊架构就位, 23 PRs merged, journey-runner dry-run全通
> 战略: Y1 "收敛与接通" — 逐项冗余清零 + 一个场景走完真实闭环

---

## 0. Context — 三条路径的内在关系

```
A (深化执行) → 证明系统能跑 → 建立信心 → 验证架构
     ↑                                    ↓
C (感知闭环) ← 自动触发执行 ← 减少手动 ← B (减法收敛)
     ↓                                    ↑
     └── 信号驱动自治 ←── 去掉不服务的代码 ─┘
```

三路径不是独立的——它们形成一个**收敛-执行-自动化**的螺旋上升。

### Y1成功判据对齐
- "逐项冗余清零" → 路径B
- "一个场景走完真实闭环" → 路径A+C
- 缺一即部分失败

---

## 1. Path A: 深化执行

### A1: 补齐 dispatcher gap (2个缺失场景)

| Scene | 缺口 | 方案 | 工程量 |
|-------|------|------|--------|
| document-review | 需AI agent审查 | Claude Task dispatcher: 传入公文内容 → AI审查 → 返回issues | ~40行 |
| engineering-delivery | 需人/agent开发 | 标记 `needs_human` + 生成任务描述 (不做自动开发) | ~15行 |

**Claude Task dispatcher设计**:
```python
def dispatch_real_review(input_data, token):
    """公文审查 — 通过AI agent执行."""
    document_ref = input_data.get("document_ref", "")
    if not document_ref:
        return {"status": "failed", "review": {"status": "failed"}}
    # 读公文内容 (通过iris get或vault ref)
    # 调AI agent审查 (格式/敏感/依据)
    # 返回审查结果
    return {"status": "succeeded", "review": {"status": "succeeded"}, "issues_found": []}
```

**关键约束**: Claude Task需要上下文窗口, journey-runner通过subprocess调外部脚本不直接嵌AI调用。实际实现: journey-runner生成审查任务描述 → 输出给operator → operator用Claude完成审查 → resume journey。

### A2: inbox-to-decision 全程 live 验证

目标: 非dry-run, 真实iris调用, 走完全程。

```bash
# 1. 真实读邮件
python3 bin/ssot/journey-runner.py run --journey inbox-to-decision --live
# → dispatch_real_inbox 调 iris list apple_mail + netease_mailmaster
# → 真实邮件进入分诊
# → under_review checkpoint 暂停

# 2. 人工审查后resume
python3 bin/ssot/journey-runner.py resume --journey-id inbox-to-decision --run-id <id>
# → document-review dispatch (AI/人工)
# → 继续到 knowledge_captured

# 3. 记录结果
python3 bin/ssot/scene-outcome-recorder.py record --scene-card ... --adjudication accepted
```

**验收标准**: 真实邮件 → 真实分诊 → 人工审查 → 知识沉淀 → 结果记录。全程有证据链。

### A3: 5个已有dispatcher的live验证

已有dispatcher (knowledge-curation, research-pipeline, periodic-reporting, meeting-supervision, project-supervision) 代码已写但未live测试。逐个跑一次:

```bash
python3 bin/ssot/journey-runner.py run --journey research-to-insight --live
# → dispatch_real_research 调 iris list rss + zhihu + wxread
```

**改动文件**: `bin/ssot/journey-runner.py` (+document-review + engineering-delivery dispatchers ~55行)

---

## 2. Path B: 减法收敛

### B1: 零调用工具审计

**现状**: bin/ssot/ 有94个工具。scene-card-* 有9个变体共~2847行。

**方案**: 新建 `bin/ssot/tool-usage-audit.py` (~80行):
- 扫描bin/ssot/所有.py文件
- 对每个工具, 检查: Makefile引用、CI workflow引用、其他脚本import
- 分类: active (有引用) / dormant (零引用) / orphaned (零引用+零commits in 60d)
- 输出报告, 不删除

```python
def audit_tools(root):
    tools = list(Path("bin/ssot").glob("*.py"))
    makefile = (root / "Makefile").read_text()
    for tool in tools:
        name = tool.stem
        in_makefile = name in makefile
        in_ci = check_ci_workflows(root, name)
        in_scripts = check_cross_refs(root, name)
        status = "active" if (in_makefile or in_ci or in_scripts) else "dormant"
        ...
```

**验收**: `make tool-audit` 输出分类报告。

### B2: scene-card-* 合并评估

9个scene-card-*变体的功能分析:

| 工具 | 行数 | 功能 | 可合并? |
|------|------|------|---------|
| scene-card-intake.py | 237 | 场景卡字段验证 | **核心** (保留) |
| scene-card-lifecycle.py | 308 | 生命周期管理 (check/activate) | **核心** (保留) |
| scene-card-candidates.py | 229 | 候选发现 | 可合入intake |
| scene-card-review.py | 230 | 审查流程 | 可合入lifecycle |
| scene-card-approval-flow.py | 314 | 审批流程 | 可合入lifecycle |
| scene-card-connector.py | 322 | 连接器绑定 | 评估是否被journey-runner替代 |
| scene-card-decision-inbox.py | 325 | 决策收件箱 | 评估是否被outcome-recorder替代 |
| scene-card-intake-pipeline.py | 378 | intake流水线 | 可合入intake |
| scene-card-task-bridge.py | 204 | 任务桥接 | 评估是否被journey-state-store替代 |

**方案**: 不立即合并 (风险高, 需逐个验证调用方)。先**标记**可合并项, 记技术债, 等Y1结束前统一处理。

**改动文件**: `bin/ssot/tool-usage-audit.py` (新建), `Makefile` (+target)

### B3: Y1冗余清单对账

对齐三年规划的5项冗余:

| 冗余项 | 状态 | 清零路径 |
|--------|------|---------|
| 知识层双头 (gbrain × kairon-kos) | 未清零 | 等MOS归并 (Y1远期) |
| 无消费者模块 | 待审计 | tool-usage-audit标记 |
| 无违规历史的required规则 | 待审计 | GaC规则审计 |
| 零调用脚本 | 待审计 | tool-usage-audit标记 |
| 休眠项目 | 待审计 | project-registry status检查 |

---

## 3. Path C: 感知闭环

### C1: signal-poller watch模式 + 自动触发

**现状**: signal-poller支持`--watch --interval 300`, 但检测到信号只输出JSON, 不自动启动journey。

**方案**: 加 `--auto-trigger` flag:
```python
if triggers and args.auto_trigger:
    for t in triggers:
        # 触发对应journey
        journey_map = {
            "apple_mail_inbox": "inbox-to-decision",
            "netease_mailmaster": "inbox-to-decision",
        }
        journey_id = journey_map.get(t["source_id"])
        if journey_id:
            subprocess.run(["python3", "bin/ssot/journey-runner.py", "run",
                          "--journey", journey_id, "--live"])
```

**改动文件**: `bin/ssot/signal-poller.py` (+~20行)

### C2: signal-sources.yaml 扩展

当前只有apple_mail_inbox。需要加:
```yaml
sources:
  - id: apple_mail_inbox          # 已有
  - id: netease_mailmaster_inbox   # 新增
    transport: local_filesystem
    path: "~/.netease/MailMaster/"
    bos_uri: "bos://perception/netease/inbox"
  - id: github_push                # 新增
    transport: webhook
    bos_uri: "bos://perception/github/push"
```

**改动文件**: `.omo/_truth/registry/signal-sources.yaml`

### C3: JourneyRunnerAgent 自动推进

**现状**: JourneyRunnerAgent tick扫描awaiting_human runs, 但只报告不执行。

**方案**: tick中检测到human_approved=True的run时, 自动调journey-runner resume:
```python
if resumable:
    for r in resumable:
        subprocess.run(["python3", str(workspace / "bin/ssot/journey-runner.py"),
                       "resume", "--journey-id", r["journey_id"], "--run-id", r["run_id"]],
                      timeout=60, capture_output=True)
    return {"action": "trigger", "details": {"resumed": len(resumable)}}
```

**改动文件**: `projects/omo/src/omo/omo_agent_host.py` (JourneyRunnerAgent.tick扩展, ~+15行, 需omo submodule)

---

## 4. 执行顺序

```
Phase 1 (路径A: 深化执行)
  A1: 补齐2个缺失dispatcher → bin/ssot/journey-runner.py (+55行)
  A2: inbox-to-decision live验证 → 手动执行 + 证据收集
  A3: 5个已有dispatcher live验证 → 逐个跑

Phase 2 (路径B: 减法收敛)
  B1: tool-usage-audit.py → 扫描标记, 不删除
  B2: scene-card-* 合并评估 → 标记技术债
  B3: Y1冗余清单对账 → 文档记录

Phase 3 (路径C: 感知闭环)
  C1: signal-poller --auto-trigger → 信号→journey自动启动
  C2: signal-sources.yaml扩展 → 更多信号源
  C3: JourneyRunnerAgent自动推进 → daemon tick执行resume
```

Phase 1和2可以部分并行 (A1改journey-runner, B1新建audit工具)。
Phase 3依赖Phase 1 (dispatcher必须就绪才能自动触发)。

---

## 5. 验证

| 路径 | 验证命令 | 期望 |
|------|---------|------|
| A2 | `journey-runner run --journey inbox-to-decision --live` | 真实邮件→分诊→checkpoint |
| A3 | `journey-runner run --journey research-to-insight --live` | iris list rss/zhihu/wxread 被调用 |
| B1 | `make tool-audit` | dormant工具被标记 |
| C1 | `signal-poller --watch --auto-trigger` | 检测到信号→自动启动journey |
| C3 | `omo daemon run_once --agent-host` | JourneyRunnerAgent推进pending run |
