"""Kronos Dispatcher — 自动分发到 vault/WPS/KOS。

集成了 WPS content-digest skill 的排版模板和异常处理模式。
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import NotRequired, TypedDict

from kronos.config import get_config  # type: ignore[import-not-found]

VAULT_BASE = Path(get_config().vault_path)


class VaultResult(TypedDict):
    """Vault 写入结果"""

    path: str
    title: str
    size: int


class WpsResult(TypedDict, total=False):
    """WPS 分发结果"""

    status: str
    note_title: NotRequired[str]
    xml_preview: NotRequired[str]
    error: NotRequired[str]


class DispatchResult(TypedDict):
    """分发结果"""

    vault: VaultResult | None
    wps: WpsResult | None
    kos: bool


def _domain_dir(content_type: str) -> str:
    """根据内容类型返回 vault 子目录"""
    domain_map = {
        "文章": "20-知识域/AI-与智能体",
        "论文": "50-参考资料/报告",
        "论文类": "50-参考资料/报告",
        "技术文档": "20-知识域/AI-与智能体",
        "公众号": "20-知识域/AI-与智能体",
        "快讯": "10-收件箱",
    }
    return domain_map.get(content_type, "10-收件箱")


def vault_write(content_type: str, title: str, body: str) -> VaultResult:
    """写入 Obsidian vault，遵循 ONTOLOGY.md 的 frontmatter 规范"""
    subdir = _domain_dir(content_type)
    safe_title = re.sub(r"[^\w\s\-_（）]", "", title).strip()[:40] or "未命名"
    filename = f"{safe_title}.md"
    filepath = VAULT_BASE / subdir / filename

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(body, encoding="utf-8")

    return {
        "path": str(filepath.relative_to(VAULT_BASE)),
        "title": title,
        "size": len(body),
    }


# ── WPS XML 排版模板（对齐 content-digest） ──────────────


def wps_blockquote(source_url: str, source_label: str = "") -> str:
    """WPS 来源 blockquote"""
    label = f" · {escape(source_label)}" if source_label else ""
    # URL scheme 校验，拒绝不安全协议
    if not source_url.startswith(("http://", "https://")):
        source_url = ""
    return f'<blockquote>🔗 来源：<a href="{escape(source_url)}">{escape(source_url)}</a>{label}</blockquote>'


def wps_heading(text: str) -> str:
    """WPS H2 标题（content-digest 规范：禁止 H1 emoji，全部用 H2）"""
    return f"<h2>{escape(text)}</h2>"


def wps_highlight(text: str, bg: str = "#FAF1E6", border: str = "#FEC794", emoji: str = "💡") -> str:
    """WPS 高亮提示块"""
    return (
        f'<highlightBlock emoji="{escape(emoji)}"'
        f' highlightBlockBackgroundColor="{escape(bg)}"'
        f' highlightBlockBorderColor="{escape(border)}">'
        f"<p>{escape(text)}</p></highlightBlock>"
    )


def wps_key_points(points: list[str]) -> str:
    """WPS 要点列表"""
    xml = ""
    for p in points:
        xml += f'<p listType="bullet" listLevel="0">{escape(p)}</p>\n'
    return xml


def wps_columns(left: str, right: str, left_bg: str = "#EBF2FF", right_bg: str = "#FFF5EB") -> str:
    """WPS 双栏布局（用于金句/思考对比）"""
    return (
        f"<columns>"
        f'<column columnBackgroundColor="{left_bg}"><p>{left}</p></column>'
        f'<column columnBackgroundColor="{right_bg}"><p>{right}</p></column>'
        f"</columns>"
    )


def wps_summary_note(
    title: str,
    summary: str,
    key_points: list[str],
    source_url: str,
    source_label: str = "",
    quotes: list[str] | None = None,
    thinking: str = "",
    todos: list[str] | None = None,
) -> str:
    """生成完整的 WPS 摘要笔记 XML（对齐 content-digest 模板）"""
    parts = []

    # 来源
    parts.append(wps_blockquote(source_url, source_label))

    # 一句话概括
    parts.append(wps_heading("📌 一句话概括"))
    parts.append(f"<p>{escape(summary)}</p>")

    # 核心观点
    parts.append(wps_heading("💡 核心观点"))
    parts.append(wps_columns("核心要点", " ".join(key_points[:3])))

    # 要点列表
    parts.append(wps_heading("🔑 关键要点"))
    parts.append(wps_key_points(key_points))

    # 金句摘录
    if quotes:
        parts.append(wps_heading("⭐ 金句摘录"))
        for q in quotes:
            parts.append(f"<blockquote>{escape(q)}</blockquote>")

    # 我的思考
    if thinking:
        parts.append(wps_heading("💬 我的思考"))
        parts.append(f"<p>{escape(thinking)}</p>")

    # 行动清单
    if todos:
        parts.append(wps_heading("✅ 行动清单"))
        for t in todos:
            parts.append(f'<p listType="todo" listLevel="0" checked="0">{escape(t)}</p>')

    return "\n".join(parts)


# ── 分发主函数 ──────────────────────────────────


def dispatch(
    content_type: str,
    title: str,
    markdown_body: str,
    source_url: str = "",
    source_label: str = "",
    key_points: list[str] | None = None,
    quotes: list[str] | None = None,
    thinking: str = "",
) -> DispatchResult:
    """全自动分发到 vault + WPS + KOS"""
    result: DispatchResult = {"vault": None, "wps": None, "kos": False}

    # → vault
    vault_result = vault_write(content_type, title, markdown_body)
    result["vault"] = vault_result

    # → WPS（使用 content-digest 模板生成 XML）
    try:
        wps_xml = wps_summary_note(
            title=title,
            summary=markdown_body.split("\n")[0].replace("> ", "")[:100],
            key_points=key_points or [],
            source_url=source_url,
            source_label=source_label,
            quotes=quotes,
            thinking=thinking,
        )
        result["wps"] = {
            "status": "xml_ready",
            "note_title": title,
            "xml_preview": wps_xml[:100],
        }
    except Exception as e:
        result["wps"] = {"status": "failed", "error": str(e)}

    # KOS 索引不由 dispatcher 写 (KOS 由 kos indexer daemon 扫 workspace zones 维护
    # FTS5+LanceDB 向量, 见 kos.maintenance.indexer --daemon; dispatcher 写会重复).
    # 旧 `import kos; result["kos"]=True` 是假接通 (不调任何 API), 已移除.
    # result["kos"] 保持初始化 False (DispatchResult 结构保留, 诚实标注 dispatcher 不接 KOS).

    return result
