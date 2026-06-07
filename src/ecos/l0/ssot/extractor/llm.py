"""
ssot-kernel — extractor/llm.py
================================
LLM 提取器：通过本地或远程 LLM 从自由文本中提取结构化知识。

支持后端：
1. Ollama（本地，默认）— http://localhost:11434
2. OpenAI 兼容 API（OpenAI / vLLM / 硅基流动等）

设计原则：
- 模板提取器优先（快、免费、确定），LLM 兜底（慢、有成本、非确定）
- LLM 输出必须经过 CandidateValidator 校验后才写入 YAML
- 所有提取结果标记 verified_by=llm，可追溯
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

from .base import ExtractionCandidate, ExtractionResult, Extractor, TextSource

# ── LLM 后端基类 ──────────────────────────────────────


class LLMBackend(ABC):
    """LLM 后端抽象类。所有后端（Ollama/OpenAI）实现此接口。"""

    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        """发送 prompt 给 LLM，返回文本响应"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        ...


class OllamaBackend(LLMBackend):
    """Ollama 本地后端"""

    def __init__(self, model: str = "", base_url: str = ""):
        # 默认模型：qwen3.5:4b（速度快，召回高，精度可接受）
        # 可被 OLLAMA_MODEL 环境变量覆盖
        default_model = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
        self.model = model or default_model
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST", "") or "http://localhost:11434").rstrip("/")

    def health_check(self) -> str:
        """快速检测 Ollama 是否可达。

        Returns:
            空字符串 = 正常；非空字符串 = 错误描述
        """
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")  # noqa: S310
            urllib.request.urlopen(req, timeout=2)  # noqa: S310
            return ""
        except urllib.error.URLError as e:
            if isinstance(e.reason, ConnectionRefusedError):
                return "Ollama 服务未启动"
            return f"Ollama 不可达: {e.reason}"
        except TimeoutError:
            return f"Ollama ({self.base_url}) 2 秒无响应"
        except Exception as e:
            return f"Ollama 检测异常: {e}"

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        import json as _json
        import urllib.request

        # 先快速健康检查，避免卡在 urlopen 上
        health = self.health_check()
        if health:
            raise ConnectionError(
                f"无法连接到 Ollama ({self.base_url}): {health}\n"
                f"  ───\n"
                f"  📋 本地已安装 Ollama，但服务未运行。请执行:\n"
                f"     $ ollama serve\n"
                f"  \n"
                f"  然后确认模型已下载:\n"
                f"     $ ollama pull {self.model}\n"
                f"  \n"
                f"  验证状态:\n"
                f"     $ ollama ps"
            )

        payload = _json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "temperature": temperature,
            }
        ).encode()

        timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

        req = urllib.request.Request(  # noqa: S310
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Ollama 请求失败 ({self.base_url}): {e.reason}\n  请确认 Ollama 正在运行 (ollama ps)"
            ) from e
        except TimeoutError:
            raise TimeoutError(
                f"Ollama ({self.base_url}) {timeout} 秒无响应，请检查:\n"
                f"  1. 模型是否正在加载中 (ollama ps)\n"
                f"  2. 模型 '{self.model}' 是否已下载 (ollama pull {self.model})\n"
                f"  3. 如需更长等待，可设置环境变量 OLLAMA_TIMEOUT=300"
            ) from None
        data = _json.loads(resp.read().decode())
        return data.get("message", {}).get("content", "")


class OpenAIBackend(LLMBackend):
    """OpenAI 兼容 API 后端（也支持 vLLM / 硅基流动等）"""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = "", base_url: str = "https://api.openai.com/v1"):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        import json as _json
        import urllib.request

        payload = _json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
        ).encode()

        req = urllib.request.Request(  # noqa: S310
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)  # noqa: S310
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"无法连接到 OpenAI API ({self.base_url}): {e.reason}\n  请检查 API 地址和网络连接"
            ) from e
        except TimeoutError:
            raise TimeoutError(f"OpenAI API ({self.base_url}) 30 秒无响应") from None
        data = _json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


