"""materialize-agent-brief 的合同测试（hermetic: 全部用临时目录，不碰真实 state root）。

被测契约（2026-10-26，BET-Y2Q4-T1-05）:
1. 物化 = **原样复制**：``generated_at`` 逐字保留，**绝不重打戳**；另附 provenance 块。
2. 交叉校验：pointer → manifest → artifact 逐层校验 sha256。
3. **不写半截**：源缺失 / 不可解析 / 哈希不符 ⇒ 不写目标文件、退出码非 0。
4. 原子写：读者永远看不到半截文件。

运行: ``uv run pytest tests/bin/test_materialize_agent_brief.py -q``
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "panorama" / "materialize-agent-brief.py"

_spec = importlib.util.spec_from_file_location("materialize_agent_brief", str(SCRIPT))
mat = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(mat)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _make_source(tmp_path: Path, *, brief: dict | None = None, corrupt_hash: bool = False) -> Path:
    """造一棵合法的 projection state root（pointer + manifest + artifact）。"""
    source_root = tmp_path / "state-root"
    revision_id = "a" * 64
    brief_body = json.dumps(
        brief
        if brief is not None
        else {
            "schema": "panorama-agent-brief/v1",
            "available": True,
            "generated_at": "2026-10-23T22:44:45Z",
            "objective_coverage": {"items": []},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    artifact_sha = _sha256(brief_body)
    if corrupt_hash:
        artifact_sha = "b" * 64

    revision_root = source_root / "revisions" / revision_id
    revision_root.mkdir(parents=True)
    (revision_root / "agent-brief.json").write_bytes(brief_body)

    manifest = {
        "schema_version": "zhixing-projection-manifest/v1",
        "revision_id": revision_id,
        "generated_at": "2026-10-26T10:24:09Z",
        "artifacts": {
            "agent_brief": {"filename": "agent-brief.json", "sha256": artifact_sha},
        },
    }
    manifest_body = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (revision_root / "manifest.json").write_bytes(manifest_body)

    pointer = {
        "schema_version": "zhixing-projection-pointer/v1",
        "revision_id": revision_id,
        "manifest_sha256": _sha256(manifest_body),
    }
    (source_root / "current-revision.json").write_text(
        json.dumps(pointer, ensure_ascii=False), encoding="utf-8"
    )
    return source_root


def test_materialize_copies_verbatim_with_provenance(tmp_path):
    source_root = _make_source(tmp_path)
    target = tmp_path / "out" / "agent-brief.json"

    rc = mat.main(["--source-root", str(source_root), "--target", str(target)])

    assert rc == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    # 原样复制: generated_at 逐字保留, 没有被重新打戳
    assert payload["generated_at"] == "2026-10-23T22:44:45Z"
    # 语义内容原样带过来
    assert payload["schema"] == "panorama-agent-brief/v1"
    assert payload["objective_coverage"] == {"items": []}
    # provenance 块
    provenance = payload["provenance"]
    assert provenance["revision_id"] == "a" * 64
    assert provenance["data_generated_at"] == "2026-10-23T22:44:45Z"
    assert provenance["source_path"].endswith("agent-brief.json")
    assert provenance["copied_at"]


def test_materialize_check_does_not_write(tmp_path):
    source_root = _make_source(tmp_path)
    target = tmp_path / "out" / "agent-brief.json"

    rc = mat.main(["--source-root", str(source_root), "--target", str(target), "--check"])

    assert rc == 0
    assert not target.exists()


def test_missing_source_does_not_write(tmp_path):
    target = tmp_path / "out" / "agent-brief.json"

    rc = mat.main(["--source-root", str(tmp_path / "nope"), "--target", str(target)])

    assert rc != 0
    assert not target.exists()


def test_corrupt_artifact_does_not_touch_target(tmp_path):
    source_root = _make_source(tmp_path, corrupt_hash=True)
    target = tmp_path / "out" / "agent-brief.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"sentinel": true}\n', encoding="utf-8")
    before = target.read_bytes()

    rc = mat.main(["--source-root", str(source_root), "--target", str(target)])

    assert rc != 0
    assert target.read_bytes() == before


def test_brief_without_generated_at_does_not_write(tmp_path):
    source_root = _make_source(tmp_path, brief={"schema": "panorama-agent-brief/v1"})
    target = tmp_path / "out" / "agent-brief.json"

    rc = mat.main(["--source-root", str(source_root), "--target", str(target)])

    assert rc != 0
    assert not target.exists()


def test_manifest_hash_mismatch_does_not_write(tmp_path):
    source_root = _make_source(tmp_path)
    pointer_path = source_root / "current-revision.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["manifest_sha256"] = "c" * 64
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False), encoding="utf-8")
    target = tmp_path / "out" / "agent-brief.json"

    rc = mat.main(["--source-root", str(source_root), "--target", str(target)])

    assert rc != 0
    assert not target.exists()
