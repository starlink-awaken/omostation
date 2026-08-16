"""P28-W1-E2E-DEMO — 单元测试.

目标:
  - 验证整条链路在 mock 环境下能跑通(< 30s)
  - 报告包含 ≥ 3 个可溯源引用
  - KOS 写入至少 1 个草稿实体
  - LLM 与 KOS 都可以被注入, 真实运行环境不依赖外部服务
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# 把脚本目录加进 sys.path, 让 `import e2e_health_demo` 可用
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
import sys

sys.path.insert(0, str(SCRIPTS_DIR))

import e2e_health_demo as demo  # type: ignore[reportMissingImports]
from kos.ontology._types import Entity, EntityType

# ── Fake KOS 客户端 ───────────────────────────────────────────


class FakeKOSStore:
    """在内存中模拟 KOS 写入与查询, 替代 sqlite3 连接."""

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}

    def put(self, e: Entity) -> dict[str, Any]:
        # 与真实 store.py 一致: entity_id 必须有合法前缀
        from kos.ontology._types import validate_entity_id

        if not validate_entity_id(e.entity_id):
            return {"error": f"Invalid entity ID: {e.entity_id}"}
        self.entities[e.entity_id] = e
        return {"status": "ok", "entity_id": e.entity_id}

    def search(self, query: str, entity_type: str | None = None, limit: int = 20) -> list[Entity]:
        out: list[Entity] = []
        q = query.lower()
        for e in self.entities.values():
            label_match = q in e.label.lower()
            alias_match = any(q in a.lower() for a in e.aliases)
            if label_match or alias_match:
                if entity_type is None or e.entity_type.value == entity_type:
                    out.append(e)
        return out[:limit]

    def get(self, entity_id: str) -> Entity | None:
        """返回完整实体(含 source/zone), 模拟 KOS get_entity."""
        return self.entities.get(entity_id)


# ── Fake LLM 客户端 ───────────────────────────────────────────


class FakeLLM:
    """返回固定的 LLM 输出, 含 [1] [2] [3] 引用."""

    OUTPUT = (
        "## 问题背景\n"
        "本问题涉及 [1] 和 [2], 与 [3] 也有关联.\n\n"
        "## 政策依据\n"
        "依据 [1] 与 [2] 推进.\n\n"
        "## 工作建议\n"
        "建议结合 [1] [2] [3] 三条政策落地."
    )

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system: str | None, prompt: str, temperature: float, max_tokens: int) -> str:
        self.calls += 1
        return self.OUTPUT


# ── 公共 fixture ──────────────────────────────────────────────


@pytest.fixture
def fake_kos():
    store = FakeKOSStore()
    with (
        patch.object(demo, "put_entity", side_effect=store.put),
        patch.object(demo, "search_entities", side_effect=store.search),
        patch.object(demo, "get_entity", side_effect=store.get),
    ):
        yield store


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


# ── 单元测试 ──────────────────────────────────────────────────


class TestSeedAndSearch:
    def test_seed_writes_five_policies(self, fake_kos: FakeKOSStore) -> None:
        written = demo.seed_health_policies()
        assert len(written) == 5
        # 全部以 CON- 前缀写入
        for e in written:
            assert e.entity_id.startswith("CON-")
        # 真实 KOS 落库
        assert len(fake_kos.entities) == 5

    def test_seed_is_idempotent(self, fake_kos: FakeKOSStore) -> None:
        first = demo.seed_health_policies()
        second = demo.seed_health_policies()
        assert len(first) == len(second) == 5
        # store 仍只有 5 条, 不会重复追加
        assert len(fake_kos.entities) == 5

    def test_search_finds_relevant_policies(self, fake_kos: FakeKOSStore) -> None:
        demo.seed_health_policies()
        results = demo.search_related_policies("基层医疗机构药品集采")
        labels = {e.label for e in results}
        # 问题含"基层""医疗""药品""集采"四个核心词, 5 条种子政策中至少 3 条应被命中
        assert "国家组织药品集中采购政策" in labels
        assert "基层医疗机构药品配备使用" in labels
        assert len(results) >= 3, f"期望 ≥3 条命中, 实际 {len(results)}: {labels}"

    def test_extract_keywords_filters_stopwords(self) -> None:
        kws = demo._extract_keywords("基层医疗机构药品集采")
        assert kws  # 至少 1 个
        # 停用词不应出现
        assert "的" not in kws
        assert "与" not in kws
        # 含"药品"和"集采"等核心词
        assert "药品" in kws
        assert "集采" in kws


class TestDraftGeneration:
    def test_template_draft_has_three_sections(self) -> None:
        entities = [
            Entity(
                entity_id="CON-x-001",
                entity_type=EntityType.CONCEPT,
                label="政策一",
                description="描述一",
                source="来源一",
            ),
            Entity(
                entity_id="CON-x-002",
                entity_type=EntityType.CONCEPT,
                label="政策二",
                description="描述二",
                source="来源二",
            ),
        ]
        summary, sections = demo.generate_draft_template("测试问题", entities)
        assert summary
        assert len(sections) == 3
        for s in sections:
            assert s.references  # 每节都有引用

    def test_llm_draft_parses_references(self, fake_llm: FakeLLM) -> None:
        entities = [
            Entity(entity_id="CON-x-001", entity_type=EntityType.CONCEPT, label="P1", source="S1"),
            Entity(entity_id="CON-x-002", entity_type=EntityType.CONCEPT, label="P2", source="S2"),
            Entity(entity_id="CON-x-003", entity_type=EntityType.CONCEPT, label="P3", source="S3"),
        ]
        result = asyncio.run(demo.generate_draft_with_llm("测试", entities, fake_llm))
        assert result is not None
        summary, sections = result
        assert len(sections) >= 3
        # 至少 3 条独立来源(从 3 个实体映射)
        all_refs: set[str] = set()
        for s in sections:
            all_refs.update(s.references)
        assert len(all_refs) >= 3

    def test_llm_draft_returns_none_when_no_entities(self, fake_llm: FakeLLM) -> None:
        result = asyncio.run(demo.generate_draft_with_llm("测试", [], fake_llm))
        assert result is None

    def test_llm_draft_returns_none_when_llm_unavailable(self) -> None:
        entities = [Entity(entity_id="CON-x-001", entity_type=EntityType.CONCEPT, label="P1")]
        result = asyncio.run(demo.generate_draft_with_llm("测试", entities, None))
        assert result is None


class TestEndToEnd:
    def test_full_chain_under_30_seconds(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "report.md"
        start = time.perf_counter()
        summary = demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=fake_llm,
            seed_first=True,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0, f"链路耗时 {elapsed:.2f}s, 超 30s 验收线"
        assert summary["elapsed_seconds"] < 30.0

    def test_full_chain_writes_draft_to_kos(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "report.md"
        summary = demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=fake_llm,
            seed_first=True,
        )
        # 草稿写入
        assert summary["draft_entity_id"].startswith("CON-")
        assert summary["draft_entity_id"] in fake_kos.entities
        # 5 条种子 + 1 条草稿 = 6
        assert len(fake_kos.entities) == 6

    def test_report_has_at_least_three_references(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "report.md"
        demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=fake_llm,
            seed_first=True,
        )
        assert output.exists()
        text = output.read_text(encoding="utf-8")
        # 报告章节 4 列出引用清单, 必须 ≥ 3 条
        ref_section = text.split("## 4. 可溯源引用清单")[1].split("## 5.")[0]
        items = [line for line in ref_section.splitlines() if line.strip().startswith(tuple("123456789"))]
        assert len(items) >= 3, f"引用数 {len(items)} 不足 3, 报告段落:\n{ref_section}"

    def test_report_contains_kos_record_pointer(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "report.md"
        summary = demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=fake_llm,
            seed_first=True,
        )
        text = output.read_text(encoding="utf-8")
        assert summary["draft_entity_id"] in text
        assert "KOS" in text or "gbrain" in text

    def test_chain_works_without_llm(
        self,
        fake_kos: FakeKOSStore,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LLM 不可用时, 模板式初稿仍能完成链路, 验收不阻塞."""
        monkeypatch.setenv("E2E_DEMO_NO_DEFAULT_LLM", "1")
        output = tmp_path / "report_no_llm.md"
        summary = demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=None,
            seed_first=True,
        )
        assert summary["used_llm"] is False
        assert summary["reference_count"] >= 3
        assert output.exists()

    def test_chain_works_without_seed(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
    ) -> None:
        """跳过种子步骤时, 应有 0 条命中但仍能写出草稿."""
        output = tmp_path / "report_no_seed.md"
        summary = demo.run(
            question="基层医疗机构药品集采政策梳理",
            output_path=output,
            llm=fake_llm,
            seed_first=False,
        )
        assert summary["entities_found"] == 0
        # 仍写入 1 条草稿(无引用, 但有草稿实体)
        assert summary["draft_entity_id"] in fake_kos.entities


class TestCLI:
    def test_main_runs_with_default_question(
        self,
        fake_kos: FakeKOSStore,
        fake_llm: FakeLLM,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI 主流程跑通, 输出包含关键摘要."""
        out = tmp_path / "cli_report.md"
        # 用 fake LLM 替换默认 LLM, 通过 patch make_default_llm
        monkeypatch.setattr(demo, "make_default_llm", lambda: fake_llm)

        rc = demo.main(["--output", str(out)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "完成" in captured.out
        assert out.exists()
        # CLI 打印的摘要包含关键字段
        assert "draft_entity_id" in captured.out
        assert "elapsed_seconds" in captured.out

    def test_main_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            demo.main(["--help"])
        assert exc.value.code == 0
