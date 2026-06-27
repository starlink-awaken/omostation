# GaC Quickstart — 治理即代码使用指南

> 7 机制全闭环 + 115 规则 + healthcheck 12 项全绿. 本文档是"怎么用 GaC".

## 1. 加规则 (声明式, 不改代码)

编辑 `.omo/_truth/registry/governance-checks.yaml::gac.rules`:

```yaml
- id: CR-X4-NEW-RULE              # id: native CR-* 或 indexed 原真 id
  source_type: native              # native=GaC SSOT / indexed=原真策略 SSOT
  dimension: X4                    # X1审计 / X2抗熵 / X3价值 / X4一致
  layer: L2                        # M0/L0/L1/L2/L3/meta
  check_type: ssot_pointer         # 见 schema.check_type_enum (12 种)
  target: ".omo/state/system.yaml::field"
  executor: [ci_gate, omo_audit]   # 见 schema.executor_enum (10 种)
  lifecycle: active                # draft/active/deprecated/removed
  version: "1.0.0"
  created_at: "2026-06-27"
  adr: "ADR-0106"
```

**收敛原真规则** (X1-X4/L0 源 → GaC indexed):
```bash
python3 bin/gac-ingest-legacy.py --write    # 增量 ingest
```

## 2. 检测 (5 层 drift + 体系自检)

```bash
# schema 校验 (规则结构, CI 阻塞)
python3 bin/gac-validate.py --gate

# 5 层 drift 检测
python3 bin/gac-drift.py              # GaC 规则 vs 执行器 (机制4)
python3 bin/gac-ingest-legacy.py --check  # X1-X4+L0 源 vs indexed (动态收敛)
python3 bin/gac-bootstrap.py          # GaC 自身 4 层 (schema/工具/indexed/exec)
python3 bin/gac-executor.py           # executor 声明 vs 实际存在
python3 bin/gac-mof-validate.py       # 规则 vs M2 type (机制7)

# 体系自检 (12 项全量, 一站式)
python3 bin/gac-healthcheck.py
```

## 3. 修复

```bash
python3 bin/gac-ingest-legacy.py --write          # indexed drift (源有 GaC 没)
python3 bin/gac-ingest-legacy.py --update-relates  # relates_to 重叠识别回填
python3 bin/gac-executor.py --run                  # executor 调度 POC (机制3)
```

## 4. 日常 (cron 自动, gac-crontab)

| 时间 | 检测 | 工具 |
|------|------|------|
| 03:00 | drift radar | gac-drift --report |
| 03:30 | schema validate | gac-validate --report |
| 04:00 | healthcheck (12 项) | gac-healthcheck --json |
| 04:30 | legacy drift | gac-ingest-legacy --check |
| 05:00 (周一) | gc lifecycle | gac-gc --dry-run |
| 06:00 | X1-X4 检查 | x1-x4-check.sh |
| 06:30 | X2 freshness | x2_freshness_audit.py |

**安装**: `crontab .omo/cron/gac-crontab`

## 5. 体系状态判读

```
healthcheck 12 项:
  ✅ 全绿 = GaC 体系闭环 (生产可用)
  ❌ 有红 = 看具体项修复 (drift/missing executor/M2 drift 等)
```

**核心文档**:
- `NORTH-STAR.md` — 防走偏锚定 (7 机制 + 不变量 + 反模式)
- `physical-sandbox-design.md` — 物理沙箱 P1/P2/P3
- `roadmap-v1.md` — 6 阶段路线

## 6. 关键约束 (红线)

- **加规则** = 加 YAML (声明式), 不改代码 (机制 1)
- **executor** 必须实际存在 (gac-executor 检测, 防声明不执行)
- **indexed** 必填 source_ref (指向原真策略, 不复制内容 = SSOT)
- **M2 type** 约束规则 (gac-mof-validate, 机制 7)
- **GaC 治 GaC 自己** (bootstrap, 元治理递归)

---

*GaC Quickstart v1 · 2026-06-27 · 7 机制全闭环生产级*
