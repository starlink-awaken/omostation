---
title: 三年规划执行台账 — 多 Agent 并行认领手册
type: execution-ledger
owner: 夏明星
created: 2026-08-06
lifecycle: plan
ssot: docs/plans/3y-bet-ledger.yaml
cli: bin/plan/bet-ledger.py
strategy: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
audit: docs/reports/2026-08-06-deep-review-proactive-agent-and-scenario-orchestration.md
note: >
  本文是人类视图。机器可读 SSOT 是 docs/plans/3y-bet-ledger.yaml，
  两者不一致时以 YAML 为准，且必须修 YAML 而非改本文。
last_updated: 2026-08-18
---

# 三年规划执行台账

> bet 数由 CLI 实时给出：`python3 bin/plan/bet-ledger.py status` · 轨道与窗口同样以台账 SSOT 为准 · 2026H2 → 2029
>
> 全部状态：`python3 bin/plan/bet-ledger.py status`

---

## 0. 先读这一段（否则会重蹈覆辙）

本台账诞生于一次实测事故。2026-08-06 当天，工作树在 **20 分钟内被并发 agent 清理了两次**（HEAD `847375f0` → `7d7ffdaa` → `5dff6900`），以下"已交付"产物**全部消失且无 blob 可恢复**，因为它们从未 `git add`：

| 文件 | 曾被声称 | git 状态 |
|---|---|---|
| `bin/ssot/journey-runner.py`（601 行） | v10 α.4 ✅ 已交付 | 从未 tracked |
| `bin/ssot/scene-card-lifecycle.py` | v8 A.1 ✅ 已交付 | 从未 tracked |
| `bin/ssot/validate-scene-card-v2.py` | ✅ 已交付 | 从未 tracked |
| `docs/scene-cards/v2/`（5 文件） | scene-card v2 全套 | 从未 tracked |
| `Plans/v10-*.md`（4 份） | v10 规划 SSOT | 从未 tracked |

所以本台账的第一条纪律不是关于质量，是关于**存在**：

> ### D0 铁律：任何交付物在 `git add` 之前不算交付。
>
> `git clean` 不会删除已暂存的文件。**写完立刻 `git add`，不要等 commit。**

---

## 1. 八条轨道（一条轨 = 一个 agent）

| 轨道 | 名称 | 负责什么 | 默认 workflow | PASW |
|---|---|---|---|:--:|
| **T1-TRUTH** | 真相与止血 | 指标口径 / 子模块指针 / 目标 SSOT / 归并判定 / 年度门 | `governance-state-mutation` | — |
| **T2-PERCEPT** | 感知面 | 信号源注册 / iris 轮询 / 去重幂等 / 可见降级 | `external-adapter-sync` | ✔ |
| **T3-COGNI** | 认知面（心智模型） | MOS 三表 / SceneWatcher 有状态化 / 自主性阶梯 / 跨场景学习 | `project-code-change` | — |
| **T4-OUTCOME** | 结果面 | Adjudication 事件 / 裁决存储 / calibration / 评测集 | `project-code-change` | ✔ |
| **T5-ORCH** | 编排硬化 | durable timer / 回退语义 / fork-join | `project-code-change` | — |
| **T6-SUBTRACT** | 减法 | GaC / ADR / 脚本 / 合成场景 / 项目归并 | `governance-state-mutation` | ✔ |
| **T7-SCENE** | 场景 | scene-card schema / 五档生命周期 / 三锚点迭代 | `project-doc-change` | — |
| **T8-SURFACE** | 人机界面 | /inbox /outcomes /signals /journeys | `project-code-change` | ✔ |

**PASW ✔** = 触及 `gbrain` / `cockpit` / `agora` 高冲突子模块，改动必须在 `.subtrees/<sub>/` 隔离树内完成（ADR-0371）。

---

## 2. 并发规则（多 agent 同时跑的前提）

```
最大并行 bet 数：4
独占轨道：T6-SUBTRACT（它跑的时候其余轨道只读）
冲突对（不可同时 in_progress）：
  T3-COGNI × T4-OUTCOME   ← 都写 projects/omo
  T3-COGNI × T5-ORCH      ← 都写 projects/omo
  T4-OUTCOME × T8-SURFACE ← 都写 projects/cockpit
```

