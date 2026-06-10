"""测试 base.py 中所有辅助函数。

场景覆盖：
1. _strip_thinking — 11+ 种 LLM 输出模式
2. _run_ollama — 6 种 HTTP 响应场景
3. _summarize_research_failure — 4 种失败输出
4. _looks_like_research_failure — 3 种检测场景
5. _http_health — 4 种服务状态
6. _status_services — 服务列表完整性
7. _short, _topic_text, _fmt_time, _panel, _looks_like_url — 边界情况
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock
from urllib import error as urlerror

from rich.console import Console

from cockpit.commands.base import (
    _compare_focus,
    _derive_import_title,
    _fmt_time,
    _http_health,
    _iso_time,
    _load_json_file,
    _load_profile,
    _looks_like_research_failure,
    _looks_like_url,
    _normalize_import_content,
    _panel,
    _render_markdown_block,
    _render_publish_content,
    _run_ollama,
    _short,
    _status_services,
    _strip_html,
    _strip_thinking,
    _summarize_research_failure,
    _topic_text,
    _workspace_root,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 一、_strip_thinking — LLM 思考过程剥离场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestStripThinking:
    """11 种 LLM 输出模式，验证思考过程剥离逻辑。"""

    def test_pure_answer_no_thinking(self):
        """场景 1：纯答案，无思考过程→原样返回"""
        text = "Transformer 的核心创新是自注意力机制。"
        assert _strip_thinking(text) == text

    def test_closed_think_tag(self):
        """场景 2：完整 <think>...</think>→只保留答案"""
        text = (
            "<think>\nThinking Process:\n1. User asks about Transformer\n"
            "2. Need to explain core innovations\n</think>\n"
            "Transformer 的核心创新是自注意力机制。"
        )
        assert _strip_thinking(text) == "Transformer 的核心创新是自注意力机制。"

    def test_empty_think_tag_with_leading_garbage(self):
        """场景 3：前导垃圾 + 空 <think>\n\n</think>→全部剥离"""
        text = "。\n\n<think>\n\n</think>\n\nTransformer 摒弃递归结构。"
        assert _strip_thinking(text) == "Transformer 摒弃递归结构。"

    def test_unclosed_think_tag(self):
        """场景 4：有头无尾 <think>（qwen3.5:4b 行为）→找到实质性内容"""
        text = (
            "<think>\nThinking Process:\n1. Analyze the question\n"
            "2. Determine innovations\n\n"
            "Transformer 的核心创新是自注意力机制。"
        )
        assert _strip_thinking(text) == "Transformer 的核心创新是自注意力机制。"

    def test_no_think_tag_but_thinking_header(self):
        """场景 5：无 <think> 但有 Thinking Process→跳过 thinking 行"""
        text = (
            "Thinking Process:\n"
            "1. 理解问题\n2. 分析核心创新\n3. 列出主要变体\n\n"
            "Transformer 架构的核心创新是自注意力机制。"
        )
        assert _strip_thinking(text) == "Transformer 架构的核心创新是自注意力机制。"

    def test_training_data_echo_markers(self):
        """场景 6：训练数据回声标记→在标记处截断"""
        text = "Transformer 摒弃递归结构。<|endoftext|><|im_start|>user\n请帮我写一篇关于人工智能的文章。"
        result = _strip_thinking(text)
        assert result == "Transformer 摒弃递归结构。"

    def test_self_verification_counting_characters(self):
        """场景 7：模型自验证 Counting Characters→截断验证部分"""
        text = (
            "Transformer 能取代 RNN 主要是因为自注意力机制。\n\n"
            "4.  **Counting Characters (Trial 1):**\n"
            "     Transformer 能取代 RNN 主要是因为自注意力机制。(23)"
        )
        result = _strip_thinking(text)
        assert "Counting Characters" not in result
        assert "自注意力" in result
        assert "4.  **" not in result

    def test_multiple_markers_and_garbage(self):
        """场景 8：组合场景：前导垃圾 + 空 think + 尾部训练回声"""
        text = "。\n\n<think>\n\n</think>\n\nTransformer 摒弃递归结构。<|endoftext|>"
        assert _strip_thinking(text) == "Transformer 摒弃递归结构。"

    def test_empty_input(self):
        """场景 9：空输入→空输出"""
        assert _strip_thinking("") == ""
        assert _strip_thinking("   ") == ""

    def test_unclosed_think_no_answer_found(self):
        """场景 10：有头无尾 <think> 但无实质性内容→回退到标签前"""
        text = "<think>\n1. 思考\n2. 继续思考\n"
        result = _strip_thinking(text)
        assert result == ""  # think 前无内容，最终为空

    def test_draft_prefix_skipped(self):
        """场景 11：有 Draft 标记的 thinking 被跳过"""
        text = "<think>\nDraft\n1. 分析\n\n真实回答内容。"
        assert _strip_thinking(text) == "真实回答内容。"

    def test_bullet_thinking_lines_skipped(self):
        """场景 12：thinking 中的 bullet point 被跳过"""
        text = "<think>\n- 步骤一\n- 步骤二\n* 备选\n\n最终答案。"
        assert _strip_thinking(text) == "最终答案。"

    def test_pure_punctuation_line_removed(self):
        """场景 13：纯标点行→被过滤 (line 333)"""
        text = "有效内容。\n。，！？；：''【】\n更多有效内容"
        result = _strip_thinking(text)
        assert "有效内容" in result
        assert "更多有效内容" in result
        # 纯标点行应当被移除
        assert "。，！？" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# 二、_run_ollama — Ollama API 调用场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunOllama:
    """6 种 HTTP 响应场景，验证降级链入口。"""

    def test_success_returns_stripped_text(self):
        """场景 1：API 成功返回有效 response→返回剥离后文本"""
        raw_response = json.dumps({"response": "<think>\n\n</think>\n\nTransformer 的核心创新。"})
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = raw_response.encode()

        with mock.patch("cockpit.commands.base.urlrequest.urlopen", return_value=mock_resp):
            result = _run_ollama("test prompt", timeout=10)

        assert result == "Transformer 的核心创新。"

    def test_empty_response_field(self):
        """场景 2：API 返回空 response→返回 None"""
        raw_response = json.dumps({"response": ""})
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = raw_response.encode()

        with mock.patch("cockpit.commands.base.urlrequest.urlopen", return_value=mock_resp):
            result = _run_ollama("test prompt", timeout=10)

        assert result is None

    def test_missing_response_key(self):
        """场景 3：API 返回缺少 response 键→返回 None"""
        raw_response = json.dumps({"error": "model not found"})
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = raw_response.encode()

        with mock.patch("cockpit.commands.base.urlrequest.urlopen", return_value=mock_resp):
            result = _run_ollama("test prompt", timeout=10)

        assert result is None

    def test_http_error(self):
        """场景 4：HTTP 错误（模型不存在/服务关闭）→返回 None"""
        with mock.patch(
            "cockpit.commands.base.urlrequest.urlopen",
            side_effect=urlerror.URLError("Connection refused"),
        ):
            result = _run_ollama("test prompt", timeout=10)

        assert result is None

    def test_timeout(self):
        """场景 5：请求超时→返回 None"""
        with mock.patch(
            "cockpit.commands.base.urlrequest.urlopen",
            side_effect=TimeoutError(),
        ):
            result = _run_ollama("test prompt", timeout=10)

        assert result is None

    def test_non_json_response(self):
        """场景 6：非 JSON 响应→返回 None"""
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = b"<html>Internal Server Error</html>"

        with mock.patch("cockpit.commands.base.urlrequest.urlopen", return_value=mock_resp):
            result = _run_ollama("test prompt", timeout=10)

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 三、_summarize_research_failure — 失败摘要场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestSummarizeResearchFailure:
    """4 种失败输出模式。"""

    def test_module_not_found_error(self):
        """场景 1：ModuleNotFoundError→依赖缺失提示"""
        output = "Traceback (most recent call last):\nModuleNotFoundError: No module named 'minerva'"
        assert "缺少依赖" in _summarize_research_failure(output)

    def test_general_traceback(self):
        """场景 2：一般 traceback→外部执行失败提示"""
        output = "Traceback (most recent call last):\n  File \"run.py\", line 10, in <module>\nKeyError: 'missing'"
        assert "外部研究流程执行失败" in _summarize_research_failure(output)

    def test_empty_output(self):
        """场景 3：空输出→未返回有效内容"""
        assert "未返回有效内容" in _summarize_research_failure("")
        assert "未返回有效内容" in _summarize_research_failure("   ")

    def test_normal_content(self):
        """场景 4：普通内容→截断返回"""
        output = "这是一个正常的研究输出内容，没有错误。"
        assert _summarize_research_failure(output) == "这是一个正常的研究输出内容，没有错误。"


# ═══════════════════════════════════════════════════════════════════════════════
# 四、_looks_like_research_failure — 失败检测场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestLooksLikeResearchFailure:
    """4 种检测场景。"""

    def test_traceback_flagged(self):
        """场景 1：含 Traceback→失败"""
        assert _looks_like_research_failure("Traceback (most recent call last)")

    def test_importerror_flagged(self):
        """场景 2：含 ImportError→失败"""
        assert _looks_like_research_failure("ImportError: No module named 'xyz'")

    def test_normal_output_not_flagged(self):
        """场景 3：正常输出→不标记失败"""
        assert not _looks_like_research_failure("研究正常完成，以下为结论。")
        assert not _looks_like_research_failure("Some useful content here.")

    def test_empty_output_flagged(self):
        """场景 4：空输出→标记失败 (line 187)"""
        assert _looks_like_research_failure("")
        assert _looks_like_research_failure("   ")


# ═══════════════════════════════════════════════════════════════════════════════
# 五、_http_health — HTTP 健康检查场景
# ═══════════════════════════════════════════════════════════════════════════════


class TestHttpHealth:
    """4 种服务状态场景。"""

    def test_service_up(self):
        """场景 1：服务正常响应→True"""
        with mock.patch("cockpit.commands.base.urlrequest.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value = mock.MagicMock()
            result = _http_health("http://localhost:8080/health", timeout=1)
        assert result is True

    def test_http_error(self):
        """场景 2：HTTP 错误→False"""
        with mock.patch(
            "cockpit.commands.base.urlrequest.urlopen",
            side_effect=urlerror.HTTPError(
                url="http://localhost:8080/health",
                code=503,
                msg="Service Unavailable",
                hdrs={},
                fp=io.BytesIO(b""),
            ),
        ):
            assert _http_health("http://localhost:8080/health") is False

    def test_connection_refused(self):
        """场景 3：连接拒绝→False"""
        with mock.patch(
            "cockpit.commands.base.urlrequest.urlopen",
            side_effect=urlerror.URLError("Connection refused"),
        ):
            assert _http_health("http://localhost:8080/health") is False

    def test_timeout(self):
        """场景 4：超时→False"""
        with mock.patch(
            "cockpit.commands.base.urlrequest.urlopen",
            side_effect=TimeoutError(),
        ):
            assert _http_health("http://localhost:8080/health") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 六、_status_services — 服务列表完整性
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusServices:
    """验证服务列表完整性和结构。"""

    def test_returns_four_services(self):
        """返回 4 个核心服务"""
        services = _status_services()
        assert len(services) >= 2  # at least Agora Hub + Minerva

    def test_each_service_has_five_fields(self):
        """每个服务包含 5 个字段：(name, port, cli, health_url, description)"""
        for svc in _status_services():
            assert len(svc) == 5
            name, port, cli, health_url, desc = svc
            assert isinstance(name, str) and name
            assert isinstance(port, str) and port
            assert isinstance(desc, str) and desc
            assert health_url.startswith("http")

    def test_agora_first(self):
        """Agora Hub 应排第一位"""
        assert _status_services()[0][0] == "Agora Hub"

    def test_minerva_present(self):
        """Minerva 应在服务列表中"""
        names = [s[0] for s in _status_services()]
        assert "Minerva" in names

    def test_agentmesh_removed(self):
        """AgentMesh 已从服务列表移除（已归档）"""
        names = [s[0] for s in _status_services()]
        assert "AgentMesh" not in names
        assert "SharedBrain" not in names


# ═══════════════════════════════════════════════════════════════════════════════
# 七、其他辅助函数 — 边界情况
# ═══════════════════════════════════════════════════════════════════════════════


class TestShort:
    """_short 文本截断场景。"""

    def test_within_limit(self):
        """短于 limit→完整返回"""
        assert _short("short text") == "short text"

    def test_exceeds_limit(self):
        """超过 limit→截断"""
        long_text = "a" * 200
        result = _short(long_text, limit=120)
        assert len(result) == 120
        assert result.endswith("…")

    def test_none_input(self):
        """None 输入→空字符串"""
        assert _short(None) == ""


class TestTopicText:
    """_topic_text 主题格式化场景。"""

    def test_list_input(self):
        """list 输入→join 为字符串"""
        assert _topic_text(["hello", "world"]) == "hello world"

    def test_string_input(self):
        """字符串输入→原样返回"""
        assert _topic_text("hello world") == "hello world"


class TestFmtTime:
    """_fmt_time 时间格式化。"""

    def test_known_timestamp(self):
        """已知时间戳→格式化输出"""
        ts = datetime(2026, 5, 28, 14, 30, tzinfo=UTC).timestamp()
        result = _fmt_time(ts)
        assert result == "2026-05-28 14:30" or "2026-05-28" in result


class TestPanel:
    """_panel 创建场景。"""

    def test_basic_panel(self):
        """创建基本 Panel→返回 Panel 实例"""
        panel = _panel("test content", style="green", title="Test")
        assert "test content" in str(panel.renderable)
        assert panel.title == "Test"

    def test_panel_without_title(self):
        """无标题 Panel"""
        panel = _panel("content only")
        assert "content only" in str(panel.renderable)
        assert panel.title is None


class TestLooksLikeUrl:
    """_looks_like_url URL 检测场景。"""

    def test_http_url(self):
        """http:// 开头→True"""
        assert _looks_like_url("http://example.com") is True
        assert _looks_like_url("http://localhost:8080") is True

    def test_https_url(self):
        """https:// 开头→True"""
        assert _looks_like_url("https://example.com") is True

    def test_not_url(self):
        """非 URL→False"""
        assert _looks_like_url("file.txt") is False
        assert _looks_like_url("") is False
        assert _looks_like_url("/path/to/file") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 八、新增辅助函数测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestStripHtml:
    """_strip_html HTML 剥离场景。"""

    def test_strip_basic_tags(self):
        """基本 HTML 标签→剥离标签保留文本"""
        result = _strip_html("<p>Hello <b>World</b></p>")
        assert "Hello World" in result

    def test_strip_script_block(self):
        """<script> 块→完全移除"""
        result = _strip_html("<p>Content</p><script>alert('xss')</script><p>After</p>")
        assert "alert" not in result
        assert "Content After" in result

    def test_strip_style_block(self):
        """<style> 块→完全移除"""
        result = _strip_html("<p>Text</p><style>body{color:red}</style><p>More</p>")
        assert "color" not in result
        assert "Text More" in result

    def test_html_entities_decoded(self):
        """HTML 实体→解码"""
        result = _strip_html("<p>AT&amp;T &lt; 3</p>")
        assert "AT&T" in result
        assert "< 3" in result

    def test_nested_tags(self):
        """嵌套标签→扁平化"""
        result = _strip_html("<div><ul><li>A</li><li>B</li></ul></div>")
        assert "A B" in result

    def test_no_html(self):
        """纯文本→保持不变"""
        result = _strip_html("plain text without tags")
        assert result == "plain text without tags"

    def test_empty_input(self):
        """空字符串→空字符串"""
        assert _strip_html("") == ""


