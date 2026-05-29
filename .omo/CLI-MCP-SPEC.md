# CLI & MCP 标准化规范 v1

## 一、CLI 通用规范

### 1.1 入口命名

所有工具统一使用命令名，不使用 `python -m`：

```
eidos               # ✅ 统一命令名
kos                 # ✅ 统一命令名
ontoderive           # ✅ 统一命令名
minerva research     # ✅ 统一命令名
agora               # ✅ 统一命令名
```

### 1.2 输出格式

所有 CLI 支持 `--json` 输出：

```bash
eidos list --json
kos search "量子" --json
ontoderive derive --eidos --json
```

JSON 格式统一为：

```json
{
  "tool": "eidos",
  "version": "0.1.0",
  "command": "list",
  "timestamp": "2026-05-21T10:00:00Z",
  "data": { ... }
}
```

### 1.3 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 参数错误 |
| 3 | 输入校验失败 |

### 1.4 Pipeline 协议

所有工具支持：
```
--pipeline-input <file>   输入文件
--pipeline-output <file>  输出文件
PIPELINE_MODE=1           环境变量（自动关闭人类输出）
```

## 二、MCP 服务规范

### 2.1 命名

```
eidos-mcp        Schema 定义/校验
kos-mcp          知识存储/搜索
minerva-mcp      Deep Research
ontoderive-mcp   推理引擎
agora-mcp        服务路由
```

### 2.2 协议

使用 FastMCP / stdio 传输：
```python
# 每个工具的 MCP 入口
@mcp.tool("eidos_validate")
def validate(data: str) -> str: ...

@mcp.tool("kos_search")
def search(query: str, meta_type: str = "") -> str: ...
```

### 2.3 工具命名

```
eidos_validate    校验 Schema
eidos_meta        查询元模型
kos_ingest        注入知识
kos_search        搜索知识
minerva_research  深度研究
ontoderive_derive 知识推导
```

## 三、代码结构规范

### 3.1 标准入口结构

```python
"""tool-name CLI — brief description."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool-name")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--pipeline-input", help="管线输入文件")
    parser.add_argument("--pipeline-output", help="管线输出文件")
    sub = parser.add_subparsers(dest="command")
    # ... subcommands
    return parser


def output_json(data: dict) -> None:
    """Unified JSON output for all commands."""
    print(json.dumps({"tool": "eidos", "version": "0.1.0", "data": data}, indent=2))


def output_human(data: dict) -> None:
    """Unified human-readable output."""
    pass  # tool-specific


def main():
    parser = build_parser()
    args = parser.parse_args()
    # Pipeline mode check
    if os.environ.get("PIPELINE_MODE") or args.pipeline_output:
        args.json = True
    # Execute
    result = execute(args)
    if args.json:
        output_json(result)
    else:
        output_human(result)


if __name__ == "__main__":
    main()
```