CLI 会自动判定：

```bash
python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T3-01
```

它检查四件事：状态可认领、依赖已 done、无冲突轨道在跑、未超并行上限。通过则直接打印该 bet 的完整认领与收尾命令。

---

## 3. 认领 → 执行 → 收尾（标准流程）

### 3.1 认领

```bash
# ① 看看现在能领什么
python3 bin/plan/bet-ledger.py status

# ② 选一个，检查是否可领（会打印后续所有命令）
python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T1-01

# ③ 开隔离工作树（防止和其他 agent 互相清理）
bash bin/gac/gac-worktree.sh claim bet-y1q1-t1-01

# ④ 起 workflow（ADR-0203 红线：先 start 再改文件）
uv run --with pyyaml python bin/agent-workflow.py start governance-state-mutation \
  --profile governance-agent --objective "BET-Y1Q1-T1-01 废除 X3 mtime 交付指标"

# ⑤ claim 每一个写面
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path bin/mof/generate-brief.py
```

### 3.2 执行

- 只改 `write_surfaces` 里列出的路径。改别的 = 越权（D3）。
- `non_goals` 是硬边界，不是建议。想做 non_goals 里的事 → 另开 bet。
- **每写完一个文件立刻 `git add`**（D0）。
- 超 appetite × 1.5 → 立即执行 `circuit_breaker`，不要硬扛。

### 3.3 收尾

```bash
# ① D0 优先：先入库
git add <所有 deliverable>

# ② 验收（会同时跑 D0 检查）
python3 bin/plan/bet-ledger.py verify BET-Y1Q1-T1-01 --execute

# ③ workflow 验证与关闭
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# ④ 写复盘（D5：无 retro 不得置 done）
#    .omo/_knowledge/retros/BET-Y1Q1-T1-01.md

# ⑤ 提交与释放
bash bin/gac/gac-worktree.sh submit bet-y1q1-t1-01
```

---

## 4. 六条铁律（closeout 必检）

| 编号 | 铁律 | 检查方式 | 级别 |
|---|---|---|---|
| **D0** | 任何交付物在 `git add` 之前不算交付 | `git ls-files --error-unmatch <file>` | 🔴 红 |
| **D1** | 采集不到的指标显示"未接入"，禁止代理量顶替 | review 抽查 | 🔴 红 |
| **D2** | closeout 必须报告净增减（行数/文件/规则/ADR/脚本） | `bet-ledger.py surface` | 🔴 红 |
| **D3** | 先 claim 后写，未 claim 的写面视为越权 | `bet-ledger.py claim-check` | 🔴 红 |
| **D4** | 走 ADR-0203 workflow，先 start 再改文件 | `agent-workflow.py start` | 🔴 红 |
| **D5** | 无 retro 不得置 done | `bet-ledger.py retro-due` | ⚪ 灰 |

**D2 是 Y1 主目标的下沉**：Y1 唯一硬指标是表面积净负增长，所以每个 bet 都必须回答"我让系统变大还是变小了"。

---

## 5. 复盘节律（四层）

### 5.1 每 bet 复盘（强制，D5）

路径 `.omo/_knowledge/retros/<bet-id>.md`，固定 5 问（固定是为了跨 bet 可比）：

```markdown
# <BET-ID> 复盘

**Q1 实际耗时 vs appetite？超出比例？**

**Q2 done_when 是否全部通过？哪条没过，为什么？**

**Q3 过程中发现的与 plan 不符的事实（打假）？**

**Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？**
（跑 `python3 bin/plan/bet-ledger.py surface` 贴结果）

**Q5 下一个认领本 track 的 agent 需要知道什么？**
```

Q3 和 Q4 是本台账区别于普通任务清单的地方：**Q3 强制每次执行都产出一条对计划的证伪或修正，Q4 强制每次执行都对表面积记账。**

### 5.2 每周（周五，各 track owner）

`.omo/_knowledge/retros/weekly/<YYYY-Www>.md`，回答三问：

1. 本周哪条建议真的省了时间？哪条是噪音？
2. 表面积本周净增减？
3. 有无 bet 超 appetite 1.5× 却没触发熔断？

### 5.3 每季度门（人类判定）

`.omo/_knowledge/retros/gates/<window>.md`。**门不过，下一窗口的 bet 不得启动。**

