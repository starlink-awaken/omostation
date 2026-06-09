"""
ssot-kernel — evolution/checkpoint.py
=====================================
检查点系统：每次修改 YAML 前自动备份，支持回滚。

保证"改坏了能回去"，是迭代的前提条件。
"""

from __future__ import annotations

import datetime
import json
import shutil
from pathlib import Path
from typing import Any


class CheckpointManager:
    """领域配置检查点管理器"""

    def __init__(self, domain_dir: str):
        self.domain_dir = Path(domain_dir)
        self._cp_dir = self.domain_dir / ".checkpoints"
        self._cp_dir.mkdir(exist_ok=True)

    def create(self, label: str = "") -> str:
        """创建当前所有 YAML 的快照"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        cp_name = f"{timestamp}-{label}" if label else timestamp
        cp_path = self._cp_dir / cp_name
        cp_path.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any] = {
            "created_at": timestamp,
            "label": label,
            "files": [],
        }

        for yaml_file in sorted(self.domain_dir.glob("*.yaml")):
            if yaml_file.parent == self._cp_dir:
                continue
            dest = cp_path / yaml_file.name
            shutil.copy2(yaml_file, dest)
            manifest["files"].append(yaml_file.name)

        # 写入清单
        (cp_path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return cp_name

    def list_checkpoints(self) -> list[dict]:
        """列出所有检查点"""
        checkpoints = []
        for cp_dir in sorted(self._cp_dir.iterdir()):
            if not cp_dir.is_dir():
                continue
            manifest_path = cp_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text("utf-8"))
                checkpoints.append(
                    {
                        "name": cp_dir.name,
                        "created_at": manifest.get("created_at", ""),
                        "label": manifest.get("label", ""),
                        "files": manifest.get("files", []),
                    }
                )
        return sorted(checkpoints, key=lambda x: x["created_at"], reverse=True)

    def restore(self, cp_name: str) -> list[str]:
        """从检查点恢复"""
        cp_path = self._cp_dir / cp_name
        if not cp_path.exists():
            raise FileNotFoundError(f"检查点不存在: {cp_name}")

        manifest = json.loads((cp_path / "manifest.json").read_text("utf-8"))
        restored = []

        for fname in manifest.get("files", []):
            src = cp_path / fname
            if not src.exists():
                continue
            dest = self.domain_dir / fname
            shutil.copy2(src, dest)
            restored.append(fname)

        return restored

    def diff(self, cp_name: str) -> str:
        """对比当前配置与指定检查点的差异"""
        cp_path = self._cp_dir / cp_name
        if not cp_path.exists():
            return f"检查点不存在: {cp_name}"

        lines = []
        manifest = json.loads((cp_path / "manifest.json").read_text("utf-8"))

        for fname in manifest.get("files", []):
            old_path = cp_path / fname
            new_path = self.domain_dir / fname
            old_content = old_path.read_text("utf-8") if old_path.exists() else ""
            new_content = new_path.read_text("utf-8") if new_path.exists() else ""

            if old_content == new_content:
                continue

            lines.append(f"  📄 {fname}:")
            old_lines = old_content.split("\n")
            new_lines = new_content.split("\n")
            for i, (old, new) in enumerate(zip(old_lines, new_lines), 1):
                if old != new:
                    lines.append(f"    L{i}: - {old}")
                    lines.append(f"         + {new}")

        return "\n".join(lines) if lines else "  无差异"
