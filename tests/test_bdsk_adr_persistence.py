import pytest
from pathlib import Path
from agora.server.tools_bos import persona_bdsk_evaluate


@pytest.mark.asyncio
async def test_bdsk_evaluate_deep_mode_debate_log():
    res = await persona_bdsk_evaluate(
        topic="Adaptive Edge Routing and Memory Probing", mode="deep"
    )
    assert res["status"] == "ok"
    assert res["verdict"] == "PROCEED_WITH_GUARDRAILS"
    assert "board_reviews" in res
    assert "debate_log" in res
    assert len(res["debate_log"]) >= 2
    assert res["debate_log"][0]["speaker"] == "devil"
    assert res["debate_log"][0]["action"] == "CHALLENGE"


@pytest.mark.asyncio
async def test_bdsk_evaluate_persist_adr_true(tmp_path):
    target_dir = tmp_path / "decisions"
    res = await persona_bdsk_evaluate(
        topic="Adaptive Edge Routing and Memory Probing",
        mode="deep",
        persist_adr=True,
        adr_dir=str(target_dir),
    )
    assert res["status"] == "ok"
    assert "saved_adr_path" in res
    saved_path = Path(res["saved_adr_path"])
    assert saved_path.exists()
    assert saved_path.name.startswith("0399-adr-")
    assert saved_path.name.endswith(".md")


@pytest.mark.asyncio
async def test_bdsk_evaluate_persist_adr_content_check(tmp_path):
    target_dir = tmp_path / "decisions"
    topic_str = "Apple Silicon Hardware Pressure Probe"
    res = await persona_bdsk_evaluate(
        topic=topic_str, mode="deep", persist_adr=True, adr_dir=str(target_dir)
    )
    assert res["status"] == "ok"
    saved_path = Path(res["saved_adr_path"])
    content = saved_path.read_text(encoding="utf-8")

    # Check YAML Frontmatter
    assert "---" in content
    assert f'title: "B.D.S.K 虚拟董事会决策: {topic_str}"' in content
    assert 'status: "ACCEPTED"' in content
    assert (
        'decision-makers: "B.D.S.K Virtual Board (@Builder, @Devil, @Sage, @Keeper)"'
        in content
    )

    # Check 4-Corner Deliberation Headers
    assert "# ADR: B.D.S.K 虚拟董事会共识决策" in content
    assert "### 🧑‍💻 @Builder" in content
    assert "### ⚡️ @Devil" in content
    assert "### 🧠 @Sage" in content
    assert "### 👁️ @Keeper" in content
    assert "## 4. 后续执行检查关卡 (GaC Contract)" in content


@pytest.mark.asyncio
async def test_bdsk_evaluate_fast_mode_persist(tmp_path):
    target_dir = tmp_path / "decisions_fast"
    res = await persona_bdsk_evaluate(
        topic="Quick hotfix for log level",
        mode="fast",
        persist_adr=True,
        adr_dir=str(target_dir),
    )
    assert res["status"] == "ok"
    assert res["verdict"] == "PROCEED_FAST"
    saved_path = Path(res["saved_adr_path"])
    assert saved_path.exists()
    content = saved_path.read_text(encoding="utf-8")
    assert "PROCEED_FAST" in content