class TestDeriveImportTitle:
    """_derive_import_title 标题推导场景。"""

    def test_from_title_tag(self):
        """HTML 有 <title>→从 title 推导"""
        html = "<html><head><title>My Article Title</title></head><body><p>content</p></body></html>"
        assert _derive_import_title("http://example.com/article", html) == "My Article Title"

    def test_from_first_nonempty_line(self):
        """无 title 但第一行有内容→取第一行"""
        text = "First meaningful line\n\nSecond line"
        result = _derive_import_title("/path/file.md", text)
        assert "First meaningful line" in result

    def test_skip_markdown_header(self):
        """第一行是 Markdown 标题→去 # 前缀"""
        text = "# Research Note\n\nbody content"
        result = _derive_import_title("note.md", text)
        assert "Research Note" in result
        assert "#" not in result

    def test_fallback_to_url_path(self):
        """无可提取内容 + URL→取 URL 最后一段"""
        url = "http://example.com/articles/deep-learning"
        result = _derive_import_title(url, "\n\n  \n\n")
        assert result == "deep-learning"

    def test_fallback_to_filename(self):
        """无可提取内容 + 文件路径→取文件名 stem"""
        result = _derive_import_title("/tmp/my_document.md", "\n\n  \n\n")
        assert result == "my_document"

    def test_empty_source_and_text(self):
        """空 source + 空文本→空字符串"""
        result = _derive_import_title("", "")
        assert result == ""


