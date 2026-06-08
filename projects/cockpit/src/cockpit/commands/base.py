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
    c.print('  [cyan]workspace research "你的主题"[/]')
    c.print("  [cyan]workspace research --list[/]")
    c.print("  [cyan]workspace status[/]")
    c.print("  [cyan]workspace demo[/]")
    c.print()
    c.print("[yellow]主旅程 (Phase 1):[/]")
    c.print("  [dim]import → research / search → open / ask → publish → dossier / timeline → daily[/]")
    c.print("  [cyan]workspace research --open <ID>[/]")
    c.print("  [cyan]workspace research --publish <ID> --style brief[/]")
    c.print("  [cyan]workspace research --dossier <ID>[/]")
    c.print("  [cyan]workspace research --timeline <ID>[/]")
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
OLLAMA_MODEL = os.environ.get("WKS_OLLAMA_MODEL", "qwen3.5:4b")


def _run_ollama(prompt: str, *, timeout: int = 60) -> str | None:
    """调用本地 ollama 模型生成文本（通过 API 而非 CLI，更快更稳定）。

    Args:
        prompt: 发送给模型的提示词。
        timeout: API 请求超时秒数。

    Returns:
        成功时返回模型输出文本（已去除思考过程），失败返回 None。
    """
    try:
        body = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "raw": True,
                "options": {"num_predict": 500, "temperature": 0.3},
            }
        ).encode()
        req = urlrequest.Request(
            os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate"),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urlrequest.urlopen(req, timeout=timeout)  # noqa: S310
        data = json.loads(resp.read())
        text = (data.get("response") or "").strip()
        if text:
            return _strip_thinking(text)
    except Exception:
        pass
    return None


def _run_ollama_stream(prompt: str, *, timeout: int = 120) -> str | None:
    """流式调用 ollama — 逐 token 打印到 stdout，同时累积完整文本。

    Returns:
        成功时返回完整累积文本，失败返回 None。
    """
    try:
        body = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "raw": True,
                "options": {"num_predict": 500, "temperature": 0.3},
            }
        ).encode()
        req = urlrequest.Request(
            os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate"),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urlrequest.urlopen(req, timeout=timeout)  # noqa: S310
        full_text = ""
        thinking = False
        # 逐行读取 NDJSON 流
        for line in resp:
            try:
                chunk = json.loads(line.decode())
                token = (chunk.get("response") or "")
                if not token:
                    continue
                # 跳过 <｜end▁of▁thinking｜> 标签
                if "<｜end▁of▁thinking｜>" in token:
                    thinking = True
                    continue
                if "响应" in token or "回答" in token:
                    thinking = False
                    continue
                if not thinking:
                    print(token, end="", flush=True)
                    full_text += token
                if chunk.get("done"):
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        print()  # 换行
        return full_text.strip() or None
    except Exception:
        pass
    return None


def _status_services() -> list[tuple[str, str, str | None, str, str]]:
    """硬编码服务列表，作为动态发现的 fallback。"""
    agora_url = os.environ.get("AGORA_ENDPOINT", "http://localhost:7430")
    minerva_url = os.environ.get("MINERVA_ENDPOINT", "http://localhost:8765")
    return [
        ("Agora Hub", ":7430", "agora", f"{agora_url}/health", "MCP 服务治理中枢"),
        ("Minerva", ":8765", "minerva", f"{minerva_url}/health", "深度研究系统"),
    ]


def _discover_services() -> list[tuple[str, str, str | None, str, str]]:
    """通过 Agora /api/services 动态发现服务，失败则回退到硬编码列表。"""
    try:
        agora_url = os.environ.get("AGORA_ENDPOINT", "http://localhost:7430")
        req = urlrequest.Request(f"{agora_url}/api/services", headers={"Accept": "application/json"})
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
