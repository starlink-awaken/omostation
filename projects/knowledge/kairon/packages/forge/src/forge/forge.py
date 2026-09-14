#!/usr/bin/env python3
from __future__ import annotations

"""
ai_toolbox.py — Forge 统一命令行入口

将所有离散脚本整合为单一 CLI。

用法:
  forge <command> [args...]        # 全局命令（推荐）
  forge <command> [args...]   # 或项目内

命令:
  # 日常操作
  health            — 运行健康检查
  status            — 项目状态概览
  schedule          — 配置每日巡更定时任务
  routine           — 显示每日例行流程

  # 服务模式
  serve-mcp         — 启动 MCP 服务器（stdio/SSE）
  serve-api         — 启动 HTTP REST API

  # 即时捕获（10 秒）
  capture           — 记下新工具（sediment-capture 别名）

  # 图谱
  build-graph       — 构建知识图谱
  query-graph       — 查询图谱
  recommend         — 知识推荐
  discover-links    — 自动关联发现
  graph-viz         — 图谱可视化（HTML/Mermaid）
  sync-registry     — 同步工具注册表（生成 Markdown 快照）

  # 嗅探
  sniff-local       — 本地嗅探
  sniff-network     — 网络嗅探（GitHub Release）

  # 洞察
  insight           — 洞察引擎（缺口分析 / 周报 / 组合分析）
  classify          — 请求分类器

  # 沉淀
  sediment          — 工具沉淀管理（capture/detect）
  sediment-capture  — 显式捕获 Skill（sediment 别名）
  sediment-detect   — 频率检测沉淀

  # 反熵
  sunrise           — 候选池管理
  sunset            — 日落条款
  converge          — 收敛检查
  entropy           — 反熵统一入口（sunrise/sunset/converge）

  # 集成
  kos-bridge        — KOS 桥接
  sync-agora        — Agora 同步
  rss-manager       — RSS 源管理（list/enable/disable/sync）
  check-updates     — 检查工具更新
  discover-ecosystem — 发现新工具/服务

  # 安装与环境
  sniff             — 环境嗅探（检测依赖/工具/集成点）
  install           — 一键安装器（symlink/cron/MCP/deps）

  # 维护
  verify            — 运行验证（phase1/2/3/all）
  upgrade-schema    — Schema 升级
  asset             — 资产清册（list/register/check/scan/export）
  cron              — 定时任务管理（list/register/enable/disable/status/reminder）

  # 看门狗 & 面板
  watch             — 启动健康检查看门狗守护进程
  dashboard         — 启动 Web 仪表盘（基于 http_api.py）

  # 别名
  help              — 显示此帮助
"""

import argparse
import fcntl
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge.forge_config import ADAPTERS_DIR as ADAPTERS  # type: ignore[import-not-found]
from forge.forge_config import FORGE_ROOT as TOOLBOX
from forge.forge_config import SCRIPTS_DIR as SCRIPTS
from forge.forge_config import SRC

COMMANDS: dict = {
    "build-graph": ("script", str(SCRIPTS / "build-graph.sh"), ""),
    "query-graph": ("python", str(SRC / "query_graph.py"), ""),
    "recommend": ("python", str(SRC / "recommend.py"), ""),
    "discover-links": ("python", str(SRC / "discover_links.py"), ""),
    "graph-viz": ("python", str(SRC / "graph_viz.py"), ""),
    "sniff-local": ("python", str(SRC / "sniff.py"), ""),
    "sniff-network": ("python", str(SRC / "sniff.py"), ""),
    "insight": ("python", str(SRC / "insight_report.py"), ""),
    "classify": ("script", str(ADAPTERS / "classify.sh"), ""),
    "sediment-capture": ("python", str(SRC / "sediment.py"), ""),
    "sediment-detect": ("python", str(SRC / "sediment.py"), ""),
    "kos-bridge": ("script", str(ADAPTERS / "kos-bridge.sh"), ""),
    "sync-agora": ("script", str(ADAPTERS / "sync-agora.sh"), ""),
    "sync-registry": ("python", str(SRC / "sync_registry.py"), ""),
    "check-updates": ("python", str(SRC / "sniff.py"), ""),
    "discover-ecosystem": ("python", str(SRC / "discover_ecosystem.py"), ""),
    "rss-manager": ("python", str(SCRIPTS / "rss-manager.py"), ""),
    "upgrade-schema": ("python", str(TOOLBOX / "scripts" / "upgrade-schema-v2.py"), ""),
    "asset": ("python", str(SRC / "asset_cli.py"), ""),
    "cron": ("python", str(SRC / "cron_manager.py"), ""),
    "entropy": ("python", str(SRC / "entropy.py"), ""),
    "watchdog": ("python", str(SRC / "watchdog.py"), ""),
}

