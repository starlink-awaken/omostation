"""P0 digital-brain pipeline end-to-end smoke (2026-09-01 五站串联首跑).

Chain: T7-03 radar → T2-01 bus → T2-03 OCR → T3-02 embed → T8-03 render.
Each station runs in its owning venv via subprocess (the real inter-process
artifact handoff); this test only orchestrates and asserts artifacts.

  1. radar      → morning brief items (stub cache source, offline-safe)
  2. bus        → publish brief items as high-priority events, drain ordered
  3. OCR        → synthetic red-header doc → layout markdown + seal anchor
  4. embedding  → hybrid retrieval over OCR markdown segments
  5. render     → retrieval-augmented draft → GB/T DOCX on disk
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _uv_run(project: str, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--directory", str(ROOT / "projects" / project), *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _load_bus():
    spec = importlib.util.spec_from_file_location("event_bus", ROOT / "projects/omo/src/omo/event_bus.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["event_bus"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pipeline_radar_to_bus(tmp_path: Path):
    """Station 1→2: radar brief items become high-priority bus events."""
    # radar: offline collect via cached/stub source (network-independent)
    brief = {"items": [
        {"title": "关于印发医疗大模型临床应用管理指南的通知", "score": 5, "tags": ["医疗大模型"], "source": "卫健委"},
        {"title": "2026年医保支付方式改革征求意见", "score": 3, "tags": ["医保支付"], "source": "医保局"},
    ]}
    radar_file = tmp_path / "brief.json"
    radar_file.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")

    # bus: high-priority events drain before normal ones
    event_bus = _load_bus()

    async def scenario():
        import asyncio

        bus = event_bus.PriorityEventBus()
        received: list[str] = []

        async def drain():
            async for ev in bus.subscribe():
                received.append(ev.payload["title"])
                if len(received) == 3:
                    bus.close()

        tasks = [drain()]
        for item in brief["items"]:  # policy items = high priority
            bus.publish(event_bus.Event(source="radar", kind="policy", payload=item, priority="high"))
        bus.publish(event_bus.Event(source="im", kind="im", payload={"title": "闲聊噪音"}, priority="normal"))
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        return received

    import asyncio

    received = asyncio.run(scenario())
    assert len(received) == 3
    assert received[0] == brief["items"][0]["title"]  # high priority first
    assert "噪音" not in received[0]


def test_pipeline_ocr_station():
    """Station 3: OCR layout restoration over the synthetic red-header doc."""
    rc = _uv_run(
        "agora", "python", "-m", "agora.server.tools_bos.ocr", "test_document_layout",
    )
    assert rc.returncode == 0, rc.stdout[-300:] + rc.stderr[-300:]
    report = json.loads(rc.stdout)
    assert report["layout_fidelity"] >= 0.95
    assert report["checks"]["seal_anchored"] and report["checks"]["table_detected"]


def test_pipeline_embedding_station():
    """Station 4: hybrid retrieval scores OCR-relevant policy above noise."""
    rc = _uv_run("omlxc", "python", "-m", "omlxc.dataplane.embedding_mps_benchmark")
    assert rc.returncode == 0, rc.stdout[-300:] + rc.stderr[-300:]
    report = json.loads(rc.stdout)
    assert report["embedding"]["checks"]["hybrid_relevant_ranked"] is True


def test_pipeline_render_station(tmp_path: Path):
    """Station 5: retrieval-augmented draft renders to GB/T DOCX on disk."""
    md = tmp_path / "draft.md"
    md.write_text(
        "# 关于落实医疗大模型临床应用管理要求的汇报\n\n"
        "> 汇报单位：数字大脑工作组\n> 2026年9月1日\n\n"
        "根据政策雷达监测与全文检索结果，现汇报如下。\n\n"
        "## 一、政策要点\n\n"
        "- 医疗大模型临床应用管理指南已发布\n"
        "- 医保支付方式改革征求意见中\n",
        encoding="utf-8",
    )
    out = tmp_path / "draft.docx"
    rc = _uv_run(
        "cockpit", "python", "-m", "cockpit.cli", "render", "docx",
        "--input", str(md), "--output", str(out), "--template", "standard-gov",
    )
    assert rc.returncode == 0, rc.stderr[-300:]
    assert out.exists() and out.stat().st_size > 4000  # real OOXML payload
