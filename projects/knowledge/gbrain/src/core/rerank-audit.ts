/**
 * v0.35.0.0+ — rerank-failure audit trail.
 *
 * Writes warn-severity rows to `~/.gbrain/audit/rerank-failures-YYYY-Www.jsonl`
 * (ISO-week rotation, mirrors slug-fallback-audit.ts). Fired when
 * `applyReranker` in src/core/search/rerank.ts catches a RerankError from
 * the gateway. Failure is fail-open at the search layer (results pass
 * through in RRF order); the audit row is the cross-process signal that
 * `gbrain doctor reranker_health` reads.
 *
 * Success events are intentionally NOT logged here. Per the plan (CDX2-F22):
 *   1) writing once per tokenmax search is hot-path I/O churn — the
 *      slug-fallback pattern is rare-event-only.
 *   2) success events leak query volume + timing into a local audit file
 *      that previously held only failures.
 * The doctor check reads `search.reranker.enabled` first to interpret
 * "no events in window" correctly (enabled + no events = healthy;
 * disabled = no failures expected).
 *
 * Best-effort writes. Write failures go to stderr but search continues.
 */

import { z } from 'zod';
import { AppendOnlyLog, ZTimestampSchema } from './append-only-log.ts';
import { resolveAuditDir } from './minions/handlers/shell-audit.ts';

/** Stable error-classification union; matches RerankError.reason. */
export type RerankFailureReason =
  | 'auth'
  | 'rate_limit'
  | 'network'
  | 'timeout'
  | 'payload_too_large'
  | 'unknown';

export const RerankFailureEventSchema = ZTimestampSchema.extend({
  /** Provider:model — e.g. `'zeroentropyai:zerank-2'`. */
  model: z.string(),
  /** Classified failure mode (see RerankFailureReason). */
  reason: z.enum(['auth', 'rate_limit', 'network', 'timeout', 'payload_too_large', 'unknown']),
  /** SHA-256 prefix of the rerank query (8 hex chars). Privacy: never log
   *  query text. Lets doctor dedupe repeat failures on the same query. */
  query_hash: z.string(),
  /** Number of documents that were being reranked when failure fired. */
  doc_count: z.number(),
  /**
   * Truncated upstream error message (first 200 chars). Useful for
   * diagnosing flaky providers without leaking PII; query text is hashed
   * separately so this string never carries it.
   */
  error_summary: z.string(),
  /** Always 'warn' — matches RerankError's "all failures degrade UX". */
  severity: z.literal('warn'),
});
export interface RerankFailureEvent extends z.infer<typeof RerankFailureEventSchema> {}

const rerankLog = (): AppendOnlyLog =>
  new AppendOnlyLog({
    filePath: resolveAuditDir() + '/{YYYY-Www}',
    prefix: 'rerank-failures',
    schema: RerankFailureEventSchema,
  });

/** ISO-week-rotated filename: `rerank-failures-YYYY-Www.jsonl`. */
export function computeRerankAuditFilename(now: Date = new Date()): string {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const dayNum = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - dayNum + 3);
  const isoYear = d.getUTCFullYear();
  const firstThursday = new Date(Date.UTC(isoYear, 0, 4));
  const firstThursdayDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstThursdayDayNum + 3);
  const weekNum = Math.round((d.getTime() - firstThursday.getTime()) / (7 * 86400000)) + 1;
  const ww = String(weekNum).padStart(2, '0');
  return `rerank-failures-${isoYear}-W${ww}.jsonl`;
}

/**
 * Truncate a string for audit logging. Plain length cut — error messages
 * from the gateway are already free of caller-controlled prefixes.
 */
function truncateErrorSummary(msg: string, max = 200): string {
  if (msg.length <= max) return msg;
  return msg.slice(0, max - 1) + '…';
}

/**
 * Append a rerank-failure event. Best-effort: write failure logs to stderr
 * but never throws.
 */
export function logRerankFailure(event: Omit<RerankFailureEvent, 'ts' | 'severity'>): void {
  const row: RerankFailureEvent = {
    ts: new Date().toISOString(),
    severity: 'warn',
    ...event,
    error_summary: truncateErrorSummary(event.error_summary),
  };
  try {
    rerankLog().append(row);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[gbrain] rerank-failure audit write failed (${msg}); search continues\n`);
  }
}

/**
 * Read recent (`days` window, default 7) rerank-failure events. Used by
 * `gbrain doctor`'s `reranker_health` check. Missing file / corrupt rows
 * are skipped silently — the audit trail is informational.
 */
export function readRecentRerankFailures(days = 7, now: Date = new Date()): RerankFailureEvent[] {
  const cutoff = now.getTime() - days * 86400000;
  const out: RerankFailureEvent[] = [];
  // Walk the current + previous ISO week so a 7-day window straddling
  // Monday-midnight stays covered.
  const filenames = [
    computeRerankAuditFilename(now),
    computeRerankAuditFilename(new Date(now.getTime() - 7 * 86400000)),
  ];
  for (const filename of filenames) {
    const fullPath = `${resolveAuditDir()}/${filename}`;
    const records = new AppendOnlyLog({
      filePath: fullPath,
      schema: RerankFailureEventSchema,
    }).readAllSync<RerankFailureEvent>();
    for (const ev of records) {
      const ts = Date.parse(ev.ts);
      if (Number.isFinite(ts) && ts >= cutoff) out.push(ev);
    }
  }
  return out;
}