VERIFY_COMMANDS = {
    "phase1": "phase1",
    "phase2": "phase2",
    "phase3": "phase3",
}


def cmd_status() -> None:
    """项目状态概览"""
    reg_path = TOOLBOX / "tools-registry.json"
    try:
        with reg_path.open("rb") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            reg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("❌ 无法读取 tools-registry.json")
        return
    schema = reg.get("schema_version", "?")
    tools = len(reg["tools"])
    events = len(reg.get("event_log", []))
    active = sum(1 for t in reg["tools"] if t.get("status") == "active")
    tel = sum(1 for t in reg["tools"] if t.get("telemetry", {}).get("use_count", 0) > 0)
    candidates = sum(1 for t in reg["tools"] if t.get("status") == "candidate")

    g_path = TOOLBOX / "graph" / "graph.json"
    g_n = g_e = 0
    if g_path.exists():
        g = json.loads(g_path.read_text())
        g_n, g_e = g["stats"]["total_nodes"], g["stats"]["total_edges"]

    print(f"Forge  {schema}  |  {tools} 工具 ({active} 活跃, {candidates} 候选)")
    print(f"  event_log: {events} 条  |  telemetry: {tel} 工具")
    print(f"  图谱: {g_n} 节点 / {g_e} 边")
    print(f"  路径: {TOOLBOX}")


def cmd_capture(args: list[str]) -> None:
    """记下新工具（sediment-capture 的友好入口）"""
    if not args or args[0] in ("--help", "-h"):
        print("用法: ./forge.sh capture --name <id> --desc '<描述>' --steps '[步骤]'")
        print()
        print("记下一个新工具或操作模式。生成 SKILL.md 并注册到注册表。")
        print("这是沉淀引擎最好的数据源——比频率检测更可靠。")
        print()
        print("示例:")
        print('  forge capture --name "check-mcp-versions" \\')
        print('    --desc "查看所有 MCP 服务的版本" \\')
        print('    --steps \'["cd Workspace/agora", "python3 -m agora version"]\'')
        return

    _run_script("sediment-capture", args)


def cmd_health(args: list[str] | None = None) -> None:
    """健康检查"""
    subprocess.run([sys.executable, str(SRC / "health_check.py")] + (args or []), cwd=TOOLBOX)


def cmd_list(args: list[str] | None = None) -> None:
    """List registered tools as JSON."""
    from mcp_server import list_tools  # type: ignore[import-not-found]

    limit = 50
    if args:
        if args and args[0] in {"--help", "-h"}:
            print("用法: forge list [limit]")
            return
        try:
            limit = int(args[0])
        except ValueError:
            print(f"❌ 无效 limit: {args[0]}")
            sys.exit(1)

    print(json.dumps({"tools": list_tools(limit=limit)}, ensure_ascii=False))


def cmd_dashboard(_args: list[str] | None = None) -> None:
    """启动 Web 仪表盘"""
    import webbrowser

    url = "http://localhost:8766"
    pid_file = SRC / ".dashboard.pid"
    dashboard_path = SRC / "dashboard.html"

    # 杀掉旧的 API 进程
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(0.5)
        except (ProcessLookupError, ValueError, OSError):
            pass

    print(f"🌐 打开仪表盘: {url}")
    print(f"   仪表盘: file://{dashboard_path}")
    webbrowser.open(f"file://{dashboard_path}")
    proc = subprocess.Popen(
        [sys.executable, str(SRC / "http_api.py")],
        cwd=TOOLBOX,
    )
    pid_file.write_text(str(proc.pid))
    print(f"   API 已启动 (PID: {proc.pid})")


def cmd_verify(args: list[str]) -> None:
    """运行验证"""
    phase = args[0] if args else "all"
    if phase == "all":
        for name, path in VERIFY_COMMANDS.items():
            print(f"\n--- Verify {name} ---")
            subprocess.run(["bash", path], cwd=TOOLBOX)
    elif phase in VERIFY_COMMANDS:
        subprocess.run(["bash", VERIFY_COMMANDS[phase]], cwd=TOOLBOX)
    else:
        print(f"❌ 未知阶段: {phase}，可选: {', '.join(VERIFY_COMMANDS.keys())}, all")
        sys.exit(1)


