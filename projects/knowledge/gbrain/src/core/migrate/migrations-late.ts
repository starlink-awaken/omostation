import type { Migration, BrainEngine } from './types.ts';

// MIGRATIONS_LATE v64-v86 (auto-extracted F7114ABA Wave 2 3/7).
export const MIGRATIONS_LATE: Migration[] = [
  {
    version: 64,
    name: 'oauth_clients_source_id_fk_restrict',
    // v0.34.1 (#876): flip the source_id FK from ON DELETE SET NULL (v60
    // posture) to ON DELETE RESTRICT now that federated_read provides
    // the alternative scope-loss path. Pre-fix, deleting a source could
    // silently widen any oauth_client to super-reader (source_id → NULL).
    // Post-flip, source delete is refused if any client references it;
    // the operator's path is "revoke or re-scope the clients first."
    idempotent: true,
    sql: `
      DO $$
      BEGIN
        IF EXISTS (
          SELECT 1 FROM pg_constraint
          WHERE conname = 'oauth_clients_source_id_fkey'
        ) THEN
          ALTER TABLE oauth_clients DROP CONSTRAINT oauth_clients_source_id_fkey;
        END IF;
        ALTER TABLE oauth_clients
          ADD CONSTRAINT oauth_clients_source_id_fkey
          FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT;
      END $$;
    `,
  },
  {
    version: 65,
    name: 'oauth_clients_federated_read_gin_index',
    // v0.34.1 (#876): GIN index for array-containment lookups
    // (`WHERE p.source_id = ANY(federated_read)` and similar). The five
    // read-side ops fall back to scalar sourceId when no auth is set, so
    // this index only matters under load on federated-scoped clients.
    idempotent: true,
    sql: `
      CREATE INDEX IF NOT EXISTS idx_oauth_clients_federated_read
        ON oauth_clients USING GIN (federated_read);
    `,
  },
  {
    version: 78,
    name: 'embedding_multimodal_column',
    // D20 Phase 3: add the unified-multimodal vector column to content_chunks.
    //
    // Column-only migration — the HNSW partial index is built AFTER the first
    // bulk reindex completes (via `gbrain reindex --multimodal --build-index`
    // or auto-built at completion). pgvector docs explicitly note that HNSW
    // build is faster after data load, and per-row index maintenance during
    // bulk reindex would slow the operation 2-3x.
    //
    // Operator class will be vector_cosine_ops to match the existing
    // embedding_image index for ranking parity.
    //
    // The column ships at 1024 dims to match Voyage multimodal-3 output.
    // Operators wanting a different dim (Cohere multimodal at 1408d, etc.)
    // need a column rebuild — surfaced by the `multimodal_column_dim_match`
    // doctor check (D20 model+dim pin).
    idempotent: true,
    sql: `
      ALTER TABLE content_chunks ADD COLUMN IF NOT EXISTS embedding_multimodal vector(1024);
    `,
    sqlFor: {
      pglite: `
        ALTER TABLE content_chunks ADD COLUMN IF NOT EXISTS embedding_multimodal vector(1024);
      `,
    },
  },
  {
    version: 77,
    name: 'mcp_spend_log',
    // D23-#6: per-OAuth-client paid-API spend tracking. search_by_image
    // (Phase 2 of cross-modal wave) makes paid Voyage calls on behalf of
    // remote OAuth clients. The existing v0.22.7 limiter caps requests/min
    // but not spend. A 100-req/min attacker can burn ~$3/hour at Voyage
    // rates. This table aggregates spend so the daily-budget check can
    // refuse new calls when a client crosses
    // search.image_query.daily_budget_usd_per_client (default $5).
    //
    // Indexed for the hot read: (client_id, day) lookup, summed.
    // Row count is bounded by O(clients × days) — tiny.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS mcp_spend_log (
        id SERIAL PRIMARY KEY,
        client_id TEXT,
        token_name TEXT,
        operation TEXT NOT NULL,
        spend_cents NUMERIC(12, 4) NOT NULL DEFAULT 0,
        provider TEXT,
        model TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      -- BTREE on (client_id, created_at) covers the per-day rollup query
      -- (SELECT SUM ... WHERE client_id = $ AND created_at >= today_start) via
      -- range scan on created_at. date_trunc in an index expression would
      -- require IMMUTABLE — TIMESTAMPTZ truncation depends on session timezone.
      CREATE INDEX IF NOT EXISTS idx_mcp_spend_log_client_time
        ON mcp_spend_log (client_id, created_at);
      CREATE INDEX IF NOT EXISTS idx_mcp_spend_log_token_time
        ON mcp_spend_log (token_name, created_at);
    `,
    sqlFor: {
      pglite: `
        CREATE TABLE IF NOT EXISTS mcp_spend_log (
          id SERIAL PRIMARY KEY,
          client_id TEXT,
          token_name TEXT,
          operation TEXT NOT NULL,
          spend_cents NUMERIC(12, 4) NOT NULL DEFAULT 0,
          provider TEXT,
          model TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_mcp_spend_log_client_time
          ON mcp_spend_log (client_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_mcp_spend_log_token_time
          ON mcp_spend_log (token_name, created_at);
      `,
    },
  },
  {
    version: 66,
    name: 'embed_stale_partial_index',
    // Renumbered v58→v59→v60→v66 across merge waves:
    //   - v58 was taken by master's v0.33.3 edges_backfilled_at.
    //   - v59 was taken by master's v0.34.0 code_traversal_cache.
    //   - v60-v65 were taken by master's v0.34.1 oauth_clients source-isolation cluster.
    // All landed before this branch could ship.
    //
    // Partial index for `embedding IS NULL` on content_chunks.
    //
    // The `embed --stale` command scans for chunks missing embeddings.
    // Without this index, the query does a full table scan of 300K+ rows
    // to find the ~48K NULLs, taking >2 min and hitting Supabase's
    // statement_timeout. With the partial index, the scan is instant.
    //
    // Also used by countStaleChunks() for the pre-flight check.
    //
    // Engine-aware via handler (mirrors v14): Postgres uses
    // CREATE INDEX CONCURRENTLY to avoid the ShareLock on `content_chunks`
    // that a plain CREATE INDEX takes for the duration of the build.
    // On a 373K-row table this lock blocks every concurrent write (sync,
    // embed, autopilot). CONCURRENTLY refuses to run inside a transaction
    // AND postgres.js's multi-statement `.unsafe()` wraps in an implicit
    // transaction, so each statement runs as a separate call. A failed
    // CONCURRENTLY leaves an invalid index with the target name; the
    // handler pre-drops any invalid remnant via pg_index.indisvalid.
    // PGLite has no concurrent writers, so plain CREATE is safe.
    idempotent: true,
    sql: '',
    handler: async (engine) => {
      if (engine.kind === 'postgres') {
        await engine.runMigration(
          66,
          `DO $$ BEGIN
             IF EXISTS (
               SELECT 1 FROM pg_index i
               JOIN pg_class c ON c.oid = i.indexrelid
               WHERE c.relname = 'idx_chunks_embedding_null' AND NOT i.indisvalid
             ) THEN
               EXECUTE 'DROP INDEX CONCURRENTLY IF EXISTS idx_chunks_embedding_null';
             END IF;
           END $$;`
        );
        await engine.runMigration(
          66,
          `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_null
             ON content_chunks (page_id, chunk_index)
             WHERE embedding IS NULL;`
        );
      } else {
        await engine.runMigration(
          66,
          `CREATE INDEX IF NOT EXISTS idx_chunks_embedding_null
             ON content_chunks (page_id, chunk_index)
             WHERE embedding IS NULL;`
        );
      }
    },
  },
  {
    version: 67,
    name: 'facts_typed_claim_columns',
    // v0.35.4 — typed-claim columns for trajectory queries.
    //
    // Adds four optional columns to `facts` so metric assertions like
    // "$50K MRR" can be stored as (claim_metric=mrr, claim_value=50000,
    // claim_unit=USD, claim_period=monthly) and queried chronologically
    // by `gbrain eval trajectory` + the `find_trajectory` MCP op.
    //
    // All columns nullable: existing fence rows persist identically.
    // The partial index covers only metric-bearing rows and stays
    // zero-byte until the v0.35.4 extraction path (`src/core/facts/extract.ts`)
    // starts emitting typed fields, so this migration is metadata-only
    // on both engines.
    //
    // See plan: ~/.claude/plans/system-instruction-you-are-working-curious-jellyfish.md
    // Locked decisions D1 (inline extension), D-CDX-7 (v66→v67 renumber).
    idempotent: true,
    sql: `
      ALTER TABLE facts
        ADD COLUMN IF NOT EXISTS claim_metric  TEXT,
        ADD COLUMN IF NOT EXISTS claim_value   DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS claim_unit    TEXT,
        ADD COLUMN IF NOT EXISTS claim_period  TEXT;

      CREATE INDEX IF NOT EXISTS facts_typed_claim_idx
        ON facts (entity_slug, claim_metric, valid_from)
        WHERE claim_metric IS NOT NULL;
    `,
  },
  {
    version: 68,
    name: 'calibration_profiles_v0_36',
    // v0.36.1.0 — Hindsight calibration wave. Per-holder profile rows
    // aggregating TakesScorecard data into qualitative pattern statements.
    //
    // Schema design (from plan D17/D18):
    //   - source_id is REQUIRED — every read routes through sourceScopeOpts(ctx)
    //     so we can never leak a profile across the v0.34.1 source-isolation
    //     boundary. FK to sources(id) with CASCADE so source deletion cleans
    //     up the per-source profile.
    //   - wave_version stamps every row so `gbrain calibration --undo-wave
    //     v0.36.1.0` can reverse just this wave's writes.
    //   - published BOOL gates E8 team-brain mount sharing (D15 asymmetric
    //     opt-in). Default false: nothing leaks until owner explicitly publishes.
    //   - grade_completion REAL [0..1]: fraction of unresolved takes the
    //     grade_takes phase actually processed before its budget cap fired
    //     (F1 fix — dashboard shows "60% graded" badge instead of silently
    //     reading stale data).
    //   - voice_gate_passed + voice_gate_attempts: D11 audit columns. When
    //     passed=false the row uses the template-fallback narrative and
    //     surfaces for review.
    //   - judge_model_agreement REAL: ensemble agreement on profile
    //     generation itself (E2 applied to the meta-step).
    //   - active_bias_tags TEXT[] with GIN index: E3 (calibration-aware
    //     contradictions) joins on this; E7 (nudges) matches new takes against it.
    //
    // PGLite parity: identical DDL works since PGLite ships GIN.
    // Idempotent across both engines.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS calibration_profiles (
        id                      BIGSERIAL PRIMARY KEY,
        source_id               TEXT         NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        holder                  TEXT         NOT NULL,
        wave_version            TEXT         NOT NULL DEFAULT 'v0.36.1.0',
        generated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
        published               BOOLEAN      NOT NULL DEFAULT false,
        total_resolved          INTEGER      NOT NULL,
        brier                   REAL,
        accuracy                REAL,
        partial_rate            REAL,
        grade_completion        REAL         NOT NULL DEFAULT 1.0,
        domain_scorecards       JSONB        NOT NULL,
        pattern_statements      TEXT[]       NOT NULL,
        voice_gate_passed       BOOLEAN      NOT NULL,
        voice_gate_attempts     SMALLINT     NOT NULL,
        active_bias_tags        TEXT[]       NOT NULL,
        model_id                TEXT         NOT NULL,
        cost_usd                NUMERIC(10,4),
        judge_model_agreement   REAL
      );
      CREATE INDEX IF NOT EXISTS calibration_profiles_holder_recent_idx
        ON calibration_profiles (source_id, holder, generated_at DESC);
      CREATE INDEX IF NOT EXISTS calibration_profiles_bias_tags_gin
        ON calibration_profiles USING GIN (active_bias_tags);
      CREATE INDEX IF NOT EXISTS calibration_profiles_published_idx
        ON calibration_profiles (source_id, published, holder)
        WHERE published = true;
    `,
  },
  {
    version: 69,
    name: 'take_proposals_v0_36',
    // v0.36.1.0 — propose_takes phase queue.
    //
    // Schema design:
    //   - (source_id, page_slug, content_hash, prompt_version) is the
    //     idempotency cache (mirrors dream_verdicts in v0.23 synthesize).
    //     Without this, every propose_takes cycle re-spends LLM tokens on
    //     unchanged pages.
    //   - dedup_against_fence_rows JSONB (F2 fix): records the fence state
    //     at proposal time so we can audit "did the LLM see the existing
    //     fence rows when it proposed?" Prevents duplicate proposals.
    //   - proposal_run_id (CDX-4 fix): groups proposals from a single
    //     `gbrain dream --phase propose_takes` run so --rollback <run_id>
    //     can bulk-reject a bad-prompt run.
    //   - predicted_brier + predicted_brier_bucket_n (E5): forecast computed
    //     at proposal time so the queue UX shows "your historical Brier in
    //     this bucket is 0.31" without recomputing.
    //   - status enum guards against undefined states.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS take_proposals (
        id                          BIGSERIAL PRIMARY KEY,
        source_id                   TEXT         NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        page_slug                   TEXT         NOT NULL,
        content_hash                TEXT         NOT NULL,
        prompt_version              TEXT         NOT NULL,
        wave_version                TEXT         NOT NULL DEFAULT 'v0.36.1.0',
        proposed_at                 TIMESTAMPTZ  NOT NULL DEFAULT now(),
        proposal_run_id             TEXT         NOT NULL,
        status                      TEXT         NOT NULL DEFAULT 'pending'
                                                 CHECK (status IN ('pending','accepted','rejected','superseded')),
        claim_text                  TEXT         NOT NULL,
        kind                        TEXT         NOT NULL,
        holder                      TEXT         NOT NULL,
        weight                      REAL         NOT NULL,
        domain                      TEXT,
        dedup_against_fence_rows    JSONB,
        model_id                    TEXT         NOT NULL,
        acted_at                    TIMESTAMPTZ,
        acted_by                    TEXT,
        promoted_row_num            INTEGER,
        predicted_brier             REAL,
        predicted_brier_bucket_n    INTEGER
      );
      CREATE UNIQUE INDEX IF NOT EXISTS take_proposals_idempotency_idx
        ON take_proposals (source_id, page_slug, content_hash, prompt_version);
      CREATE INDEX IF NOT EXISTS take_proposals_pending_idx
        ON take_proposals (source_id, status, proposed_at DESC)
        WHERE status = 'pending';
      CREATE INDEX IF NOT EXISTS take_proposals_run_id_idx
        ON take_proposals (proposal_run_id);
    `,
  },
  {
    version: 70,
    name: 'take_grade_cache_v0_36',
    // v0.36.1.0 — grade_takes verdict cache.
    //
    // Mirrors eval_contradictions_cache (v52) pattern:
    //   - Composite primary key (take_id, prompt_version, judge_model_id,
    //     evidence_signature) — prompt edits OR evidence-set changes
    //     cleanly invalidate prior verdicts.
    //   - judge_model_id is the literal model string for single-model runs
    //     OR 'ensemble:openai+anthropic+google' for E2 ensemble runs.
    //   - applied BOOLEAN: did we auto-resolve based on this verdict, or
    //     did it surface to review? D17 default-off auto-resolve means
    //     most rows start applied=false on fresh installs.
    //   - confidence REAL: the discretized self-reported judge confidence.
    //     CDX-11 drift detection compares this against actual accuracy
    //     over 90-day windows.
    //   - wave_version for --undo-wave reversal.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS take_grade_cache (
        take_id            BIGINT       NOT NULL,
        prompt_version     TEXT         NOT NULL,
        judge_model_id     TEXT         NOT NULL,
        evidence_signature TEXT         NOT NULL,
        wave_version       TEXT         NOT NULL DEFAULT 'v0.36.1.0',
        graded_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
        verdict            TEXT         NOT NULL
                                        CHECK (verdict IN ('correct','incorrect','partial','unresolvable')),
        confidence         REAL         NOT NULL,
        applied            BOOLEAN      NOT NULL DEFAULT false,
        cost_usd           NUMERIC(10,4),
        PRIMARY KEY (take_id, prompt_version, judge_model_id, evidence_signature)
      );
      CREATE INDEX IF NOT EXISTS take_grade_cache_applied_idx
        ON take_grade_cache (take_id, applied);
      CREATE INDEX IF NOT EXISTS take_grade_cache_wave_idx
        ON take_grade_cache (wave_version, graded_at DESC);
    `,
  },
  {
    version: 71,
    name: 'take_nudge_log_v0_36',
    // v0.36.1.0 — E7 nudge log + cooldown state (D16/F3 + CDX-5).
    //
    // Polymorphic reference (CDX-5 fix): a nudge can fire on a
    // canonical take (take_id set) OR on a pending proposal (proposal_id
    // set) BEFORE the proposal gets accepted. CHECK constraint enforces
    // exactly one is set.
    //
    // (take_id, nudge_pattern, fired_at DESC) index supports the cooldown
    // probe ("did we fire this pattern for this take in the last 14 days?").
    // Same shape works for proposal_id via the index below.
    //
    // channel column lets future routing (webhook/admin-spa-toast) reuse
    // the same cooldown semantics. v0.36.1.0 ships with channel='stderr'
    // only (multi-channel routing deferred to v0.37+).
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS take_nudge_log (
        id              BIGSERIAL PRIMARY KEY,
        source_id       TEXT         NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        take_id         BIGINT,
        proposal_id     BIGINT       REFERENCES take_proposals(id) ON DELETE CASCADE,
        nudge_pattern   TEXT         NOT NULL,
        fired_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
        channel         TEXT         NOT NULL DEFAULT 'stderr',
        wave_version    TEXT         NOT NULL DEFAULT 'v0.36.1.0',
        CONSTRAINT take_nudge_log_target_xor
          CHECK ((take_id IS NOT NULL) <> (proposal_id IS NOT NULL))
      );
      CREATE INDEX IF NOT EXISTS take_nudge_log_take_cooldown_idx
        ON take_nudge_log (take_id, nudge_pattern, fired_at DESC)
        WHERE take_id IS NOT NULL;
      CREATE INDEX IF NOT EXISTS take_nudge_log_proposal_cooldown_idx
        ON take_nudge_log (proposal_id, nudge_pattern, fired_at DESC)
        WHERE proposal_id IS NOT NULL;
      CREATE INDEX IF NOT EXISTS take_nudge_log_wave_idx
        ON take_nudge_log (wave_version, fired_at DESC);
    `,
  },
  {
    version: 72,
    name: 'takes_resolved_at_trend_idx_v0_36',
    // v0.36.1.0 — F10 perf finding. Brier-trend aggregation queries
    // (90-day windowed scorecard) hit takes WHERE resolved_at IS NOT NULL.
    // Without this partial index, large takes tables do full scans even
    // when the resolved subset is small.
    //
    // Partial index because most takes are unresolved on fresh brains;
    // resolution is the sparse dimension. Engine-aware via handler since
    // Postgres benefits from CONCURRENTLY on large tables.
    idempotent: true,
    sql: '',
    handler: async (engine) => {
      if (engine.kind === 'postgres') {
        // Pre-drop invalid remnant from a failed CONCURRENTLY attempt.
        await engine.runMigration(
          71,
          `DO $$ BEGIN
             IF EXISTS (
               SELECT 1 FROM pg_index i
               JOIN pg_class c ON c.oid = i.indexrelid
               WHERE c.relname = 'takes_resolved_at_idx' AND NOT i.indisvalid
             ) THEN
               EXECUTE 'DROP INDEX CONCURRENTLY IF EXISTS takes_resolved_at_idx';
             END IF;
           END $$;`
        );
        await engine.runMigration(
          71,
          `CREATE INDEX CONCURRENTLY IF NOT EXISTS takes_resolved_at_idx
             ON takes (resolved_at DESC)
             WHERE resolved_at IS NOT NULL;`
        );
      } else {
        await engine.runMigration(
          71,
          `CREATE INDEX IF NOT EXISTS takes_resolved_at_idx
             ON takes (resolved_at DESC)
             WHERE resolved_at IS NOT NULL;`
        );
      }
    },
    transaction: false,
  },
  {
    version: 73,
    name: 'think_ab_results_v0_36',
    // v0.36.1.0 (T18 / D19) — A/B harness data for `gbrain think --ab`.
    //
    // Each row records one side-by-side comparison of think with vs.
    // without --with-calibration. After 30 days of data, `gbrain
    // calibration ab-report` aggregates win/loss across the table and
    // surfaces a calibration_net_negative doctor warning if the
    // with-calibration variant loses >55% of trials (n >= 20).
    //
    // wave_version stamped so --undo-wave can scrub these too if needed.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS think_ab_results (
        id              BIGSERIAL PRIMARY KEY,
        source_id       TEXT         NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        wave_version    TEXT         NOT NULL DEFAULT 'v0.36.1.0',
        ran_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
        question        TEXT         NOT NULL,
        baseline_answer TEXT         NOT NULL,
        with_calibration_answer TEXT NOT NULL,
        preferred       TEXT         NOT NULL CHECK (preferred IN ('baseline','with_calibration','neither','tie')),
        model_id        TEXT,
        notes           TEXT
      );
      CREATE INDEX IF NOT EXISTS think_ab_results_recent_idx
        ON think_ab_results (source_id, ran_at DESC);
    `,
  },
  {
    version: 74,
    name: 'eval_candidates_embedding_column',
    // v0.36.3.0 (D16 / CDX-10): persist the resolved embedding column on
    // each eval_candidates row so replay against a captured query uses
    // the column that was active at capture time — not whichever column
    // is current local default. Without this, switching
    // `search_embedding_column` between capture and replay produces
    // false-positive "regressions" that are just column changes.
    //
    // Nullable for back-compat: pre-v0.36 rows have NULL; replay treats
    // NULL as "use current default" so existing captures keep working
    // exactly as before the migration.
    //
    // Renumbered v68→v74 during the second master merge: master's
    // v0.36.1.0 calibration wave claimed v68-v73 first. The ALTER
    // itself is unchanged; only the slot number moved. The column is
    // also in PGLITE_SCHEMA_SQL / src/schema.sql so fresh installs get
    // it natively without running this migration.
    idempotent: true,
    sql: `
      ALTER TABLE eval_candidates
        ADD COLUMN IF NOT EXISTS embedding_column TEXT;
    `,
    // PGLite parity: same ALTER, same IF NOT EXISTS guard makes this a
    // no-op on subsequent boots.
    sqlFor: {
      pglite: `
        ALTER TABLE eval_candidates
          ADD COLUMN IF NOT EXISTS embedding_column TEXT;
      `,
    },
  },
  {
    version: 75,
    name: 'op_checkpoints_table',
    // v0.36+ autonomous-remediation wave (renumbered v67→v75 during master
    // merge — master's v0.36.1.0 calibration + v0.36.3.0 captured v67-v74).
    // Shared checkpoint table for long-running ops (embed, extract, lint,
    // backlinks, reindex, integrity). Pre-fix, each op had its own
    // file-backed checkpoint (or none), which broke on Postgres multi-worker
    // hosts and silently fingerprint-collided across param variations
    // (extract links vs extract timeline shared one file). DB-backed primary;
    // PGLite engine falls back to file-backed at
    // ~/.gbrain/checkpoints/<op>-<fingerprint>.json because it's single-host
    // by construction.
    //
    // Fingerprint = sha8 of canonical-JSON of relevant params per op
    // (chunker_version + embedding_model for embed, mode for extract, etc.).
    // completed_keys are op-defined strings: chunk ids for embed, file paths
    // for extract/lint/backlinks/reindex, page slugs for integrity.
    //
    // GC: cycle's purge phase drops rows older than 7 days.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS op_checkpoints (
        op TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        completed_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (op, fingerprint)
      );
      CREATE INDEX IF NOT EXISTS op_checkpoints_updated_at_idx
        ON op_checkpoints (updated_at);
    `,
  },
  {
    version: 76,
    name: 'minion_jobs_doctor_run_id_index',
    // v0.36+ autonomous-remediation wave (renumbered v68→v76 during master
    // merge). Partial GIN on minion_jobs.data for `data ? 'doctor_run_id'`.
    // Lets `gbrain doctor --remediate` runs be queried by run id for audit
    // trail without sequential-scanning months of cron history. Partial so
    // only doctor-submitted jobs are indexed; ordinary cron submissions
    // don't bloat the index.
    //
    // PGLite skips via empty sqlFor — JSONB GIN partial indexes aren't
    // supported the same way; audit query falls through to sequential
    // scan, which is fine for PGLite's single-host scope.
    idempotent: true,
    sql: '',
    sqlFor: {
      postgres: `
        CREATE INDEX IF NOT EXISTS minion_jobs_doctor_run_id_idx
          ON minion_jobs USING GIN (data jsonb_path_ops)
          WHERE data ? 'doctor_run_id';
      `,
      pglite: '',
    },
  },
  {
    version: 79,
    name: 'pages_last_retrieved_at',
    // v0.37.1.0 brainstorm/lsd wave (D15 + D11 + D12):
    // Originally planned as v77 but v77 + v78 were claimed by the v0.37.0.0
    // skillpack-registry + cross-modal waves landing on master first.
    //
    // Adds `pages.last_retrieved_at TIMESTAMPTZ NULL` — the real stale-page
    // signal for `gbrain lsd`'s "your brain at 3am noticing what it forgot"
    // mode. Bumped by op-layer write-back inside the `search` / `query` /
    // `get_page` op handlers AFTER results return (NOT inside the engine
    // methods — internal callers like sync / migrations / tests must not
    // pollute the signal per codex round 2 #3).
    //
    // Full index, no partial WHERE per D12 + codex round 2 #6: LSD's primary
    // query is `WHERE last_retrieved_at IS NULL OR last_retrieved_at < NOW()
    // - INTERVAL '90 days'`. Postgres B-tree indexes handle NULL (sorted to
    // one end), so one index supports both branches. A partial `WHERE NOT
    // NULL` would miss LSD's prioritized never-retrieved branch.
    //
    // ADD COLUMN with no DEFAULT (NULL) is metadata-only on Postgres 11+
    // and PGLite 17.5; instant on tables of any size.
    idempotent: true,
    sql: `
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS last_retrieved_at TIMESTAMPTZ NULL;
      CREATE INDEX IF NOT EXISTS pages_last_retrieved_at_idx
        ON pages (last_retrieved_at);
    `,
  },
  {
    version: 80,
    name: 'takes_unresolvable_quality_v0_37_2_0',
    // v0.37.2.0 hotfix (master) — accepts quality='unresolvable' as a 4th
    // valid resolution state. Unblocks production grading scripts that write
    // the 4th verdict type (the judge in grade-takes returns
    // correct|incorrect|partial|unresolvable, but v37's CHECKs only allowed
    // the first three).
    //
    // Two CHECKs to widen:
    //   (a) Table-level `takes_resolution_consistency` enumerates valid
    //       (quality, outcome) pairs. We add ('unresolvable', NULL).
    //   (b) Column-level CHECK on resolved_quality enumerates valid string
    //       values. Postgres auto-names this `takes_resolved_quality_check`
    //       when it's attached via ADD COLUMN ... CHECK. We drop it and
    //       re-add with the wider value list (named explicitly this time
    //       so future widening targets a known name).
    //
    // v0.38 note: master's v80 (this migration) shipped to master between
    // when this branch cut and the v0.38 ship. The v0.38 schema-pack
    // migrations renumbered to v81 + v82 to land cleanly above it. Order
    // matters because v80 drops + re-adds takes_resolved_quality_values
    // and v81 will drop takes_kind_check — both touch the takes table but
    // different constraints, no ordering hazard between them.
    idempotent: true,
    sql: `
      -- (b) Drop both possible names for the column-level CHECK:
      ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_resolved_quality_check;
      ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_resolved_quality_values;
      ALTER TABLE takes ADD CONSTRAINT takes_resolved_quality_values CHECK (
        resolved_quality IS NULL
        OR resolved_quality IN ('correct', 'incorrect', 'partial', 'unresolvable')
      );

      -- (a) Widen the (quality, outcome) consistency CHECK.
      ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_resolution_consistency;
      ALTER TABLE takes ADD CONSTRAINT takes_resolution_consistency CHECK (
        (resolved_quality IS NULL             AND resolved_outcome IS NULL)
        OR (resolved_quality = 'correct'      AND resolved_outcome = true)
        OR (resolved_quality = 'incorrect'    AND resolved_outcome = false)
        OR (resolved_quality = 'partial'      AND resolved_outcome IS NULL)
        OR (resolved_quality = 'unresolvable' AND resolved_outcome IS NULL)
      );
    `,
  },
  {
    version: 81,
    name: 'pages_provenance_columns',
    // v0.38 ingestion cathedral (eng review E4):
    // Adds four nullable provenance columns to `pages` so every ingested
    // page carries a record of WHERE it came from. The columns are
    // populated by the ingest_capture Minion handler (via the put_page
    // write-through path landing in a sibling commit). NULL is the
    // historical-page default — pre-v0.38 pages never had provenance.
    //
    //   - ingested_via    TEXT  — source kind taxonomy
    //                             (file-watcher | inbox-folder | webhook |
    //                              cron-scheduler | capture-cli |
    //                              <skillpack-kind>)
    //   - ingested_at     TIMESTAMPTZ — UTC time the ingestion daemon
    //                                   accepted the event
    //   - source_uri      TEXT  — original URI/path/message-id the event
    //                             carried (file path, mail message-id, URL)
    //   - source_kind     TEXT  — duplicates ingested_via for indexed
    //                             filtering convenience (one column for
    //                             "type of source", one for richer label
    //                             — kept narrow + indexable separately)
    //
    // ADD COLUMN with NULL default is metadata-only on Postgres 11+ and
    // PGLite 17.5 — instant on tables of any size.
    //
    // No index: provenance queries are admin-surface only.
    //
    // Forward-reference bootstrap: every brain that upgrades through this
    // version needs the columns visible to the embedded SCHEMA_SQL replay
    // BEFORE migrations run. applyForwardReferenceBootstrap on both
    // engines covers this; REQUIRED_BOOTSTRAP_COVERAGE pins the contract.
    //
    // Renumbered v80→v81 during master merge with v0.37.2.0's
    // takes_unresolvable_quality hotfix.
    idempotent: true,
    sql: `
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS ingested_via TEXT NULL;
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NULL;
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS source_uri TEXT NULL;
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS source_kind TEXT NULL;
    `,
  },
  {
    version: 82,
    name: 'subagent_tool_executions_stable_id',
    // (master v0.38.1.0; see end of conflict marker block for full body)
    idempotent: true,
    sql: `
      ALTER TABLE subagent_tool_executions
        ADD COLUMN IF NOT EXISTS ordinal INTEGER,
        ADD COLUMN IF NOT EXISTS gbrain_tool_use_id UUID;
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint
          WHERE conname = 'subagent_tool_executions_stable_id'
        ) THEN
          ALTER TABLE subagent_tool_executions
            ADD CONSTRAINT subagent_tool_executions_stable_id
            UNIQUE (job_id, message_idx, ordinal);
        END IF;
      END$$;
    `,
    sqlFor: {
      pglite: `
        ALTER TABLE subagent_tool_executions
          ADD COLUMN IF NOT EXISTS ordinal INTEGER;
        ALTER TABLE subagent_tool_executions
          ADD COLUMN IF NOT EXISTS gbrain_tool_use_id UUID;
        ALTER TABLE subagent_tool_executions
          DROP CONSTRAINT IF EXISTS subagent_tool_executions_stable_id;
        ALTER TABLE subagent_tool_executions
          ADD CONSTRAINT subagent_tool_executions_stable_id
          UNIQUE (job_id, message_idx, ordinal);
      `,
    },
  },
  {
    version: 83,
    name: 'mcp_spend_reservations',
    // (master v0.38.1.0 — full body in merged region)
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS mcp_spend_reservations (
        reservation_id UUID PRIMARY KEY,
        client_id TEXT NOT NULL,
        job_id BIGINT NULL REFERENCES minion_jobs(id) ON DELETE SET NULL,
        estimated_cents NUMERIC(12, 4) NOT NULL,
        actual_cents NUMERIC(12, 4) NULL,
        model TEXT NOT NULL,
        provider TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending', 'settled', 'expired')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        settled_at TIMESTAMPTZ NULL,
        expires_at TIMESTAMPTZ NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_mcp_spend_reservations_client_time
        ON mcp_spend_reservations (client_id, created_at);
      CREATE INDEX IF NOT EXISTS idx_mcp_spend_reservations_pending_expires
        ON mcp_spend_reservations (status, expires_at)
        WHERE status = 'pending';
    `,
  },
  {
    version: 84,
    name: 'oauth_clients_budget_usd_per_day',
    // (master v0.38.1.0 — full body in merged region)
    idempotent: true,
    sql: `
      ALTER TABLE oauth_clients
        ADD COLUMN IF NOT EXISTS budget_usd_per_day NUMERIC(10, 2) NULL;
    `,
  },
  {
    version: 85,
    name: 'oauth_clients_agent_binding',
    // (master v0.38.1.0 — full body in merged region)
    idempotent: true,
    sql: `
      ALTER TABLE oauth_clients
        ADD COLUMN IF NOT EXISTS bound_tools TEXT[] NULL,
        ADD COLUMN IF NOT EXISTS bound_source_id TEXT NULL,
        ADD COLUMN IF NOT EXISTS bound_brain_id TEXT NULL,
        ADD COLUMN IF NOT EXISTS bound_slug_prefixes TEXT[] NULL,
        ADD COLUMN IF NOT EXISTS bound_max_concurrent INTEGER NOT NULL DEFAULT 1;
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint
          WHERE conname = 'fk_oauth_clients_bound_source'
        ) THEN
          BEGIN
            ALTER TABLE oauth_clients
              ADD CONSTRAINT fk_oauth_clients_bound_source
              FOREIGN KEY (bound_source_id)
              REFERENCES sources(id) ON DELETE SET NULL;
          EXCEPTION WHEN others THEN
            NULL;
          END;
        END IF;
      END$$;
    `,
    sqlFor: {
      pglite: `
        ALTER TABLE oauth_clients
          ADD COLUMN IF NOT EXISTS bound_tools TEXT[] NULL;
        ALTER TABLE oauth_clients
          ADD COLUMN IF NOT EXISTS bound_source_id TEXT NULL;
        ALTER TABLE oauth_clients
          ADD COLUMN IF NOT EXISTS bound_brain_id TEXT NULL;
        ALTER TABLE oauth_clients
          ADD COLUMN IF NOT EXISTS bound_slug_prefixes TEXT[] NULL;
        ALTER TABLE oauth_clients
          ADD COLUMN IF NOT EXISTS bound_max_concurrent INTEGER NOT NULL DEFAULT 1;
      `,
    },
  },
  {
    version: 86,
    name: 'page_links_view_alias',
    // v0.39.0.0 schema-cathedral wave. Renumbered v81→v86 during the
    // master-merge of v0.38.0.0 ingestion cathedral + v0.38.1.0 agent loop
    // (master claimed v81-v85). page_links view alias is idempotent so
    // brains that already ran it under shanghai-v3's v81 number are safe.
    //
    // pglite-engine.ts and postgres-engine.ts both query a relation named
    // `page_links` (see pglite-engine.ts:896 / postgres-engine.ts:959). The
    // canonical table has always been `links`. This view aliases the table
    // so brains initialized before the v0.38 schema bundle pick up the
    // alias on upgrade.
    //
    // Narrow projection (id, from_page_id, to_page_id) so the view doesn't
    // depend on later-added columns — keeps DROP COLUMN + bootstrap probes
    // unblocked on legacy brains.
    sql: `
      CREATE OR REPLACE VIEW page_links AS
        SELECT id, from_page_id, to_page_id FROM links;
    `,
  },
  {
    version: 87,
    name: 'takes_kind_drop_check',
    // v0.39.0.0 schema-cathedral wave (T3 + codex T10 fix). Renumbered
    // v80→v81→v82→v87 across successive master merges. Final renumber
    // landed it after master's v0.38.1.0 agent-loop bundle (v81-v85).
    //
    // Pre-v0.38: `takes.kind` was enforced by a DB CHECK constraint
    // CHECK (kind IN ('fact','take','bet','hunch')) at the original
    // table-creation migration (v41 / v48 in pre-renumber numbering).
    // The same closed enum was duplicated as a TS type union.
    //
    // v0.38 opens the type surface so schema packs declare allowed kinds
    // at runtime against the active pack's `annotation` primitive
    // `takes_kinds:` field. This migration drops the DB CHECK; runtime
    // validation in src/core/schema-pack/registry.ts takes over.
    //
    // Codex F10: dropping the DB CHECK without also widening the TS
    // type "moves inconsistency around" — old clients and raw SQL could
    // poison rows that runtime-validate cleanly. Both layers move
    // together: this migration + src/core/engine.ts + src/core/takes-fence.ts
    // already widened to `string`.
    //
    // Idempotent: `IF EXISTS` on both engines. PGLite supports
    // ALTER TABLE DROP CONSTRAINT IF EXISTS (standard SQL).
    idempotent: true,
    sql: `
      ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_kind_check;
    `,
  },
  {
    version: 88,
    name: 'eval_candidates_schema_pack_per_source',
    // v0.39.0.0 schema-cathedral wave (T4 + T28 + E10 + E11 codex fold).
    // Renumbered v81→v82→v83→v88 across successive master merges. Final
    // renumber landed it after master's v0.38.1.0 agent-loop bundle.
    //
    // Adds `eval_candidates.schema_pack_per_source JSONB` so `gbrain
    // eval replay` reproduces the EXACT per-source closure that the
    // captured query ran against. Without this, a year-old replay
    // against an evolved pack returns different rows than the original
    // capture — eval becomes a moving target.
    //
    // Shape (E11 inline canonical snapshot):
    //   {
    //     "<source_id>": {
    //       "pack_name": "garry-pack",
    //       "pack_version": "1.2.0",
    //       "manifest_sha8": "ab12cd34",
    //       "alias_closure_resolved": {"person": ["person","researcher"], ...}
    //     },
    //     ...
    //   }
    //
    // Inline snapshot (E11): captures the FULL resolved alias graph at
    // query time so replay is self-contained — no dependency on the
    // pack file still existing in ~/.gbrain/schema-packs/. ~1KB per row
    // for a typical 50-type pack; ~10MB/year for a heavy user (10K
    // captured queries). Acceptable storage cost for permanent replay
    // reliability.
    //
    // Codex F8 (replay version-mismatch policy): replay fails closed by
    // default when captured pack identity drifts from the active. Pass
    // --use-captured-snapshot flag to replay against the inline closure
    // anyway.
    //
    // Pack identity = `<pack-name>@<version>+<manifest_sha8>` (codex F7).
    //
    // ADD COLUMN with no DEFAULT (NULL) is metadata-only on Postgres 11+
    // and PGLite 17.5; instant on tables of any size.
    idempotent: true,
    sql: `
      ALTER TABLE eval_candidates
        ADD COLUMN IF NOT EXISTS schema_pack_per_source JSONB NULL;
    `,
  },
  {
    version: 89,
    name: 'pages_memtheta_columns',
    // Search ranking now projects pages.access_count + pages.confidence_score
    // directly. Older brains missing the additive columns must self-heal.
    idempotent: true,
    sql: `
      ALTER TABLE pages
        ADD COLUMN IF NOT EXISTS access_count INT NOT NULL DEFAULT 0;
      ALTER TABLE pages
        ADD COLUMN IF NOT EXISTS confidence_score REAL NOT NULL DEFAULT 1.0;
    `,
  },
];