```bash
python3 bin/plan/bet-ledger.py gate Y1Q1
```

| 门 | 唯一问题 | 通过条件 | 不通过 |
|---|---|---|---|
| **Y1Q1** | 过去一周系统看到了多少条来自真实工作的信号？ | > 0 | Q2 只跑 T6 减法轨 |
| **Y1Q2** | 这个月我接受了系统几条建议？改了什么？ | ≥ 4 且有 edit_diff | 场景全降回 shadow |
| **Y1Q3** | 归并后行数 < 50 万？MOS 唯一读写路径？ | 两者皆是 | 回滚归并 |
| **Y1Q4** | 表面积达标？ | ≤69万行 / ADR≤120 / GaC≤80 | Y2 不启动扩展 |
| **Y2Q4** | 修订率较 Y1 基线下降 ≥20%？ | 是 | **愿景证伪** |
| **Y3H2** | 三年终局三条同时成立？ | 是 | 收窄至单场景维持 |

### 5.4 年度门

Y1 → 2027-07 ｜ Y2 → 2027-12 ｜ Y3 → 2029-06。Y2Q4 是**愿景证伪点**：修订率不下降 = 系统没在学 = "个人业务操作系统"定位不成立。

---

## 6. 台账全景

### Y1 · 2026H2–2027H1 — 收敛与接通（净减法年，31 bet）

#### Y1Q1 止血·接通·起跑（14 bet）

| ID | 轨 | Appetite | 标题 | ★ |
|---|---|---|---|:--:|
| BET-Y1Q1-T1-00 | T1 | 2 days | 并发写冲突止血 — 共享主树禁写 + PASW 全覆盖 | |
| BET-Y1Q1-T1-01 | T1 | 1 day | 废除 X3 mtime 交付指标 | |
| BET-Y1Q1-T1-02 | T1 | 3 days | 子模块指针对齐 + 漂移 CI 门禁 | ★ |
| BET-Y1Q1-T1-03 | T1 | 1 day | goals/current.yaml 复活 | ★ |
| BET-Y1Q1-T1-04 | T1 | 2 days | 未入库产物普查 + D0 铁律门禁 | |
| BET-Y1Q1-T2-01 | T2 | 3 days | signal-sources 注册表与感知面契约 | |
| BET-Y1Q1-T2-02 | T2 | 1 week | **iris apple_mail 真实轮询打通** | ★ |
| BET-Y1Q1-T3-01 | T3 | 1 week | MOS agent_belief 三表 schema 与写入路径 | |
| BET-Y1Q1-T3-02 | T3 | 3 days | SceneWatcher 决策日志真写 MOS | |
| BET-Y1Q1-T4-01 | T4 | 1 week | AdjudicationRecorded 事件与裁决存储 | |
| BET-Y1Q1-T7-01 | T7 | 3 days | scene-card 五档生命周期 schema | |
| BET-Y1Q1-T7-02 | T7 | 1 week | v10 失落产物重建并入库 | |
| BET-Y1Q1-T7-03 | T7 | 1 week | 公文场景砍到 3 node 并进 shadow | |
| BET-Y1Q1-T8-01 | T8 | 2 weeks | **/inbox 决策收件箱最小版** | |

#### Y1Q2 减法·编排硬化

| ID | 轨 | Appetite | 标题 | ★ |
|---|---|---|---|:--:|
| BET-Y1Q2-T6-01 | T6 | 1 week | GaC 规则减法第一轮 134 → ≤100 | |
| BET-Y1Q2-T6-02 | T6 | 1 week | ADR 有效集分层 344 → ≤200 | |
| BET-Y1Q2-T6-03 | T6 | 1 week | bin 脚本清理 309 → ≤240 | |
| BET-Y1Q2-T6-04 | T6 | 3 days | 合成协作场景归档 221 → ≤40 | |
| BET-Y1Q2-T6-05 | T6 | 3 days | **减法配额制门禁上线（增1删1）** | |
| BET-Y1Q2-T5-01 | T5 | 2 weeks | durable timer — waiting_approval 跨进程 ≥7 天 | |
| BET-Y1Q2-T5-02 | T5 | 1 week | 回退边执行语义 + 次数上限 + 升级路径 | |
| BET-Y1Q2-T1-01 | T1 | 2 weeks | omo-debt + c2g 并入 omo | ★ |
| BET-Y1Q2-T1-02 | T1 | 1 week | model-driven 去留判定 | ★ |
| BET-Y1Q2-T1-03 | T1 | 1 day | Blueprint W1-05 JSONL shadow migration adapter | |
| BET-Y1Q2-T7-01 | T7 | 1 week | 工程交付 dogfood 开 shadow | |
| BET-Y1Q2-T4-01 | T4 | 1 week | capability_calibration 自动更新 | |
| BET-Y1Q2-T8-01 | T8 | 2 weeks | /outcomes 结果与校准面板 | |

