#!/usr/bin/env python3
"""projection-republisher — 投影服务租约自动续期 (freshness renewal).

事故动机 (2026-10-03 第 3 次实证复发):
  revision-bound reader (deploy 侧 runtime_paths.py) 要求
  ``fresh_until - generated_at <= 15min``; 而全量 publisher
  (本目录 panorama-collect.py) 受「工作区 == origin/main 且完全洁净」的
  强身份校验 + 5~14min 采集耗时约束, 生产环境长期无法自动发布新 revision,
  导致 dashboard (:43191) 周期性 503 projection_stale, 已由人工手动续期 3 次.

本工具把「续期」这一机械动作自动化 — 它不是 publisher 的替代品:

  - 读取当前 pointer → 上一 revision (manifest 哈希须经 pointer 校验)
  - 原样继承其工件 (data.json/index.html/agent-brief.json) 与 provenance
    (producer / dashboard / source_hashes / claims / artifacts, 逐字保留)
  - 仅重打 ``generated_at`` / ``fresh_until`` (= now + 10min, 与 publisher
    同语义, 留 5min 裕量低于读端 15min 硬上限)
  - ``revision_id = sha256(canonical_json(manifest_basis))`` — 与 publisher
    完全同一身份语义; 新目录落盘, 原子替换 pointer
  - 数据观测时间 (payload ``observed_at``) 不变 — UI 数据龄期显示保持诚实,
    本工具绝不刷新数据内容, 只续服务租约

安全性质:
  - flock 防并发; 任何一步失败 fail-closed (旧 pointer 保持有效)
  - 复制工件后逐一复核 sha256 == manifest.artifacts.*.sha256 才允许换指针
  - ``--gc`` 仅保留最近 N 个 revision (默认 48, ≈6.4h 回滚窗)
    (2026-10-03 实证: 631 个孤儿 revision 占用 9.9GB)
  - 距离过期 >180s 时跳过续期, 避免每 8min 白造一个 revision 目录

用法:
  projection-republisher.py                # 续期一次 (幂等; launchd 每 8min 调)
  projection-republisher.py --status       # 只读诊断 (不续期不 GC)
  projection-republisher.py --gc [--keep N]# 续期 + 顺带清理旧 revision (保留最近 N 个)

退出码: 0 = 已续期/仍新鲜/skipped; 2 = 无基线 revision (需先跑一次全量 publisher);
        1 = 错误 (fail-closed).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTION_STATE_ROOT = Path(
    os.environ.get(
        "ZHIXING_DASHBOARD_STATE_ROOT",
        str(Path.home() / ".local/share/zhixing-dashboard"),
    )
).expanduser()
PROJECTION_POINTER_NAME = "current-revision.json"
PROJECTION_REVISIONS_NAME = "revisions"
PROJECTION_POINTER_SCHEMA = "zhixing-projection-pointer/v1"
PROJECTION_MANIFEST_SCHEMA = "zhixing-projection-manifest/v1"

LEASE = timedelta(minutes=10)        # 与 panorama-collect publisher 一致
# 剩余租约 ≤3min 即续期. 配合 480s 调度间隔: 每次续期时剩余 90~180s 裕量,
# 单次调度抖动/延迟不会穿透租约; 若整轮 missed, 看门狗会 --force 兜底。
RENEW_THRESHOLD = timedelta(seconds=180)
MAX_FRESHNESS = timedelta(minutes=15)  # 读端 runtime_paths._MAX_FRESHNESS 硬上限
CLOCK_SKEW = timedelta(seconds=60)

DEFAULT_KEEP = 48


class RepublishError(RuntimeError):
    """fail-closed 续期失败; 旧 pointer 保持有效。"""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _read_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RepublishError(f"unsafe_or_missing:{path.name}")
    return path.read_bytes()


def _write_private(path: Path, body: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)


def _atomic_replace_bytes(path: Path, body: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(body)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _load_baseline(root: Path) -> tuple[dict, dict, Path]:
    """读 pointer + manifest, 交叉校验哈希。返回 (pointer, manifest, revision_root)。"""
    pointer_path = root / PROJECTION_POINTER_NAME
    pointer = json.loads(_read_bytes(pointer_path))
    if pointer.get("schema_version") != PROJECTION_POINTER_SCHEMA:
        raise RepublishError("pointer_schema_mismatch")
    revision_id = pointer.get("revision_id", "")
    manifest_sha = pointer.get("manifest_sha256", "")
    if not (len(revision_id) == 64 and len(manifest_sha) == 64):
        raise RepublishError("pointer_fields_invalid")

    revision_root = root / PROJECTION_REVISIONS_NAME / revision_id
    manifest_body = _read_bytes(revision_root / "manifest.json")
    if _sha256_bytes(manifest_body) != manifest_sha:
        raise RepublishError("manifest_hash_mismatch")
    manifest = json.loads(manifest_body)
    if (
        manifest.get("schema_version") != PROJECTION_MANIFEST_SCHEMA
        or manifest.get("revision_id") != revision_id
    ):
        raise RepublishError("manifest_schema_mismatch")
    return pointer, manifest, revision_root


def renew(root: Path, *, now: datetime | None = None, force: bool = False) -> dict:
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    root = root.resolve()
    revisions_root = root / PROJECTION_REVISIONS_NAME
    if revisions_root.is_symlink():
        raise RepublishError("projection_revisions_symlink")
    revisions_root.mkdir(mode=0o700, exist_ok=True)
    # 锁文件放在 revisions/ 内 (该目录已被 deploy 侧 .gitignore 覆盖),
    # 避免在 state root 顶层产生未跟踪文件 —— 读端启动要求 dashboard 仓库
    # 完全洁净, 顶层 stray 文件会触发 CODE_DRIFT 使服务无法启动 (2026-10-03 实证)。
    lock_path = revisions_root / ".republisher.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RepublishError("republisher_conflict") from exc

        _, manifest, revision_root = _load_baseline(root)

        fresh_until = _utc(manifest["fresh_until"])
        if not force and fresh_until - now > RENEW_THRESHOLD:
            return {
                "status": "skipped_still_fresh",
                "revision_id": manifest["revision_id"],
                "fresh_until": manifest["fresh_until"],
                "seconds_left": int((fresh_until - now).total_seconds()),
            }

        generated_at = now
        fresh_new = now + LEASE
        if fresh_new - generated_at > MAX_FRESHNESS or generated_at > now + CLOCK_SKEW:
            raise RepublishError("freshness_window_invalid")

        basis = {
            key: manifest[key]
            for key in (
                "schema_version",
                "producer",
                "dashboard",
                "state_root",
                "contracts",
                "source_hashes",
                "claims",
                "artifacts",
            )
        }
        basis["generated_at"] = generated_at.isoformat().replace("+00:00", "Z")
        basis["fresh_until"] = fresh_new.isoformat().replace("+00:00", "Z")
        if _utc(basis["generated_at"]) <= _utc(manifest["generated_at"]):
            raise RepublishError("clock_not_advanced")

        revision_id = _sha256_bytes(_canonical_json_bytes(basis))
        new_manifest = dict(basis, revision_id=revision_id)
        manifest_body = _canonical_json_bytes(new_manifest)
        manifest_sha = _sha256_bytes(manifest_body)

        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=revisions_root))
        final = revisions_root / revision_id
        try:
            for name, meta in manifest["artifacts"].items():
                body = _read_bytes(revision_root / meta["filename"])
                if _sha256_bytes(body) != meta["sha256"]:
                    raise RepublishError(f"artifact_hash_mismatch:{name}")
                _write_private(staging / meta["filename"], body)
            _write_private(staging / "manifest.json", manifest_body)
            if final.exists():
                shutil.rmtree(staging)
            else:
                os.replace(staging, final)
            pointer = {
                "schema_version": PROJECTION_POINTER_SCHEMA,
                "revision_id": revision_id,
                "manifest_sha256": manifest_sha,
            }
            _atomic_replace_bytes(root / PROJECTION_POINTER_NAME, _canonical_json_bytes(pointer))
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return {
            "status": "renewed",
            "revision_id": revision_id,
            "previous_revision_id": manifest["revision_id"],
            "generated_at": basis["generated_at"],
            "fresh_until": basis["fresh_until"],
            "data_observed_at_preserved": True,
        }


def gc(root: Path, *, keep: int = DEFAULT_KEEP) -> dict:
    root = root.resolve()
    _, manifest, _ = _load_baseline(root)
    revisions_root = root / PROJECTION_REVISIONS_NAME
    scored = []
    staging_removed = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    for child in revisions_root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith(".staging-"):
            # 崩溃残留的暂存目录 (>1h) —— pointer 永不引用, 可安全清除;
            # 1h 窗口避免误删正在发布的暂存。
            if now_ts - child.stat().st_mtime > 3600:
                shutil.rmtree(child)
                staging_removed += 1
            continue
        try:
            m = json.loads(_read_bytes(child / "manifest.json"))
            scored.append((_utc(m["generated_at"]), child.name))
        except Exception:
            continue  # 不可读目录不动
    scored.sort(reverse=True)
    protected = {manifest["revision_id"]} | {name for _, name in scored[:keep]}
    removed = []
    for _, name in scored[keep:]:
        if name in protected:
            continue
        shutil.rmtree(revisions_root / name)
        removed.append(name)
    return {
        "status": "gc_done",
        "total": len(scored),
        "removed": len(removed),
        "kept": len(scored) - len(removed),
        "staging_removed": staging_removed,
        "removed_sample": removed[:5],
    }


def status(root: Path) -> dict:
    root = root.resolve()
    try:
        _, manifest, _ = _load_baseline(root)
    except (RepublishError, OSError, json.JSONDecodeError) as exc:
        return {"status": "unhealthy", "error": type(exc).__name__, "detail": str(exc)}
    now = datetime.now(timezone.utc)
    fresh_until = _utc(manifest["fresh_until"])
    seconds_left = int((fresh_until - now).total_seconds())
    return {
        "status": "fresh" if seconds_left > 0 else "stale",
        "revision_id": manifest["revision_id"],
        "generated_at": manifest["generated_at"],
        "fresh_until": manifest["fresh_until"],
        "seconds_left": seconds_left,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-root", default=str(PROJECTION_STATE_ROOT))
    ap.add_argument("--status", action="store_true", help="只读诊断 (不续期不 GC)")
    ap.add_argument("--gc", action="store_true", help="续期后顺带清理旧 revision (keep N)")
    ap.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    ap.add_argument("--force", action="store_true", help="即使仍新鲜也强制续期")
    args = ap.parse_args()

    root = Path(args.state_root).expanduser()
    try:
        if args.status:
            result = status(root)
        else:
            # 默认动作始终含续期; --gc 作为伴随项在续期后执行 (单次调用原子完成
            # 租约续期 + 孤儿清理, 防 revision 目录无界回涨 —— 631个/9.9GB 实证)。
            try:
                result = renew(root, force=args.force)
            except RepublishError as exc:
                if "manifest_hash_mismatch" in str(exc) or "unsafe_or_missing" in str(exc):
                    result = {"status": "no_baseline", "error": str(exc)}
                    print(json.dumps(result, ensure_ascii=False))
                    return 2
                raise
            if args.gc:
                result = dict(result, gc=gc(root, keep=args.keep))
    except RepublishError as exc:
        result = {"status": "error", "error": str(exc)}

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") not in {"error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
