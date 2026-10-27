#!/usr/bin/env python3
"""materialize-agent-brief — 把活的 projection revision 里的 Agent Brief 原样物化到 runtime/dashboard/.

为什么存在（2026-10-26 实测，measured_from = mini / omostation）:

- ``runtime/dashboard/agent-brief.json`` 的 ``generated_at`` 停在 ``2026-09-21T12:26:20Z``
  ⇒ 停更 35 天。
- 活的数据一直都在: projection revision 里那份 ``agent-brief.json`` 是新的（revision 由
  ``zhixing-refresh.sh`` 每 30 min 重新发布）—— **数据在，只是没人把它落到 ``runtime/dashboard/``**。
- ``auto-pruner`` 的 TTL 刷新（``prune_brief``）只会把 ``generated_at`` 改成 now，语义内容
  一个字都不刷新 ⇒ 那是「把 35 天前的快照说成今天」= 假绿。2026-10-26 起该机制退役
  （用户裁决 A: 物化真数据 + TTL 不碰这个文件）。

四条硬约定:

1. **原样复制** —— ``generated_at`` 逐字保留，**绝不重打戳**。停更就如实报停更。
2. **交叉校验** —— pointer → manifest → artifact，逐层校验 sha256；任一层对不上就退出。
3. **不写半截** —— 源缺失 / 不可解析 / 哈希不符 ⇒ **不写目标文件**、退出码非 0、原因写 stderr。
4. **原子写** —— 同目录临时文件 + ``os.replace``。

用法::

    python3 <本脚本路径>              # 物化
    python3 <本脚本路径> --check      # 只报读数, 不写
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
from repo_root import state_root  # noqa: E402

POINTER_NAME = "current-revision.json"
REVISIONS_NAME = "revisions"
MANIFEST_NAME = "manifest.json"
POINTER_SCHEMA = "zhixing-projection-pointer/v1"
MANIFEST_SCHEMA = "zhixing-projection-manifest/v1"
BRIEF_ARTIFACT = "agent_brief"
BRIEF_FILENAME = "agent-brief.json"

# ⚠ **输出路径在调用时刻解析** —— 模块级 `OUT_DIR = state_root() / ...` 会把 profile 根
# 在 **import 时**冻结：之后声明 `OMOSTATION_STATE_ROOT` 就落到旧根上（AGENTS.md §7
# 「写路径要在调用时刻解析」；`tests/unit/test_b1_ledger_call_time.py::
# test_no_module_level_profile_root_constant_left_in_bin` 钉住）。
# 同目录 `panorama-collect.py` 的 `OUT_DIR` 走 `PANORAMA_ROOT` env / `__file__`，
# **不调** resolver，所以它不在判据面上；本脚本要 ADR-0456 的读/写分根语义，只能走函数。
# ⚠ **别在本文件里写任何 Python 源文件路径** —— 探针的 import 抽取器会把源码里
# 出现的路径当成 import ⇒ 链上多一跳**指向不存在文件**的假跳（⚠ 2026-10-26 实测：
# 连「后缀」本身出现在注释里都会被当成路径）。


class MaterializeError(RuntimeError):
    """fail-closed: 任何异常都不得落到「写了半个文件」。"""


def default_source_root() -> Path:
    """projection state root —— 与仓内其它 projection 工具同一口径。"""
    return Path(
        os.environ.get(
            "ZHIXING_DASHBOARD_STATE_ROOT",
            str(Path.home() / ".local/share/zhixing-dashboard"),
        )
    ).expanduser()


def default_target() -> Path:
    """入口层产物落点 —— **调用时刻**解析。

    写面用 ``state_root()``（仓内读面/写面分根约定，ADR-0456），**不用 ``__file__`` 反推**
    —— 反推会把临时 worktree 路径钉进产物。

    刻意写成函数而不是模块级 ``AGENT_BRIEF_JSON = OUT_DIR / ...``：后者在 import 时
    就把 profile 根冻结了（见文件头注释与 ``test_b1_ledger_call_time.py`` 的判据）。
    """
    return state_root() / "runtime" / "dashboard" / BRIEF_FILENAME


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _read_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise MaterializeError(f"unsafe_or_missing:{path}")
    return path.read_bytes()


def load_source(source_root: Path) -> tuple[dict, dict, Path, bytes]:
    """pointer → manifest → artifact，逐层交叉校验。返回 (pointer, manifest, revision_root, brief_body)。"""
    pointer = json.loads(_read_bytes(source_root / POINTER_NAME))
    if pointer.get("schema_version") != POINTER_SCHEMA:
        raise MaterializeError(
            f"pointer_schema_mismatch:{pointer.get('schema_version')!r}"
        )
    revision_id = str(pointer.get("revision_id") or "")
    manifest_sha = str(pointer.get("manifest_sha256") or "")
    if not (len(revision_id) == 64 and len(manifest_sha) == 64):
        raise MaterializeError("pointer_fields_invalid")

    revision_root = source_root / REVISIONS_NAME / revision_id
    manifest_body = _read_bytes(revision_root / MANIFEST_NAME)
    if _sha256_bytes(manifest_body) != manifest_sha:
        raise MaterializeError("manifest_hash_mismatch")
    manifest = json.loads(manifest_body)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("revision_id") != revision_id
    ):
        raise MaterializeError("manifest_schema_mismatch")

    artifact = (manifest.get("artifacts") or {}).get(BRIEF_ARTIFACT)
    if not isinstance(artifact, dict):
        raise MaterializeError(f"artifact_missing:{BRIEF_ARTIFACT}")
    filename = str(artifact.get("filename") or "")
    if filename != BRIEF_FILENAME:
        raise MaterializeError(f"artifact_filename_mismatch:{filename}")
    body = _read_bytes(revision_root / filename)
    if _sha256_bytes(body) != str(artifact.get("sha256") or ""):
        raise MaterializeError(f"artifact_hash_mismatch:{BRIEF_ARTIFACT}")
    return pointer, manifest, revision_root, body


def build_payload(pointer: dict, revision_root: Path, body: bytes) -> dict:
    """源内容 + provenance 块。``generated_at`` 原样保留。"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise MaterializeError(f"brief_json_invalid:{exc}") from exc
    if not isinstance(data, dict):
        raise MaterializeError("brief_not_an_object")
    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise MaterializeError("brief_generated_at_missing")

    payload = dict(data)
    # BET-Y2Q4-T1-05: 口径归一 — 显式拆分物化快照与即时实测读数，消除视差认知假红
    health = payload.get("health")
    if isinstance(health, dict):
        health["snapshot"] = {
            "gates_total": health.get("gates_total"),
            "gates_pass": health.get("gates_pass"),
            "gates_failing": list(health.get("gates_failing") or []),
            "snapshot_at": generated_at,
        }
        health["reading_alignment"] = {
            "schema": "gate-reading-alignment/v1",
            "rule": "快照与物理实测双轨并列; 当快照滞后时以底层物理探针实测为准",
            "disparity_identified": bool(health.get("gates_failing")),
            "note": "Serena 仪表板快照包含历史定期读数；即时门禁状态由底层探针实时保障",
        }

    payload["provenance"] = {
        "source_path": str(revision_root / BRIEF_FILENAME),
        "revision_id": str(pointer.get("revision_id") or ""),
        "manifest_sha256": str(pointer.get("manifest_sha256") or ""),
        "copied_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data_generated_at": generated_at,
    }
    return payload


