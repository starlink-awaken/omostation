"""cockpit.commands.base — shared utilities for CLI command modules.

console, err, get_data_access are lazily resolved via cli module for
monkeypatch compatibility in tests.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from rich import box as _box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# ── Lazy accessors (look up from cli module for monkeypatch compatibility) ──


def _get_console() -> Console:
    from .. import cli as _cli

    return _cli.console


def _get_err() -> Console:
    from .. import cli as _cli

    return _cli.err


def _get_data_access():
    from .. import cli as _cli

    return _cli.get_data_access()


# ── Paths ──

_CLI_DIR = Path(__file__).resolve().parent.parent
_SCRIPT_DIR = _CLI_DIR / "scripts"

_PROFILE_PATH = Path.home() / ".workspace" / "persona.yaml"


# ── Helpers ──


def _find_cli(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _topic_text(topic: list[str] | str) -> str:
    return " ".join(topic) if isinstance(topic, list) else topic


def _short(text: str | None, limit: int = 120) -> str:
    value = (text or "").strip().replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _print_research_help_suggestions() -> None:
    c = _get_console()
    c.print("[yellow]试试以下命令:[/]")
    c.print('  [cyan]cockpit research "你的主题"[/]')
    c.print("  [cyan]cockpit research --list[/]")
    c.print("  [cyan]cockpit status[/]")
    c.print("  [cyan]cockpit demo[/]")
    c.print()
    c.print("[yellow]主旅程 (Phase 1):[/]")
    c.print("  [dim]import → research / search → open / ask → publish → dossier / timeline → daily[/]")
    c.print("  [cyan]cockpit research --open <ID>[/]")
    c.print("  [cyan]cockpit research --publish <ID> --style brief[/]")
    c.print("  [cyan]cockpit research --dossier <ID>[/]")
    c.print("  [cyan]cockpit research --timeline <ID>[/]")
    c.print()


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _iso_time(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), tz=UTC).isoformat().replace("+00:00", "Z")


def _http_health(url: str, timeout: float = 3.0) -> bool:
    try:
        with urlrequest.urlopen(url, timeout=timeout):  # noqa: S310
            return True
    except (urlerror.URLError, TimeoutError, ValueError):
        return False


def _render_markdown_block(title: str, body: str, style: str = "green") -> None:
    _get_console().print(
        Panel(Markdown(body or "[dim]无内容[/dim]"), title=title, border_style=style, box=_box.ROUNDED)
    )


def _panel(text: str, style: str = "green", title: str | None = None) -> Panel:
    return Panel.fit(text, title=title, border_style=style, box=_box.ROUNDED)


def _looks_like_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _strip_html(raw: str) -> str:
    without_script = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    without_style = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_script, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", without_style)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _derive_import_title(source: str, text: str) -> str:
    title_match = re.search(r"<title>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if title_match and title_match.group(1).strip():
        return _short(_strip_html(title_match.group(1)), 80)
    for line in text.splitlines():
        candidate = line.strip()
        if candidate.startswith("#"):
            candidate = candidate.lstrip("# ").strip()
        if candidate:
            return _short(candidate, 80)
    if _looks_like_url(source):
        return source.rstrip("/").split("/")[-1] or source
    return Path(source).stem


def _normalize_import_content(source: str, raw_text: str) -> tuple[str, str]:
    text = raw_text.strip()
    title = _derive_import_title(source, text)
    if "<html" in text.lower() or "<body" in text.lower() or "<title" in text.lower():
        body = _strip_html(text)
    else:
        body = text
    return title, body.strip()


def _research_progress(task: str) -> None:
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}[/bold]"),
        BarColumn(bar_width=None),
        TimeElapsedColumn(),
        console=_get_console(),
        transient=True,
    ) as progress:
        progress_task = progress.add_task(task, total=100)
        for step in (10, 25, 40, 55, 70, 85, 100):
            time.sleep(max(0.03, (100 - step) * 0.002))
            progress.update(progress_task, completed=step, description=f"{task} · {step}%")


def _notify_research_complete(topic: str) -> None:
    _notify_pipeline_success("研究", topic)


def _notify_pipeline_success(stage: str, detail: str) -> None:
    _notify_pipeline_event(f"{stage}完成", detail)


def _notify_pipeline_error(stage: str, detail: str) -> None:
    _notify_pipeline_event(f"{stage}失败", detail)


def _notify_pipeline_event(event: str, detail: str) -> None:
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{event}: {_short(detail, 50)}" with title "Workspace" sound name "default"',
            ],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass


def _looks_like_research_failure(output: str) -> bool:
    lowered = output.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in ("traceback", "modulenotfounderror", "importerror"))


def _summarize_research_failure(output: str) -> str:
    lowered = output.strip().lower()
    if "modulenotfounderror" in lowered or "importerror" in lowered:
        return "minerva 运行环境缺少依赖，研究未完成。"
    if "traceback" in lowered:
        return "外部研究流程执行失败，研究未完成。"
    for line in output.splitlines():
        candidate = line.strip()
        if candidate and "traceback" not in candidate.lower():
            return _short(candidate, 160)
    return "外部研究流程未返回有效内容。"


def _compare_focus(records: list[dict[str, Any]]) -> str:
    token_sets: list[set[str]] = []
    for record in records:
        topic = str(record.get("topic", "")).replace("-", " ").replace("_", " ")
        token_sets.append({token.lower() for token in topic.split() if len(token) >= 4})
    common = set.intersection(*token_sets) if token_sets else set()
    if common:
        return "、".join(sorted(word.title() for word in common))
    return "这些研究都围绕同一主题域展开，但切入角度不同。"


def _render_publish_content(result: dict[str, Any], style: str) -> str:
    created_at = datetime.fromtimestamp(float(result["created_at"])).strftime("%Y-%m-%d %H:%M")
    summary = str(result.get("summary") or "")
    body = str(result.get("full_text") or summary)
    source_count = int(result.get("source_count") or 0)
    if style == "brief":
        section_title = "## One-Page Brief"
        content_body = f"{section_title}\\n{summary or '暂无摘要'}\\n\\n## Key Details\\n- Source Count: {source_count}\\n- Research ID: {result['id']}\\n\\n## Full Context\\n{body}"
    elif style == "memo":
        content_body = f"## Internal Memo\\n{summary or '暂无摘要'}\\n\\n## Notes\\n{body}"
    else:
        content_body = f"## Executive Summary\\n{summary or '暂无摘要'}\\n\\n## Full Report\\n{body}"
    return f"# {result['topic']}\\n\\nPublished: {created_at}\\nSource Count: {source_count}\\nResearch ID: {result['id']}\\n\\n{content_body}\\n\\n---\\nPublished by Workspace CLI\\n"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"未找到文件: {path}"
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {exc.msg} (line {exc.lineno}, column {exc.colno})"
    except OSError as exc:
        return None, f"读取文件失败: {exc}"
    if not isinstance(data, dict):
        return None, "JSON 顶层必须是 object"
    return data, None


def _load_profile() -> dict:
    import yaml

    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH) as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError):
            return {}
    return {}


def _strip_thinking(text: str) -> str:
    """去除 LLM 推理模型的思考过程。

    处理策略：
    1. 有 <think> 标签：剥离标签本身及之前的所有内容（全为垃圾）
    2. 有头无尾 <think>...：找到第一个实质性中文段落后截断
    3. 无标记但有编号思考步骤：跳过 1. 2. 3. 等编号行
    """
    text = text.strip()
    if not text:
        return text

    # 策略 1：有 <think> 标签 — 剥离一切直到 </think>
    kept: list[str] = []
    if "<think>" in text:
        if "</think>" in text:
            # 完整的闭合标签：取 </think> 之后的内容
            text = text[text.index("</think>") + 8 :].strip()
        else:
            # 无闭合标签：从 <think> 后找第一个实质性行
            think_idx = text.index("<think>")
            after = text[think_idx + 7 :]
            lines = after.split("\n")
            found = False
            for line in lines:
                s = line.strip()
                if not found:
                    if not s:
                        continue
                    if re.match(r"^\d+\.\s", s) or s.startswith(("Thinking", "- ", "* ", "Draft")):
                        continue
                    found = True
                kept.append(line)
            text = "\n".join(kept).strip() if found else text[:think_idx].strip()

    # 策略 2：无 <think> 但开头有 Thinking/编号
    else:
        lines = text.split("\n")
        in_thinking = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Thinking"):
                in_thinking = True
                continue
            if in_thinking and (not stripped or re.match(r"^(\d+\.\s|-\s|\*\s|Draft)", stripped)):
                continue
            if in_thinking:
                in_thinking = False
            kept.append(line)
        if kept:
            text = "\n".join(kept).strip()

    # 去除特殊标记及其之后的内容（训练数据回声）
    for marker in ("<|endoftext|>", "<|im_start|>"):
        if marker in text:
            text = text.split(marker)[0].strip()

    # 策略 3：截断模型自验证内容（如 Counting Characters、Trial、字数统计等）
    # 这些表现为 \n4.  **xxx (Trial N):** 模式，属于模型完成任务后的自我检查
    text = re.sub(
        r"\n\d+\.\s+\*\*.*?(?:Trial|Counting|trial|counting).*\n.*",
        "",
        text,
        flags=re.DOTALL,
    ).strip()

    # 清理：去除首尾纯标点行
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        s = line.strip()
        if s and all(c in "。，、！？；：''【】《》（）—…·.,!?;:\"'()[]{}" for c in s):
            continue  # 纯标点或空白行直接跳过
        cleaned.append(line)
    return "\n".join(cleaned).strip()


# 默认 Ollama 模型名，可通过环境变量 WKS_OLLAMA_MODEL 覆盖
_OLLAMA_BASE = os.environ.get("OLLAMA_ENDPOINT", "")
_OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_ENDPOINT", "")


def _ollama_endpoints() -> tuple[str, str]:
    from cockpit.llm_router import OLLAMA_API

    base = _OLLAMA_BASE or f"{OLLAMA_API}/api/generate"
    tags = _OLLAMA_TAGS_URL or f"{OLLAMA_API}/api/tags"
    return base, tags


def _discover_ollama_model(fallback: str = "gemma4:31b-mlx") -> str:
    try:
        import json as _json
        from urllib import request as urlrequest

        _base, _tags = _ollama_endpoints()
        req = urlrequest.Request(_tags)  # noqa: S310
        with urlrequest.urlopen(req, timeout=3) as resp:  # noqa: S310
            data = _json.loads(resp.read())
        models = data.get("models") or []
        for m in models:
            name = (m.get("name") or "").strip()
            if name:
                return name
    except Exception:
        pass
    return fallback


OLLAMA_MODEL = os.environ.get("WKS_OLLAMA_MODEL") or _discover_ollama_model()


def _ollama_request(prompt: str, *, stream: bool, timeout: int) -> bytes:
    """构建 ollama API 请求，发送 HTTP POST，返回原始响应体。"""
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": stream,
            "raw": True,
            "options": {"num_predict": 500, "temperature": 0.3},
        }
    ).encode()
    _base, _tags = _ollama_endpoints()
    req = urlrequest.Request(_base, data=body, headers={"Content-Type": "application/json"})  # noqa: S310
    with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _ollama_timeout(default: int = 60) -> int:
    """安全地从环境变量读取 OLLAMA_TIMEOUT，异常时返回默认值。"""
    try:
        return int(os.environ.get("OLLAMA_TIMEOUT", str(default)))
    except (ValueError, TypeError):
        return default


def _run_ollama(prompt: str, *, timeout: int = 60) -> str | None:
    """调用本地 ollama 模型生成文本（非流式）。"""
    try:
        raw = _ollama_request(prompt, stream=False, timeout=timeout)
        data = json.loads(raw)
        text = (data.get("response") or "").strip()
        if text:
            return _strip_thinking(text)
    except Exception:  # defensive fallback
        pass
    return None


def _run_ollama_stream(prompt: str, *, timeout: int = 120) -> str | None:
    """流式调用 ollama — 逐 token 打印到 stdout，同时累积完整文本。

    Returns:
        成功时返回完整累积文本，失败返回 None。
    """
    try:
        raw = _ollama_request(prompt, stream=True, timeout=timeout)
        full_text = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = chunk.get("response") or ""
            done = chunk.get("done", False)
            if done and not token:
                break
            if token:
                print(token, end="", flush=True)
                full_text += token
        print()
        return full_text.strip() or None
    except Exception:  # defensive fallback
        pass
    return None


def _status_services() -> list[tuple[str, str, str | None, str, str]]:
    """硬编码服务列表，作为动态发现的 fallback。

    2026-07-15 修正: 旧列表检查 Agora Hub :7430 (stdio-only 网关, 设计上不监听,
    见 ADR-0179) 与 Minerva :8765 (port-registry 已废弃端口) — 恒报离线的幻影红灯。
    现改为 port-registry 在册且有 /health 的真实 HTTP 面; 端口经 env var 引用 (P77-7)。
    """
    sse_port = os.environ.get("AGORA_MCP_SSE_PORT", "7431")
    kos_port = os.environ.get("KOS_REST_PORT", "8766")
    sse_url = os.environ.get("AGORA_SSE_ENDPOINT", f"http://localhost:{sse_port}")
    kos_url = os.environ.get("KOS_ENDPOINT", f"http://localhost:{kos_port}")
    return [
        ("Agora SSE", f":{sse_port}", "agora", f"{sse_url}/health", "MCP SSE 网关 (bos:// 路由)"),
        ("KOS", f":{kos_port}", None, f"{kos_url}/health", "知识检索系统 REST API"),
    ]


def get_cockpit_jwt() -> str:
    """获取或生成模拟的 JWT token，用于穿越 Agora/MetaOS 的 RBAC 拦截."""
    return os.environ.get("COCKPIT_JWT_TOKEN", "mock_admin_token_for_cli")


def _discover_services() -> list[tuple[str, str, str | None, str, str]]:
    """通过 Agora /api/services 动态发现服务，失败则回退到硬编码列表。"""
    try:
        agora_url = os.environ.get(
            "AGORA_ENDPOINT", f"http://localhost:{os.environ.get('AGORA_INTERNAL_PORT', '7430')}"
        )
        headers = {"Accept": "application/json"}
        token = get_cockpit_jwt()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urlrequest.Request(f"{agora_url}/api/services", headers=headers)  # noqa: S310
        resp = urlrequest.urlopen(req, timeout=3)  # noqa: S310
        data = json.loads(resp.read())
        if isinstance(data, list) and data:
            svc: list[tuple[str, str, str | None, str, str]] = []
            for s in data:
                name = s.get("name", "?")
                port = s.get("port") or 0
                port_str = f":{port}" if port else ""
                cli_name = name.lower().replace(" ", "")
                health_url = s.get("health_endpoint") or ""
                desc = s.get("description") or ""
                svc.append((name, port_str, cli_name, health_url, desc))
            if svc:
                return svc
    except (urlerror.URLError, json.JSONDecodeError, OSError, TimeoutError):
        pass
    return _status_services()


# ── Standard Output Renderer (Phase 3: 命令行优雅输出系统) ──────────────────


class OutputFormat:
    """输出呈现格式名称常量枚举."""

    TTY = "tty"
    JSON = "json"
    MARKDOWN = "markdown"
    TUI = "tui"


def render_command_header(title: str, subtitle: str | None = None, category: str = "COMMAND") -> None:
    """渲染极客顶栏 Header，展示统一视觉形象."""
    console = _get_console()
    header_text = f"[bold cyan]🛸 Cockpit ·[/bold cyan] [bold white]{title}[/bold white]"
    if subtitle:
        header_text += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(header_text, border_style="cyan", box=_box.ROUNDED, expand=False))


def render_command_result(
    title: str,
    data: Any,
    output_format: str = OutputFormat.TTY,
    columns: list[str | tuple[str, str]] | None = None,
    summary: str | None = None,
) -> None:
    """标准·优雅多形态命令结果通用输出引擎.

    参数:
        title: 表格/面板的主标题
        data: 支持 list[dict] 或 dict 数据格式
        output_format: "tty", "json", 或 "markdown"
        columns: [(field_key, column_name), ...] 可选的显式列声明
        summary: 可选的附加底注或描述文字
    """
    console = _get_console()

    def _normalize_cols(cols_in: Any, sample_keys: Any) -> list[tuple[str, str]]:
        if not cols_in:
            return [(str(k), str(k).upper()) for k in sample_keys]
        res = []
        for c in cols_in:
            if isinstance(c, tuple) and len(c) == 2:
                res.append((str(c[0]), str(c[1])))
            elif isinstance(c, str):
                res.append((c, c.upper()))
            else:
                res.append((str(c), str(c).upper()))
        return res

    # 1. 结构化 JSON 模式 (自动化管道 / 机器消费友善)
    if output_format == OutputFormat.JSON:
        payload = {"title": title, "summary": summary, "data": data} if summary else data
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    # 2. Markdown 模式 (GitHub Markdown 输出)
    if output_format == OutputFormat.MARKDOWN:
        md_lines = [f"### 🛸 {title}\n"]
        if summary:
            md_lines.append(f"> {summary}\n")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            cols = _normalize_cols(columns, list(data[0].keys()))
            md_lines.append("| " + " | ".join(name for _, name in cols) + " |")
            md_lines.append("| " + " | ".join("---" for _ in cols) + " |")
            for item in data:
                md_lines.append("| " + " | ".join(str(item.get(k, "")) for k, _ in cols) + " |")
        elif isinstance(data, dict):
            md_lines.append("| Field | Value |")
            md_lines.append("| --- | --- |")
            for k, v in data.items():
                md_lines.append(f"| {k} | {v} |")
        else:
            md_lines.append(f"```\n{data}\n```")
        console.print(Markdown("\n".join(md_lines)))
        return

    # 3. TTY 交互模式 (Rich 极客视觉输出)
    if summary:
        console.print(f"[dim]ℹ️  {summary}[/dim]")

    if isinstance(data, list):
        if not data:
            console.print(f"[dim]🛸 {title} — (无数据记录)[/dim]")
            return
        table = Table(
            title=f"[bold cyan]{title}[/bold cyan]",
            box=_box.ROUNDED,
            border_style="cyan",
            show_header=True,
            header_style="bold yellow",
        )
        first_item = data[0]
        if isinstance(first_item, dict):
            cols = _normalize_cols(columns, list(first_item.keys()))
            for _, col_name in cols:
                table.add_column(col_name, overflow="fold")
            for item in data:
                row_cells = []
                for field_key, _ in cols:
                    val = item.get(field_key, "")
                    s_val = str(val) if val is not None else ""
                    # 极客状态关键字颜色微渲染
                    if s_val.lower() in ("active", "ok", "passed", "true", "alive"):
                        s_val = f"[bold green]{s_val}[/bold green]"
                    elif s_val.lower() in ("error", "failed", "false", "dead"):
                        s_val = f"[bold red]{s_val}[/bold red]"
                    elif s_val.lower() in ("draft", "warning", "pending"):
                        s_val = f"[bold yellow]{s_val}[/bold yellow]"
                    row_cells.append(s_val)
                table.add_row(*row_cells)
            console.print(table)
        else:
            for idx, val in enumerate(data, 1):
                console.print(f"  [cyan]{idx}.[/cyan] {val}")
    elif isinstance(data, dict):
        table = Table(
            title=f"[bold cyan]{title}[/bold cyan]",
            box=_box.ROUNDED,
            border_style="cyan",
            show_header=True,
            header_style="bold yellow",
        )
        table.add_column("属性 (Field)", style="cyan")
        table.add_column("取值 (Value)", overflow="fold")
        for k, v in data.items():
            s_val = str(v)
            if s_val.lower() in ("ok", "active", "true"):
                s_val = f"[bold green]{s_val}[/bold green]"
            elif s_val.lower() in ("error", "false"):
                s_val = f"[bold red]{s_val}[/bold red]"
            table.add_row(str(k), s_val)
        console.print(table)
    else:
        console.print(Panel(str(data), title=f"[bold cyan]{title}[/bold cyan]", box=_box.ROUNDED))


def is_interactive() -> bool:
    """Check whether stdout is connected to an interactive TTY."""
    import sys

    return sys.stdout.isatty()


def output_result(data: Any, args: Any = None, default_render_fn: Any = None) -> int:
    """Unified output renderer respecting --json, global output mode, and TTY purity."""
    import json

    fmt = getattr(args, "format", None) or getattr(args, "global_output", "text")
    if getattr(args, "json", False) or fmt == "json":
        if isinstance(data, (dict, list)):
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"result": data}, ensure_ascii=False, indent=2))
        return 0

    if default_render_fn:
        return default_render_fn(data)

    console = _get_console()
    if isinstance(data, (dict, list)):
        render_geek_panel(data)
    else:
        console.print(data)
    return 0

