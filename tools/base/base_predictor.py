"""
BasePredictor — 统一预测器基类
所有域预测器继承此类，复用趋势预测、风险预警能力
"""
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


class BasePredictor(ABC):
    """统一预测器基类"""

    def __init__(self, domain_root: Path, config: dict | None = None):
        self.domain_root = Path(domain_root)
        self.config = config or {}
        self._model = None

    # === 通用预测能力 ===

    def detect_stale_docs(self, days: int = 90) -> list[dict]:
        """检测过期文档"""
        stale = []
        knowledge_dir = self.domain_root / "_knowledge"
        if not knowledge_dir.exists():
            return stale

        now = datetime.now().timestamp()
        threshold = days * 86400

        for md_file in knowledge_dir.rglob("*.md"):
            mtime = md_file.stat().st_mtime
            if now - mtime > threshold:
                stale.append({
                    "file": str(md_file.relative_to(self.domain_root)),
                    "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                    "days_old": int((now - mtime) / 86400)
                })

        stale.sort(key=lambda x: -x["days_old"])
        return stale

    def detect_orphan_files(self) -> list[dict]:
        """检测孤儿文件（有文件无索引）"""
        orphans = []
        knowledge_dir = self.domain_root / "_knowledge"
        if not knowledge_dir.exists():
            return orphans

        index_file = knowledge_dir / "INDEX.md"
        if not index_file.exists():
            return [{"issue": "INDEX.md missing"}]

        index_content = index_file.read_text(encoding="utf-8")

        for md_file in knowledge_dir.rglob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            rel_path = str(md_file.relative_to(self.domain_root))
            if rel_path not in index_content and md_file.stem not in index_content:
                orphans.append({
                    "file": rel_path,
                    "size": md_file.stat().st_size
                })

        return orphans

    def predict_growth(self, days: int = 30) -> dict:
        """预测知识增长趋势"""
        knowledge_dir = self.domain_root / "_knowledge"
        if not knowledge_dir.exists():
            return {"predictable": False}

        # Simple linear trend based on file mtimes
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
            "predicted_next_30d": int(recent_count * 1.1)  # Simple 10% growth
        }

    def risk_assessment(self) -> dict:
        """风险评估"""
        risks = []

        # Check stale docs
        stale = self.detect_stale_docs()
        if len(stale) > 10:
            risks.append({
                "type": "stale_documents",
                "severity": "medium",
                "count": len(stale),
                "description": f"{len(stale)} 文档超过 90 天未更新"
            })

        # Check orphan files
        orphans = self.detect_orphan_files()
        if len(orphans) > 5:
            risks.append({
                "type": "orphan_files",
                "severity": "low",
                "count": len(orphans),
                "description": f"{len(orphans)} 文件未编入索引"
            })

        return {
            "risk_level": "high" if any(r["severity"] == "high" for r in risks) else "medium" if risks else "low",
            "risks": risks,
            "assessed_at": datetime.now().isoformat()
        }

    # === 抽象方法 ===

    @abstractmethod
    def predict_domain_trend(self) -> dict:
        """域特有趋势预测"""
        pass

    @abstractmethod
    def detect_domain_risks(self) -> dict:
        """域特有风险检测"""
        pass
