"""LLM增强层测试 — 后端检测 + 增强入口 + 错误处理"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import os
from unittest.mock import MagicMock, patch

from ontoderive.intelligence.llm import LLMEnhancer


class TestLLMEnhancerInit:
    def test_none_backend(self):
        e = LLMEnhancer(backend="none")
        assert e.backend == "none"
        assert not e.available

    def test_unknown_backend(self):
        e = LLMEnhancer(backend="nonexistent")
        assert e.backend == "nonexistent"

    def test_openai_backend_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            e = LLMEnhancer(backend="openai")
            assert e.backend == "openai"
            assert not e.available

    def test_anthropic_backend_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            e = LLMEnhancer(backend="anthropic")
            assert e.backend == "anthropic"
            assert not e.available


class TestLLMEnhancerDetect:
    def test_detect_openai_with_key(self):
        with patch.dict(os.environ, {"ONTODERIVE_LLM_BACKEND": "auto", "OPENAI_API_KEY": "sk-test"}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("urllib.request.urlopen", side_effect=OSError):
                    e = LLMEnhancer(backend="auto")
                    assert e.backend == "openai"

    def test_detect_anthropic_with_key(self):
        with patch.dict(os.environ, {"ONTODERIVE_LLM_BACKEND": "auto", "ANTHROPIC_API_KEY": "sk-ant-test"}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("urllib.request.urlopen", side_effect=OSError):
                    e = LLMEnhancer(backend="auto")
                    assert e.backend == "anthropic"

    def test_detect_none_when_no_backend(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("urllib.request.urlopen", side_effect=OSError):
                    e = LLMEnhancer(backend="auto")
                    assert e.backend == "none"
                    assert not e.available

    def test_detect_ollama_with_models(self):
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "NAME\tID\tSIZE\nqwen3.5:4b\tabc\t3.5GB\n"
        with patch.dict(os.environ, {"ONTODERIVE_LLM_BACKEND": "auto"}):
            with patch("urllib.request.urlopen", side_effect=OSError):
                with patch("subprocess.run", return_value=mock_run):
                    e = LLMEnhancer(backend="auto")
                    assert e.backend == "ollama"

    def test_detect_litellm_from_standard_env(self):
        with patch.dict(
            os.environ,
            {
                "ONTODERIVE_LLM_BACKEND": "auto",
                "LLM_PROVIDER": "litellm",
                "LLM_BASE_URL": "http://127.0.0.1:4000/v1",
                "LLM_MODEL": "claude-3-5-sonnet",
                "LLM_API_KEY": "litellm-secret",
            },
            clear=True,
        ):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("urllib.request.urlopen", side_effect=OSError):
                    e = LLMEnhancer(backend="auto")
                    assert e.backend == "openai"
                    assert e.base_url == "http://127.0.0.1:4000/v1"
                    assert e.model == "claude-3-5-sonnet"
                    assert e.available


class TestLLMEnhancerCall:
    def test_call_unavailable_returns_none(self):
        e = LLMEnhancer(backend="none")
        result = e._call("prompt", "system", 0.3)
        assert result is None

    def test_ollama_call_timeout(self):
        e = LLMEnhancer(backend="ollama", model="test-model")
        e.available = True
        with patch("subprocess.run", side_effect=TimeoutError):
            result = e._call("prompt")
            assert result is None

    def test_local_call_timeout(self):
        e = LLMEnhancer(backend="local", model="test-model", base_url="http://localhost:1234")
        e.available = True
        with patch("urllib.request.urlopen", side_effect=OSError):
            result = e._call("prompt")
            assert result is None


class TestLLMEnhancerEnhancements:
    def test_enhance_derivation_no_llm(self):
        e = LLMEnhancer(backend="none")
        hints = e.enhance_derivation_hints("测试", "推论", ["hint1"])
        assert hints == ["hint1"]

    def test_detect_contradictions_no_llm(self):
        e = LLMEnhancer(backend="none")
        r = e.detect_contradictions("A", "B", ["D-F1"])
        assert r is None

    def test_smart_match_no_llm(self):
        e = LLMEnhancer(backend="none")
        tools = [{"id": "M-001", "name": "SWOT", "description": "框架"}]
        r = e.smart_match_tools("分析", "", tools)
        assert r is None


class TestLLMEnhancerMockCall:
    """使用mock enhancer模拟真实调用路径"""

    def test_enhance_derivation_with_mock_call(self):
        e = LLMEnhancer(backend="openai")
        e.available = True
        e.model = "gpt-4o-mini"
        with patch.object(e, "_call", return_value="建议: 增加事实引用"):
            hints = e.enhance_derivation_hints("事实", "推论", ["hint1"])
            assert len(hints) > 1
            assert any("事实引用" in h for h in hints)

    def test_detect_contradictions_with_mock_yes(self):
        e = LLMEnhancer(backend="openai")
        e.available = True
        with patch.object(e, "_call", return_value="YES"):
            assert e.detect_contradictions("A", "B", ["D-F1"]) is True

    def test_detect_contradictions_with_mock_no(self):
        e = LLMEnhancer(backend="openai")
        e.available = True
        with patch.object(e, "_call", return_value="NO"):
            assert e.detect_contradictions("A", "B", ["D-F1"]) is False

    def test_smart_match_with_mock(self):
        e = LLMEnhancer(backend="openai")
        e.available = True
        tools = [{"id": "M-001", "name": "SWOT", "description": "框架"}]
        with patch.object(e, "_call", return_value="M-001, S-002, T-003"):
            ids = e.smart_match_tools("分析", "", tools)
            assert ids == ["M-001", "S-002", "T-003"]

    def test_call_dispatch_openai(self):
        e = LLMEnhancer(backend="openai")
        e.available = True
        with patch.object(e._provider, "call", return_value="response") as mock:
            result = e._call("prompt", "system", 0.3)
            assert result == "response"
            mock.assert_called_once()

    def test_call_dispatch_ollama(self):
        e = LLMEnhancer(backend="ollama", model="qwen3.5:4b")
        e.available = True
        with patch.object(e._provider, "call", return_value="response") as mock:
            result = e._call("prompt", "system", 0.3)
            assert result == "response"
            mock.assert_called_once()

    def test_call_dispatch_local(self):
        e = LLMEnhancer(backend="local", model="test")
        e.available = True
        with patch.object(e._provider, "call", return_value="response") as mock:
            result = e._call("prompt", "system", 0.3)
            assert result == "response"
            mock.assert_called_once()


class TestLLMEnhancerEdgeCases:
    def test_model_selection_from_env(self):
        with patch.dict(os.environ, {"ONTODERIVE_LLM_MODEL": "gpt-4"}):
            e = LLMEnhancer(backend="openai")
            assert e.model == "gpt-4"

    def test_base_url_from_env(self):
        with patch.dict(os.environ, {"ONTODERIVE_LLM_URL": "http://my-proxy:8080"}):
            e = LLMEnhancer(backend="local")
            assert e.base_url == "http://my-proxy:8080"

    def test_ollama_probe_model_not_found(self):
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "NAME\tID\tSIZE\nother-model\tabc\t3.5GB\n"
        with patch.dict(os.environ, {"ONTODERIVE_LLM_BACKEND": "auto"}):
            with patch("subprocess.run", return_value=mock_run):
                e = LLMEnhancer(backend="auto", model="qwen3.5:4b")
                assert not e.available

    def test_probe_exception_returns_false(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            e = LLMEnhancer(backend="ollama", model="test")
            assert not e.available

    def test_get_enhancer_returns_singleton(self):
        from ontoderive.intelligence.llm import get_enhancer

        e1 = get_enhancer()
        e2 = get_enhancer()
        assert e1 is e2

    def test_get_enhancer_force(self):
        from ontoderive.intelligence.llm import get_enhancer

        e1 = get_enhancer()
        e2 = get_enhancer(force=True)
        assert e1 is not e2
