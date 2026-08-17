import type { BrainEngine } from './engine.ts';
import type { Migration } from './migrate/types.ts';
import { MIGRATIONS_EARLY } from './migrate/migrations-early.ts';
import { MIGRATIONS_MID1 } from './migrate/migrations-mid1.ts';
import { MIGRATIONS_MID2 } from './migrate/migrations-mid2.ts';
import { MIGRATIONS_LATE } from './migrate/migrations-late.ts';

/**
 * Schema migrations — run automatically on initSchema().
 *
 * Each migration is a version number + idempotent SQL. Migrations are embedded
 * as string constants (Bun's --compile strips the filesystem).
 *
 * Each migration runs in a transaction: if the SQL fails, the version stays
 * where it was and the next run retries cleanly.
 *
 * Migrations can also include a handler function for application-level logic
 * (e.g., data transformations that need TypeScript, not just SQL).
 */


/**
 * Resolve idempotent classification with the v0.30.1 default. Used by the
 * migration runner's verify path and by the twice-run safety test
 * (test/migrate-idempotent-classify.test.ts).
 */
export function isMigrationIdempotent(m: Migration): boolean {
  // Default true: existing migrations were authored as idempotent (every
  // CREATE/ALTER uses IF NOT EXISTS guards). Explicit false opts out.
  return m.idempotent !== false;
}

/**
 * Migration drift error — verify hook failed and migration is non-idempotent.
 * Caller surfaces the column/table names that diverged and requires
 * `--skip-verify` to force re-run.
 */
export class MigrationDriftError extends Error {
  constructor(
    public readonly version: number,
    public readonly migrationName: string,
    public readonly hint: string,
  ) {
    super(`Migration v${version} (${migrationName}) verify failed: ${hint}`);
    this.name = 'MigrationDriftError';
  }
}

/**
 * Retry-exhausted envelope (v0.30.1 / Finding F2). Surface the most recent
 * idle blockers we observed so the user has a paste-ready
 * pg_terminate_backend(<pid>) command.
 */
export class MigrationRetryExhausted extends Error {
  constructor(
    public readonly version: number,
    public readonly migrationName: string,
    public readonly attempts: number,
    public readonly lastBlockers: IdleBlocker[],
    public readonly lastError: Error,
  ) {
    const lastB = lastBlockers[0];
    const hint = lastB
      ? `PID ${lastB.pid} idle since ${lastB.query_start} likely holds the lock; run: psql ... -c "SELECT pg_terminate_backend(${lastB.pid})"`
      : 'No idle-in-transaction blockers detected; check pg_locks for active waiters and ~/.gbrain/audit/connection-events-*.jsonl';
    super(
      `Migration v${version} (${migrationName}) failed after ${attempts} attempts. ${hint}. Original: ${lastError.message}`
    );
    this.name = 'MigrationRetryExhausted';
  }
}

// Migrations are embedded here, not loaded from files.
// Add new migrations at the end. Never modify existing ones.
// Exported for tests that structurally assert migration contents (e.g., "v9 must
// pre-create idx_timeline_dedup_helper before the DELETE..."). Read-only contract.
export const MIGRATIONS: Migration[] = [
  ...MIGRATIONS_EARLY,
  ...MIGRATIONS_MID1,
  ...MIGRATIONS_MID2,
  ...MIGRATIONS_LATE,
];

export const LATEST_VERSION = MIGRATIONS.length > 0
  ? Math.max(...MIGRATIONS.map(m => m.version))
  : 1;

/**
 * Row returned by `getIdleBlockers`. The shape is the public contract
 * for both `gbrain doctor --locks` output and the internal DDL pre-flight.
 */
export interface IdleBlocker {
  pid: number;
  state: string;
  query_start: string;
  query: string;
}