def cmd_schedule(args: list[str]) -> None:
    """配置每日巡更定时任务"""
    if "--show" in args:
        print("当前 cron 配置:")
        subprocess.run(["crontab", "-l"], check=False)
        return

    health_script = str(SCRIPTS / "health-check.sh")
    cron_line = f"0 8 * * * bash {health_script} >> {TOOLBOX}/logs/health.log 2>&1"

    print("=== 配置每日巡更 ===")
    print(f"建议 cron: {cron_line}")
    print()
    print("要添加到 crontab:")
    print(f"  (crontab -l 2>/dev/null; echo '{cron_line}') | crontab -")
    print()
    print("或手动运行每天:")
    print("  forge health")
    print()
    print("日常流程:")
    print("  每天早上8点:  forge health    # ~5 分钟")
    print("  发现新工具时:  forge capture   # ~10 秒")
    print("  两周后:       forge status     # 看 event_log + telemetry")


def cmd_routine() -> None:
    """显示每日例行流程"""
    print("=== Forge 日常操作 ===")
    print()
    print("每天早上")
    print("  ─────────────────────────────────")
    print("  forge health            # 5 分钟健康检查")
    print("  检查 event_log 了解昨日变更        # 1 分钟")
    print()
    print("随时")
    print("  ─────────────────────────────────")
    print("  forge capture \\         # 10 秒记下新工具")
    print('    --name "tool-name" \\')
    print('    --desc "做什么的" \\')
    print("    --steps '[使用步骤]'")
    print()
    print("  forge sniff-local       # 扫描本地新工具")
    print("  forge sniff-network     # 扫描在线新版本")
    print()
    print("每周一")
    print("  ─────────────────────────────────")
    print("  forge insight --weekly   # 自动周报")
    print("  forge insight --gaps     # 能力缺口分析")
    print()
    print("两周后")
    print("  ─────────────────────────────────")
    print("  forge status             # 看数据趋势")
    print("  event_log 和 telemetry 会告诉你    # 决定 Phase 5 方向")


def cmd_sniff(*_: object) -> None:
    """环境嗅探 — 检测当前系统有哪些工具/依赖可用"""
    print("=== Forge 环境嗅探 ===")
    print()

    items = []

    # 1. Python 环境
    py_ver = sys.version.split()[0]
    items.append(("python3", py_ver, True))

    # 2. fastmcp（MCP 服务依赖）
    try:
        _fm = __import__("fastmcp")
        items.append(("fastmcp", getattr(_fm, "__version__", "?"), True))
    except ImportError:
        items.append(("fastmcp", "未安装", False))

    # 3. Claude Desktop
    claude_config = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if claude_config.exists():
        items.append(("Claude Desktop", "已安装", True))
    else:
        items.append(("Claude Desktop", "未安装", False))

    # 4. 全局 forge 命令
    ai_bin = shutil.which("forge")
    if ai_bin:
        if str(TOOLBOX) in str(Path(ai_bin).resolve()):
            items.append(("forge 命令", ai_bin, True))
        else:
            items.append(("forge 命令", f"{ai_bin} (不同源)", False))
    else:
        items.append(("forge 命令", "未安装", False))

    # 5. ~/.local/bin 在 PATH
    local_bin = Path.home() / ".local/bin"
    in_path = str(local_bin) in os.environ.get("PATH", "")
    items.append(("~/.local/bin", "在 PATH 中" if in_path else "不在 PATH", in_path))

    # 6. cron
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        has_cron = r.returncode == 0
        items.append(("定时任务", "已配置" if has_cron else "未配置", has_cron))
    except Exception:
        items.append(("定时任务", "不可用", False))

    # 7. Git
    git_avail = shutil.which("git") is not None
    items.append(("git", "可用" if git_avail else "不可用", git_avail))

    # 8. gh (GitHub CLI)
    gh_avail = shutil.which("gh") is not None
    items.append(("gh (GitHub CLI)", "可用" if gh_avail else "不可用", gh_avail))

    # 9. MCP 服务状态
    mcp_ok = (SRC / "mcp_server.py").exists()
    items.append(("MCP 服务", "就绪" if mcp_ok else "缺失", mcp_ok))

    # 10. 图谱数据
    graph_ok = (TOOLBOX / "graph" / "graph.json").exists()
    items.append(("知识图谱", "已构建" if graph_ok else "未构建", graph_ok))

    # 打印结果
    for name, status, ok in items:
        icon = "✅" if ok else ("⚠️" if "未" in str(status) else "❌")
        print(f"  {icon} {name:20s} {status}")

    ok_count = sum(1 for _, _, ok in items if ok)
    print(f"\n  环境评分: {ok_count}/{len(items)} 项就绪")

    if ok_count < len(items):
        print("\n运行 forge install 选择安装缺失组件")


