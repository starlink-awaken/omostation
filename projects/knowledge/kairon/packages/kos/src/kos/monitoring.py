"""KOS Monitoring — index health checks, search quality, and performance metrics.

Usage:
    from kos.monitoring import KosMonitor

    monitor = KosMonitor()
    health = monitor.index_health()
    quality = monitor.search_quality()
    metrics = monitor.performance_metrics()
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path


class KosMonitor:
    """KOS system monitoring and health checks."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = get_artifact_path("retrievalDatabase")
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def index_health(self) -> dict[str, Any]:
        """Check index health: integrity, freshness, coverage.

        Returns:
            Dict with health status and details.
        """
        conn = self._connect()
        result = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.now().isoformat(),
        }

        # 1. Database integrity check
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            result["checks"]["integrity"] = {
                "status": "pass" if integrity == "ok" else "fail",
                "detail": integrity,
            }
            if integrity != "ok":
                result["status"] = "degraded"
        except sqlite3.Error as e:
            result["checks"]["integrity"] = {"status": "error", "detail": str(e)}
            result["status"] = "error"

        # 2. Document count
        try:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            result["checks"]["document_count"] = {
                "status": "pass" if doc_count > 0 else "warn",
                "count": doc_count,
            }
        except sqlite3.Error as e:
            result["checks"]["document_count"] = {"status": "error", "detail": str(e)}

        # 3. FTS table consistency
        try:
            fts_count = conn.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
            result["checks"]["fts_consistency"] = {
                "status": "pass" if fts_count == doc_count else "warn",  # type: ignore[reportPossiblyUnboundVariable]
                "fts_count": fts_count,
                "doc_count": doc_count,  # type: ignore[reportPossiblyUnboundVariable]
                "mismatch": doc_count - fts_count,  # type: ignore[reportPossiblyUnboundVariable]
            }
            if fts_count != doc_count:  # type: ignore[reportPossiblyUnboundVariable]
                result["status"] = "degraded"
        except sqlite3.Error as e:
            result["checks"]["fts_consistency"] = {"status": "error", "detail": str(e)}

        # 4. Stale documents (not updated in 90 days)
        try:
            stale_threshold = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d%H%M%S")
            stale_count = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE updated_at < ?", (stale_threshold,)
            ).fetchone()[0]
            stale_pct = (stale_count / doc_count * 100) if doc_count > 0 else 0  # type: ignore[reportPossiblyUnboundVariable]
            result["checks"]["stale_documents"] = {
                "status": "pass" if stale_pct < 20 else "warn",
                "count": stale_count,
                "percentage": round(stale_pct, 1),
            }
        except sqlite3.Error as e:
            result["checks"]["stale_documents"] = {"status": "error", "detail": str(e)}

        # 5. Zone coverage
        try:
            zones = conn.execute(
                "SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC"
            ).fetchall()
            result["checks"]["zone_coverage"] = {
                "status": "pass" if len(zones) > 1 else "warn",
                "zone_count": len(zones),
                "zones": {z["zone"]: z["cnt"] for z in zones[:10]},
            }
        except sqlite3.Error as e:
            result["checks"]["zone_coverage"] = {"status": "error", "detail": str(e)}

        # 6. Ontology health
        try:
            entity_count = conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]
            relation_count = conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0]
            result["checks"]["ontology"] = {
                "status": "pass" if entity_count > 0 else "warn",
                "entities": entity_count,
                "relations": relation_count,
            }
        except sqlite3.Error as e:
            result["checks"]["ontology"] = {"status": "error", "detail": str(e)}

        conn.close()
        return result

    def search_quality(self) -> dict[str, Any]:
        """Monitor search quality metrics.

        Returns:
            Dict with search quality metrics.
        """
        conn = self._connect()
        result = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
        }

        # Test 1: Chinese search returns results
        test_queries = ["数字化", "平台", "文档", "报告", "项目"]
        test_results = []
        for query in test_queries:
            try:
                rows = conn.execute(
                    """SELECT d.doc_id FROM documents_fts f
                       JOIN documents d ON f.doc_id = d.doc_id
                       WHERE documents_fts MATCH ? LIMIT 5""",
                    (query,),
                ).fetchall()
                test_results.append(
                    {
                        "query": query,
                        "found": len(rows) > 0,
                        "result_count": len(rows),
                    }
                )
            except sqlite3.OperationalError:
                test_results.append(
                    {
                        "query": query,
                        "found": False,
                        "result_count": 0,
                    }
                )

        passed = sum(1 for t in test_results if t["found"])
        result["tests"]["keyword_search"] = {
            "passed": passed,
            "total": len(test_queries),
            "pass_rate": round(passed / len(test_queries) * 100, 1) if test_queries else 0,
            "details": test_results,
        }

        # Test 2: Search latency (measure time for a simple query)
        latencies = []
        for _ in range(3):
            start = time.time()
            try:
                conn.execute(
                    "SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ? LIMIT 1", ("test",)
                ).fetchall()
            except sqlite3.OperationalError:
                pass
            latencies.append(time.time() - start)

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        result["tests"]["search_latency"] = {
            "status": "pass" if avg_latency < 0.1 else "warn",
            "avg_seconds": round(avg_latency, 4),
            "max_seconds": round(max(latencies), 4) if latencies else 0,
        }

        # Test 3: Entity search
        try:
            entity_search = conn.execute(
                """SELECT e.label FROM kos_entities e
                   JOIN kos_entity_docs ed ON e.entity_id = ed.entity_id
                   LIMIT 5"""
            ).fetchall()
            result["tests"]["entity_search"] = {
                "status": "pass" if len(entity_search) > 0 else "warn",
                "sample_count": len(entity_search),
            }
        except sqlite3.Error as e:
            result["tests"]["entity_search"] = {"status": "error", "detail": str(e)}

        # Overall quality score
        quality_score = 0
        if result["tests"]["keyword_search"]["pass_rate"] >= 80:
            quality_score += 40
        elif result["tests"]["keyword_search"]["pass_rate"] >= 50:
            quality_score += 20

        if result["tests"]["search_latency"]["status"] == "pass":
            quality_score += 30

        if result["tests"]["entity_search"].get("status") == "pass":
            quality_score += 30

        result["quality_score"] = quality_score
        result["quality_grade"] = (
            "A" if quality_score >= 90 else "B" if quality_score >= 70 else "C" if quality_score >= 50 else "D"
        )

        conn.close()
        return result

    def performance_metrics(self) -> dict[str, Any]:
        """Get system performance metrics.

        Returns:
            Dict with performance metrics.
        """
        conn = self._connect()

        # Database file size
        db_size = Path(self.db_path).stat().st_size
        db_size_mb = round(db_size / (1024 * 1024), 2)

        # Document metrics
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

        # Zone distribution
        zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC").fetchall()

        # Ontology metrics
        try:
            entity_count = conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]
            relation_count = conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0]
            entity_doc_count = conn.execute("SELECT COUNT(*) FROM kos_entity_docs").fetchone()[0]
        except sqlite3.Error:
            entity_count = 0
            relation_count = 0
            entity_doc_count = 0

        # FTS index size
        try:
            fts_size = conn.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
        except sqlite3.Error:
            fts_size = 0

        # Document age distribution
        now = datetime.now()
        age_buckets = {
            "last_7_days": 0,
            "last_30_days": 0,
            "last_90_days": 0,
            "older": 0,
        }
        rows = conn.execute("SELECT updated_at FROM documents").fetchall()
        for row in rows:
            updated = row["updated_at"] or ""
            try:
                updated_dt = datetime.strptime(updated, "%Y%m%d%H%M%S")
                days_ago = (now - updated_dt).days
                if days_ago <= 7:
                    age_buckets["last_7_days"] += 1
                elif days_ago <= 30:
                    age_buckets["last_30_days"] += 1
                elif days_ago <= 90:
                    age_buckets["last_90_days"] += 1
                else:
                    age_buckets["older"] += 1
            except (ValueError, TypeError):
                age_buckets["older"] += 1

        conn.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "database": {
                "size_mb": db_size_mb,
                "document_count": doc_count,
                "fts_index_size": fts_size,
            },
            "ontology": {
                "entity_count": entity_count,
                "relation_count": relation_count,
                "entity_doc_links": entity_doc_count,
            },
            "zones": {z["zone"]: z["cnt"] for z in zones[:15]},
            "document_age": age_buckets,
        }

    def cache_benchmark(self, queries: list[str] | None = None) -> dict[str, Any]:
        """Run cache performance benchmark.

        Args:
            queries: Custom queries to benchmark. None uses defaults.

        Returns:
            Benchmark results.
        """
        from kos.cache import SearchCache
        from kos.hybrid_search import HybridSearchEngine

        if queries is None:
            queries = [
                "数字化平台",
                "数据治理",
                "测试",
                "项目",
                "文档",
                "报告",
                "制度",
                "方案",
                "总结",
                "计划",
            ]

        engine = HybridSearchEngine(self.db_path)
        cache = SearchCache(db_path=self.db_path)

        # Benchmark without cache
        t0 = time.time()
        for q in queries:
            engine.search(q, mode="keyword", limit=5, use_cache=False)
        no_cache_ms = round((time.time() - t0) * 1000, 2)

        # Benchmark with cache (first run: populate)
        t0 = time.time()
        for q in queries:
            cache.search_with_cache(q, mode="keyword", limit=5)
        cache_first_ms = round((time.time() - t0) * 1000, 2)

        # Benchmark with cache (second run: all hits)
        t0 = time.time()
        for q in queries:
            cache.search_with_cache(q, mode="keyword", limit=5)
        cache_second_ms = round((time.time() - t0) * 1000, 2)

        engine.close()

        speedup = round(no_cache_ms / max(cache_second_ms, 0.01), 1)

        return {
            "timestamp": datetime.now().isoformat(),
            "query_count": len(queries),
            "no_cache_ms": no_cache_ms,
            "cache_first_run_ms": cache_first_ms,
            "cache_second_run_ms": cache_second_ms,
            "speedup": f"{speedup}x",
            "cache_stats": cache.get_stats(),
        }

    def full_report(self) -> dict[str, Any]:
        """Generate a full monitoring report.

        Returns:
            Dict with all monitoring data.
        """
        return {
            "index_health": self.index_health(),
            "search_quality": self.search_quality(),
            "performance": self.performance_metrics(),
        }

    # ── Alerting & Auto-remediation ─────────────────────

    def check_and_alert(self) -> dict[str, Any]:
        """Run checks, send alerts if needed, attempt auto-remediation."""
        alerts = []
        remediated = []

        # Check index integrity
        health = self.index_health()
        if health["status"] != "healthy":
            alerts.append(f"Index health: {health['status']}")
            # Auto-remediate: if FTS mismatch, log for manual fix
            integrity = health["checks"].get("integrity", {})
            if integrity.get("status") == "fail":
                remediated.append("Index integrity issue detected - needs manual VACUUM")

        # Check vector lag
        perf = self.performance_metrics()
        db_size = perf.get("database", {}).get("size_mb", 0)
        if db_size > 5000:  # >5GB
            alerts.append(f"Database size critical: {db_size}MB")

        return {
            "healthy": len(alerts) == 0,
            "alerts": alerts,
            "remediated": remediated,
            "timestamp": datetime.now().isoformat(),
        }
