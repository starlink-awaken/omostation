"""Domain Cartridge Capsule Packager (ADR-0203).

Bundles a domain directory containing manifest, knowledge, and rules into a signed .cartridge archive.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path
from typing import Any
from cockpit.cartridge.spec import CartridgeManifest


class CartridgePackager:
    """领域卡带打包器."""

    @staticmethod
    def pack(source_dir: Path, output_file: Path) -> CartridgeManifest:
        """将源目录打包为带有 SHA-256 签名的 .cartridge 归档文件."""
        manifest_path = source_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest.json in {source_dir}")

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = CartridgeManifest.from_dict(manifest_data)

        # 计算目录文件内容哈希
        hasher = hashlib.sha256()
        for root, _, files in sorted(os.walk(source_dir)):
            for f in sorted(files):
                if f == output_file.name:
                    continue
                file_p = Path(root) / f
                hasher.update(file_p.read_bytes())

        manifest.manifest_hash = hasher.hexdigest()
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_file, "w:gz") as tar:
            for item in source_dir.iterdir():
                tar.add(item, arcname=item.name)

        return manifest