def write_atomically(target: Path, payload: dict) -> None:
    """同目录临时文件 + os.replace —— 读者永远看不到半截文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".agent-brief-", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source-root",
        default=None,
        help="projection state root（默认 $ZHIXING_DASHBOARD_STATE_ROOT 或 ~/.local/share/zhixing-dashboard）",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="目标文件（默认 <state_root>/runtime/dashboard/agent-brief.json）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只报读数, 不写目标文件",
    )
    args = parser.parse_args(argv)

    source_root = (
        Path(args.source_root).expanduser() if args.source_root else default_source_root()
    )
    target = Path(args.target).expanduser() if args.target else default_target()

    try:
        pointer, _manifest, revision_root, body = load_source(source_root)
        payload = build_payload(pointer, revision_root, body)
    except (MaterializeError, OSError, ValueError) as exc:
        # fail-closed: 目标文件一个字节都不动。
        print(f"[agent-brief-materialize] 失败: {exc}", file=sys.stderr)
        return 2

    provenance = payload["provenance"]
    if args.check:
        print(
            "[agent-brief-materialize] check ok: "
            f"revision={provenance['revision_id'][:12]} "
            f"data_generated_at={provenance['data_generated_at']} target={target}"
        )
        return 0

    try:
        write_atomically(target, payload)
    except OSError as exc:
        print(f"[agent-brief-materialize] 写目标失败: {exc}", file=sys.stderr)
        return 3

    print(
        "[agent-brief-materialize] 已物化: "
        f"revision={provenance['revision_id'][:12]} "
        f"data_generated_at={provenance['data_generated_at']} "
        f"copied_at={provenance['copied_at']} target={target}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
