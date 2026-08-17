/**
 * v0.35.5 — phantom-redirect audit trail.
 *
 * Writes one JSONL row per phantom-redirect decision to
 * `~/.gbrain/audit/phantoms-YYYY-Www.jsonl` (ISO-week rotation, mirrors
 * `audit-slug-fallback.ts`). Records BOTH success ('redirected') and
 * informational skip outcomes ('ambiguous', 'drift', 'no_canonical',
 * 'not_phantom_has_residue', 'pass_skipped_lock_busy') so operators can
 * triage what the autopilot cycle saw without re-running it.
 *
 * Sister surface of `src/core/facts/stub-guard-audit.ts` (different
 * consumer — stub-guard logs PREVENTIVE writes that never made it to
 * disk; phantom-audit logs CLEANUP outcomes for pages already on disk).
 * Keeping them separate means each file has a stable schema and the
 * doctor checks don't need to grow a discriminator.
 *
 * Best-effort writes. Failures emit a stderr line but never throw — a
 * disk-full or audit-dir-permission issue must not stall the cycle.
 */

import { z } from 'zod';
import { AppendOnlyLog, ZTimestampSchema } from '../append-only-log.ts';
import { isoWeekFilename, resolveAuditDir } from '../audit-week-file.ts';

export type PhantomOutcome =
  | 'redirected'
  | 'ambiguous'
  | 'drift'
  | 'no_canonical'
  | 'not_phantom_has_residue'
  | 'pass_skipped_lock_busy';

export const PhantomAuditEventSchema = ZTimestampSchema.extend({
  phantom_slug: z.string().optional(),
  canonical_slug: z.string().optional(),
  outcome: z.enum([
    'redirected',
    'ambiguous',
    'drift',
    'no_canonical',
    'not_phantom_has_residue',
    'pass_skipped_lock_busy',
  ]),
  fact_count: z.number().optional(),
  source_id: z.string(),
  reason: z.string().optional(),
  candidates: z.array(z.object({ slug: z.string(), connection_count: z.number() })).optional(),
});
export interface PhantomAuditEvent extends z.infer<typeof PhantomAuditEventSchema> {}

const phantomLog = (): AppendOnlyLog =>
  new AppendOnlyLog({
    filePath: resolveAuditDir() + '/{YYYY-Www}',
    prefix: 'phantoms',
    schema: PhantomAuditEventSchema,
  });

/** ISO-week-rotated filename: `phantoms-YYYY-Www.jsonl`. Delegates to
 *  `src/core/audit-week-file.ts`. */
export function computePhantomAuditFilename(now: Date = new Date()): string {
  return isoWeekFilename('phantoms', now);
}

/**
 * Append a phantom-redirect event to the current week's audit JSONL.
 *
 * `ts` is stamped at call time (caller-provided overrides honored). Write
 * failure is logged to stderr; the caller's cycle continues either way.
 */
export function logPhantomEvent(event: Omit<PhantomAuditEvent, 'ts'> & { ts?: string }): void {
  const record: PhantomAuditEvent = {
    ts: event.ts ?? new Date().toISOString(),
    outcome: event.outcome,
    source_id: event.source_id,
    ...(event.phantom_slug !== undefined ? { phantom_slug: event.phantom_slug } : {}),
    ...(event.canonical_slug !== undefined ? { canonical_slug: event.canonical_slug } : {}),
    ...(event.fact_count !== undefined ? { fact_count: event.fact_count } : {}),
    ...(event.reason !== undefined ? { reason: event.reason } : {}),
    ...(event.candidates !== undefined ? { candidates: event.candidates } : {}),
  };
  try {
    phantomLog().append(record);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[gbrain] phantom audit write failed (${msg}); cycle continues\n`);
  }
}

/**
 * Read recent phantom-redirect events from the current + previous ISO
 * weeks. Used by future `gbrain doctor` `phantoms_pending` check (T9
 * follow-up) and by tests asserting the audit-write contract.
 *
 * Missing files / corrupt rows are skipped silently — the audit trail is
 * informational and shouldn't block any consumer.
 */
export function readRecentPhantomEvents(days = 7, now: Date = new Date()): PhantomAuditEvent[] {
  const cutoff = now.getTime() - days * 86400000;
  const out: PhantomAuditEvent[] = [];
  const filenames = [
    computePhantomAuditFilename(now),
    computePhantomAuditFilename(new Date(now.getTime() - 7 * 86400000)),
  ];
  for (const filename of filenames) {
    const fullPath = `${resolveAuditDir()}/${filename}`;
    const records = new AppendOnlyLog({
      filePath: fullPath,
      schema: PhantomAuditEventSchema,
    }).readAllSync<PhantomAuditEvent>();
    for (const ev of records) {
      const ts = Date.parse(ev.ts);
      if (Number.isFinite(ts) && ts >= cutoff) out.push(ev);
    }
  }
  return out;
}