#### Y1Q3 知识层归并（6 bet · 含唯一不可逆点）

| ID | 轨 | Appetite | 标题 | ★ |
|---|---|---|---|:--:|
| BET-Y1Q3-T3-01 | T3 | 6 weeks | MOS 双栈一致性观察 8 周（归并前置硬门） | |
| BET-Y1Q3-T3-02 | T3 | 1 week | Neo4j 生产启用 | ★ |
| BET-Y1Q3-T3-03 | T3 | 1 week | 退役 mem0 / memtheta 仿真适配器 | |
| BET-Y1Q3-T6-01 | T6 | 6 weeks | **gbrain + kairon 归并为 knowledge（不可逆）** | ★ |
| BET-Y1Q3-T7-01 | T7 | 1 week | 知识场景召回被引用率上线 | |
| BET-Y1Q3-T2-01 | T2 | 1 week | 感知面第二根管子（文件夹 / 日历） | ★ |

#### Y1Q4 放权·收口（6 bet）

| ID | 轨 | Appetite | 标题 | ★ |
|---|---|---|---|:--:|
| BET-Y1Q4-T3-01 | T3 | 2 weeks | 自主性阶梯 L0-L3 判据实现 | |
| BET-Y1Q4-T7-01 | T7 | 1 week | **公文场景 format_check 升 L2（首次放权）** | ★ |
| BET-Y1Q4-T5-01 | T5 | 2 weeks | 并行会签 fork/join | |
| BET-Y1Q4-T6-01 | T6 | 2 weeks | aetherforge 并入 runtime | ★ |
| BET-Y1Q4-T4-01 | T4 | 1 week | 真实评测集 v1（≥200 条，非合成） | |
| BET-Y1Q4-T1-01 | T1 | 3 days | Y1 表面积盘点与年度门 | ★ |

### Y2 · 2027 — 深化与放权（12 bet）

| 窗口 | ID | 轨 | Appetite | 标题 |
|---|---|---|---|---|
| Y2Q1 | BET-Y2Q1-T3-01 | T3 | 2 weeks | 世界模型 world_snapshot 全量 + delta |
| Y2Q1 | BET-Y2Q1-T3-02 | T3 | 1 week | 意图模型接 goals / tasks 实时 |
| Y2Q1 | BET-Y2Q1-T3-03 | T3 | 2 weeks | **Agent 据心智模型决策（脱离纯阈值）** |
| Y2Q2 | BET-Y2Q2-T7-01 | T7 | 2 weeks | 知识入库场景升 assisted ★ |
| Y2Q2 | BET-Y2Q2-T7-02 | T7 | 3 weeks | 中试平台 / 政策申报场景 draft → shadow |
| Y2Q2 | BET-Y2Q2-T8-01 | T8 | 2 weeks | **/inbox 每日习惯化改造** |
| Y2Q3 | BET-Y2Q3-T3-01 | T3 | 3 weeks | **跨场景校准迁移（验证"学习"是真的）** |
| Y2Q3 | BET-Y2Q3-T3-02 | T3 | 2 weeks | 漂移监控与自动降级 |
| Y2Q3 | BET-Y2Q3-T6-01 | T6 | 2 weeks | 减法第二轮维持（防反弹） |
| Y2Q4 | BET-Y2Q4-T3-01 | T3 | 3 weeks | 多模型路由按实测成本优化（v10 γ 解冻） |
| Y2Q4 | BET-Y2Q4-T2-01 | T2 | 2 weeks | 感知面第三 / 四根管子 ★ |
| Y2Q4 | BET-Y2Q4-T1-01 | T1 | 3 days | **Y2 年度门 + 愿景证伪检查** ★ |