/**
 * Find idle-in-transaction connections older than 5 minutes that might
 * block DDL. Postgres-only. Returns `[]` on PGLite, query failure, or
 * no blockers. The query-failure path is intentionally silent because
 * some managed Postgres configs restrict `pg_stat_activity` — a partial
 * view of the server is still useful for doctor/pre-flight.
 *
 * Single source of truth shared by:
 *   - `checkForBlockingConnections` (DDL pre-flight warning)
 *   - `gbrain doctor --locks` (CLI diagnostic)
 *   - any future `--exclusive` drain-wait logic
 */
export async function getIdleBlockers(engine: BrainEngine): Promise<IdleBlocker[]> {
  if (engine.kind !== 'postgres') return [];
  try {
    return await engine.executeRaw<IdleBlocker>(
      `SELECT pid, state, query_start::text, substring(query, 1, 120) as query
       FROM pg_stat_activity
       WHERE state = 'idle in transaction'
         AND query_start < NOW() - INTERVAL '5 minutes'
         AND pid != pg_backend_pid()`
    );
  } catch {
    return [];
  }
}

/**
 * Check for idle-in-transaction connections that might block DDL.
 * Returns true if blockers were found (logged as warnings).
 */
async function checkForBlockingConnections(engine: BrainEngine): Promise<boolean> {
  const rows = await getIdleBlockers(engine);
  if (rows.length > 0) {
    console.warn(`\n⚠️  Found ${rows.length} idle-in-transaction connection(s) older than 5 minutes:`);
    for (const r of rows) {
      console.warn(`  PID ${r.pid} — idle since ${r.query_start}`);
      console.warn(`    Query: ${r.query}`);
    }
    console.warn(`  These may block ALTER TABLE DDL. To kill: SELECT pg_terminate_backend(<pid>);\n`);
    return true;
  }
  return false;
}

/**
 * v0.30.1 (Cherry D3 / Finding F2): wrap a migration attempt in 3-attempt
 * retry+backoff (5s/15s/45s). Retry only on statement_timeout (57014) or
 * connection-reset patterns; other errors fail loud immediately.
 *
 * Before each retry: log idle-in-transaction blockers so the user knows
 * which PID is holding the lock. After exhaustion: throw
 * `MigrationRetryExhausted` with the named PID + suggested
 * pg_terminate_backend command.
 */
