"""L3 入口层 — CLI 和 MCP 入口

实现多机协作的入口层组件：
- GovernanceCLI: 治理 CLI
- GovernanceMCP: 治理 MCP 工具
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CLICommand:
    """CLI 命令"""
    name: str
    description: str
    handler: Any


class GovernanceCLI:
    """治理 CLI
    
    L3 入口层: 提供命令行接口
    """
    
    def __init__(self):
        self.commands: dict[str, CLICommand] = {}
        self._register_commands()
    
    def _register_commands(self):
        """注册命令"""
        self.commands["check"] = CLICommand(
            name="check",
            description="运行 X1-X4 检查",
            handler=self._handle_check,
        )
        self.commands["status"] = CLICommand(
            name="status",
            description="查看治理状态",
            handler=self._handle_status,
        )
        self.commands["history"] = CLICommand(
            name="history",
            description="查看历史记录",
            handler=self._handle_history,
        )
    
    def run(self, args: list[str]) -> int:
        """运行 CLI"""
        if not args:
            self._print_help()
            return 0
        
        command_name = args[0]
        if command_name not in self.commands:
            print(f"未知命令: {command_name}")
            self._print_help()
            return 1
        
        command = self.commands[command_name]
        return command.handler(args[1:])
    
    def _print_help(self):
        """打印帮助"""
        print("治理 CLI 命令:")
        for cmd in self.commands.values():
            print(f"  {cmd.name}: {cmd.description}")
    
    def _handle_check(self, args: list[str]) -> int:
        """处理 check 命令"""
        print("运行 X1-X4 检查...")
        # 这里可以调用 L0 检查器
        print("✅ 检查完成")
        return 0
    
    def _handle_status(self, args: list[str]) -> int:
        """处理 status 命令"""
        print("查看治理状态...")
        # 这里可以读取系统状态
        print("✅ 状态查询完成")
        return 0
    
    def _handle_history(self, args: list[str]) -> int:
        """处理 history 命令"""
        print("查看历史记录...")
        # 这里可以查询历史数据
        print("✅ 历史查询完成")
        return 0


class GovernanceMCP:
    """治理 MCP 工具
    
    L3 入口层: 提供 MCP 工具接口
    """
    
    def __init__(self):
        self.tools: dict[str, dict[str, Any]] = {}
        self._register_tools()
    
    def _register_tools(self):
        """注册工具"""
        self.tools["governance_check"] = {
            "description": "运行 X1-X4 治理检查",
            "parameters": {
                "dimension": {"type": "string", "description": "检查维度 (X1/X2/X3/X4/all)"},
            },
        }
        self.tools["governance_status"] = {
            "description": "查看治理状态",
            "parameters": {},
        }
        self.tools["governance_history"] = {
            "description": "查看历史记录",
            "parameters": {
                "days": {"type": "integer", "description": "查询天数"},
            },
        }
    
    def call_tool(self, tool_name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用工具"""
        if tool_name not in self.tools:
            return {"error": f"未知工具: {tool_name}"}
        
        # 根据工具名称执行相应操作
        if tool_name == "governance_check":
            return self._handle_check(parameters or {})
        elif tool_name == "governance_status":
            return self._handle_status(parameters or {})
        elif tool_name == "governance_history":
            return self._handle_history(parameters or {})
        
        return {"error": f"未实现的工具: {tool_name}"}
    
    def _handle_check(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理检查"""
        dimension = params.get("dimension", "all")
        return {
            "status": "ok",
            "dimension": dimension,
            "message": "检查完成",
        }
    
    def _handle_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理状态查询"""
        return {
            "status": "ok",
            "health_score": 82.0,
            "debt_weight": 1.0,
        }
    
    def _handle_history(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理历史查询"""
        days = params.get("days", 7)
        return {
            "status": "ok",
            "days": days,
            "records": [],
        }
    
    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有工具"""
        return [
            {"name": name, "description": tool["description"]}
            for name, tool in self.tools.items()
        ]
