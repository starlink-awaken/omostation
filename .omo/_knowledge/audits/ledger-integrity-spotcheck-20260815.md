---
title: 台账 done 状态完整性抽样审计
type: audit
status: final
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - docs/plans/3y-bet-ledger.yaml
  - .omo/_knowledge/retros/BET-Y1Q3-T3-01.md
context: >
  触发事件: BET-Y1Q3-T3-01 被标 done 而其 retro 记录 done_when 两条未过 (87.5% vs
  99%, 窗口仅 1 周), 属 AGENT-BRIEF §1.3「声明 ≠ 事实」真实案例。本审计按人类
  2026-08-15 指令对 52 个 done bet 做分层抽样核实。判定分级: A=机械重跑 verify 命令
  (只读), B=信 retro Q2/验证节逐条判定, C=语义模糊不判交人。时间窗口条款强制
  算术核对 (done_at 距窗口起算点)。
last_updated: 2026-08-25
---

# 台账 done 状态完整性抽样审计 — 2026-08-15

## 1. 抽样方法（可复现）

```python
# pool = 52 个 status:done 减去 6 个无 retro 文件的机械违例 (见 §3)
rng = random.Random(20260815)          # 固定 seed
long_pick  = rng.sample(long_pool, 8)  # appetite ≥ 1 周 (16 个, 剔除 T3-01 自己)
short_pick = rng.sample(short_pool, 2) # appetite < 1 周 (对照组)
```

覆盖 6 条 track (T1/T2/T4/T5/T6/T7), 2 个 window (Y1Q1/Y1Q2)。

## 2. 逐 bet 核实结论

### 长周期 8 个

| Bet | Track | 判定 | 证据 |
|---|---|---|---|
| BET-Y1Q2-T5-01 | T5-ORCH | **✅ 名副其实** | retro Q2 三条全 ✅ 且带具体测试名 (`test_pending_approval_survives_restart_until_deadline` / `test_seven_day_policy_expires_and_is_durable`, 时间注入绕开真实 7 天); `tests/integration/run-all.sh` 存在 |
| BET-Y1Q1-T2-02 | T2-PERCEPT | **❌ 不符 (T3-01 同款)** | retro Q2 自记: 第1条 ✅(打假为 copy-paste 误差)、**第2条 ⚠️「连续 7 天每天有 signal 落盘 — 单次会话无法覆盖 7 天运行周期」、第3条 ⚠️「断连场景未验证」** — 两条未过却标 done。`last_signal_at` grep=5 只证明机制在, 不证明连续 7 天 |
| BET-Y1Q1-T1-06 | T1-TRUTH | **❌ 不符 (轻)** | retro Q2 五条中**第5条 ⏳「拓扑改造完成后删除 PASW 实现与 D5 — 未完成, 依赖 T1-05」**。属"终局条件挂在过渡 bet 上"的结构问题 (该条天然要等 T1-05), 但 retro 没说清就标 done 是事实。机械项全过: submodule=19 (18→19 后续新增 AetherForge), PASW_ISOLATED_SUBS grep=5 |
| BET-Y1Q2-T4-01 | T4-OUTCOME | **✅ 名副其实** | retro「验证结果」节: 37 tests passed (具体测试文件名), 三条 done_when 逐条 ✅ |
| BET-Y1Q2-T5-02 | T5-ORCH | **⚠️ 无法机械核实 (verify 已过时)** | retro 验证节记录 `run --journey inbox-to-decision --backedge-limit 2` 正常; 但台账 verify 命令按原文跑**双重失效** (CLI 语法变 + spec 路径解析变, 实测 FileNotFoundError)。bet 本体可能完成, 但 verify 命令与现实漂移, 后人无法复核 |
| BET-Y1Q2-T6-02 | T6-SUBTRACT | **✅ 名副其实** | 机械重跑 `adr-coverage.py --json` 含分层统计 (361 ADR, 0 缺号 0 重号); retro 验证节三条与 done_when 对齐 |
| BET-Y1Q2-T6-01 | T6-SUBTRACT | **✅ 名副其实** | retro 记录 4 条 superseded 归档 (CR-P76/P77 系); 机械项 `gac_required` 现值 27 — 但注意: 基线 26 → 该 bet 后**净 +1** (后续 bet 又加了 required 规则), 与 done_when「gac_required 下降」字面不符, 但 surface 输出自证 +1 来自后来者, 非该 bet 虚报。**瑕疵: retro 文件标题挂错** (写 BET-Y1Q2-T6-06, 实为 T6-01 的账) |
| BET-Y1Q1-T7-02 | T7-SCENE | **✅ 名副其实** | 机械重跑 `git ls-files --error-unmatch` 两个重建文件全 tracked; retro Q2 四条全 ✅ |

