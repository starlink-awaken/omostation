#!/usr/bin/env python3
"""织星驾驶舱（:43191）宿主资产的只读漂移检查。

问题（docs/DASHBOARDS.md §3.1，2026-09-17 实证）:
主入口 `:43191` 的部署目录 `~/.local/share/zhixing-dashboard/` **不在任何 git
仓库中**。多 agent 并发编辑同一 `template.html` / `refresh.py` / `live_server.py`
会**互相覆盖**:

  - 场景系统面板被另一 agent 的「metrics redesign」覆盖丢失（所有备份均无该代码）
  - 该次覆盖同时回退了已修好的 `ens[n.type]` bug
  - 一处语法错误直接使整个第二脚本失效 → `D is not defined` → 页面主功能损坏

既有 `zhixing-panel-sync.py` 已**版本化 panels**（`bin/panorama/assets/panels/`）
并幂等注入 —— 但**宿主文件本身未纳管**，而它正是被覆盖的那个。本工具补上:

| 子命令    | 作用 |
|----------|------|
| `status`  | 逐文件 sha 对比（仓库 vs 部署）+ 漂移汇总 |
| `plan`    | 从登记的 LaunchAgent 解析实际运行根，并只读计算明确选择资产的漂移 |
| `check`   | `plan` 的全受管资产兼容别名；漂移或身份不符时 exit 1 |
| `migrate` | plist 迁移: entrypoint → current/live_server.py (建立基线版本) |
| `publish` | 受管发布: 版本目录 + 原子切换 current + SHA 校验 + 回滚 |
| `restore` | 回滚: current 切回上一版本 |

**稳定入口契约** (DCP-20 spec v1.1.0): plist entrypoint 指向 `current/live_server.py`；
`current` 是唯一允许的 symlink，目标落在 `releases/<40位commit-OID>/` 或显式选择的 `releases/<commit>--pub-<32hex>/`；版本目录是
普通目录、无内部 symlink、SHA 对齐主仓资产。`apply`/`capture` 仍 BLOCKED。

用法:
    python3 bin/gac/zhixing-host-sync.py status --json
    python3 bin/gac/zhixing-host-sync.py migrate --json
    python3 bin/gac/zhixing-host-sync.py publish --file live_server.py --file observatory_query.py --json
    python3 bin/gac/zhixing-host-sync.py restore --json
    # 同一 Git 来源补充发布；首次新格式需明确选择新版身份 helper:
    python3 bin/gac/zhixing-host-sync.py publish --publication-id <32hex> --file live_server.py --file release_identity.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = _ROOT / "bin" / "panorama" / "assets" / "host"
DASHBOARD_DIR = Path.home() / ".local" / "share" / "zhixing-dashboard"
LAUNCH_AGENT_LABEL = "com.omostation.zhixing-dashboard"
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)

# 纳管范围: 宿主模板 + 采集器。数据/产物 (index.html, current.json, caches) 不入仓。
# 映射: (部署目录中的文件名, 仓库资产的相对名)。
#
# 为什么 refresh.py 的仓库名带 .asset 后缀: script-registry / bin-quota 两个门禁
# 都把 `bin/**/*.py` 视为**脚本**(排除规则只认 bin/_* 目录)。而这是部署文件的
# 版本化副本 —— 是**资产不是脚本**, 注册成脚本会污染脚本治理面。用 .asset 后缀
# 既保持与同行 panels 资产相邻 (bin/panorama/assets/), 又不误纳入脚本治理。
HOST_FILES: tuple[tuple[str, str], ...] = (
    ("template.html", "template.html"),
    ("ecosystem_ui.js", "ecosystem_ui.js.asset"),
    ("workbench_ui.js", "workbench_ui.js.asset"),
    ("refresh.py", "refresh.py.asset"),
    ("live_server.py", "live_server.py.asset"),
    ("runtime_paths.py", "runtime_paths.py.asset"),
    ("observatory_query.py", "observatory_query.py.asset"),
    ("panorama-collect-main.py", "panorama-collect-main.py.asset"),
    # 2026-09-26: 驾驶舱推理引擎(副驾对话 / RAG 向量+重排)纳管 —— 此前不在任何仓库,
    # 直连 oMLX :8000 且无鉴权; 已改经 aetherforge 门面。
    ("copilot_service.py", "copilot_service.py.asset"),
    ("rag_engine.py", "rag_engine.py.asset"),
    ("strategy_sources.py", "strategy_sources.py.asset"),
    ("collectors/strategy.py", "strategy_collector.py.asset"),
    ("collectors/documents.py", "documents_collector.py.asset"),
    ("collectors/workflow.py", "workflow_collector.py.asset"),
    ("collectors/scheduler.py", "scheduler_collector.py.asset"),
    ("orchestrator.py", "orchestrator.py.asset"),
    ("collectors/portfolio.py", "portfolio_collector.py.asset"),
    ("strategy_projection.py", "strategy_projection.py.asset"),
    ("collectors/agent_brief.py", "agent_brief_collector.py.asset"),
    ("collectors/base.py", "collectors.base.py.asset"),
    ("collectors/orca.py", "collectors.orca.py.asset"),
    ("collectors/ruflo.py", "ruflo_collector.py.asset"),
    ("collectors/environment.py", "collectors.environment.py.asset"),
    # 2026-10-21: reference_cell 与 ruflo 的 verifier 路径此前是裸相对路径, 在
    # release 检出里永不解析 (那里没有 bin/gac/) => reference_cell 从未成功过
    # (last_success_at: null)。两者改为经 collectors/_script_paths.py 解析, 该
    # helper 随之纳管, 否则部署出去的 reference_cell 仍 import 不到它。
    ("collectors/reference_cell.py", "reference_cell_collector.py.asset"),
    ("collectors/_script_paths.py", "collectors._script_paths.py.asset"),
    # 2026-10-23: 投影 artifact 上限从 16MiB 提到 64MiB 后必须纳管 (由第 75 行声明) —— 它决定
    # revision 能否加载, 而 release 树与 manifest 必须一致, 否则发布器拒绝发布
    # (release_tree_hash_mismatch)。
    ("release_identity.py", "release_identity.py.asset"),
)
RELEASE_ID_RE = re.compile(r"[0-9a-f]{40}\Z")
PUBLICATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
VERSION_ID_RE = re.compile(r"[0-9a-f]{40}(?:--pub-[0-9a-f]{32})?\Z")
RELEASE_MANIFEST = ".zhixing-host-release.json"
# Runtime bytecode is regenerated in place by the refresh/orchestrator jobs that
# run with cwd=<release>. Hashing it would make every release self-invalidate
# minutes after publish, so both the publisher and the verifier skip it.
RUNTIME_BYTECODE_DIRS = frozenset({"__pycache__"})
RUNTIME_BYTECODE_SUFFIX = ".pyc"

BLOCKED_REASON = "g0_m0_hold_release_bet_required"
BLOCKED_COMMANDS = frozenset({"apply", "capture"})

# 稳定入口契约 (DCP-20 spec v1.1.0): plist entrypoint 必须指向 current/live_server.py,
# current 只指向直接的 legacy OID 或 <commit>--pub-<publication-id> 版本目录。
CURRENT_LINK = DASHBOARD_DIR / "current"
RELEASES_DIR = DASHBOARD_DIR / "releases"
CURRENT_ENTRYPOINT = CURRENT_LINK / "live_server.py"


def _source_identity(source_dir: Path | None = None) -> tuple[str, str]:
    """Identify the bytes' actual source, rejecting dirty Git worktrees."""
    source = source_dir or HOST_DIR
    completed = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True,
    )
    oid = completed.stdout.strip()
    if completed.returncode == 0:
        if not RELEASE_ID_RE.fullmatch(oid):
            return "", "git_commit"
        dirty = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", "."],
            check=False, capture_output=True, text=True,
        )
        if dirty.returncode != 0 or dirty.stdout.strip():
            return "", "git_commit"
        return oid, "git_commit"
    if "not a git repository" not in completed.stderr.lower():
        return "", "unknown"
    digest = hashlib.sha1()
    found = False
    try:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                return "", "content_snapshot"
            if not path.is_file():
                continue
            digest.update(path.relative_to(source).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
            found = True
    except OSError:
        return "", "content_snapshot"
    return (digest.hexdigest(), "content_snapshot") if found else ("", "content_snapshot")


def _source_commit_oid(source_dir: Path | None = None) -> str:
    """Return only a real Git commit OID; content snapshots are not commit OIDs."""
    identity, kind = _source_identity(source_dir)
    return identity if kind == "git_commit" else ""


def _release_tree_files(root: Path) -> dict[str, str] | None:
    """Hash a release tree while refusing symlinks and non-regular entries."""
    if root.is_symlink() or not root.is_dir():
        return None
    files: dict[str, str] = {}
    try:
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            base = Path(directory)
            # Git pointers/metadata belong to the old checkout, never the release.
            dirnames[:] = [name for name in dirnames
                           if name != ".git" and name not in RUNTIME_BYTECODE_DIRS]
            for name in dirnames:
                if (base / name).is_symlink():
                    return None
            for name in filenames:
                if name == ".git" or name.endswith(RUNTIME_BYTECODE_SUFFIX):
                    continue
                path = base / name
                if path.is_symlink() or not path.is_file():
                    return None
                relative = path.relative_to(root).as_posix()
                if relative != RELEASE_MANIFEST:
                    files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    return files


def _write_release_manifest(root: Path, *, oid: str, selected: tuple[str, ...],
                            base_version: str | None, identity_kind: str,
                            files: dict[str, str], version_id: str | None = None,
                            publication_id: str | None = None) -> bytes:
    payload = {
        "schema": ("zhixing-host-release-manifest/v1" if publication_id is None
                   else "zhixing-host-release-manifest/v2"),
        "version_id": version_id or oid,
        "identity_kind": identity_kind,
        "commit_oid": oid if identity_kind == "git_commit" else None,
        "selected_assets": list(selected),
        "base_version": base_version,
        "files": dict(sorted(files.items())),
    }
    if publication_id is not None:
        payload["publication_id"] = publication_id
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _base_manifest_valid(root: Path) -> bool:
    """Validate an existing manifest before inheriting its bytes, including migration baselines."""
    manifest = root / RELEASE_MANIFEST
    if not manifest.exists() and not manifest.is_symlink():
        return RELEASE_ID_RE.fullmatch(root.name) is not None  # Legacy checkout.
    try:
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1024 * 1024:
            return False
        data = json.loads(manifest.read_bytes())
        if not isinstance(data, dict) or data.get("version_id") != root.name:
            return False
        oid, kind, schema = data.get("commit_oid"), data.get("identity_kind"), data.get("schema")
        if schema == "zhixing-host-release-manifest/v1":
            if not RELEASE_ID_RE.fullmatch(root.name):
                return False
            if not ((kind == "deployment_baseline" and oid is None)
                    or (kind == "git_commit" and oid == root.name)):
                return False
        elif schema == "zhixing-host-release-manifest/v2":
            token = data.get("publication_id")
            if (kind != "git_commit" or not isinstance(oid, str) or not RELEASE_ID_RE.fullmatch(oid)
                    or not isinstance(token, str) or not PUBLICATION_ID_RE.fullmatch(token)
                    or root.name != f"{oid}--pub-{token}"):
                return False
        else:
            return False
        files = data.get("files")
        return isinstance(files, dict) and bool(files) and files == _release_tree_files(root)
    except (OSError, ValueError, TypeError):
        return False


def _validate_release_helper(root: Path, helper: Path) -> dict:
    """Run the actual helper at a complete candidate's real release path."""
    if helper.is_symlink() or not helper.is_file():
        raise ValueError("release_identity_helper_missing")
    import types
    module = types.ModuleType("zhixing_candidate_release_identity")
    exec(compile(helper.read_bytes(), str(helper), "exec"), module.__dict__)
    identity = module.managed_release_identity(root)
    if not isinstance(identity, dict):
        raise ValueError("managed_release_identity_missing")
    return identity


def _prepare_version(assets: tuple[tuple[str, str], ...], oid: str,
                    source_dir: Path | None = None, *, publication_id: str | None = None) -> dict:
    """Build a complete immutable release in a sibling temp directory.

    Publishes start from the current complete release and overlay only selected
    assets. Migration builds its first baseline from the deployed files passed in.
    """
    src = source_dir or HOST_DIR
    if not RELEASE_ID_RE.fullmatch(oid):
        return {"ok": False, "reason": "version_id_invalid", "oid": oid}
    if RELEASES_DIR.is_symlink():
        return {"ok": False, "reason": "releases_dir_symlink", "path": str(RELEASES_DIR)}
    try:
        RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "reason": "releases_dir_unavailable", "detail": str(exc)}
    version_id = oid if publication_id is None else f"{oid}--pub-{publication_id}"
    if publication_id is not None and (src != HOST_DIR or not isinstance(publication_id, str)
                                       or not PUBLICATION_ID_RE.fullmatch(publication_id)):
        return {"ok": False, "reason": "publication_id_invalid"}
    if publication_id is not None:
        assets = tuple(sorted(assets))
    version_dir = RELEASES_DIR / version_id
    if version_dir.is_symlink():
        return {"ok": False, "reason": "version_path_symlink", "path": str(version_dir)}
    if src == HOST_DIR:
        source_identity, source_kind = _source_identity(src)
        if not source_identity or source_identity != oid:
            return {"ok": False, "reason": "source_identity_mismatch",
                    "identity_kind": source_kind, "version_id": oid}
    base_version = _current_version() if src == HOST_DIR else None
    base_dir = RELEASES_DIR / base_version if base_version else None
    if src == HOST_DIR and CURRENT_LINK.is_symlink() and base_dir is None:
        return {"ok": False, "reason": "current_release_invalid"}
    if base_dir is not None and _release_tree_files(base_dir) is None:
        return {"ok": False, "reason": "current_release_unsafe", "path": str(base_dir)}
    if base_dir is not None and not _base_manifest_valid(base_dir):
        return {"ok": False, "reason": "current_release_integrity_invalid", "path": str(base_dir)}
    if base_version == version_id and version_dir.is_dir() and not version_dir.is_symlink():
        try:
            prior_manifest = json.loads((version_dir / RELEASE_MANIFEST).read_text(encoding="utf-8"))
            if (isinstance(prior_manifest, dict)
                    and prior_manifest.get("version_id") == version_id
                    and prior_manifest.get("selected_assets") == [name for name, _ in assets]):
                base_version = prior_manifest.get("base_version")
        except (OSError, json.JSONDecodeError):
            pass

    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=f".{oid}.stage.", dir=RELEASES_DIR))
        if base_dir is not None:
            for directory, dirnames, filenames in os.walk(base_dir, followlinks=False):
                source_parent = Path(directory)
                dirnames[:] = [name for name in dirnames
                               if name != ".git" and name not in RUNTIME_BYTECODE_DIRS]
                relative_parent = source_parent.relative_to(base_dir)
                target_parent = staging / relative_parent
                target_parent.mkdir(parents=True, exist_ok=True)
                for dirname in dirnames:
                    if (source_parent / dirname).is_symlink():
                        raise ValueError("release_symlink_rejected")
                for filename in filenames:
                    if filename == ".git" or filename.endswith(RUNTIME_BYTECODE_SUFFIX):
                        continue
                    source_file = source_parent / filename
                    if source_file.is_symlink() or not source_file.is_file():
                        raise ValueError("release_non_regular_entry_rejected")
                    target_file = target_parent / filename
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_file, target_file)
        selected_manifest: list[dict] = []
        for deploy_name, repo_name in assets:
            relative = Path(deploy_name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("asset_destination_invalid")
            source = src / repo_name
            if source.is_symlink() or not source.is_file():
                return {"ok": False, "reason": "source_asset_missing", "asset": str(source)}
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            selected_manifest.append({"name": deploy_name, "source": str(source),
                                      "version": str(version_dir / relative), "sha": _sha(destination)})
        files = _release_tree_files(staging)
        if files is None:
            return {"ok": False, "reason": "release_tree_unsafe", "path": str(staging)}
        if src == HOST_DIR and _source_identity(src) != (oid, "git_commit"):
            return {"ok": False, "reason": "source_identity_mismatch"}
        if base_dir is not None and not _base_manifest_valid(base_dir):
            return {"ok": False, "reason": "current_release_integrity_invalid", "path": str(base_dir)}
        manifest_bytes = _write_release_manifest(
            staging, oid=oid, selected=tuple(name for name, _ in assets),
            base_version=base_version,
            identity_kind=("deployment_baseline" if src != HOST_DIR else _source_identity(src)[1]),
            files=files, version_id=version_id, publication_id=publication_id,
        )
        (staging / RELEASE_MANIFEST).write_bytes(manifest_bytes)
        if version_dir.exists():
            existing_files = _release_tree_files(version_dir)
            try:
                existing_manifest = (version_dir / RELEASE_MANIFEST).read_bytes()
            except OSError:
                existing_manifest = None
            if (existing_files == files and existing_manifest == manifest_bytes
                    and not version_dir.is_symlink()):
                return {"ok": True, "version_dir": str(version_dir), "oid": oid,
                        "manifest": selected_manifest, "created": False, "already_exists": True}
            return {"ok": False, "reason": "version_identity_conflict", "path": str(version_dir)}
        try:
            os.rename(staging, version_dir)
        except FileExistsError:
            return {"ok": False, "reason": "version_identity_conflict", "path": str(version_dir)}
        staging = None
        return {"ok": True, "version_dir": str(version_dir), "oid": oid,
                "manifest": selected_manifest, "created": True, "already_exists": False}
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "version_prepare_failed", "detail": str(exc)}
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def _history_path() -> Path:
    """Keep switch history outside immutable release directories."""
    return RELEASES_DIR / ".current-history.json"


