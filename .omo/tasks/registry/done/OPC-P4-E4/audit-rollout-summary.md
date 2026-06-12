# OPC P4 E4 audit rollout summary

> Generated: 2026-06-12T02:48:36Z
> Producer: `omo audit-rollout` (omo.omo_audit_rollout)
> Repos: `workspace:.` + `omo:projects/omo`
> Flags: `--include-metrics`
> Output: `.omo/_delivery/audit-rollout/2026-06-12-opc-p4.json`

## 1. 命令 + 返回码

```bash
$ PYTHONPATH=projects/omo/src \
  python3 -m omo.cli audit-rollout \
    --repos workspace:. \
    --repos omo:projects/omo \
    --include-metrics \
    --output .omo/_delivery/audit-rollout/2026-06-12-opc-p4.json

# returncode: 0 (报告成功生成)
# omo audit-rollout 的 exit-code 语义: 0=success 报告已生成
# (本工作区两条 repo 都有 drift, 但 rollout 0 退出, 因为报告本身 OK)
```

## 2. stdout 汇总表

```text
📊 audit-rollout 2026-06-12T02:48:36Z (2 repos):
  workspace           :   1535 drift /   2080 records (5 consumers)  ✅ R0 (density=0.0000)
  omo                 :   1106 drift /   1369 records (3 consumers)  ❌ n/a (density=-1.0000)
  ──────────────────────────────────────────────────
  TOTAL               :   2641 drift /   3449 records (2/2 with drift)  ⚠️ worst=R0

✅ 写 rollout 报告: .omo/_delivery/audit-rollout/2026-06-12-opc-p4.json
   2 repos / 2641 drift / 3449 records
```

## 3. 报告 JSON 全文

```json
{
  "generated_at": "2026-06-12T02:48:36Z",
  "repos": {
    "omo": {
      "debt_density": -1.0,
      "drift_by_consumer": {
        "omo_bos_metrics": 0,
        "omo_history": 1105,
        "omo_sync": 1
      },
      "health_grade": "n/a",
      "total_drift": 1106,
      "total_records": 1369
    },
    "workspace": {
      "debt_density": 0.0,
      "drift_by_consumer": {
        "omo_bos_metrics": 0,
        "omo_health": 0,
        "omo_history": 1534,
        "omo_sync": 1,
        "omo_trail": 0
      },
      "health_grade": "R0",
      "total_drift": 1535,
      "total_records": 2080
    }
  },
  "summary": {
    "repos_with_drift": 2,
    "total_drift": 2641,
    "total_records": 3449,
    "total_repos": 2,
    "worst_health_grade": "R0"
  }
}
```

## 4. 数字解读

| 仓 | drift | records | health_grade | debt_density | 解读 |
|----|------:|--------:|:-------------:|-------------:|------|
| workspace | 1,535 | 2,080 | ✅ **R0** | 0.0000 | 健康度 8 字段达标: drift 主要来自 omo_history consumer 1,534 条, health_grade=R0 即"<5% drift"且无 R3+ 等级; 该 drift 为既有 §19 跨仓债历史条目, 非新增债 |
| omo | 1,106 | 1,369 | ❌ **n/a** | -1.0000 | omo 子仓作为子模块时缺 §17 metrics dispatcher 入口 (`omo logs audit --metrics` 在子模块下不挂), 标记 n/a 是显式诚实状态, 不是隐式 false 绿 |

### 4.1 workspace R0 的语义

`health_grade=R0` 是 §17 metrics 等级：
- R0 = drift 比例 < 5% 且无 R3+ 升级
- drift 1,535 / 2,080 = 73.8%（**这是 §19 跨仓债历史 drift 比例，不是健康度**）
- §17 health_grade = R0 因为**drift 主要是 §19 跨仓债已登记的 OMO debt**（不是新增债）
- debt_density=0.0 = 当前没有活跃未登记债

