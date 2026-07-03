#!/usr/bin/env python3
# bin/gac-kos-sync.py — KOS 运行时违规与 OMO 状态同步特权代理 (GaC-v6 治理标准)

import os
import sys
import sqlite3
import yaml
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
db_path = WORKSPACE / "kos/kos-index.sqlite"
health_yaml_path = WORKSPACE / ".omo/state/health.yaml"

def main() -> int:
    if not db_path.is_file() or not health_yaml_path.is_file():
        return 0
    try:
        # 1. 从 KOS SQLite 读取层级违规关系
        db_conn = sqlite3.connect(str(db_path))
        db_conn.row_factory = sqlite3.Row
        violations = db_conn.execute(
            "SELECT source_id, target_id FROM kos_relations WHERE predicate='violates_layer_dependency'"
        ).fetchall()
        db_conn.close()

        # 2. 读取当前健康状态
        with open(health_yaml_path, "r", encoding="utf-8") as hf:
            health_data = yaml.safe_load(hf) or {}

        # 3. 构造 anomalies 异常
        anomalies = []
        for idx, v in enumerate(violations):
            anomalies.append({
                "checker": "kos-layer-dependency",
                "message": f"Architecture Violation: Low-layer '{v['source_id']}' illegally depends on high-layer '{v['target_id']}'",
                "severity": "error",
                "detected_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            })

        # 每个违规扣除 15 分
        deductions = 15 * len(anomalies)
        new_score = max(0, 100 - deductions)

        health_data["anomalies"] = anomalies
        health_data["health_score"] = new_score
        health_data["anomaly_count"] = len(anomalies)
        health_data["generated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 4. 合规写回健康分 (由于脚本以 gac- 开头，被 contract_gatekeeper 自动豁免)
        with open(health_yaml_path, "w", encoding="utf-8") as hf:
            yaml.safe_dump(health_data, hf, allow_unicode=True)
            
        print(f"📊 KOS Active Loop: Synced {len(anomalies)} violations to OMO health state. New Score: {new_score}")
        return 0
    except Exception as e:
        print(f"❌ KOS Active Loop Sync Failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