def _release_version(path: Path) -> str | None:
    """Accept only a real direct legacy or explicit publication release child."""
    try:
        if path.is_symlink() or RELEASES_DIR.is_symlink():
            return None
        resolved_root = RELEASES_DIR.resolve(strict=True)
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    if len(relative.parts) != 1 or not VERSION_ID_RE.fullmatch(relative.name):
        return None
    return relative.name if resolved.is_dir() else None


def _current_version() -> str | None:
    if not CURRENT_LINK.is_symlink():
        return None
    try:
        return _release_version(CURRENT_LINK.resolve(strict=True))
    except OSError:
        return None


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write one control file atomically, leaving no temp file on failure."""
    temp = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")
    try:
        if temp.exists() or temp.is_symlink():
            temp.unlink()
        temp.write_bytes(payload)
        os.replace(temp, path)
    finally:
        if temp.exists() or temp.is_symlink():
            try:
                temp.unlink()
            except OSError:
                pass


def _switch_state_snapshot() -> dict:
    """Capture pointer and predecessor metadata before a multi-step transition."""
    history = _history_path()
    if history.is_symlink() or (history.exists() and not history.is_file()):
        return {"ok": False, "error": "history_path_not_regular_file"}
    try:
        current_target = os.readlink(CURRENT_LINK) if CURRENT_LINK.is_symlink() else None
        history_bytes = history.read_bytes() if history.is_file() else None
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "current_target": current_target, "history_bytes": history_bytes}


def _restore_switch_state(snapshot: dict) -> dict:
    """Restore current and its predecessor metadata from a pre-switch snapshot."""
    errors: list[str] = []
    current_target = snapshot.get("current_target")
    temp_link = DASHBOARD_DIR / f".current.restore.tmp.{uuid.uuid4().hex}"
    try:
        if current_target is None:
            if CURRENT_LINK.is_symlink():
                CURRENT_LINK.unlink()
            elif CURRENT_LINK.exists():
                errors.append("current_not_symlink")
        else:
            if temp_link.exists() or temp_link.is_symlink():
                temp_link.unlink()
            temp_link.symlink_to(current_target, target_is_directory=True)
            os.replace(temp_link, CURRENT_LINK)
    except OSError as exc:
        errors.append(f"current_restore_failed:{exc}")
    finally:
        if temp_link.exists() or temp_link.is_symlink():
            try:
                temp_link.unlink()
            except OSError:
                pass

    history = _history_path()
    try:
        history_bytes = snapshot.get("history_bytes")
        if history_bytes is None:
            if history.exists() or history.is_symlink():
                history.unlink()
        else:
            _atomic_write_bytes(history, history_bytes)
    except OSError as exc:
        errors.append(f"history_restore_failed:{exc}")
    return {"ok": not errors, "errors": errors}


def _write_previous_version(previous_version: str | None) -> None:
    payload = json.dumps({"previous_version": previous_version}, sort_keys=True).encode("utf-8")
    _atomic_write_bytes(_history_path(), payload)


def _switch_current(target_version_dir: Path) -> dict:
    """Atomically switch current and persist the actual prior pointer target."""
    version = _release_version(target_version_dir)
    if version is None:
        return {"ok": False, "reason": "version_dir_missing", "path": str(target_version_dir)}
    if _release_tree_files(RELEASES_DIR / version) is None:
        return {"ok": False, "reason": "version_tree_unsafe", "path": str(RELEASES_DIR / version)}
    if CURRENT_LINK.exists() and not CURRENT_LINK.is_symlink():
        return {"ok": False, "reason": "current_pointer_not_symlink", "path": str(CURRENT_LINK)}
    if _history_path().is_symlink():
        return {"ok": False, "reason": "history_path_symlink", "path": str(_history_path())}
    previous = _current_version()
    if CURRENT_LINK.is_symlink() and previous is None:
        return {"ok": False, "reason": "current_target_invalid", "path": str(CURRENT_LINK)}
    if previous == version:
        return {"ok": True, "current": str(CURRENT_LINK),
                "target": str(RELEASES_DIR / version), "previous_version": _previous_version(),
                "already_current": True}
    snapshot = _switch_state_snapshot()
    if not snapshot.get("ok"):
        return {"ok": False, "reason": "switch_state_unreadable",
                "detail": snapshot.get("error")}
    temp_link = DASHBOARD_DIR / f".current.tmp.{uuid.uuid4().hex}"
    try:
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
        temp_link.symlink_to(RELEASES_DIR / version, target_is_directory=True)
        os.replace(temp_link, CURRENT_LINK)
        _write_previous_version(previous)
    except OSError as exc:
        recovery = _restore_switch_state(snapshot)
        return {
            "ok": False,
            "reason": "current_switch_failed",
            "detail": str(exc),
            "recovery": recovery,
        }
    finally:
        if temp_link.exists() or temp_link.is_symlink():
            try:
                temp_link.unlink()
            except OSError:
                pass
    return {
        "ok": True,
        "current": str(CURRENT_LINK),
        "target": str(target_version_dir),
        "previous_version": previous,
    }


def _previous_version() -> str | None:
    """Read the predecessor recorded when current was actually switched."""
    if _history_path().is_symlink():
        return None
    try:
        payload = json.loads(_history_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    previous = payload.get("previous_version") if isinstance(payload, dict) else None
    if not isinstance(previous, str) or not VERSION_ID_RE.fullmatch(previous):
        return None
    return previous if _release_version(RELEASES_DIR / previous) == previous else None


def _baseline_version_id(assets: tuple[tuple[str, str], ...], source_dir: Path) -> str | None:
    """Name a deployment-state baseline by the exact bytes copied into it."""
    digest = hashlib.sha256()
    for deploy_name, source_name in assets:
        source = source_dir / source_name
        try:
            digest.update(deploy_name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.read_bytes())
            digest.update(b"\0")
        except OSError:
            return None
    return digest.hexdigest()[:40]


def _runtime_baseline_assets() -> tuple[tuple[str, str], ...] | None:
    """Capture runtime code and packaged resources, excluding mutable host data."""
    root_files = {".py", ".js", ".css", ".html"}
    root_json_files = {"manifest.json"}
    package_dirs = ("collectors", "models", "schemas", "static", "assets", "templates")
    excluded_names = {"index.html", "current.json", "previous-snapshot.json"}
    excluded_py = ("test_", "_test.py", "smoke", "contract_check")
    selected: set[str] = set()
    try:
        for path in DASHBOARD_DIR.iterdir():
            if path.is_symlink():
                if path.name in package_dirs or path.suffix.lower() in root_files:
                    return None
                continue
            if path.is_file():
                if path.name in excluded_names:
                    continue
                if path.name in root_json_files or (
                    path.suffix.lower() in root_files
                    and not any(marker in path.name.lower() for marker in excluded_py)
                ):
                    selected.add(path.name)
                continue
            if not path.is_dir() or path.name not in package_dirs:
                continue
            for child in path.rglob("*"):
                relative = child.relative_to(DASHBOARD_DIR)
                if any(part.startswith(".") or part in {"__pycache__", ".pytest_cache", "tests"}
                       for part in relative.parts):
                    continue
                if child.is_symlink():
                    return None
                if not child.is_file():
                    continue
                suffix = child.suffix.lower()
                if suffix not in {".py", ".json", ".yaml", ".yml", ".toml", ".html",
                                  ".js", ".css", ".svg", ".txt"}:
                    continue
                if child.name in excluded_names or any(
                    marker in child.name.lower() for marker in excluded_py
                ):
                    continue
                selected.add(relative.as_posix())
    except OSError:
        return None
    return tuple((name, name) for name in sorted(selected))


def _discard_new_version(version_dir: Path, existed_before: bool) -> None:
    """Remove only an unreferenced release directory created by this failed attempt."""
    if existed_before or version_dir.is_symlink() or not version_dir.exists():
        return
    version = _release_version(version_dir)
    if version is None or _current_version() == version or _previous_version() == version:
        return
    try:
        shutil.rmtree(version_dir)
    except OSError:
        pass


def publish(files: list[str] | tuple[str, ...] | None, *, publication_id: str | None = None) -> dict:
    """受管发布: 版本目录准备 → 原子切换 current → SHA 校验 → 失败回滚。

    前置: plist entrypoint 必须已迁移到 current/live_server.py (先跑 migrate)。
    """
    runtime = _running_registered_runtime()
    if not runtime.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "runtime": runtime}
    # 身份链: 解析后的 entrypoint 必须落在 RELEASES_DIR 下 (current symlink → releases/<OID>/)
    entry = Path(runtime["entrypoint"])
    if RELEASES_DIR not in entry.parents:
        return {
            "ok": False, "reason": "plist_not_migrated",
            "detail": "先跑 migrate 将 plist entrypoint 指向 current/live_server.py",
            "entrypoint": runtime["entrypoint"],
        }
    if _current_version() is None:
        return {"ok": False, "reason": "current_release_invalid",
                "detail": "publish requires current to resolve to a direct legacy or explicit publication release directory"}
    try:
        assets = _selected_assets(files)
    except ValueError as exc:
        return {"ok": False, "reason": "invalid_asset_selection", "detail": str(exc)}
    oid, identity_kind = _source_identity(HOST_DIR)
    if identity_kind != "git_commit" or not RELEASE_ID_RE.fullmatch(oid):
        return {"ok": False, "reason": "source_git_commit_required",
                "identity_kind": identity_kind, "commit_oid": None, "version_id": None}
    snapshot = _switch_state_snapshot()
    if not snapshot.get("ok"):
        return {"ok": False, "reason": "switch_state_unreadable",
                "detail": snapshot.get("error")}
    previous = _current_version()
    if publication_id is not None and (not isinstance(publication_id, str)
                                       or not PUBLICATION_ID_RE.fullmatch(publication_id)):
        return {"ok": False, "reason": "publication_id_invalid"}
    prepared = _prepare_version(assets, oid, publication_id=publication_id)
    if not prepared.get("ok"):
        return prepared
    # Validate newly managed bytes before changing the production pointer.
    release_root = Path(prepared["version_dir"])
    if publication_id is not None:
        try:
            _validate_release_helper(release_root, release_root / "release_identity.py")
        except (OSError, ValueError, ImportError, AttributeError, SyntaxError, TypeError) as exc:
            _discard_new_version(release_root, not prepared.get("created", False))
            return {"ok": False, "reason": "publication_identity_helper_incompatible",
                    "detail": f"Explicitly select --file release_identity.py from the compatible source: {exc}"}
    if (release_root / "release_identity.py").exists():
        try:
            import importlib.util
            import types
            source_helper = HOST_DIR / "release_identity.py.asset"
            helper = types.ModuleType("zhixing_publisher_release_identity")
            exec(compile(source_helper.read_bytes(), str(source_helper), "exec"), helper.__dict__)
            helper.managed_release_identity(release_root)
        except (OSError, ValueError, ImportError, AttributeError) as exc:
            _discard_new_version(release_root, not prepared.get("created", False))
            return {"ok": False, "reason": "managed_release_identity_invalid", "detail": str(exc)}
    switched = _switch_current(release_root)
    if not switched.get("ok"):
        return switched
    # SHA 校验: 新版本目录中已发布资产与主仓一致
    deployed = _asset_plan(Path(prepared["version_dir"]), files, HOST_DIR)
    if not deployed.get("ok"):
        recovery = _restore_switch_state(snapshot)
        if recovery.get("ok"):
            _discard_new_version(Path(prepared["version_dir"]), not prepared.get("created", False))
        return {
            "ok": False,
            "reason": "deploy_verify_failed",
            "detail": "发布后校验失败, 已尝试回滚",
            "deploy": deployed,
            "recovery": recovery,
        }
    return {
        "ok": True, "oid": oid, "version_id": release_root.name, "commit_oid": oid,
        "identity_kind": identity_kind, "version_dir": prepared["version_dir"],
        "previous_version": previous, "write_performed": True,
        "manifest": prepared["manifest"], "deploy": deployed,
    }


def restore() -> dict:
    """回滚: 将 current symlink 切回上一版本。"""
    previous = _previous_version()
    if not previous:
        return {"ok": False, "reason": "no_previous_version"}
    target = RELEASES_DIR / previous
    if not target.is_dir():
        return {"ok": False, "reason": "previous_version_missing", "version": previous}
    return _switch_current(target)


def migrate() -> dict:
    """plist 迁移: entrypoint → current/live_server.py (先以当前部署态建立基线版本)。

    前置: 当前部署态可捕获 (host 文件与 repo 资产对齐或接受为基线)。
    """
    registration = _registered_runtime()
    if not registration.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "registration": registration}
    current_entry = registration["entrypoint"]
    if (CURRENT_LINK.is_symlink()
            and _resolved(Path(current_entry)) == _resolved(CURRENT_ENTRYPOINT)):
        return {"ok": True, "already_migrated": True, "entrypoint": current_entry}
    plist_path = _resolved(LAUNCH_AGENT_PLIST)
    backup = plist_path.with_suffix(".plist.bak")
    try:
        plist_before = plist_path.read_bytes()
        if backup.is_symlink():
            return {"ok": False, "reason": "plist_backup_path_symlink", "path": str(backup)}
        backup_before = backup.read_bytes() if backup.is_file() else None
    except OSError as exc:
        return {"ok": False, "reason": "plist_backup_failed", "detail": str(exc)}

    switch_snapshot = _switch_state_snapshot()
    def rollback(reason: str, *, detail: str | None = None, runtime: dict | None = None,
                 version_dir: Path | None = None, version_existed: bool = True) -> dict:
        errors: list[str] = []
        try:
            _atomic_write_bytes(plist_path, plist_before)
        except OSError as exc:
            errors.append(f"plist_restore_failed:{exc}")
        if switch_snapshot.get("ok"):
            switch_recovery = _restore_switch_state(switch_snapshot)
            errors.extend(switch_recovery["errors"])
        else:
            errors.append("switch_state_not_captured")
        try:
            if backup_before is None:
                if backup.exists() or backup.is_symlink():
                    backup.unlink()
            else:
                _atomic_write_bytes(backup, backup_before)
        except OSError as exc:
            errors.append(f"backup_restore_failed:{exc}")
        if version_dir is not None:
            _discard_new_version(version_dir, version_existed)
        result = {"ok": False, "reason": reason, "recovery": {"ok": not errors, "errors": errors}}
        if detail is not None:
            result["detail"] = detail
        if runtime is not None:
            result["runtime"] = runtime
        return result

    if not switch_snapshot.get("ok"):
        return {"ok": False, "reason": "switch_state_unreadable",
                "detail": switch_snapshot.get("error"),
                "recovery": {"ok": True, "errors": []}}
    try:
        _atomic_write_bytes(backup, plist_before)
    except OSError as exc:
        return rollback("plist_backup_failed", detail=str(exc))

    # Capture the installed runtime code and packaged resources, not mutable
    # dashboards, caches, worktrees, history, or other host data.
    assets = _runtime_baseline_assets()
    if assets is None:
        return rollback("baseline_runtime_tree_unsafe")
    if not assets:
        return rollback("baseline_no_deployed_files")
    baseline = _baseline_version_id(assets, DASHBOARD_DIR)
    if baseline is None:
        return rollback("baseline_source_unreadable")
    version_dir = RELEASES_DIR / baseline
    version_existed = version_dir.exists()
    prepared = _prepare_version(assets, baseline, source_dir=DASHBOARD_DIR)
    if not prepared.get("ok"):
        return rollback(prepared["reason"], detail=prepared.get("detail"),
                        version_dir=version_dir, version_existed=version_existed)
    switched = _switch_current(Path(prepared["version_dir"]))
    if not switched.get("ok"):
        return rollback(switched["reason"], detail=switched.get("detail"),
                        version_dir=version_dir, version_existed=version_existed)

    # 入口和执行根必须作为一个配置变化切换到 current。
    try:
        payload = plistlib.loads(plist_before)
    except (OSError, plistlib.InvalidFileException) as exc:
        return rollback("plist_read_failed", detail=str(exc), version_dir=version_dir,
                        version_existed=version_existed)
    arguments = payload.get("ProgramArguments")
    if not isinstance(arguments, list):
        return rollback("launch_agent_program_missing", version_dir=version_dir,
                        version_existed=version_existed)
    replaced = False
    for idx, value in enumerate(arguments):
        if isinstance(value, str) and Path(value).name == "live_server.py":
            arguments[idx] = str(CURRENT_ENTRYPOINT)
            replaced = True
    if not replaced:
        return rollback("plist_entrypoint_not_found", version_dir=version_dir,
                        version_existed=version_existed)
    # WorkingDirectory 对齐迁移后的运行根 (版本目录), 否则 root_mismatch
    payload["WorkingDirectory"] = str(CURRENT_LINK)
    try:
        _atomic_write_bytes(plist_path, plistlib.dumps(payload))
    except OSError as exc:
        return rollback("plist_write_failed", detail=str(exc), version_dir=version_dir,
                        version_existed=version_existed)
    # 迁移后校验: 解析后的 entrypoint 必须落在 RELEASES_DIR 下
    migrated = _registered_runtime()
    if not migrated.get("ok") or RELEASES_DIR not in Path(migrated["entrypoint"]).parents:
        return rollback("migrate_verify_failed", runtime=migrated, version_dir=version_dir,
                        version_existed=version_existed)
    return {
        "ok": True, "baseline_version": baseline, "entrypoint": str(CURRENT_ENTRYPOINT),
        "backup": str(backup), "write_performed": True,
    }


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _resolved(path: Path) -> Path:
    """Resolve a user supplied path without requiring that it already exists."""
    return path.expanduser().resolve()


def _registered_runtime() -> dict:
    """Read the single installed Zhixing LaunchAgent registration.

    The production read plane has no path or plist override: a caller can inspect
    only the machine's registered runtime, never nominate a target of its own.
    """
    plist_path = _resolved(LAUNCH_AGENT_PLIST)
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        return {"ok": False, "reason": "launch_agent_plist_unreadable", "detail": str(exc)}

    if payload.get("Label") != LAUNCH_AGENT_LABEL:
        return {"ok": False, "reason": "launch_agent_label_mismatch"}
    arguments = payload.get("ProgramArguments")
    working_directory = payload.get("WorkingDirectory")
    if not isinstance(arguments, list):
        return {"ok": False, "reason": "launch_agent_program_missing"}

    scripts = [argument for argument in arguments if isinstance(argument, str)
               and Path(argument).name == "live_server.py"]
    if len(scripts) != 1:
        return {"ok": False, "reason": "launch_agent_live_server_ambiguous"}

    script = Path(scripts[0]).expanduser()
    if not script.is_absolute():
        if not isinstance(working_directory, str):
            return {"ok": False, "reason": "launch_agent_relative_entrypoint_without_root"}
        script = _resolved(Path(working_directory)) / script
    script = _resolved(script)
    root = script.parent
    if isinstance(working_directory, str) and _resolved(Path(working_directory)) != root:
        return {
            "ok": False,
            "reason": "launch_agent_root_mismatch",
            "runtime_root": str(root),
            "entrypoint": str(script),
        }
    if script.name != "live_server.py":
        return {"ok": False, "reason": "launch_agent_entrypoint_mismatch"}
    return {
        "ok": True,
        "label": LAUNCH_AGENT_LABEL,
        "plist": str(plist_path),
        "runtime_root": str(root),
        "entrypoint": str(script),
    }


def _running_registered_runtime() -> dict:
    """Bind read-only planning to the registered LaunchAgent's current process."""
    registration = _registered_runtime()
    if not registration.get("ok"):
        return registration

    domain = f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"
    try:
        launchctl = subprocess.run(
            ["launchctl", "print", domain],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "reason": "launch_agent_pid_unavailable", "detail": str(exc),
                "registration": registration}
    matched = re.search(r"(?m)^\s*pid = (\d+)\s*$", launchctl.stdout) if launchctl.returncode == 0 else None
    if matched is None:
        return {"ok": False, "reason": "launch_agent_pid_unavailable", "registration": registration}

    pid = int(matched.group(1))
    try:
        process = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "reason": "launch_agent_pid_command_unavailable", "detail": str(exc),
                "pid": pid, "registration": registration}
    command = process.stdout.strip() if process.returncode == 0 else ""
    try:
        arguments = shlex.split(command)
    except ValueError:
        arguments = []
    entrypoint = registration["entrypoint"]
    try:
        port_index = arguments.index("--port")
        port_matches = arguments[port_index + 1] == "43191"
    except (ValueError, IndexError):
        port_matches = False
    actual_entrypoints: list[Path] = []
    for argument in arguments:
        candidate = Path(argument).expanduser()
        if candidate.name != "live_server.py":
            continue
        if not candidate.is_absolute():
            candidate = Path(registration["runtime_root"]) / candidate
        actual_entrypoints.append(candidate.resolve())
    expected_entrypoint = Path(entrypoint).resolve()
    if (len(actual_entrypoints) != 1 or actual_entrypoints[0] != expected_entrypoint
            or not port_matches):
        return {
            "ok": False,
            "reason": "launch_agent_pid_command_mismatch",
            "pid": pid,
            "command": command,
            "registration": registration,
        }
    return {"ok": True, "pid": pid, "command": command, **registration}