### Y3 · 2028–2029 — 复利与外扩（8 bet）

| 窗口 | ID | 轨 | Appetite | 标题 |
|---|---|---|---|---|
| Y3H1 | BET-Y3H1-T3-01 | T3 | 4 weeks | **新场景冷启动 < 2 周（证明复利存在）** |
| Y3H1 | BET-Y3H1-T7-01 | T7 | 4 weeks | 中试 / 政策申报升 assisted ★ |
| Y3H1 | BET-Y3H1-T5-01 | T5 | 3 weeks | 编排模板化 |
| Y3H1 | BET-Y3H1-T6-01 | T6 | 1 week | 表面积不反弹审计 |
| Y3H2 | BET-Y3H2-T7-01 | T7 | 3 weeks | **公文场景 routine（限格式类，首次 L3）** ★ |
| Y3H2 | BET-Y3H2-T4-01 | T4 | 2 weeks | 复利收益归因报告 |
| Y3H2 | BET-Y3H2-T1-01 | T1 | 1 week | 对外扩展决策 ADR（默认不做）★ |
| Y3H2 | BET-Y3H2-T1-02 | T1 | 3 days | **三年终局门** ★ |

---

## 7. 需要你本人到场的 bet（★ 共 16 个）

Agent 领不了这些，会卡住。按时间排序，前三个决定 Y1 能否启动：

| 顺序 | Bet | 你需要做什么 |
|---|---|---|
| 1 | BET-Y1Q1-T1-03 | 口述 3 条真实未完成目标（agent 只做格式化落盘；goals 仅人类可改） |
| 2 | BET-Y1Q1-T1-02 | 确认哪个分支/指针是权威 |
| 3 | **BET-Y1Q1-T2-02** | **到场一次打通 iris：CDP 9222 + operator grant。感知面从 0 到 1 的唯一钥匙** |
| 4 | BET-Y1Q2-T1-02 | model-driven 去留拍板 |
| 5 | BET-Y1Q2-T1-01 | 批准 omo-debt/c2g 归并 |
| 6 | BET-Y1Q3-T3-02 | 本机 Docker / brew 起 Neo4j |
| 7 | BET-Y1Q3-T2-01 | 第二信号源授权 |
| 8 | **BET-Y1Q3-T6-01** | **批准知识层归并（唯一不可逆点）** |
| 9 | BET-Y1Q4-T6-01 | 批准 aetherforge 归并 |
| 10 | **BET-Y1Q4-T7-01** | **批准首次放权（L2）** |
| 11 | BET-Y1Q4-T1-01 | Y1 年度门判定 |
| 12-16 | Y2/Y3 各门与放权 | 见上表 |

---

## 8. 常用命令速查

```bash
python3 bin/plan/bet-ledger.py status                    # 总览 + 当前可认领
python3 bin/plan/bet-ledger.py list --window Y1Q1        # 按窗口列
python3 bin/plan/bet-ledger.py list --track T3-COGNI     # 按轨道列
python3 bin/plan/bet-ledger.py list --claimable          # 只看能领的
python3 bin/plan/bet-ledger.py show BET-Y1Q1-T3-01       # 看单个 bet 全文
python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T3-01  # 能不能领 + 认领命令
python3 bin/plan/bet-ledger.py verify BET-Y1Q1-T1-01 --execute  # 验收 + D0 检查
python3 bin/plan/bet-ledger.py surface                   # 表面积记账（D2）
python3 bin/plan/bet-ledger.py retro-due                 # 缺复盘的 bet（D5）
python3 bin/plan/bet-ledger.py gate Y1Q1                 # 季度门
python3 bin/plan/bet-ledger.py lint                      # 台账自检
```

---

## 9. 如何修改台账

- **改 YAML，不改本文。** 本文是视图，YAML 是 SSOT。
- 改完跑 `bet-ledger.py lint`。
- 新增 bet 必须给全：`goal` / `non_goals` / `done_when` / `verify` / `write_surfaces` / `circuit_breaker`。缺一项 lint 就报错。
- **新增 bet 时先问：这是不是在增加表面积？** 如果是，它必须配一个对应的减法 bet（守减法配额制）。
