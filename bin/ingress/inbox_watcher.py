#!/usr/bin/env python3
"""~/Documents/_inbox 真实文件感知与 LECP 实体分诊器 (LECP v3.0 规范版)"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml


def _parse_frontmatter(path: Path) -> dict:
    title = path.stem
    domain = "p0_work"
    privacy_level = "internal"
    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    
    try:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1])
                if isinstance(fm, dict):
                    title = fm.get("title", title)
                    d = str(fm.get("domain", "")).lower()
                    if "family" in d:
                        domain = "p2_family"
                        privacy_level = "secret"
                    elif "health" in d or "health" in str(path).lower():
                        domain = "p1_health"
                        privacy_level = "secret"
                    elif "work" in d or "weijian" in d:
                        domain = "p0_work"
                        privacy_level = "internal"
                    
                    if "date" in fm:
                        created_at = str(fm["date"])
    except Exception:
        pass
    
    # 路径兜底
    if "health" in str(path).lower():
        domain = "p1_health"
        privacy_level = "secret"
    elif "family" in str(path).lower():
        domain = "p2_family"
        privacy_level = "secret"

    # 基于路径哈希生成稳定 entity_id
    h = hashlib.md5(str(path).encode("utf-8")).hexdigest()[:8]
    entity_id = f"evt-inbox-{h}"

    return {
        "entity_id": entity_id,
        "title": title,
        "domain": domain,
        "privacy_level": privacy_level,
        "source": "local_file",
        "file_path": str(path),
        "created_at": created_at,
    }


def scan_inbox(inbox_root: Path | None = None) -> list[dict]:
    root = inbox_root or Path("/Users/xiamingxing/Documents/_inbox")
    events = []
    if not root.exists():
        return events
    for path in root.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            events.append(_parse_frontmatter(path))
    # 按创建/修改时间倒序排列
    events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return events


if __name__ == "__main__":
    items = scan_inbox()
    print(f"Total inbox items: {len(items)}")
    for item in items[:10]:
        print(json.dumps(item, ensure_ascii=False))