def status(dashboard_dir: Path | None = None, host_dir: Path | None = None) -> dict:
    dash = dashboard_dir or DASHBOARD_DIR
    host = host_dir or HOST_DIR
    files = []
    drifted = missing_repo = missing_deploy = 0
    for deploy_name, repo_name in HOST_FILES:
        repo, live = host / repo_name, dash / deploy_name
        name = deploy_name
        rs, ls = _sha(repo), _sha(live)
        if rs is None:
            state = "no_repo_copy"
            missing_repo += 1
        elif ls is None:
            state = "no_deploy_copy"
            missing_deploy += 1
        elif rs == ls:
            state = "in_sync"
        else:
            state = "drifted"
            drifted += 1
        files.append({"name": name, "state": state, "repo_sha": rs, "deploy_sha": ls,
                      "repo_bytes": _size(repo), "deploy_bytes": _size(live)})
    return {
        "dashboard_dir": str(dash),
        "host_dir": str(host),
        "files": files,
        "drifted": drifted,
        "missing_repo_copy": missing_repo,
        "missing_deploy_copy": missing_deploy,
        "ok": drifted == 0 and missing_repo == 0 and missing_deploy == 0,
    }


def _selected_assets(files: list[str] | tuple[str, ...] | None) -> tuple[tuple[str, str], ...]:
    if not files:
        raise ValueError("必须至少指定一个 --file；禁止隐式全量检查")
    mapping = dict(HOST_FILES)
    requested = tuple(files)
    if len(requested) != len(set(requested)):
        raise ValueError("--file 不能重复")
    unknown = [name for name in requested if name not in mapping]
    if unknown:
        raise ValueError("未登记的宿主资产: " + ", ".join(unknown))
    return tuple((name, mapping[name]) for name in requested)


