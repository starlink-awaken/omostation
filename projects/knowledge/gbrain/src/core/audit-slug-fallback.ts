/**
 * v0.32.7 CJK wave — slug-fallback audit trail.
 *
 * Writes info-severity rows to `~/.gbrain/audit/slug-fallback-YYYY-Www.jsonl`
 * (ISO-week rotation, mirrors `subagent-audit.ts`). Fired when import-file's
 * empty-path-slug + frontmatter-fallback path resolves a slug that wouldn't
 * otherwise derive from the file path (emoji, Thai, Arabic, etc. filenames
 * whose slugifyPath() returns empty even after the CJK ranges land).
 *
 * Why a separate JSONL instead of `~/.gbrain/sync-failures.jsonl`:
 *   - sync-failures.jsonl carries commit-attribution semantics that gate
 *     bookmark advancement; importFromFile doesn't know the commit.
 *   - Fallback events are informational, NOT failures. Routing them through
 *     the failure surface would force doctor / classifyErrorCode /
 *     acknowledgeSyncFailures to grow a severity tier they weren't designed
 *     for. Codex outside-voice C7 caught this drift.
 *
 * Best-effort writes. Write failures go to stderr but the import continues.
 */

import { z } from 'zod';
import { AppendOnlyLog, ZTimestampSchema } from './append-only-log.ts';
import { isoWeekFilename, resolveAuditDir } from './audit-week-file.ts';

export const SlugFallbackAuditEventSchema = ZTimestampSchema.extend({
  /** Resolved slug (the frontmatter slug that overrode the empty path slug). */
  slug: z.string(),
  /** Repo-relative path that produced an empty slugifyPath(). */
  source_path: z.string(),
  /** Always 'info' — keeps the schema explicit for future severity tiers. */
  severity: z.literal('info'),
  /** Stable code consumed by `gbrain doctor`'s slug_fallback_audit check. */
  code: z.literal('SLUG_FALLBACK_FRONTMATTER'),
});
export type SlugFallbackAuditEvent = z.infer<typeof SlugFallbackAuditEventSchema>;

const slugFallbackLog = (): AppendOnlyLog =>
  new AppendOnlyLog({
    filePath: resolveAuditDir() + '/{YYYY-Www}',
    prefix: 'slug-fallback',
    schema: SlugFallbackAuditEventSchema,
  });

/** ISO-week-rotated filename: `slug-fallback-YYYY-Www.jsonl`. Delegates to
 *  `src/core/audit-week-file.ts`. */
export function computeSlugFallbackAuditFilename(now: Date = new Date()): string {
  return isoWeekFilename('slug-fallback', now);
}

/**
 * Append a slug-fallback event to the current week's audit JSONL.
 *
 * Also emits one stderr line per call for operator visibility (per D7 dual
 * logging). Write failure to the JSONL is logged but does NOT throw — the
 * import succeeds either way.
 */
export function logSlugFallback(slug: string, sourcePath: string): void {
  process.stderr.write(`[gbrain] slug fallback: ${sourcePath} → ${slug} (frontmatter slug; path slugified empty)\n`);
  const event: SlugFallbackAuditEvent = {
    ts: new Date().toISOString(),
    slug,
    source_path: sourcePath,
    severity: 'info',
    code: 'SLUG_FALLBACK_FRONTMATTER',
  };
  try {
    slugFallbackLog().append(event);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[gbrain] slug-fallback audit write failed (${msg}); import continues\n`);
  }
}

/**
 * Read recent (`days` window, default 7) slug-fallback events from the
 * latest week's JSONL. Used by `gbrain doctor`'s slug_fallback_audit check.
 * Missing file / corrupt rows are skipped silently — the audit trail is
 * informational and shouldn't block doctor.
 */
export function readRecentSlugFallbacks(days = 7, now: Date = new Date()): SlugFallbackAuditEvent[] {
  const cutoff = now.getTime() - days * 86400000;
  const out: SlugFallbackAuditEvent[] = [];
  // Walk the current + previous ISO week so a 7-day window straddling
  // Monday-midnight stays covered.
  const prefixes = [
    computeSlugFallbackAuditFilename(now),
    computeSlugFallbackAuditFilename(new Date(now.getTime() - 7 * 86400000)),
  ];
  for (const filename of prefixes) {
    const fullPath = `${resolveAuditDir()}/${filename}`;
    const records = new AppendOnlyLog({
      filePath: fullPath,
      schema: SlugFallbackAuditEventSchema,
    }).readAllSync<SlugFallbackAuditEvent>();
    for (const ev of records) {
      const ts = Date.parse(ev.ts);
      if (Number.isFinite(ts) && ts >= cutoff) out.push(ev);
    }
  }
  return out;
}
