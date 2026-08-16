"""
OntoDerive 图灵机层 v2 — 知识状态机(K-TM)
===========================================
基于模型的状态管理：每次derive产生DeriveSnapshot，
状态转移可追踪，delta趋近于零时自动停机。
"""

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .models import DeriveSnapshot  # type: ignore[reportMissingImports]
    from .utils import all_md, rf, wf  # type: ignore[reportMissingImports]
except ImportError:
    from ontoderive.foundation.utils import all_md, rf, wf  # noqa
    from ontoderive.foundation.models import DeriveSnapshot


class KnowledgeTM:
    def __init__(self, project_root: Any) -> None:
        self.root = Path(project_root)
        self.log_dir = self.root / "_derivation_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._states: list[DeriveSnapshot] = []
        self._load_history()

    def _load_history(self) -> None:
        snapshots = sorted(self.log_dir.glob("snapshot-*.json"))
        for s in snapshots:
            try:
                data = json.loads(s.read_text())
                ds = DeriveSnapshot(
                    timestamp=data.get("timestamp", ""),
                    facts=data.get("facts", 0),
                    entities=data.get("entities", 0),
                    inferences=data.get("inferences", 0),
                    scheme_files=data.get("scheme_files", 0),
                    metrics=data.get("metrics"),
                )
                self._states.append(ds)
            except Exception:
                pass

    def snapshot(self) -> Any:
        """创建当前知识状态快照（基于模型，非MD5）"""
        import re

        facts_text = ""
        for f in all_md(self.root / "facts"):
            facts_text += rf(f)
        n_facts = len(set(re.findall(r"(D-F\d+|P-F\d+)", facts_text)))

        infs_text = ""
        inf_blocks = 0
        for f in all_md(self.root / "inferences"):
            text = rf(f)
            infs_text += text
            inf_blocks += len(re.findall(r"^##\s+", text, re.MULTILINE))

        entities_text = ""
        for f in all_md(self.root / "entities"):
            entities_text += rf(f)
        n_entities = len(set(re.findall(r"\*\*(ORG-[\w-]+|ROL-[\w-]+|PRJ-[\w-]+)\*\*", entities_text)))

        n_schemes = len(all_md(self.root / "scheme"))

        # 基础文件快照（保留兼容性）
        files = {}
        for f in all_md(self.root):
            if "_derivation_logs" in str(f) or "ontoderive.egg-info" in str(f):
                continue
            text = rf(f)
            files[str(f.relative_to(self.root))] = {
                "size": len(text),
                "hash": hashlib.md5(text.encode()).hexdigest()[:8],  # noqa: S324
            }

        state = DeriveSnapshot(
            timestamp=datetime.datetime.now().isoformat(),
            facts=n_facts,
            entities=n_entities,
            inferences=max(0, inf_blocks - 1),
            scheme_files=n_schemes,
        )

        self._states.append(state)

        # 保存为JSON
        snapshot_path = self.log_dir / f"snapshot-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        wf(
            snapshot_path,
            json.dumps(
                {
                    "timestamp": state.timestamp,
                    "facts": state.facts,
                    "entities": state.entities,
                    "inferences": state.inferences,
                    "scheme_files": state.scheme_files,
                    "file_count": len(files),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        wf(
            self.log_dir / "latest-snapshot.json",
            json.dumps(
                {
                    "timestamp": state.timestamp,
                    "file_count": len(files),
                    "state": {
                        "facts": state.facts,
                        "entities": state.entities,
                        "inferences": state.inferences,
                        "scheme_files": state.scheme_files,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        print(
            f"[turing] ✅ 快照: {state.facts}事实/{state.entities}实体/{state.inferences}推论/{state.scheme_files}方案"
        )
        return state

    def delta(self) -> dict[str, Any]:
        """计算最近两次状态的差异"""
        if len(self._states) < 2:
            return {"type": "no_history", "changes": []}

        prev = self._states[-2]
        curr = self._states[-1]
        changes = []
        for field in ["facts", "entities", "inferences", "scheme_files"]:
            old_val = getattr(prev, field, 0)
            new_val = getattr(curr, field, 0)
            if old_val != new_val:
                changes.append(
                    {
                        "field": field,
                        "old": old_val,
                        "new": new_val,
                        "delta": new_val - old_val,
                    }
                )
        return {"type": "delta", "changes": changes, "timestamp": curr.timestamp}

    def should_halt(self, epsilon: Any = 0) -> Any:
        """停机检测：最近两次状态无变化"""
        if len(self._states) < 3:
            return False
        d = self.delta()
        if d["type"] == "no_history":
            return False
        changes = d["changes"]
        return len(changes) == 0 or all(abs(c["delta"]) <= epsilon for c in changes)

    def diff(self) -> Any:
        """比较最新两次快照（兼容原api）"""
        snapshots = sorted(self.log_dir.glob("snapshot-*.json"))
        if len(snapshots) < 2:
            print("[turing] ℹ️ 需要至少2次快照才能对比")
            return []

        old = json.loads(snapshots[-2].read_text())
        new = json.loads(snapshots[-1].read_text())

        changes = []
        old_files = old.get("files", {})
        new_files = new.get("files", {})

        for fname, info in new_files.items():
            if fname not in old_files:
                changes.append({"file": fname, "type": "added", "size": info["size"]})
            elif old_files[fname]["hash"] != info["hash"]:
                changes.append({"file": fname, "type": "modified", "size": info["size"]})

        for fname in old_files:
            if fname not in new_files:
                changes.append({"file": fname, "type": "removed"})

        print(f"[turing] 📊 差异: {len(changes)}处变更")
        for c in changes[:10]:
            print(f"  {c['type']:8s} {c['file']}")
        return changes

    def replay(self) -> Any:
        snapshots = sorted(self.log_dir.glob("snapshot-*.json"))
        print(f"[turing] 📜 推导时间线({len(snapshots)}步):")
        for i, s in enumerate(snapshots):
            try:
                data = json.loads(s.read_text())
            except Exception:  # noqa: S112  # defensive fallback
                continue
            # 兼容新旧格式
            if "state" in data:
                st = data["state"]
                print(f"  q{i}: [{data.get('timestamp', '')[:19]}] {st.get('facts', 0)}F/{st.get('inferences', 0)}I")
            else:
                fc = len(data.get("files", {}))
                print(f"  q{i}: [{data.get('timestamp', 'unknown')[:19]}] {fc}文件")
        return snapshots