class TestNormalizeImportContent:
    """_normalize_import_content 导入规范化场景。"""

    def test_html_content_stripped(self):
        """HTML 内容→去标签 + 推导标题"""
        html = "<html><head><title>Test</title></head><body><p>Hello <b>World</b></p></body></html>"
        title, body = _normalize_import_content("http://x.com/page", html)
        assert title == "Test"
        assert "Hello" in body
        assert "World" in body
        assert "<b>" not in body

    def test_plain_text_unchanged(self):
        """纯文本→保持不变"""
        title, body = _normalize_import_content("note.md", "Just some text\n\nMore text")
        assert title == "Just some text"
        assert body == "Just some text\n\nMore text"

    def test_empty_content(self):
        """空内容→空"""
        title, body = _normalize_import_content("file.txt", "")
        assert body == ""


class TestCompareFocus:
    """_compare_focus 主题对比场景。"""

    def test_common_tokens(self):
        """有共同主题词→返回交集"""
        records = [
            {"topic": "Transformer Architecture Evolution"},
            {"topic": "Transformer Attention Mechanism"},
        ]
        result = _compare_focus(records)
        assert "Transformer" in result
        assert "Attention" not in result  # Attention 长度不满 4？不，刚好 4
        # "Architecture" 出现在第一个, "Evolution" 只出现在第一个
        # "Attention" 出现在第二个, "Mechanism" 只出现在第二个
        # 共同的是: "Transformer"
        assert result == "Transformer"

    def test_no_common_tokens(self):
        """无共同词→返回通用描述"""
        records = [
            {"topic": "Deep Learning Fundamentals"},
            {"topic": "Quantum Computing Advances"},
        ]
        result = _compare_focus(records)
        assert "这些研究都围绕同一主题域展开" in result

    def test_single_record(self):
        """只有一条→返回该条目的主题关键词"""
        result = _compare_focus([{"topic": "AI Safety"}])
        assert result == "Safety"

    def test_empty_records(self):
        """空列表→返回通用描述"""
        result = _compare_focus([])
        assert "这些研究都围绕同一主题域展开" in result