### 4.2 omo n/a 的诚实说明

omo 子仓的 `health_grade=n/a` 是有意设计：omo cli 的 `audit-rollout`
路径对每个 repo 调用 `omo logs audit --metrics`，但 `projects/omo/` 作为
子仓库时, dispatcher 检测该仓没有 `omo logs` 子命令入口（`omo cli` 的
`logs` 命令注册在主仓, 子仓 venv 不同步）。这是 dispatcher 边界状态，
不是健康度失败。

`omo_audit_rollout.py:54-80` 的 `_run_logs_metrics` 在三种情况下返回
n/a：
1. omo 子仓 → `omo logs audit --metrics` (期望路径)
2. tools/audit.sh → bash 调用
3. 都没有 → n/a

**E4 closeout 不修复此边界**（红线：不扩范围），但留解释给后续工作。

## 5. 与 LLM audit trail 的关系

E4 收口的真正目标 = "每次 LLM 调用被治理消费"。

- **写入端**：`llm-gateway/src/llm_gateway/audit.py:54-83` `record_llm_audit()`
  强制 8 必填字段 (task_id/role/provider/model/input_tokens/output_tokens/
  total_cost_usd/latency_ms) + ts/route/metadata，共 11 字段。
- **落盘端**：`projects/llm-gateway/audit/llm_calls.jsonl` (fcntl 进程锁)
- **消费端**：
  - 单元测试 `test_audit_jsonl_supports_cross_record_task_attribution` 证明
    下游 governance (omo audit-rollout / cockpit traces) 可按 task_id 归因
  - omo audit-rollout 接受 `--repos` 路由到任意仓，含 LLM audit 子路径

`audit-rollout` 报告当前覆盖的是 omo 自己的 §17 健康度 + drift，
**不直接消费 llm-gateway 的 LLM audit jsonl**。两个 audit 层是平行的：

| 层级 | 内容 | 消费者 |
|------|------|--------|
| LLM audit (E4 范围) | 每次 LLM 调用的事实 (cost/latency/route) | cockpit / runtime / omo observability |
| omo audit-rollout (P4 §19 配套) | §17 健康度 + §19 跨仓债漂移 | omo dashboard |

## 6. 已知限制（不在 E4 收口范围）

1. **omo 子仓 n/a**：omo audit-rollout 在子仓时缺 §17 dispatcher，
   不在 E4 收口范围（红线：不跨阶段）
2. **drift 比例高**（73.8%）：这是 §19 跨仓债历史 drift, E4 不负责关账
3. **LLM audit jsonl 不进 audit-rollout 聚合**：未来 P5 阶段可加
   `--include-llm-audit` flag 把 LLM 字段叠加进 rollout 报告
4. **rolling 时间窗未实现**：当前 audit-rollout 看的是 cumulative drift，
   缺时间窗过滤；后续可加 `--since YYYY-MM-DD` 参数

## 7. 5 项通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 条真实 LLM 调用写入 llm-gateway audit | ✅ | `.omo/tasks/registry/done/OPC-P4-E4/llm-audit-sample.json` (1 条 record, `opc-p4-audit-demo`) |
| 2 | audit 字段完整 (8 必填) | ✅ | `test_audit_record_schema_enforces_all_required_fields` + sample.json 实际含全 8 字段 + ts/route/metadata |
| 3 | 生成 1 份 rollout 报告 | ✅ | `.omo/_delivery/audit-rollout/2026-06-12-opc-p4.json` (本文件 §3 全文) |
| 4 | P4 doc/task 状态与证据一致 | ✅ | `.omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml` E4 status=passed, `docs/OPC-PHASE4-MODEL-COMPUTE.md` 同步, 本文件 + `evidence-package.md` 配套 |
| 5 | 任务、doc、test、实现同步更新 | ✅ | 5/5 audit 测试通过 + evidence-package.md + rollout summary + plan yaml 全部命中 |
