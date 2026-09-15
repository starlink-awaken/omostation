"""公文/政策文档分析 — 统一入口

保持向后兼容：所有公开 API 在此 re-export。
"""

from typing import Any

from codeanalyze.documents.official.models import PolicyDocument, PolicyGraph  # type: ignore[import-not-found]
from codeanalyze.documents.official.parsers import (  # type: ignore[import-not-found]
    _clean_title,
    _extract_doc_number,
    _strip_control_chars,
    extract_file_content,
)
from codeanalyze.documents.official.pipeline import (  # type: ignore[import-not-found]
    _extract_domain_from_path,
    _guess_level_from_path_or_name,
    analyze_policy_directory,
    format_policy_graph_report,
)

# Keep old function names for backward compatibility
_extract_file_content = extract_file_content


def _try_llm_fallback(*a: Any) -> None:
    return None  # moved to parsers


__all__ = [
    "PolicyDocument",
    "PolicyGraph",
    "analyze_policy_directory",
    "format_policy_graph_report",
    "extract_file_content",
    "_strip_control_chars",
    "_clean_title",
    "_extract_doc_number",
    "_guess_level_from_path_or_name",
    "_extract_domain_from_path",
    "_extract_file_content",
]
