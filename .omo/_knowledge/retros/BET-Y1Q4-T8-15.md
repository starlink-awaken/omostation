---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T8-15
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-05
type: ephemeral
---

# BET-Y1Q4-T8-15 retro — 冷启动 Fast-path 与全域 Lazy Import

## What changed

- **基线测量**（-X importtime 定位）：`import cockpit.cli` 159ms，大头为
  `commands.base` 链 76ms（base 顶部拖 rich.markdown→markdown_it 14ms +
  urllib.request 14ms + rich.console/http.client）——由 26 个顶部贪婪
  `from .commands.X import` 中的任一触发；`create_parser` 全量注册 60ms。
- **改造 1（全域懒加载）**：25 个 `commands.*` 顶部贪婪 import 机械转为
  lazy wrapper 函数（AST 定位 + 逆序替换，沿用仓内既有 cmd_ssb 模式，
  dispatch 字典零改动）；`commands.base` 的 `_SCRIPT_DIR`/`_find_cli`
  改 lazy 代理 + 4 处引用点函数内 import。`import cockpit.cli`
  **159ms → 60ms**，base/audit/agora 等不再进入 sys.modules。
- **改造 2（Fast-path 直通）**：`telemetry`/`completion` 无 flag 简单形态
  跳过全量 parser 注册直达命令（带 flag 走全量路径保持语义）。端到端
  `cockpit telemetry status` **~240ms → 67ms（优化 72% > 50%）**。
- **测试**：test_fast_path.py 4 个（贪婪加载断言/import 预算 120ms/
  fast-path 端到端 <200ms/懒化后 dispatch 可达）；既有回归 30 个全过，
  ruff clean（转换顺带修复主 checkout 4 处 import 排序）。

## Q3 (打假)

- **流程违规自曝**: 本 bet 的代码改造先于 agent-workflow start 执行（跳过了
  claim 门），complete 的 vision→retro 链校验以 missing_bet_binding 正确
  拦截后补 start/claim。次序违规已记入 error-knowledge 素材——治理链的
  事后拦截有效，但流程纪律不应依赖兜底。

- 首轮只 lazy 化 audit+base 不够：base 被 24 个 commands 共用，**任一贪婪
  import 都触发全链**——懒加载必须全域一致，没有 80/20 捷径。
- 机械转换器两个教训：多行括号 import 的文本替换丢换行；正则改写会误伤
  import 语句内的同名符号。AST 定位边界 + 行级改写 + 改后 ast.parse 验证
  是可靠组合。
- fast-path 只覆盖无 flag 形态是刻意的：Namespace 直构容易漏全局 flag
  级联语义，保守覆盖高频简单调用。

## Q4 (遗留)

- create_parser 60ms 对非 fast 命令仍存在——argparse choices 全集注册，
  结构性瓶颈，后续可评估命令组按需注册。
