# workspace→cockpit 命名 SSOT 统一 (架构师视角系统性债)

> **Upstream**: MS-PRODUCT-WALKTHROUGH-V3 (双视角走查, 架构师维度: 命名 SSOT 碎片根治)
> **Appetite:** 0.5 day

## 背景与上下文

产品走查 v3 (架构师视角) 发现 cockpit 历史叫 `workspace`, 改名不彻底, **src 中 118 处命令提示残留 `workspace XXX`** (7 文件: cockpit_mcp/l4bridge/importer/base/research/quickstart/status)。用户照提示敲 `workspace status` → command not found。这是命名 SSOT 碎片 (同一 CLI 两个名字), 系统性技术债。

## 目标

- src 中 `workspace <command>` 命令提示 → `cockpit <command>` (精确匹配 38 子命令)
- 不动 `~/.workspace` 路径 / workspace 概念词 / 测试断言 (测试单独 bet)
- 用户提示一致, 不再 command not found

## NoGOS (YAGNI)

- 不改测试断言 (test_quickstart assert "workspace research" 等单独 bet, 避免本轮破坏测试)
- 不改 ~/.workspace 目录名 (路径 SSOT, 另议)
- 不改 console_scripts 入口 (cockpit 已是入口)

## 验收

- [ ] `python3 /tmp/fix_workspace_naming.py --apply` 精确替换 src 命令提示
- [ ] cockpit pytest 通过 (非测试文件改动, 测试不受影响)
- [ ] `cockpit profile` / `cockpit daily` 提示全显 cockpit