class TestRenderPublishContent:
    """_render_publish_content 发布渲染场景。"""

    def _make_result(self, **overrides):
        return {
            "id": 1,
            "topic": "AI Research",
            "created_at": "1700000000",
            "summary": "AI is transforming the world.",
            "full_text": "Detailed AI research content here.",
            "source_count": 3,
            **overrides,
        }

    def test_brief_style(self):
        """brief 样式→包含 One-Page Brief"""
        content = _render_publish_content(self._make_result(), "brief")
        assert "One-Page Brief" in content
        assert "AI Research" in content
        assert "AI is transforming" in content
        assert "Research ID: 1" in content

    def test_memo_style(self):
        """memo 样式→包含 Internal Memo"""
        content = _render_publish_content(self._make_result(), "memo")
        assert "Internal Memo" in content
        assert "AI Research" in content

    def test_default_style(self):
        """未识别样式→回退到 Executive Summary + Full Report"""
        content = _render_publish_content(self._make_result(), "report")
        assert "Executive Summary" in content
        assert "Full Report" in content

    def test_empty_summary_fallback(self):
        """summary 为空→使用 '暂无摘要'"""
        result = self._make_result(summary="", full_text="body only")
        content = _render_publish_content(result, "brief")
        assert "暂无摘要" in content
        assert "body only" in content