def _blocked(operation: str) -> dict:
    return {
        "ok": False,
        "state": "BLOCKED",
        "operation": operation,
        "reason": BLOCKED_REASON,
        "detail": "G0=PARTIAL/HOLD and M0=FAIL/HOLD; a separately admitted release BET is required.",
    }


def capture(*_args: object, **_kwargs: object) -> dict:
    """Legacy programmatic entry point: production capture is unavailable."""
    return _blocked("capture")


def _asset_plan(runtime_root: Path,
                files: list[str] | tuple[str, ...] | None,
                host_dir: Path) -> dict:
    try:
        assets = _selected_assets(files)
    except ValueError as exc:
        return {"ok": False, "reason": "invalid_asset_selection", "detail": str(exc)}

    planned: list[dict] = []
    for deploy_name, repo_name in assets:
        source = host_dir / repo_name
        destination = runtime_root / deploy_name
        source_sha = _sha(source)
        runtime_sha = _sha(destination)
        if source_sha is None:
            state = "versioned_asset_missing"
        elif runtime_sha is None:
            state = "runtime_asset_missing"
        elif source_sha == runtime_sha:
            state = "in_sync"
        else:
            state = "drifted"
        planned.append({
            "name": deploy_name,
            "state": state,
            "source": str(source),
            "runtime": str(destination),
            "source_sha": source_sha,
            "runtime_sha": runtime_sha,
        })
    return {
        "ok": all(item["state"] == "in_sync" for item in planned),
        "target_root": str(runtime_root),
        "files": planned,
        "write_performed": False,
    }


