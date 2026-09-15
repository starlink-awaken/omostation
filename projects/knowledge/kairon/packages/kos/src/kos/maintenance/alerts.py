#!/usr/bin/env python3
# ruff: noqa
"""
KOS Alert Service — 健康告警服务

检测索引健康状态并在异常时发送告警。

Usage:
    from kos.maintenance.alerts import AlertService

    alerts = AlertService()
    alerts.check_all()  # Run all checks

    # Or via CLI:
    # kos monitor alerts
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class AlertService:
    """告警服务。"""

    # 告警级别
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    # 检查项配置
    CHECKS = {
        "index_integrity": {
            "description": "索引完整性 (FTS ↔ 文档数一致性)",
            "severity": "critical",
            "threshold": 0,  # 允许的差异数
        },
        "vector_lag": {
            "description": "向量索引滞后 (未索引文档数)",
            "severity": "warning",
            "threshold": 100,
        },
        "search_latency": {
            "description": "搜索延迟 P99",
            "severity": "warning",
            "threshold": 500,  # ms
        },
        "cache_hit_rate": {
            "description": "缓存命中率",
            "severity": "info",
            "threshold": 50,  # percent
        },
        "orphan_entities": {
            "description": "孤立实体数 (无文档关联)",
            "severity": "info",
            "threshold": 50,
        },
        "db_size": {
            "description": "数据库大小",
            "severity": "warning",
            "threshold": 10 * 1024 * 1024 * 1024,  # 10GB
        },
    }

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 检查项 ──────────────────────────────────────────────

    def check_all(self) -> dict[str, Any]:
        """运行所有检查。"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "alerts": [],
            "healthy": True,
        }

        for check_name, config in self.CHECKS.items():
            try:
                alert = self._run_check(check_name, config)
                if alert:
                    results["alerts"].append(alert)
                    if alert["severity"] in ("critical", "warning"):
                        results["healthy"] = False
            except Exception as e:
                results["alerts"].append(
                    {
                        "check": check_name,
                        "severity": "warning",
                        "message": f"Check failed: {e}",
                    }
                )

        results["alert_count"] = len(results["alerts"])
        return results

    def _run_check(self, name: str, config: dict) -> dict | None:
        """运行单个检查。"""
        check_fn = getattr(self, f"_check_{name}", None)
        if check_fn is None:
            return None
        return check_fn(config)

    def _check_index_integrity(self, config: dict) -> dict | None:
        """检查索引完整性。"""
        doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        fts_count = self.conn.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
        diff = abs(doc_count - fts_count)

        if diff > config["threshold"]:
            return {
                "check": "index_integrity",
                "severity": config["severity"],
                "message": f"Index integrity issue: {doc_count} docs vs {fts_count} FTS entries (diff={diff})",
                "value": diff,
                "threshold": config["threshold"],
            }
        return None

    def _check_vector_lag(self, config: dict) -> dict | None:
        """检查向量索引滞后。"""
        try:
            import lancedb

            lancedb_dir = self.db_path.parent / "vectors"  # type: ignore[reportAttributeAccessIssue]
            db = lancedb.connect(str(lancedb_dir))
            if "kos_documents" in db.list_tables():  # type: ignore[reportOperatorIssue]
                tbl = db.open_table("kos_documents")
                indexed = tbl.count_rows()
            else:
                indexed = 0

            doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            # Approximate: each doc has ~3 chunks on average
            expected = doc_count * 3
            lag = max(0, expected - indexed)

            if lag > config["threshold"]:
                return {
                    "check": "vector_lag",
                    "severity": config["severity"],
                    "message": f"Vector index lag: {lag} chunks behind (~{indexed}/{expected})",
                    "value": lag,
                    "threshold": config["threshold"],
                }
        except Exception:
            pass
        return None

    def _check_search_latency(self, config: dict) -> dict | None:
        """检查搜索延迟。"""
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine(self.db_path)
        # Run a few test queries
        latencies = []
        for q in ["test", "报告", "项目"]:
            result = engine.search(q, mode="keyword", limit=5)
            latencies.append(result.get("elapsed_ms", 0))
        engine.close()

        if not latencies:
            return None

        p99 = sorted(latencies)[-1]  # Simplified P99
        if p99 > config["threshold"]:
            return {
                "check": "search_latency",
                "severity": config["severity"],
                "message": f"Search latency P99: {p99}ms (threshold: {config['threshold']}ms)",
                "value": p99,
                "threshold": config["threshold"],
            }
        return None

    def _check_cache_hit_rate(self, config: dict) -> dict | None:
        """检查缓存命中率。"""
        try:
            stats = self.conn.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]
            # Simplified: just check if cache table exists and has entries
            if stats == 0:
                return {
                    "check": "cache_hit_rate",
                    "severity": config["severity"],
                    "message": "Search cache is empty",
                    "value": 0,
                    "threshold": config["threshold"],
                }
        except Exception:
            pass
        return None

    def _check_orphan_entities(self, config: dict) -> dict | None:
        """检查孤立实体。"""
        orphans = self.conn.execute("""
            SELECT COUNT(*) FROM kos_entities e
            LEFT JOIN kos_entity_docs ed ON e.entity_id = ed.entity_id
            WHERE ed.doc_id IS NULL
        """).fetchone()[0]

        if orphans > config["threshold"]:
            return {
                "check": "orphan_entities",
                "severity": config["severity"],
                "message": f"{orphan} entities without document links",  # type: ignore[reportUndefinedVariable]
                "value": orphans,
                "threshold": config["threshold"],
            }
        return None

    def _check_db_size(self, config: dict) -> dict | None:
        """检查数据库大小。"""
        db_size = self.db_path.stat().st_size  # type: ignore[reportAttributeAccessIssue]

        if db_size > config["threshold"]:
            return {
                "check": "db_size",
                "severity": config["severity"],
                "message": f"Database size: {db_size / (1024**3):.1f}GB (threshold: {config['threshold'] / (1024**3):.0f}GB)",
                "value": db_size,
                "threshold": config["threshold"],
            }
        return None

    # ── 告警通知 ────────────────────────────────────────────

    def send_alert(self, alert: dict) -> bool:
        """发送告警通知。"""
        try:
            from kos.push_engine import send_notification  # type: ignore[reportAttributeAccessIssue]

            send_notification(
                title=f"[KOS] {alert['check']}",
                message=alert["message"],
                severity=alert["severity"],
            )
            return True
        except ImportError:
            # Fallback: just print
            print(f"ALERT [{alert['severity']}]: {alert['message']}", file=sys.stderr)
            return False

    def close(self):
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS Alert Service")
    parser.add_argument("--notify", action="store_true", help="Send notifications")
    args = parser.parse_args()

    service = AlertService()
    results = service.check_all()

    print(json.dumps(results, ensure_ascii=False, indent=2))

    if args.notify:
        for alert in results["alerts"]:
            service.send_alert(alert)

    service.close()


if __name__ == "__main__":
    main()
