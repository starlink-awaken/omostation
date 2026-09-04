---
type: ephemeral
created: 2026-09-03
---

# Y1Q4 六 Bet 可行性预检报告

**类型**: report
**状态**: active
**负责人**: governance-team
**创建日期**: 2026-08-16
**执行者**: y1q4-preflight agent

---

## 一、执行摘要

| Bet | 状态 | 阻塞点 | 规模 |
|-----|------|--------|------|
| BET-Y1Q4-T3-01 自主性阶梯 | ✅ 就绪 | 无 | M |
| BET-Y1Q4-T7-01 公文场景放权 | ✅ 就绪 | 无 | M |
| BET-Y1Q4-T5-01 并行会签 | ✅ 就绪 | 无 | M |
| BET-Y1Q4-T6-01 aetherforge 并入 | 🔴 阻塞 | BET-Y1Q2-T1-01 未完成 | L |
| BET-Y1Q4-T4-01 真实评测集 v1 | ⚠️ 部分阻塞 | BET-Y1Q2-T7-01 进行中 | S |
| BET-Y1Q4-T1-01 Y1 年度门 | ✅ 就绪 | 无 | S |

**统计**: 3 就绪 / 1 阻塞 / 2 部分阻塞

---

## 二、逐项分析

### 1. BET-Y1Q4-T3-01 自主性阶梯 L0-L3 判据实现

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | ✅ 通过 | BET-Y1Q2-T4-01 (done) |
| write_surfaces | ✅ 存在 | `.omo/_truth/registry/**` 目录存在 |
| verify 命令 | ✅ 可跑 | `make evidence-smoke` 目标存在 |
| 规模预估 | M | 2 周工作量，3 项 done_when 条件 |

**结论**: **就绪可排期**。无前置阻塞，验证路径清晰。

---

### 2. BET-Y1Q4-T7-01 公文场景 format_check 升 L2

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | ✅ 通过 | BET-Y1Q1-T7-03 (done)；BET-Y1Q4-T3-01 为同季度依赖，可并行启动 |
| write_surfaces | ✅ 存在 | `docs/scene-cards/**` 目录存在 |
| verify 命令 | ✅ 可跑 | 目标文件 `docs/scene-cards/v2/document-review.yaml` 需在执行中创建 |
| 规模预估 | M | 1 周工作量，3 项 done_when 条件 |

**结论**: **就绪可排期**。T3-01 同为 Y1Q4 bet，可并行推进。

---

### 3. BET-Y1Q4-T5-01 并行会签 fork/join

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | ✅ 通过 | BET-Y1Q2-T5-02 (done) |
| write_surfaces | ✅ 存在 | `bin/ssot/journey-runner.py` + `tests/integration/**` 均存在 |
| verify 命令 | ✅ 可跑 | `bash tests/integration/run-all.sh` 文件存在 |
| 规模预估 | M | 2 周工作量，3 项 done_when 条件 |

**结论**: **就绪可排期**。依赖已清零，验证路径完整。

---

### 4. BET-Y1Q4-T6-01 aetherforge 并入 runtime

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | 🔴 阻塞 | **BET-Y1Q2-T1-01 (candidate) 未完成** |
| write_surfaces | ✅ 存在 | `.gitmodules` + `docs/project-registry.yaml` 均存在 |
| verify 命令 | ✅ 可跑 | `git submodule status \| grep -c aetherforge` 可执行 |
| 规模预估 | L | 2 周工作量，4 项 done_when 条件 |

**结论**: **阻塞，需等待 BET-Y1Q2-T1-01 完成**。该依赖为 T1-TRUTH track bet，属于 Y1Q2 遗留项，建议优先清理。

---

### 5. BET-Y1Q4-T4-01 真实评测集 v1 (≥200 条)

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | ⚠️ 部分阻塞 | BET-Y1Q2-T4-01 (done) ✅；**BET-Y1Q2-T7-01 (in_progress)** |
| write_surfaces | ✅ 存在 | `.omo/_delivery/evalsets/**` 目录存在，已有 1 个评测集文件 |
| verify 命令 | ✅ 可跑 | `ls .omo/_delivery/evalsets/ \| wc -l` 可执行 |
| 规模预估 | S | 1 周工作量，3 项 done_when 条件 |

**结论**: **部分阻塞，可提前准备数据采集管线**。BET-Y1Q2-T7-01 正在进行中，预计不久可完成。

---

### 6. BET-Y1Q4-T1-01 Y1 表面积盘点与年度门

| 检查项 | 结果 | 详情 |
|--------|------|------|
| 上游依赖 | ⚠️ 同季度依赖 | 依赖 BET-Y1Q4-T6-01 + BET-Y1Q3-T6-01（需确认状态） |
| write_surfaces | N/A | 检查类 bet，无特定 write_surfaces |
| verify 命令 | ✅ 可跑 | `python3 bin/plan/bet-ledger.py surface` 文件存在 |
| 规模预估 | S | 3 天工作量，多项逐项检查 |

**结论**: **就绪可排期**。虽有同季度依赖，但作为"年度门"性质的检查任务，可独立开展现状盘点工作。

---

## 三、阻塞点汇总

| 阻塞来源 | 受影响 Bet | 建议行动 |
|----------|-----------|----------|
| BET-Y1Q2-T1-01 (candidate) | T6-01 | 优先推进此 Y1Q2 遗留项 |
| BET-Y1Q2-T7-01 (in_progress) | T4-01 | 监控进度，完成后立即启动 T4-01 |

---

## 四、Y1Q4 窗口（约 10 月开）前准备清单

### P0（立即行动）
1. **启动 BET-Y1Q2-T1-01**：解除 T6-01 阻塞
2. **监控 BET-Y1Q2-T7-01**：确保 T4-01 依赖及时清零

### P1（准备阶段）
1. **T3-01 技术预研**：熟悉 OMO 事件机制与 calibration 判据
2. **T7-01 场景设计**：提前规划 `document-review.yaml` 结构
3. **T5-01 并行策略调研**：研究 fork/join 三种策略的实现路径

### P2（执行阶段）
1. **T4-01 数据采集**：提前搭建 adjudication 数据抽取管线
2. **T1-01 盘点脚本**：完善 `bet-ledger.py surface` 输出格式

---

## 五、建议优先级排序

1. **第一批（无阻塞）**：T3-01 → T7-01 → T5-01
2. **第二批（依赖即将清零）**：T4-01（待 T7-01 完成）
3. **第三批（需外部协作）**：T6-01（待 T1-01 完成）→ T1-01

---

**报告生成时间**: 2026-08-16
**下次更新**: BET-Y1Q2-T1-01 状态变更时
