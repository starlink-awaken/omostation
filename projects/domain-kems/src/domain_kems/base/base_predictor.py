"""
BasePredictor — 统一预测器基类
"""
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class BasePredictor:
    """统一预测器基类"""

    def __init__(self, domain_root: Path):
        self.domain_root = Path(domain_root)
        self.root = self.domain_root
        self._model = None

    def detect_stale_docs(self, days: int = 90) -> List[dict]:
        stale = []
        knowledge_dir = self.root / "_knowledge"
        if not knowledge_dir.exists():
            return stale
        now = datetime.now().timestamp()
        threshold = days * 86400
        for md_file in knowledge_dir.rglob("*.md"):
            mtime = md_file.stat().st_mtime
            if now - mtime > threshold:
                stale.append({
                    "file": str(md_file.relative_to(self.root)),
                    "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                    "days_old": int((now - mtime) / 86400),
                })
        stale.sort(key=lambda x: -x["days_old"])
        return stale

    def detect_orphan_files(self) -> List[dict]:
        orphans = []
        knowledge_dir = self.root / "_knowledge"
        if not knowledge_dir.exists():
            return orphans
        index_file = knowledge_dir / "INDEX.md"
        if not index_file.exists():
            return [{"issue": "INDEX.md missing"}]
        index_content = index_file.read_text(encoding="utf-8")
        for md_file in knowledge_dir.rglob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            rel_path = str(md_file.relative_to(self.root))
            if rel_path not in index_content and md_file.stem not in index_content:
                orphans.append({"file": rel_path, "size": md_file.stat().st_size})
        return orphans

    def predict_growth(self, days: int = 30) -> dict:
        knowledge_dir = self.root / "_knowledge"
        if not knowledge_dir.exists():
            return {"predictable": False}
        now = datetime.now().timestamp()
        period = days * 86400
        recent_count = 0
        total_count = 0
        for md_file in knowledge_dir.rglob("*.md"):
            total_count += 1
            if now - md_file.stat().st_mtime < period:
                recent_count += 1
        return {
            "predictable": True,
            "total_files": total_count,
            "recent_files": recent_count,
            "period_days": days,
            "growth_rate": recent_count / total_count if total_count > 0 else 0,
        }

    def risk_assessment(self) -> dict:
        risks = []
        stale = self.detect_stale_docs()
        if len(stale) > 10:
            risks.append({"type": "stale_documents", "severity": "medium", "count": len(stale)})
        orphans = self.detect_orphan_files()
        if len(orphans) > 5:
            risks.append({"type": "orphan_files", "severity": "low", "count": len(orphans)})
        return {
            "risk_level": "high" if any(r["severity"] == "high" for r in risks) else "medium" if risks else "low",
            "risks": risks,
            "assessed_at": datetime.now().isoformat(),
        }
