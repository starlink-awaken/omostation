# OPC P5-F4 cockpit 统一入口 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F4

## 1. 目标

用户不理解仓边界也能跑 3 个 scenario；cockpit CLI 增加统一命令；
3 scenario 可直接触发。

## 2. 统一入口设计

```
cockpit scenario {radar | assistant | health} [--query Q] [--limit N]
```

- **1 条统一命令** `cockpit scenario`（顶层命令）
- **3 个子命令**：`radar` / `assistant` / `health`
- 共享 `_f1/_f2/_f3` 实现 + `cmd_scenario(args)` 入口
- 子命令注册位置：`projects/cockpit/src/cockpit/cli.py:294-322`

## 3. 命令帮助实证

```text
$ PYTHONPATH=/Users/xiamingxing/Workspace/projects/cockpit/src \
  python3 -m cockpit scenario --help

usage: cockpit scenario [-h] {radar,assistant,health} ...

positional arguments:
  {radar,assistant,health}
    radar               P5-F1 technical-radar: 扫描研究活动, 产出 ≥3 upgrade
                        candidates
    assistant           P5-F2 work-assistant: 1 真实工作 query → 结构化草稿
    health              P5-F3 family-health: 1 真实家庭健康 query → 3 级
                        next-action (privacy=confidential)

options:
  -h, --help            show this help message and exit
```

```text
$ python3 -m cockpit scenario radar --help
usage: cockpit scenario radar [-h] [--limit LIMIT]
  --limit LIMIT        最多产出多少 candidates (默认 10, 红线 ≥3)

$ python3 -m cockpit scenario assistant --help
usage: cockpit scenario assistant [-h] [--query QUERY]
  --query QUERY        真实工作 query

$ python3 -m cockpit scenario health --help
usage: cockpit scenario health [-h] [--query QUERY]
  --query QUERY        真实家庭健康 query
```

## 4. 3 scenario 跑通证据

| Scenario | 命令 | returncode | 输出路径 |
|----------|------|:---:|----------|
| radar | `cockpit scenario radar --limit 5` | 0 | JSON stdout（3 candidates, 含 source/timestamp/next-action） |
| assistant | `cockpit scenario assistant --query "OPC P5 路线图"` | 0 | JSON stdout（结构化草稿 + audit_ref） |
| health | `cockpit scenario health --query "高烧不退是否需要立即去医院"` | 0 | JSON stdout（privacy_class=confidential + urgent） |

详细见：
- `.omo/tasks/registry/done/OPC-P5-F1/evidence-package.md`
- `.omo/tasks/registry/done/OPC-P5-F2/evidence-package.md`
- `.omo/tasks/registry/done/OPC-P5-F3/evidence-package.md`

## 5. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | 命令帮助清晰 | ✅ | 4 段 help 输出（scenario + 3 子命令） |
| 2 | 3 条命令或 1 条统一命令可跑通 | ✅ | 1 统一命令 `cockpit scenario {radar,assistant,health}`，3 子命令全跑通 |

## 6. 关键设计决策

### 6.1 为什么不直接 3 条独立命令？

- 用户认知成本：3 条独立命令需要记 3 个入口名
- 统一命名空间：scenario 是 P5 的核心交付物，未来 F5/F6 都挂此命名空间
- 容易扩展：未来加 `cockpit scenario archive` 或 `cockpit scenario list` 不用改顶层

### 6.2 为什么不走 3 条独立短命令（如 `cockpit radar`）？

- radar/assistant/health 是 scenario 子集, 不应与 search/research 等顶级
  命令平级
- 保持 `cockpit <domain>` 的一致范式（已有 `cockpit research`, `cockpit vault`）

## 7. 红线遵守

- ✅ 用户通过 cockpit 一键跑 3 scenario（不需切仓）
- ✅ 无需理解仓边界（用户只看到 `cockpit scenario X`）
- ✅ 1 条统一命令 + 3 子命令，不重复发明