def cmd_market(args: list[str]) -> None:
    """GitHub 工具市场 — install/list/remove"""
    from forge.market import cli as _market_cli

    sys.exit(_market_cli(args))


def cmd_install(args: list[str]) -> None:
    """交互式安装器 — 嗅探 + 安装"""
    # 如果指定了具体项，直接安装
    if args:
        item = args[0]
        if item in ("symlink", "command"):
            _install_symlink()
        elif item in ("mcp", "mcp-config"):
            _install_mcp_config()
        elif item in ("cron", "crontab"):
            _install_cron()
        elif item in ("deps", "dependencies"):
            _install_deps()
        elif item == "all":
            _install_symlink()
            _install_mcp_config()
            _install_cron()
            _install_deps()
        else:
            print(f"❌ 未知安装项: {item}")
            print("可选: symlink, mcp, cron, deps, all")
        return

    # 交互模式
    print("=== Forge 安装器 ===")
    print()
    print("可安装的组件:")
    print()

    available = []

    # 检查各组件状态
    ai_bin = shutil.which("forge")
    need_symlink = not ai_bin or str(TOOLBOX) not in str(Path(ai_bin).resolve())
    available.append((need_symlink, "1", "全局命令", "创建 forge 到 ~/.local/bin", _install_symlink))

    claude_config = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    mcp_installed = False
    if claude_config.exists():
        try:
            cfg = json.loads(claude_config.read_text())
            mcp_installed = "forge" in cfg.get("mcpServers", {})
        except Exception:
            pass
    available.append((not mcp_installed, "2", "MCP 配置", "注册到 Claude Desktop", _install_mcp_config))

    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        has_cron = "health" in r.stdout
    except Exception:
        has_cron = False
    available.append((not has_cron, "3", "每日巡更", "配置 cron 定时健康检查", _install_cron))

    try:
        __import__("fastmcp")
        need_deps = False
    except ImportError:
        need_deps = True
    available.append((need_deps, "4", "Python 依赖", "安装 fastmcp 等依赖", _install_deps))

    for need, num, name, desc, _ in available:
        icon = "❌" if need else "✅"
        print(f"  [{num}] {icon} {name:15s} {desc}")

    print()
    print("  [a] 全部安装")
    print("  [q] 退出")
    print()

    # 非交互模式：如果没有任何需要安装的，直接退出
    if not any(need for need, _, _, _, _ in available):
        print("✅ 所有组件已就绪，无需安装")
        return

    # 简单处理：用第一个参数作为选择
    choice = input("请选择 [1-4/a/q]: ").strip().lower() if sys.stdin.isatty() else "q"
    if choice == "a":
        for _, _, _, _, fn in available:
            fn()
    elif choice in ("1", "2", "3", "4"):
        idx = int(choice) - 1
        if 0 <= idx < len(available):
            _, _, _, _, fn = available[idx]
            if callable(fn):
                fn()
    elif choice == "q":
        return
    else:
        print("未知选择，退出")


def _install_symlink() -> None:
    """安装全局 forge 命令"""
    local_bin = Path.home() / ".local/bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    target = local_bin / "forge"
    src_path = SRC / "ai_toolbox.py"
    target.unlink(missing_ok=True)
    target.symlink_to(src_path)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"✅ 已创建: {target} → {src_path}")
    print("   现在可以在终端直接使用: forge help")


def _install_mcp_config() -> None:
    """注册 MCP 到 Claude Desktop"""
    claude_config = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    claude_config.parent.mkdir(parents=True, exist_ok=True)

    # 写入前备份
    if claude_config.exists():
        backup = claude_config.with_suffix(".json.bak")
        shutil.copy2(claude_config, backup)

    mcp_entry = {
        "command": sys.executable,
        "args": [str(TOOLBOX / "server" / "mcp_server.py")],
    }

    if claude_config.exists():
        cfg = json.loads(claude_config.read_text())
    else:
        cfg = {}

    if "mcpServers" not in cfg:
        cfg["mcpServers"] = {}
    cfg["mcpServers"]["forge"] = mcp_entry
    claude_config.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print("✅ 已注册 MCP 到 Claude Desktop")
    print(f"   配置: {claude_config}")
    print("   重启 Claude Desktop 生效")