def _standard_backend_from_env() -> LLMBackend | None:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        return None

    model = os.environ.get("LLM_MODEL", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()

    if provider == "ollama":
        return OllamaBackend(
            model=model or "qwen3.5:4b",
            base_url=base_url or "http://localhost:11434",
        )

    if provider in {"litellm", "openai", "openrouter", "deepseek", "siliconflow"}:
        return OpenAIBackend(
            model=model or "gpt-4o-mini",
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            base_url=base_url or "https://api.openai.com/v1",
        )

    return None


# ── LLM 提取器 ──────────────────────────────────────────

# 系统提示词：指令 LLM 从文本中提取结构化知识
SYSTEM_PROMPT = """你是一个知识提取器。从用户提供的文本中提取实体、事实、推论和关系。

输出格式：纯 YAML，不要包含任何解释或```标记。直接以 entities: / facts: / inferences: 开头。

## 实体提取规则

entities:
  - id: 唯一ID（前缀-名称，如 person-yangbo / ORG-国转中心 / org-gzzx）
    type: Person | Organization | Role | Project
    meta_type: MET-DOMAIN
    name: 名称
    status: active | draft | deprecated
    attributes:
      nature: 本质描述（尽量提取原文字句）
      source: 信息来源

## 事实提取规则

facts:
  - id: 唯一ID（POL-编号 / DAT-编号）
    title: 标题
    value: 数值（如果没有数值就写描述）
    unit: 单位（如适用）
    source: 来源
    date: 日期

## 规则

- 只提取文本中明确陈述或强烈暗示的信息，不要编造
- 不确定的字段留空
- 文本中没有可提取的结构化信息时，请输出一个空列表：entities: []
- 不要添加任何不在原文中的推论或判断"""


class LLMExtractor(Extractor):
    """LLM 提取器：通过本地或远程 LLM 从自由文本提取知识。

    支持后端链：自动检测 Ollama / 硅基流动 / DeepSeek / OpenAI，
    extract() 会按优先级依次尝试，失败自动降级到下一个后端。

    使用方式：
        1. 默认 auto_detect=True — 自动扫描环境变量，构建后端链
        2. 手动传入 backends 列表 — 精确指定
        3. backends=[OllamaBackend("qwen3.5:4b")] — 只用 Ollama
    """

    def __init__(self, backends: list[LLMBackend] | None = None, auto_detect: bool = True):
        self.backends = backends or []
        if not self.backends and auto_detect:
            self.backends = self._detect_backends()

    @property
    def available(self) -> bool:
        return len(self.backends) > 0

    @property
    def extractor_name(self) -> str:
        if self.available:
            names = ", ".join(b.name for b in self.backends)
            return f"llm:[{names}]"
        return "llm:unavailable"

    def can_handle(self, source: TextSource) -> bool:
        """LLM 提取器可以处理任何文本"""
        return self.available

    # ── extract 核心：遍历后端链 ─────────────────────

    def extract(self, source: TextSource) -> ExtractionResult:
        if not self.available:
            return ExtractionResult(
                summary="LLM 提取器不可用：未检测到可用的 LLM 后端",
                errors=self._build_no_backend_guide(),
            )

        text = source.raw_text

        # 大文档走分块提取
        if len(text) > 8000:
            return self._chunked_extract(text, source.source_name)

        if len(text) > 6000:
            text = text[:8000] + f"\n\n（原文共 {len(text)} 字符，已截断至前 8000 字符）"

        user_prompt = f"""从以下文本中提取实体和事实：

---文本开始---
{text}
---文本结束---

输出 YAML 格式的提取结果。不要添加不在原文中的信息。"""

        # 遍历后端链，依次尝试
        errors = []
        for backend in self.backends:
            try:
                response = backend.complete(SYSTEM_PROMPT, user_prompt, temperature=0.1)
            except Exception as e:
                errors.append(f"[{backend.name}] {e}")
                continue

            candidates = self._parse_response(response)
            if candidates:
                return ExtractionResult(
                    candidates=candidates,
                    summary=f"LLM 提取完成: {len(candidates)} 个候选 (后端: {backend.name})",
                    confidence=0.7,
                )

        return ExtractionResult(
            summary="所有 LLM 后端均无法提取",
            errors=errors,
        )

    def _chunked_extract(self, text: str, source_name: str) -> ExtractionResult:
        """大文档分块提取：按 AST 章节分块，逐块送 LLM，合并去重

        选择第一个健康的后端执行全部分块提取（不跨后端混合）。
        """
        import sys

        # 选第一个可用的后端（有 health_check 的优先验证）
        backend = self._pick_backend()
        if backend is None:
            return ExtractionResult(
                summary="所有 LLM 后端均不可用",
                errors=self._build_no_backend_guide(),
            )

        from .chunker import Chunker

        chunker = Chunker(max_chars=7000)
        chunks = chunker.chunk_by_sections(text)
        print(f"  📦 大文档: {len(text)}字 → {len(chunks)} 块 (完整章节)", file=sys.stderr)

        all_candidates = []
        seen_ids = set()

        for i, chunk in enumerate(chunks):
            if not chunk.content.strip():
                continue
            section_name = chunk.headings[0] if chunk.headings else f"段落{i + 1}"
            print(
                f"  ▶ 块{i + 1}/{len(chunks)}: {section_name} ({chunk.char_count}字 ~{chunk.token_estimate}tok)",
                file=sys.stderr,
            )

            context_prompt = f"""请从以下「{section_name}」章节中提取实体和事实。

只提取本段中明确出现的内容。实体使用 person-xxx / org-xxx / project-xxx 格式的 ID。

---文本开始---
{chunk.content}
---文本结束---

输出 YAML 格式。只输出 entities: 和 facts: 字段。如果某类没有内容就写空列表。"""

            try:
                response = backend.complete(SYSTEM_PROMPT, context_prompt, temperature=0.1)
            except Exception as e:
                print(f"    ❌ 块{i + 1} {backend.name} 调用失败: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)
                continue

            chunk_candidates = self._parse_response(response)
            print(f"    → LLM提取 {len(chunk_candidates)} 个候选", file=sys.stderr)

            # 确权过滤（去幻觉）+ 块内去重
            before = len(chunk_candidates)
            chunk_candidates = self._confirm_candidates(chunk_candidates, chunk.content)
            chunk_seen = set()
            deduped = []
            for c in chunk_candidates:
                cid = c.id or c.content.get("id", "")
                if cid:
                    if cid not in chunk_seen:
                        chunk_seen.add(cid)
                        deduped.append(c)
                else:
                    deduped.append(c)
            chunk_candidates = deduped
            after_dedup = before - (len(chunk_candidates) + (before - len(deduped)))
            print(f"    → 确权过滤 {before - len(chunk_candidates)} 幻觉, {after_dedup} 重复", file=sys.stderr)

            # 合并去重
            for c in chunk_candidates:
                cid = c.id or c.content.get("id", "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    all_candidates.append(c)
                elif not cid:
                    all_candidates.append(c)

        return ExtractionResult(
            candidates=all_candidates,
            summary=f"分块LLM提取: {len(chunks)}块 → {len(all_candidates)} 候选 (后端: {backend.name})",
            confidence=0.7,
        )

    def _pick_backend(self) -> LLMBackend | None:
        """从后端链中选第一个健康的后端"""
        for b in self.backends:
            if hasattr(b, "health_check"):
                health = b.health_check()
                if not health:
                    return b
            else:
                return b
        # 没有健康的后端 → 再试第一个，让它抛异常给上层
        return self.backends[0] if self.backends else None

    def _confirm_candidates(self, candidates: list[ExtractionCandidate], source_text: str) -> list[ExtractionCandidate]:
        """确权过滤：只保留在原文中出现过的候选（去 LLM 幻觉）"""
        result = []
        for c in candidates:
            cid = c.id or c.content.get("id", "")
            if not cid:
                result.append(c)
                continue
            # 在原文中搜索 ID
            if cid in source_text:
                result.append(c)
                continue
            # 去掉前缀的短 ID
            parts = cid.split("-", 1)
            if len(parts) > 1 and parts[1] in source_text:
                result.append(c)
                continue
            # 未在原文中找到 → 可能是幻觉
            # print(f"    🚫 幻觉过滤: {cid}", file=sys.stderr)
        return result

    def _parse_response(self, response: str) -> list[ExtractionCandidate]:
        """解析 LLM 的 YAML 响应，处理多种常见输出格式"""
        candidates: list[ExtractionCandidate] = []
        raw = response.strip()

        # 调试：保存原始响应（可通过 --verbose 查看）
        self._last_raw_response = raw

        # 策略1：直接提取 ```yaml ... ``` 块（最标准）
        yaml_block = re.search(r"```(?:yaml|yml)?\s*\n(.*?)\n\s*```", raw, re.DOTALL)
        yaml_text = yaml_block.group(1) if yaml_block else raw

        # 策略2：如果响应包含"这里是提取结果"之类的文字，尝试找 YAML 开始
        if not yaml_block:
            # 找 "entities:" 或 "facts:" 开始的结构
            yaml_start = re.search(r"\b(entities:|facts:|inferences:)", yaml_text)
            if yaml_start:
                yaml_text = yaml_text[yaml_start.start() :]

        # 策略3：以上都不行，直接尝试解析整个 cleaned 文本
        cleaned = yaml_text.strip()
        # 移除 ``` 残留
        cleaned = re.sub(r"^```\w*\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.MULTILINE)

        # 尝试解析
        data = None
        try:
            import yaml

            data = yaml.safe_load(cleaned)
        except Exception:
            pass

        if not data or not isinstance(data, dict):
            # 最后尝试：看看是不是被包裹在更多文字里
            fallback = re.search(r"((?:entities:|facts:).*)", raw, re.DOTALL)
            if fallback:
                try:
                    import yaml

                    data = yaml.safe_load(fallback.group(1))
                except Exception:
                    pass

        if not data or not isinstance(data, dict):
            return candidates

        # 解析 entities
        for ent in data.get("entities", []) or []:
            if isinstance(ent, dict):
                candidates.append(
                    ExtractionCandidate(
                        category="entity",
                        id=ent.get("id", ""),
                        content=ent,
                        confidence=0.7,
                    )
                )

        # 解析 facts
        for fact in data.get("facts", []) or []:
            if isinstance(fact, dict):
                candidates.append(
                    ExtractionCandidate(
                        category="fact",
                        id=fact.get("id", ""),
                        content=fact,
                        confidence=0.7,
                    )
                )

        return candidates

    @staticmethod
    def _build_no_backend_guide() -> list[str]:
        """生成无可用后端时的引导信息"""
        return [
            "未检测到可用的 LLM 后端。可通过以下方式配置:",
            "",
            "  📍 方式一: 本地 Ollama（推荐，免费）",
            "     $ ollama serve",
            "     $ ollama pull qwen3.5:4b",
            "",
            "  📍 方式二: 云端 API（选一个即可）",
            "     # 硅基流动（国内，便宜）",
            "     $ export SILICONFLOW_API_KEY=sf-xxx",
            "",
            "     # DeepSeek（国内，便宜）",
            "     $ export DEEPSEEK_API_KEY=sk-xxx",
            "",
            "     # OpenAI",
            "     $ export OPENAI_API_KEY=sk-xxx",
            "",
            "  📍 方式三: 跳过 LLM，直接编辑 YAML",
            "     $ vim domain/entities.yaml",
        ]

    def _detect_backends(self) -> list[LLMBackend]:
        """自动检测可用的 LLM 后端，按优先级返回后端链。

        优先级: Ollama → 硅基流动 → DeepSeek → OpenAI
        extract() 会依次尝试直到成功。
        """
        import os
        import sys

        backends: list[LLMBackend] = []
        standard_backend = _standard_backend_from_env()
        if standard_backend is not None:
            backends.append(standard_backend)
            print(f"  🔌 [{len(backends)}] 标准 LLM 路由 ({standard_backend.name})", file=sys.stderr)

        # ── 1. Ollama（本地，免费，最快） ──────────────
        try:
            import json
            import urllib.request

            req = urllib.request.Request("http://localhost:11434/api/tags")
            resp = urllib.request.urlopen(req, timeout=2)  # noqa: S310
            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            if models:
                preferred = [
                    "qwen3.5:4b",
                    "qwen3.5",
                    "qwen2.5:7b",
                    "qwen2.5",
                    "deepseek-r2:7b",
                    "deepseek-r1:7b",
                    "llama3.2",
                    "mistral",
                ]
                chosen = None
                for p in preferred:
                    for m in models:
                        if p in m.get("name", ""):
                            chosen = m["name"]
                            break
                    if chosen:
                        break
                if not chosen:
                    chosen = models[0]["name"]
                if ":" not in chosen:
                    chosen = f"{chosen}:latest"
                backends.append(OllamaBackend(model=chosen))
                print(f"  🔌 [{len(backends)}] Ollama (模型: {chosen})", file=sys.stderr)
        except Exception:
            pass

        # ── 2. 硅基流动（国内用户友好，价格便宜） ──────
        sf_key = os.environ.get("SILICONFLOW_API_KEY", "")
        if sf_key:
            sf_model = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct")
            sf_url = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            backends.append(
                OpenAIBackend(
                    model=sf_model,
                    api_key=sf_key,
                    base_url=sf_url,
                )
            )
            print(f"  🔌 [{len(backends)}] 硅基流动 (模型: {sf_model})", file=sys.stderr)

        # ── 3. DeepSeek（国内，价格便宜） ──────────────
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if ds_key:
            ds_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
            ds_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            backends.append(
                OpenAIBackend(
                    model=ds_model,
                    api_key=ds_key,
                    base_url=ds_url,
                )
            )
            print(f"  🔌 [{len(backends)}] DeepSeek (模型: {ds_model})", file=sys.stderr)

        # ── 4. OpenAI（通用，较贵） ────────────────────
        oa_key = os.environ.get("OPENAI_API_KEY", "")
        if oa_key:
            oa_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            oa_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            backends.append(
                OpenAIBackend(
                    model=oa_model,
                    api_key=oa_key,
                    base_url=oa_url,
                )
            )
            print(f"  🔌 [{len(backends)}] OpenAI (模型: {oa_model})", file=sys.stderr)

        # ── 结果 ──────────────────────────────────────
        if backends:
            names = " → ".join(b.name.split("/")[0] for b in backends)
            print(f"  📎 LLM 后端链: {names}", file=sys.stderr)
        else:
            print(
                "  ⚠️  未检测到可用的 LLM 后端\n"
                "  ───\n"
                "  如需使用 LLM 提取，请:\n"
                "  \n"
                "  📍 启动本地 Ollama:\n"
                "     $ ollama serve\n"
                "  \n"
                "  📍 或配置云端 API Key:\n"
                "     $ export SILICONFLOW_API_KEY=sf-xxx\n"
                "     $ export DEEPSEEK_API_KEY=sk-xxx\n"
                "     $ export OPENAI_API_KEY=sk-xxx\n"
                "  \n"
                "  📍 或直接编辑 YAML:\n"
                "     $ vim domain/entities.yaml",
                file=sys.stderr,
            )

        return backends


# ── 向后兼容 ──────────────────────────────────────────
# 新代码推荐使用 llm-gateway，旧代码通过此别名继续工作
