# BET-Y1Q2-T6-03 Retro: bin 脚本清理

## 完成日期
2026-08-08

## 交付物
- `bin/gac/bin-orphan-scan.py`: 零引用脚本扫描 + 归档工具
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
