"""扫描 FamilyShared 健康档案目录。

约定路径：~/Library/Mobile Documents/iCloud~md~obsidian/Documents/FamilyShared/02.健康/档案/*.json
目录不存在时返回空列表（由 runner 给出用户友好提示，不在此层抛错）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from health_profile.io import read_json
from health_profile.models import HealthProfile

DEFAULT_PROFILE_DIR: Path = Path(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/FamilyShared/02.健康/档案"
).expanduser()


def scan_profiles(root: Path | None = None) -> list[HealthProfile]:
    """扫描目录下所有 *.json 档案。

    - 目录不存在 → 返回 []（不抛错）
    - 单文件解析失败 → 跳过 + stderr 警告，不影响其他文件
    - 文件名 `<member>.health.json` 或 `<member>.json` 都接受
    """
    root = root if root is not None else DEFAULT_PROFILE_DIR
    if not root.exists():
        print(f"[WARN] 档案目录不存在: {root}", file=sys.stderr)
        return []
    if not root.is_dir():
        print(f"[WARN] 档案路径不是目录: {root}", file=sys.stderr)
        return []

    profiles: list[HealthProfile] = []
    for json_file in sorted(root.glob("*.json")):
        try:
            profiles.append(read_json(json_file))  # type: ignore[reportArgumentType]
        except Exception as exc:
            print(f"[WARN] skip {json_file.name}: {exc}", file=sys.stderr)
    return profiles