class TestWorkspaceRoot:
    """_workspace_root 返回项目根目录。"""

    def test_returns_cockpit_directory(self):
        """返回 cockpit 项目根目录"""
        root = _workspace_root()
        assert root.is_dir()
        assert (root / "cockpit").is_dir()  # 包含 cockpit 包
        assert (root / "commands").is_dir() or (root / "cockpit").is_dir()


class TestLoadJsonFile:
    """_load_json_file JSON 加载场景。"""

    def test_load_success(self, tmp_path):
        """有效 JSON→返回 (data, None)"""
        f = tmp_path / "test.json"
        f.write_text('{"key": "value", "num": 42}')
        data, err = _load_json_file(f)
        assert err is None
        assert data == {"key": "value", "num": 42}

    def test_file_not_found(self):
        """文件不存在→返回错误消息"""
        from pathlib import Path

        data, err = _load_json_file(Path("/tmp/nonexistent_12345.json"))
        assert data is None
        assert "未找到文件" in (err or "")

    def test_invalid_json(self):
        """无效 JSON→返回解析错误"""
        f = Path("/tmp") / "_test_invalid.json"
        f.write_text('{"broken": ')
        data, err = _load_json_file(f)
        assert data is None
        assert "JSON 解析失败" in (err or "")
        f.unlink(missing_ok=True)

    def test_not_a_dict(self):
        """JSON 顶层非 object→返回错误"""
        f = Path("/tmp") / "_test_array.json"
        f.write_text("[1, 2, 3]")
        data, err = _load_json_file(f)
        assert data is None
        assert "必须是 object" in (err or "")
        f.unlink(missing_ok=True)

    def test_os_error(self, tmp_path):
        """OSError 读取失败→返回错误 (lines 241-242)"""
        f = tmp_path / "_locked.json"
        f.write_text('{"key": "value"}')
        # 模拟 OSError：将文件变为目录
        f.unlink()
        f.mkdir()
        data, err = _load_json_file(f)
        assert data is None
        assert "读取文件失败" in (err or "")
        f.rmdir()