### 短周期对照 2 个

| Bet | Track | 判定 | 证据 |
|---|---|---|---|
| BET-Y1Q2-T4-02 | T4-OUTCOME | **✅ 名副其实** | retro「验证与审查」节: OMO 86 项 + Cockpit 58 项回归通过, 独立审查 APPROVE/CLEAR; 测试文件存在性确认 (`test_personal_episode.py`)。注意其「四周价值门」本身设计为持续观察, retro 明示「这些证据只证明观测机制正确, 不是个人价值样本」——诚实记账, 不算虚标 |
| BET-Y1Q1-T1-02 | T1-TRUTH | **✅ 名副其实** | 机械重跑: `git status --short` 子模块漂移 = 0; `submodule-gitlink-check.py` 输出「✅ 所有 submodule gitlink 同步, 无漂移」; retro Q2 五条全 ✅ |

## 3. 机械违例单列（不占抽样名额，100% 确认）

6 个 done bet **无 retro 文件**（D5 铁律违例，无需抽样即结论不符）：

- BET-Y1Q2-T6-06 / T6-07 / T6-08 / T6-09 / T6-10 —— 其中 T6-06~10 的 done_evidence 是 2026-08-14 修复轮补登记的最小结构（台账有 done_evidence 但从未有 retro 文件）
- BET-Y1Q2-T9-01 —— 台账记 done_at=None, 无 done_evidence 无 retro

## 4. 发现汇总

| 级别 | 数量 | 明细 |
|---|---|---|
| ❌ 不符 (T3-01 同款: 时间窗口/条件未满标 done) | **2** | T2-02 (7 天窗口 ⚠️ 未满), T1-06 (终局条件 ⏳ 未到) |
| ⚠️ 无法机械核实 (verify 漂移) | 1 | T5-02 (CLI 已变, 命令跑不通) |
| 瑕疵 (retro 文件标题挂错) | 1 | T6-01 retro 标题写 T6-06 |
| 机械违例 (done 无 retro, D5) | 6 | T6-06~10 + T9-01 |
| ✅ 名副其实 | 7/10 抽样 + 1 (T3-01 已另行纠正) | — |

**污染率估计**：抽样 10 个中 3 个有问题 (2❌+1⚠️) = 30%；加 6 个机械违例外推 52 done 池, **约 8-15 个存在不同程度不符**。done 池整体可信度不足 85%, "done" 标签不可再作为免检通行证。

## 5. 并行健康检查：T1-05A shadow 时钟

按人类指令核验（不推进、只确认时钟活着）：

- `shadow_events` 最后写入 2026-08-15T01:17:47Z, `agent_health` 心跳 2026-08-15T01:53:43Z（5min 节奏, 核验时 01:58Z）→ **时钟正常记录**
- 窗口 08-14 → 08-21 未满, **不得置 done**（本轮红线, 已在 T1-05A retro 与 spotcheck 双处锚定）

## 6. 处置建议（交人类拍板，本轮不自行改状态）

1. **T2-02 / T1-06**：是否翻回 in_progress（同 T3-01 处理）？或接受 retro 诚实记录、以备注形式在台账注明"部分条件移交后续 bet"？
2. **6 个无 retro 的 done**：是否补追溯 retro 或标 blocked？
3. **T5-02 verify 漂移**：是否单开小 bet 修台账 verify 命令（改为现行 CLI 语法）？
4. **T6-01 retro 标题挂错**：顺手修正即可，无需决策。
5. **#1494 批量 ledger completion 是 done 误标集中来源**——是否追溯该 commit 标 done 的全部 bet（git log 按行 diff 可列出）？
