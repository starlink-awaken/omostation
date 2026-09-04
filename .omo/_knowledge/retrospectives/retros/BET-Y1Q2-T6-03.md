---
lifecycle: history
owner: governance-team
last_updated: 2026-08-11
bet_id: BET-Y1Q2-T6-03
title: "BET-Y1Q2-T6-03 Retro: bin 脚本清理"
type: retro
---

# BET-Y1Q2-T6-03 Retro: bin 脚本清理

## 完成日期
2026-08-08

## 交付物
- `bin/_archive/2026-08-25-dfsq-quota/bin-orphan-scan.py`: 零引用脚本扫描 + 归档工具
- 77 个零引用脚本归档到 `bin/_archive/`
- 脚本数: 360 → 283 (活跃)

## 扫描方法
1. 递归扫描 bin/ 下所有 .py/.sh
2. 排除 _lib.py, test_*.py, __init__.py, _archive/
3. 检查引用: Makefile, .githooks/, .github/workflows/, AGENTS.md, CLAUDE.md, README.md, 其他 bin/ 脚本
4. 零引用 → 归档

## 教训
- 扫描工具本身也被归档了 (自引用问题), 需手动恢复
- 两个 gate 引用的脚本 (check-llm-gateway-only.py, mcp-tool-data-complete.py) 被误归档, 因 gate 通过字符串拼接引用, 静态扫描检测不到
- 未来应在 gate CHECKS_LIST 中显式声明依赖, 而非动态构造路径

## 验证
- `bin-orphan-scan.py --json` 输出扫描结果
- gate 引用的脚本已恢复
- 归档不影响 CI (gate 全绿)

## 2026-08-11 纠正性复验

原“gate 全绿”证据不可采信：`ci-local-fast` 在 `/bin/sh` 下以
`producer | sed` 执行四个检查，producer 非零状态被 `sed` 的零状态覆盖。
该问题不推翻已归档脚本的交付事实，但使本 BET 的验收链失真。

ADR-0407 已将目标改为真实退出码 runner，并把 Ruff 分为“26 条已审阅
CI 级 baseline + path/code/message bucket 净新增硬阻断”和“997 条全量债务显式 advisory”。纠正后
验收以失败注入测试和真实 `make ci-local-fast` 的 blocking 结果为准；不得再
把 advisory 债务描述为全绿。