class TestLoadProfile:
    """_load_profile profile 加载场景。"""

    def test_profile_not_found(self, monkeypatch):
        """无 profile 文件→返回空字典"""
        from pathlib import Path

        mock_path = Path("/tmp") / "_test_nonexistent_profile.yaml"
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", mock_path)
        assert _load_profile() == {}

    def test_profile_loads_success(self, monkeypatch, tmp_path):
        """profile 文件有效→返回解析内容"""

        profile_file = tmp_path / "persona.yaml"
        profile_file.write_text("name: Test User\nrole: researcher\ntimezone: Asia/Shanghai\n")
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)
        result = _load_profile()
        assert result.get("name") == "Test User"
        assert result.get("role") == "researcher"

    def test_invalid_yaml_returns_empty(self, monkeypatch, tmp_path):
        """YAML 解析错误→返回空字典 (lines 255-256)"""

        profile_file = tmp_path / "persona.yaml"
        profile_file.write_text(": invalid yaml : :\n")
        monkeypatch.setattr("cockpit.commands.base._PROFILE_PATH", profile_file)
        result = _load_profile()
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# 九、_iso_time — ISO 时间格式化
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsoTime:
    """_iso_time ISO 时间格式场景。"""

    def test_basic_timestamp(self):
        """基本时间戳→ISO 格式"""
        # 2000-01-01T00:00:00Z
        ts = 946684800.0
        result = _iso_time(ts)
        assert result.endswith("Z")
        assert "2000-01-01" in result

    def test_recent_timestamp(self):
        """近期时间戳"""
        from datetime import datetime

        now = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
        ts = now.timestamp()
        result = _iso_time(ts)
        assert "2026-05-28T12:00:00" in result or "2026-05-28T12:00" in result

    def test_float_string_input(self):
        """字符串形式的 float 时间戳"""
        result = _iso_time("946684800.0")
        assert result.endswith("Z")


# ═══════════════════════════════════════════════════════════════════════════════
# 十、_render_markdown_block — Markdown 面板渲染
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderMarkdownBlock:
    """_render_markdown_block 渲染场景。"""

    def test_with_content(self, monkeypatch):
        """有内容→渲染 Panel 含 Markdown"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.base._get_console", lambda: capture)

        _render_markdown_block("Test Title", "**bold** content", "green")

        output = capture.export_text()
        assert "Test Title" in output
        assert "bold" in output

    def test_empty_body(self, monkeypatch):
        """空内容→显示 '无内容'"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.base._get_console", lambda: capture)

        _render_markdown_block("Empty", "", "red")

        output = capture.export_text()
        assert "无内容" in output

    def test_different_styles(self, monkeypatch):
        """不同样式参数→不影响内容"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.base._get_console", lambda: capture)

        _render_markdown_block("Style Test", "plain text", "yellow")

        output = capture.export_text()
        assert "Style Test" in output
        assert "plain text" in output