def _install_cron() -> None:
    """配置每日健康检查定时任务"""
    health_script = str(SCRIPTS / "health-check.sh")
    log_file = str(TOOLBOX / "logs" / "health.log")
    cron_line = f"0 8 * * * bash {health_script} >> {log_file} 2>&1"

    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        existing = r.stdout if r.returncode == 0 else ""
        if cron_line not in existing:
            new_cron = existing.strip() + "\n" + cron_line + "\n"
            p = subprocess.run(["crontab"], input=new_cron, text=True, capture_output=True, timeout=5)
            if p.returncode == 0:
                print("✅ 已添加定时任务: 每天 8:00 运行健康检查")
                print(f"   日志: {log_file}")
            else:
                print("⚠️  无法添加 crontab，请手动添加:")
                print(f"   {cron_line}")
        else:
            print("✅ 定时任务已存在，无需重复添加")
    except Exception as e:
        print(f"⚠️  无法配置定时任务: {e}")
        print(f"   手动添加: (crontab -l; echo '{cron_line}') | crontab -")


def _install_deps() -> None:
    """安装 Python 依赖"""
    deps = ["fastmcp"]
    for dep in deps:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", dep, "--quiet", "--break-system-packages"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0:
            print(f"✅ 已安装: {dep}")
        else:
            print(f"⚠️  安装 {dep} 失败: {r.stderr.strip()[:80]}")


def cmd_help() -> None:
    print(__doc__)
    print("常用:")
    print("  forge health             # 每日巡更（5 分钟）")
    print("  forge sniff              # 环境嗅探")
    print("  forge install            # 一键安装器")
    print("  forge capture            # 记新工具（10 秒）")
    print("  forge market             # 工具市场 install/list/remove")
    print("  forge status             # 看数据")
    print("  forge routine            # 日常流程")
    print("  forge schedule           # 配置定时任务")
    print("  forge rss               # RSS 源管理（list/enable/disable/sync）")
    print("  forge cron               # 定时任务管理（list/enable/disable/status）")
    print("  forge entropy            # 反熵系统（sunrise/sunset/converge）")
    print("  forge verify all         # 全量验证")
    print()


def _discover_scripts() -> dict:
    """Auto-discover shell scripts from scripts/ and adapters/ (whitelist-based)."""
    whitelist = {"run-pipeline.sh", "design-pipeline.sh", "asset-watch.sh", "pipeline-research.sh"}
    discovered: dict = {}
    for d in [SCRIPTS, ADAPTERS]:
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix == ".sh" and f.name in whitelist:
                    name = f.stem.replace("_", "-").replace(" ", "-")
                    discovered[name] = str(f)
    return discovered


_DISCOVERED_SCRIPTS = _discover_scripts()


def _run_script(name: str, args: list[str]) -> None:
    entry = COMMANDS.get(name)
    if not entry:
        script_path = _DISCOVERED_SCRIPTS.get(name)
        if script_path:
            subprocess.run(["bash", script_path] + args, cwd=TOOLBOX)
            return
        print(f"❌ 未知命令: {name}")
        print("运行 ./forge.sh help")
        sys.exit(1)
    cmd_type, path, _ = entry
    if cmd_type == "script":
        subprocess.run(["bash", str(path)] + args, cwd=TOOLBOX)
    elif cmd_type == "python":
        subprocess.run([sys.executable, str(path)] + args, cwd=TOOLBOX)


ALIASES = {
    "build": "build-graph",
    "query": "query-graph",
    "reco": "recommend",
    "links": "discover-links",
    "viz": "graph-viz",
    "capture": "sediment-capture",
    "detect": "sediment-detect",
    "kos": "kos-bridge",
    "agora": "sync-agora",
    "updates": "check-updates",
    "ecosystem": "discover-ecosystem",
    "rss": "rss-manager",
    "watch": "watchdog",
}


def _setup_completion() -> bool:
    """设置 Bash/Zsh 自动补全（通过 argcomplete）。"""
    try:
        import argcomplete  # type: ignore[import-not-found]

        registry = _build_command_map()
        parser = argparse.ArgumentParser(prog="forge", add_help=False)
        sub = parser.add_subparsers()
        for name in sorted(registry):
            sub.add_parser(name, add_help=False)
        argcomplete.autocomplete(parser)
        return True
    except ImportError:
        return False


