"""OMO 并行扫描模块"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any


@dataclass
class ScanResult:
    path: str
    success: bool
    findings: list[dict[str, Any]]
    errors: list[str]
    duration_seconds: float


class ParallelScanner:
    def __init__(self, max_workers=4):
        self.max_workers = max_workers

    def scan_with_workers(self, paths, scan_func, show_progress=False):
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(self._scan_single, path, scan_func): path
                for path in paths
            }
            for future in as_completed(future_to_path):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(
                        ScanResult(
                            str(future_to_path[future]), False, [], [str(e)], 0.0
                        )
                    )
        return results

    def _scan_single(self, path, scan_func):
        import time

        start_time = time.time()
        try:
            findings = scan_func(path)
            success = True
            errors = []
        except Exception as e:
            findings = []
            errors = [str(e)]
            success = False
        duration = time.time() - start_time
        return ScanResult(str(path), success, findings, errors, duration)

    def aggregate_findings(self, results):
        all_findings = []
        all_errors = []
        total_duration = 0.0
        success_count = 0
        failure_count = 0
        for result in results:
            all_findings.extend(result.findings)
            all_errors.extend(result.errors)
            total_duration += result.duration_seconds
            if result.success:
                success_count += 1
            else:
                failure_count += 1
        return {
            "total_scanned": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "total_findings": len(all_findings),
            "total_errors": len(all_errors),
            "total_duration_seconds": total_duration,
            "findings": all_findings,
            "errors": all_errors,
        }
