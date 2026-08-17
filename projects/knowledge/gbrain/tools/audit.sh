#!/usr/bin/env bash
# gbrain audit.sh — E1 P0 跨仓债 §17 metrics 脚本
#
# 跑 gbrain 仓 §17 健康度评分:
#   1. 扫所有 ~.gbrain/audit/*.jsonl 文件
#   2. 用 AppendOnlyLog.readAllSync 校验每行
#   3. 输出 §17 R0 评分 JSON (与 omo/runtime/kairon/metaos 一致 schema)
#
# R50 P0 + E1 P0 实施: 适配 omo audit-rollout dispatcher 5 仓 → 5 仓

set -euo pipefail

GBRAIN_DIR="${1:-$(git rev-parse --show-toplevel)}"
AUDIT_DIR="${GBRAIN_DIR/#$HOME/~}/.gbrain/audit"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== gbrain 跨仓债审计 (R50 + E1 P0) ==="
echo "GBRAIN_DIR: $GBRAIN_DIR"
echo "AUDIT_DIR:  $AUDIT_DIR"
echo

# 1. gbrain 仓 AppendOnlyLog 入口
echo "1. gbrain AppendOnlyLog 入口"
cd "$GBRAIN_DIR" && bun -e 'import { AppendOnlyLog } from "./src/core/append-only-log.ts"; console.log("  ✅ AppendOnlyLog importable");' 2>&1 | tail -1

# 2. audit JSONL 文件扫描
echo "2. audit JSONL 文件"
jsonl_count=0
if [ -d "$AUDIT_DIR" ]; then
  jsonl_count=$(find "$AUDIT_DIR" -name "*.jsonl" 2>/dev/null | wc -l | tr -d ' ')
fi
echo "  发现 $jsonl_count 个 JSONL 文件"

# 3. §17 健康度评分
echo "3. §17 健康度评分"
cd "$GBRAIN_DIR" && bun -e '
import { AppendOnlyLog, ZTimestampSchema } from "./src/core/append-only-log.ts";
import { readdirSync } from "node:fs";
import { join } from "node:path";

const auditDir = process.env.HOME + "/.gbrain/audit";
let total = 0;
let drift = 0;
let files = [];
try {
  files = readdirSync(auditDir).filter(f => f.endsWith(".jsonl"));
} catch {
  // no audit dir yet — 0 records
}
for (const f of files) {
  const path = join(auditDir, f);
  const log = new AppendOnlyLog({ filePath: path, schema: ZTimestampSchema });
  for (const r of log.readAllSync()) {
    total++;
    if (typeof r !== "object" || r === null || !("ts" in r)) {
      drift++;
    }
  }
}

const density = total > 0 ? drift / total : 0.0;
let grade = "R5";
if (density <= 0.01) grade = "R0";
else if (density <= 0.05) grade = "R1";
else if (density <= 0.10) grade = "R2";
else if (density <= 0.30) grade = "R3";
else if (density <= 0.50) grade = "R4";

console.log(JSON.stringify({
  generated_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
  drift_count: drift,
  total_records: total,
  debt_density: Math.round(density * 1000000) / 1000000,
  health_grade: grade,
}, null, 2));
'

echo
echo "=== 审计完成 ==="
