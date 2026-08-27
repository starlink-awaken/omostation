"""WeChat connector backed by export-stub text imports."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.models import KnowledgeArtifact, Note


class WeChatConnector(BaseConnector):
    name = "wechat"
    display_name = "WeChat"

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or (Path.home() / ".iris" / "data" / "wechat")
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def connect(self) -> dict[str, Any]:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return {"connected": True, "mode": "export_stub"}

    def _record_paths(self) -> list[Path]:
        return sorted(self._data_dir.glob("import_*.json"))

    def _parse_messages(self, content: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for line in content.splitlines():
            match = re.match(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}).*?[-:]\s*(.+?)[-:]\s*(.+)",
                line.strip(),
            )
            if not match:
                continue
            messages.append(
                {
                    "time": match.group(1),
                    "sender": match.group(2).strip(),
                    "text": match.group(3).strip(),
                }
            )
        return messages

    def import_file(self, path: str) -> dict[str, Any]:
        source = Path(path).expanduser()
        if not source.exists():
            return {"error": f"File not found: {path}"}
        content = source.read_text(encoding="utf-8", errors="replace")
        messages = self._parse_messages(content)
        record = {
            "id": f"wechat-{int(time.time())}",
            "source": str(source),
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": len(messages),
            "messages": messages[-500:],
        }
        target = self._data_dir / f"import_{int(time.time() * 1000)}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"imported": len(messages), "file": str(source), "record_id": record["id"]}

    def _load_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for record_path in self._record_paths():
            try:
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return records

    def _message_to_note(self, record: dict[str, Any], message: dict[str, str], index: int) -> Note:
        title = f"{message.get('sender', 'Unknown')} @ {message.get('time', '')}"
        return Note(
            id=f"{record.get('id', 'wechat')}-{index}",
            title=title,
            platform=self.name,
            created_at=message.get("time", ""),
            updated_at=record.get("imported_at", ""),
            content=message.get("text", ""),
            tags=["wechat", "chat-export"],
            source_path=record.get("source", ""),
            platform_notebook="wechat-export",
        )

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        items: list[KnowledgeArtifact] = []
        for record in self._load_records():
            for index, message in enumerate(record.get("messages", [])):
                items.append(self._message_to_note(record, message, index))
        if cursor:
            items = [item for item in items if item.id > cursor]
        return items[:limit]

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        for item in self.list_items(limit=1000):
            if item.id == id:
                return item
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        needle = query.lower()
        return [item for item in self.list_items(limit=1000) if needle in cast(Note, item).content.lower()][:limit]

    def query(self, q: str) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.search(q, limit=20)]

    def list_contacts(self, limit: int = 50) -> list[str]:
        contacts: list[str] = []
        for record in self._load_records():
            for message in record.get("messages", []):
                sender = str(message.get("sender", "")).strip()
                if sender and sender not in contacts:
                    contacts.append(sender)
        return contacts[:limit]

    def status(self) -> dict[str, Any]:
        records = self._load_records()
        message_count = sum(len(record.get("messages", [])) for record in records)
        return {
            "available": self.is_available(),
            "mode": "export_stub",
            "imports": len(records),
            "messages": message_count,
            "contacts": len(self.list_contacts()),
            "data_dir": str(self._data_dir),
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        status = self.status()
        message = "WeChat export-stub connector is ready for new imports."
        if dry_run:
            message = "Dry-run: no native sync, export-stub only."
        return SyncResult(
            connector_name=self.name,
            items_found=status["messages"],
            success=True,
            message=message,
        )