REFRESH_LABEL = "com.omostation.zhixing-dashboard-refresh"


def bind_refresh(*, restore: bool = False) -> dict:
    """Bind only the already registered refresh service; preserve exact rollback."""
    plist_path = LAUNCH_AGENT_PLIST.with_name(f"{REFRESH_LABEL}.plist")
    backup = plist_path.with_name(f"{REFRESH_LABEL}.plist.release-backup")
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{REFRESH_LABEL}"
    try:
        if plist_path.is_symlink() or not plist_path.is_file() or backup.is_symlink():
            raise ValueError("refresh_plist_unsafe")
        before = plist_path.read_bytes()
        payload = plistlib.loads(before)
        loaded = subprocess.run(["launchctl", "print", service], capture_output=True, text=True)
        if loaded.returncode != 0 or payload.get("Label") != REFRESH_LABEL:
            raise ValueError("refresh_service_not_registered")
        args = payload.get("ProgramArguments")
        if not isinstance(args, list):
            raise ValueError("refresh_program_invalid")
        scripts = [(i, arg) for i, arg in enumerate(args)
                   if isinstance(arg, str) and Path(arg).name == "orchestrator.py"]
        if len(scripts) != 1:
            raise ValueError("refresh_entrypoint_invalid")
        index, old_entry = scripts[0]
        if str(old_entry) not in loaded.stdout:
            raise ValueError("refresh_loaded_registration_mismatch")
        if Path(old_entry).expanduser().resolve().parent not in {
                DASHBOARD_DIR.resolve(), CURRENT_LINK.resolve()}:
            raise ValueError("refresh_entrypoint_outside_scope")
        if restore:
            if not backup.is_file():
                raise ValueError("refresh_backup_missing")
            target = backup.read_bytes()
            original = plistlib.loads(target)
            if original.get("Label") != REFRESH_LABEL:
                raise ValueError("refresh_backup_label_mismatch")
        else:
            current = CURRENT_LINK.resolve()
            if (_current_version() is None or not (current / "orchestrator.py").is_file()):
                raise ValueError("refresh_current_unavailable")
            env = payload.get("EnvironmentVariables", {})
            if not isinstance(env, dict):
                raise ValueError("refresh_environment_invalid")
            configured = env.get("ZHIXING_DASHBOARD_STATE_ROOT")
            if configured and Path(configured).expanduser().resolve() != DASHBOARD_DIR.resolve():
                raise ValueError("refresh_state_root_mismatch")
            stable_entry = str(CURRENT_LINK / "orchestrator.py")
            if old_entry == stable_entry and configured == str(DASHBOARD_DIR):
                return {"ok": True, "already_bound": True, "write_performed": False}
            args[index] = stable_entry
            payload["WorkingDirectory"] = str(CURRENT_LINK)
            payload["EnvironmentVariables"] = dict(env, ZHIXING_DASHBOARD_STATE_ROOT=str(DASHBOARD_DIR))
            target = plistlib.dumps(payload)
            if backup.exists() and backup.read_bytes() != before:
                raise ValueError("refresh_backup_conflict")
            _atomic_write_bytes(backup, before)
        _atomic_write_bytes(plist_path, target)
        def reload():
            stopped = subprocess.run(["launchctl", "bootout", service], capture_output=True, text=True)
            if stopped.returncode != 0:
                return False
            started = subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
            if started.returncode != 0:
                return False
            verify = subprocess.run(["launchctl", "print", service], capture_output=True, text=True)
            expected = next(arg for arg in plistlib.loads(plist_path.read_bytes())["ProgramArguments"]
                            if isinstance(arg, str) and Path(arg).name == "orchestrator.py")
            return verify.returncode == 0 and expected in verify.stdout
        if not reload():
            _atomic_write_bytes(plist_path, before)
            # A failed bootstrap may leave it unloaded; restore only this service.
            subprocess.run(["launchctl", "bootout", service], capture_output=True, text=True)
            back = subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
            verified = subprocess.run(["launchctl", "print", service], capture_output=True, text=True)
            return {"ok": False, "reason": "refresh_reload_failed",
                    "recovery": {"ok": back.returncode == 0 and verified.returncode == 0
                                 and old_entry in verified.stdout}}
        return {"ok": True, "write_performed": True, "backup": str(backup), "restored": restore}
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        return {"ok": False, "reason": "refresh_binding_rejected", "detail": str(exc)}


