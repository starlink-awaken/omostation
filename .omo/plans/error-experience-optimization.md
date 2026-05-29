# 错误体验优化计划

> 目标：让 workspace CLI 的每个错误消息都告诉用户「错在哪里 + 怎么办」

## 问题现状

| 错误类型 | 当前表现 | 用户感知 |
|---------|---------|---------|
| 无参数 | argparse usage 英文 | 不知道正确用法 |
| 研究不存在 | "未找到" | 不知道有哪些可用 ID |
| 搜索无结果 | "没有匹配" | 不确定是否真的没有 |
| 服务不可用 | 502/超时 | 不知道怎么修 |
| 依赖缺失 | Python traceback | 看不懂 |

## 改动清单

### W4.1 argparse 中文错误 (cli.py)

**改动**：自定义 ArgumentParser 的 error() 方法，拦截 argparse 原生英文错误，替换为中文友好消息 + 用法提示。

**结果**：`workspace research` → 显示「请指定研究主题。试试: workspace research "你的主题"」

### W4.2 数据不存在时自动提示 (cli.py)

**改动**：cmd_research_open 和 cmd_research_ask 中，当 `get_research(id)` 返回 None 时，自动调用 `list_research(limit=3)` 显示最近可用 ID。

**结果**：`workspace research --open 99` → 「未找到 ID=99。最近的研究: [1] transformer basics, [2] ...」

### W4.3 搜索无结果时给出建议 (cli.py)

**改动**：cmd_research_search 中，当搜索结果为空时，显示搜索词 + 建议：「试试不同的关键词，或者 workspace research --list 浏览所有」

**结果**：`workspace research --search "xyz"` → 「没有找到匹配 xyz 的研究。试试: workspace research --list」

### W4.4 服务不可用时带修复建议 (cli.py)

**改动**：cmd_dashboard 中，当 uvicorn 启动失败或 HTTP 请求超时时，显示：「Dashboard 启动失败。试试: cd agora && .venv/bin/python -m uvicorn agora.web.app:app」

**结果**：Dashboard 错误不再是 502 blank page，而是清晰的修复指导。

## 验证方法

每条改动后:
```bash
python3 -m workspace research           # 无参数 → 中文提示
python3 -m workspace research --open 99  # 不存在 → 提示可用 ID
python3 -m workspace research --search "!!!" # 无结果 → 搜索建议
```

## 执行顺序

1. W4.1 → 2. W4.2 → 3. W4.3 → 4. W4.4