def main() -> None:
    args = sys.argv[1:]

    # 自动补全（在帮助和命令解析之前）
    if "_FORGE_COMPLETE" in os.environ:
        _setup_completion()

    if not args or args[0] in ("--help", "-h", "help"):
        cmd_help()
        return

    # completion install
    if args[0] == "completion":
        _install_completion()
        return

    cmd, cmd_args = args[0], args[1:]
    registry = _build_command_map()
    entry = registry.get(cmd)

    if entry is None:
        print(f"❌ 未知命令: {cmd}")
        print("运行 forge help 查看可用命令")
        sys.exit(1)

    kind = entry[0]

    if kind == "noargs":
        entry[1]()
    elif kind == "args":
        entry[1](cmd_args)
    elif kind == "serve":
        target = entry[1]
        server = (TOOLBOX / "server" / "mcp_server.py") if target == "mcp" else (SRC / "http_api.py")
        subprocess.run([sys.executable, str(server)] + cmd_args)
    elif kind == "script":
        _run_script_entry(entry[1], entry[2], cmd_args)


def _install_completion() -> None:
    """安装 CLI 自动补全到 shell rc 文件。"""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        rc = Path.home() / ".zshrc"
        line = 'eval "$(register-python-argcomplete forge)"'
    elif "bash" in shell:
        rc = Path.home() / ".bashrc"
        line = 'eval "$(register-python-argcomplete forge)"'
    else:
        print("❌ 不支持的 shell，仅支持 bash/zsh")
        print('   手动添加: eval "$(register-python-argcomplete forge)"')
        return

    if not rc.exists():
        rc.write_text("")
    current = rc.read_text()
    if line in current:
        print(f"✅ 补全已在 {rc} 中")
        return

    with rc.open("a") as f:
        f.write(f"\n# Forge CLI 自动补全\n{line}\n")
    print(f"✅ 已添加补全到 {rc}")
    print("   运行以下命令立即生效:")
    print(f"   source {rc}")


def _build_command_map() -> dict:
    """构建统一命令注册表。"""
    c: dict = {}

    def reg(name: str, kind: str, *data: Any) -> None:
        c[name] = (kind, *data)

    # 1. 内建命令
    for name in ("status", "routine"):
        reg(name, "noargs", globals()[f"cmd_{name}"])
    for name in ("health", "dashboard", "list"):
        reg(name, "args", globals()[f"cmd_{name}"])
    for name in ("verify", "schedule", "sniff", "install", "market"):
        reg(name, "args", globals()[f"cmd_{name}"])

    reg("capture", "args", cmd_capture)

    # 反熵子命令：直接调 Python 跳过 shell
    def _entropy_cmd(action: str) -> Callable[[list[str]], None]:
        def _run(args: list[str]) -> None:
            subprocess.run([sys.executable, str(SRC / "entropy.py"), action] + args, cwd=TOOLBOX)

        return _run

    reg("entropy-sunrise", "args", _entropy_cmd("sunrise"))
    reg("entropy-sunset", "args", _entropy_cmd("sunset"))
    reg("entropy-converge", "args", _entropy_cmd("converge"))
    reg("sunrise", "args", _entropy_cmd("sunrise"))
    reg("sunset", "args", _entropy_cmd("sunset"))
    reg("converge", "args", _entropy_cmd("converge"))

    # 2. 服务模式
    reg("serve-mcp", "serve", "mcp")
    reg("serve", "serve", "mcp")
    reg("serve-api", "serve", "api")
    reg("serve-http", "serve", "api")

    # 3. COMMANDS 脚本
    for name, (cmd_type, path, _) in COMMANDS.items():
        reg(name, "script", cmd_type, path)

    # 4. 别名（不覆盖已注册的内建命令）
    for alias, target in ALIASES.items():
        if target in c and alias not in c:
            c[alias] = c[target]

    # 5. 自动发现脚本（白名单）
    for name, path in _DISCOVERED_SCRIPTS.items():
        if name not in c:
            reg(name, "script", "script", path)

    return c


def _run_script_entry(cmd_type: str, path: str, args: list[str]) -> None:
    """执行 COMMANDS 中的脚本。"""
    if cmd_type == "script":
        subprocess.run(["bash", str(path)] + args, cwd=TOOLBOX)
    elif cmd_type == "python":
        subprocess.run([sys.executable, str(path)] + args, cwd=TOOLBOX)


if __name__ == "__main__":
    main()