def plan(files: list[str] | tuple[str, ...] | None) -> dict:
    """Read selected asset drift after binding the live PID to its plist entrypoint."""
    runtime = _running_registered_runtime()
    if not runtime.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "runtime": runtime}
    result = _asset_plan(Path(runtime["runtime_root"]), files, HOST_DIR)
    result["registration"] = runtime
    return result


def check() -> int:
    """Read-only compatibility check for registered assets; no report is written."""
    result = plan([deploy_name for deploy_name, _ in HOST_FILES])
    return 0 if result.get("ok") else 1


def _registered_status() -> dict:
    registration = _running_registered_runtime()
    if not registration.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "registration": registration}
    result = status(Path(registration["runtime_root"]), HOST_DIR)
    result["registration"] = registration
    result["write_performed"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] in BLOCKED_COMMANDS:
        result = _blocked(arguments[0])
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 2

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    status_parser = sub.add_parser("status", help="登记 LaunchAgent 实际运行根的只读漂移摘要")
    status_parser.add_argument("--json", action="store_true")
    plan_parser = sub.add_parser("plan", help="登记运行根中明确选择资产的只读差异计划")
    plan_parser.add_argument("--file", dest="files", action="append", required=True,
                             help="受管宿主文件名；可重复指定")
    plan_parser.add_argument("--json", action="store_true")
    check_parser = sub.add_parser("check", help="所有受管资产的只读兼容检查；漂移时 exit 1")
    check_parser.add_argument("--json", action="store_true")
    publish_parser = sub.add_parser("publish", help="受管发布: 版本目录 + 原子切换 current + SHA 校验")
    publish_parser.add_argument("--file", dest="files", action="append", required=True,
                                help="受管宿主文件名；可重复指定")
    publish_parser.add_argument("--publication-id", default=None,
                                help="32位小写十六进制发布标识；创建 <commit>--pub-<id>，Git 来源不变")
    publish_parser.add_argument("--json", action="store_true")
    sub.add_parser("restore", help="回滚: current 切回上一版本").add_argument("--json", action="store_true")
    sub.add_parser("migrate", help="plist 迁移: entrypoint → current/live_server.py").add_argument("--json", action="store_true")
    sub.add_parser("bind-refresh", help="仅绑定已登记 refresh 到 current，保留精确回退").add_argument("--json", action="store_true")
    sub.add_parser("restore-refresh", help="原生恢复 refresh 的精确 plist 备份").add_argument("--json", action="store_true")
    args = ap.parse_args(arguments)
    command = args.command or "status"

    if command == "bind-refresh":
        result = bind_refresh()
    elif command == "restore-refresh":
        result = bind_refresh(restore=True)
    elif command == "plan":
        result = plan(args.files)
    elif command == "check":
        result = plan([deploy_name for deploy_name, _ in HOST_FILES])
    elif command == "publish":
        result = publish(args.files, publication_id=args.publication_id)
    elif command == "restore":
        result = restore()
    elif command == "migrate":
        result = migrate()
    else:
        result = _registered_status()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