async function runMigrationSQLWithRetry(
  engine: BrainEngine,
  m: Migration,
  sql: string,
): Promise<void> {
  const { isStatementTimeoutError, isRetryableConnError } = await import('./retry-matcher.ts');
  // GBRAIN_MIGRATE_BACKOFF_MS lets tests skip the 5s/15s/45s backoff. In
  // production the env var is unset and the default cadence applies.
  const fastBackoff = process.env.GBRAIN_MIGRATE_BACKOFF_MS;
  const backoffs = fastBackoff !== undefined
    ? [parseInt(fastBackoff, 10) || 0, parseInt(fastBackoff, 10) || 0, parseInt(fastBackoff, 10) || 0]
    : [5000, 15000, 45000];
  let lastErr: Error | null = null;
  let lastBlockers: IdleBlocker[] = [];

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      // Pre-attempt diagnostic: if there are idle blockers, log them so
      // the operator can see what we're racing against. Cherry D3.
      if (attempt > 0) {
        lastBlockers = await getIdleBlockers(engine);
        if (lastBlockers.length > 0) {
          console.warn(`  [retry ${attempt}/3] ${lastBlockers.length} idle-in-transaction blocker(s):`);
          for (const b of lastBlockers) {
            console.warn(`    PID ${b.pid} idle since ${b.query_start} — ${b.query.slice(0, 80)}`);
          }
        }
      }
      await runMigrationSQL(engine, m, sql);
      return;
    } catch (err: unknown) {
      lastErr = err instanceof Error ? err : new Error(String(err));
      const retryable = isStatementTimeoutError(err) || isRetryableConnError(err);
      if (!retryable || attempt === 2) {
        // Final failure: capture blockers + throw enriched envelope when
        // retry-eligible (named-PID UX from F2). Non-retryable errors fall
        // through to the existing 57014 handler in runMigrations.
        if (retryable) {
          lastBlockers = await getIdleBlockers(engine);
          throw new MigrationRetryExhausted(m.version, m.name, attempt + 1, lastBlockers, lastErr);
        }
        throw err;
      }
      const delay = backoffs[attempt];
      console.warn(`  [retry ${attempt + 1}/3] ${m.name} hit ${lastErr.message.slice(0, 80)}; retrying in ${delay}ms`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  // Defensive: shouldn't reach here.
  if (lastErr) throw lastErr;
}

/**
 * Wrap migration SQL execution with Supabase-compatible timeout.
 * Uses SET LOCAL statement_timeout inside a transaction to override
 * server-enforced timeouts (required for Supabase Postgres).
 */
async function runMigrationSQL(
  engine: BrainEngine,
  m: Migration,
  sql: string,
): Promise<void> {
  const useTransaction = m.transaction !== false;

  if (useTransaction || engine.kind === 'pglite') {
    // Wrap in transaction with extended timeout for Supabase compatibility.
    // SET LOCAL scopes the timeout to this transaction only.
    await engine.transaction(async (tx) => {
      if (engine.kind === 'postgres') {
        try {
          await tx.runMigration(m.version, "SET LOCAL statement_timeout = '600000'");
        } catch {
          // Non-fatal: PGLite or older Postgres versions may not support this
        }
      }
      await tx.runMigration(m.version, sql);
    });
  } else {
    // Postgres + transaction:false → can't use SET LOCAL (needs a txn),
    // can't use plain SET on the pooled connection (leaks to other
    // queries). Instead: reserve a dedicated backend, set session-level
    // statement_timeout on just that connection, run the DDL there.
    //
    // On Supabase (both PgBouncer 6543 and direct 5432) a server-level
    // statement_timeout of ~2 min is enforced. Without this override a
    // CREATE INDEX CONCURRENTLY on a large table (e.g. 500K pages) hits
    // the timeout and aborts. SET on the reserved connection cleanly
    // overrides because the GUC scope is connection-local (session-scope
    // is fine when nobody else uses the connection).
    //
    // The reserved-connection primitive is new in PR #356. See
    // BrainEngine.withReservedConnection.
    await engine.withReservedConnection(async (conn) => {
      try {
        await conn.executeRaw("SET statement_timeout = '600000'");
      } catch {
        // Non-fatal: some managed Postgres may restrict this GUC.
        // Falling through means the DDL runs with the server default.
      }
      await conn.executeRaw(sql);
    });
  }
}

/**
 * Cheap probe: does this engine have schema migrations pending?
 *
 * Reads the `version` config row in a single round-trip (no schema replay,
 * no migration apply). Used by `connectEngine` to gate `initSchema()` so
 * short-lived CLI invocations on already-migrated brains don't pay the
 * full bootstrap-probe + SCHEMA_SQL replay + ledger-check cost on every
 * `gbrain stats` / `gbrain query` / `gbrain doctor`.
 *
 * Defensive: treats a getConfig failure (config table missing, query error)
 * as "yes pending" so the caller falls through to the full initSchema path.
 * Worst case on a wedged brain is one extra schema replay — same as before.
 *
 * Closes #651 in cooperation with the post-upgrade auto-apply hook (X1)
 * without the perf cost #652 would have introduced on every CLI call.
 */
export async function hasPendingMigrations(engine: BrainEngine): Promise<boolean> {
  try {
    const currentStr = await engine.getConfig('version');
    const current = parseInt(currentStr || '1', 10);
    return current < LATEST_VERSION;
  } catch {
    return true;
  }
}

export async function runMigrations(engine: BrainEngine): Promise<{ applied: number; current: number }> {
  const currentStr = await engine.getConfig('version');
  const current = parseInt(currentStr || '1', 10);

  // Sort by version ascending so array insertion order doesn't affect
  // correctness. Migrations MUST run in version order; if v16 accidentally
  // precedes v15 in MIGRATIONS, setConfig(version, 16) would cause v15 to
  // be skipped on the next iteration.
  const sorted = [...MIGRATIONS].sort((a, b) => a.version - b.version);

  const pending = sorted.filter(m => m.version > current);
  if (pending.length === 0) {
    return { applied: 0, current };
  }

  console.log(`  Schema version ${current} → ${LATEST_VERSION} (${pending.length} migration(s) pending)`);

  // Pre-flight: warn about connections that might block DDL
  await checkForBlockingConnections(engine);

  let applied = 0;
  for (const m of pending) {
    console.log(`  [${m.version}] ${m.name}...`);

    // Pick SQL: engine-specific `sqlFor` wins over engine-agnostic `sql`.
    const sql = m.sqlFor?.[engine.kind] ?? m.sql;

    if (sql) {
      try {
        // v0.30.1: retry wrapper handles statement_timeout + conn-reset
        // across 3 attempts (5s/15s/45s). Other errors throw immediately.
        await runMigrationSQLWithRetry(engine, m, sql);
      } catch (err: unknown) {
        // Actionable diagnostics for statement timeout (Postgres error 57014).
        // Shape matches the 4-part error standard (what / why / fix / verify).
        const code = (err as { code?: string })?.code;
        if (code === '57014' || err instanceof MigrationRetryExhausted) {
          console.error(`\n❌ Migration ${m.version} (${m.name}) ${err instanceof MigrationRetryExhausted ? 'exhausted retries' : 'hit statement_timeout (SQLSTATE 57014)'}.`);
          if (err instanceof MigrationRetryExhausted && err.lastBlockers.length > 0) {
            const b = err.lastBlockers[0];
            console.error('');
            console.error(`   Likely blocker: PID ${b.pid}, idle since ${b.query_start}`);
            console.error(`   Query: ${b.query.slice(0, 120)}`);
            console.error('');
            console.error(`   Recovery: psql ... -c "SELECT pg_terminate_backend(${b.pid})"`);
            console.error('');
          } else {
            console.error('');
            console.error('   Cause: another connection holds a lock on the target table, or the');
            console.error('   server statement_timeout (~2 min on Supabase) is too short for this DDL.');
            console.error('');
            console.error('   Fix:');
            console.error('     1. gbrain doctor --locks    # find idle-in-transaction blockers');
            console.error('     2. Terminate blocker(s) shown by step 1 via pg_terminate_backend(<pid>)');
            console.error('     3. gbrain apply-migrations --yes  # re-run from the version that failed');
            console.error('');
          }
          console.error('   Verify:');
          console.error('     gbrain doctor              # schema_version should match latest');
          console.error('');
        }
        throw err;
      }
    }

    // Application-level handler (runs outside transaction for flexibility)
    if (m.handler) {
      await m.handler(engine);
    }

    // v0.30.1 (D6): post-condition probe. If a verify hook is declared, run
    // it before bumping config.version. When verify returns false, check
    // idempotent — if true, log + retry the same migration once; if false,
    // throw MigrationDriftError so operator runs --skip-verify deliberately.
    if (m.verify) {
      const verifyOk = await m.verify(engine).catch(() => false);
      if (!verifyOk) {
        const idempotent = isMigrationIdempotent(m);
        if (idempotent) {
          console.warn(`  [${m.version}] ⚠️  verify failed; re-running idempotent migration once`);
          if (sql) await runMigrationSQLWithRetry(engine, m, sql);
          if (m.handler) await m.handler(engine);
          // Best-effort: don't double-throw if second run still fails verify.
          // Operator's next run of doctor will re-detect drift.
        } else {
          throw new MigrationDriftError(
            m.version,
            m.name,
            `Schema does not match expected post-condition. Run with --skip-verify to force.`,
          );
        }
      }
    }

    // Update version after both SQL and handler succeed
    await engine.setConfig('version', String(m.version));
    console.log(`  [${m.version}] ✓ ${m.name}`);
    applied++;
  }

  return { applied, current: LATEST_VERSION };
}
