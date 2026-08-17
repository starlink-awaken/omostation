import type { Migration, BrainEngine } from './types.ts';

// MIGRATIONS_MID2 v48-v63 (auto-extracted F7114ABA Wave 2 3/7).
export const MIGRATIONS_MID2: Migration[] = [
  {
    version: 48,
    name: 'takes_weight_round_to_grid',
    // v0.32.0 — Takes v2 wave (renumbered from v46 → v48 after merging master's
    // v0.31.3 wave which claimed v46 with mcp_request_log_params_jsonb_normalize).
    // Backfill the weight column to the 0.05 grid that v0.31's engine layer
    // enforces on insert (PR #795). Cross-modal eval over 100K production
    // takes flagged 0.74, 0.82-style values as false precision; the engine
    // now rounds new inserts to the grid, but pre-v0.32 rows still carry the
    // old precision and bias every query that reads weight (search ranking,
    // scorecard, calibration math).
    //
    // What `transaction: false` actually buys (codex review #2 correction):
    // it frees the migration runner from holding a long transaction across
    // the UPDATE so other gbrain processes (workers, MCP queries) can
    // interleave. It does NOT enable mid-statement resume — a single SQL
    // statement either completes or rolls back.
    //
    // Idempotency: the WHERE clause re-evaluates each row. After the first
    // complete pass every row is on-grid; a second invocation of the
    // migration is a zero-row UPDATE.
    //
    // The IS NOT NULL guard is cheap insurance against any stale schema
    // where weight was nullable; current schema (v28+) has NOT NULL.
    sql: `
      -- Tolerance-based comparison. weight is stored as REAL (float32), which
      -- has ~1e-7 representation noise. The 0.05 grid spacing is 5e-2. Any
      -- value with abs(weight - on_grid) > 1e-3 is genuinely off-grid; below
      -- that, the difference is float32 noise from prior round-trips and
      -- re-writing it would only re-introduce the same noise, not converge.
      -- (The naive "weight <> ROUND(...)" form fires every time because
      -- mixed REAL/NUMERIC comparison promotes weight to DOUBLE PRECISION
      -- first, surfacing the 1e-7 noise as inequality.)
      UPDATE takes
         SET weight = (ROUND(weight::numeric * 20) / 20)::real
       WHERE weight IS NOT NULL
         AND abs(weight::numeric - ROUND(weight::numeric * 20) / 20) > 0.001;
    `,
    transaction: false,
  },
  {
    version: 49,
    name: 'eval_takes_quality_runs',
    // v0.32 — Takes v2 wave (EXP-5). Renumbered from v47 → v49 after merging
    // master's v0.31.3 wave (v46 → mcp_request_log_params_jsonb_normalize).
    //
    // DB-authoritative store for the takes-quality eval CLI's receipts.
    // Codex review #6 corrected the original two-phase plan (split-brain
    // reconciliation gap) — DB row is the source of truth, the disk file
    // is a best-effort artifact.
    //
    // 4-sha unique key (corpus, prompt, model_set, rubric) so:
    //   - Re-running the same run is idempotent (ON CONFLICT DO NOTHING).
    //   - A future rubric tweak produces a different rubric_sha8 → distinct
    //     row → trend mode segregates by rubric_version (codex review #3).
    //
    // receipt_json carries the full receipt blob so `replay` can reconstruct
    // when the disk artifact is missing (DB-authoritative replay path).
    //
    // Index `(rubric_version, created_at DESC)` matches the trend query
    // shape: ORDER BY created_at DESC LIMIT N filtered by rubric_version.
    sql: `
      CREATE TABLE IF NOT EXISTS eval_takes_quality_runs (
        id                    BIGSERIAL    PRIMARY KEY,
        receipt_sha8_corpus   TEXT         NOT NULL,
        receipt_sha8_prompt   TEXT         NOT NULL,
        receipt_sha8_models   TEXT         NOT NULL,
        receipt_sha8_rubric   TEXT         NOT NULL,
        rubric_version        TEXT         NOT NULL,
        verdict               TEXT         NOT NULL CHECK (verdict IN ('pass','fail','inconclusive')),
        overall_score         REAL         NOT NULL,
        dim_scores            JSONB        NOT NULL,
        cost_usd              REAL         NOT NULL,
        receipt_json          JSONB        NOT NULL,
        receipt_disk_path     TEXT,
        created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
        UNIQUE (receipt_sha8_corpus, receipt_sha8_prompt, receipt_sha8_models, receipt_sha8_rubric)
      );
      CREATE INDEX IF NOT EXISTS eval_takes_quality_runs_trend_idx
        ON eval_takes_quality_runs (rubric_version, created_at DESC);
    `,
  },
  {
    version: 50,
    name: 'ingest_log_source_id',
    // v0.31.2 (codex P1 #3). Renumbered from v47 → v50 after the merge from
    // master picked up v0.31.3's v46 + the takes v2 wave's v48 + v49.
    //
    // facts:absorb logging (commit 13 + doctor's facts_extraction_health
    // check in commit 12) needs source_id on ingest_log so multi-source
    // brains can scope failure counts per source. Pre-fix the column doesn't
    // exist; the schema.sql header even calls it out: "NOTE (v0.18.0 Step 1):
    // ingest_log.source_id is NOT added yet — lands in v17 alongside the
    // sync rewrite." Three years on, sync.ts writes ingest_log without
    // source_id and doctor only checks 'default'. This migration adds the
    // column + backfills existing rows to 'default' via NOT NULL DEFAULT.
    //
    // Idempotent under all states (matches v47's shape):
    //   - Fresh install: ALTER no-ops on IF NOT EXISTS.
    //   - Old brain (no column): ALTER adds it with NOT NULL DEFAULT 'default';
    //     existing rows inherit the default.
    //   - Re-run after success: IF NOT EXISTS short-circuits.
    //
    // Both engines run the same SQL; ingest_log is engine-agnostic.
    sql: `
      ALTER TABLE ingest_log ADD COLUMN IF NOT EXISTS source_id TEXT NOT NULL DEFAULT 'default';

      CREATE INDEX IF NOT EXISTS idx_ingest_log_source_type_created
        ON ingest_log (source_id, source_type, created_at DESC);
    `,
  },
  {
    version: 51,
    name: 'facts_fence_columns',
    // v0.32.2: facts join the system-of-record invariant. Markdown fences on
    // entity pages become canonical; the facts table becomes a derived index.
    // The fence parser keys each row by `row_num` (monotonic, append-only) and
    // ties it back to the page it lives on via `source_markdown_slug`.
    //
    // Two ADD COLUMN IF NOT EXISTS + one partial UNIQUE index. ALTERs are
    // metadata-only on PG 11+ and PGLite because the columns are NULL-DEFAULT
    // (no rewrite). Pre-v51 rows keep NULL until the v0_32_2 orchestrator
    // backfills them from the entity page's `## Facts` fence.
    //
    // Idempotent under all states (matches v50 shape):
    //   - Fresh install: the v40 CREATE TABLE block already includes the
    //     columns (post-v0.32.2 source); these ALTERs no-op on IF NOT EXISTS.
    //   - v0.31.x brain mid-upgrade: ALTERs add the columns; existing rows
    //     have NULL until backfill.
    //   - Re-run after success: ALTERs and index creation both short-circuit.
    //
    // Partial UNIQUE rationale: legacy NULL row_num rows must not collide
    // (multiple v0.31 facts about the same entity coexist before backfill).
    // The `WHERE row_num IS NOT NULL` clause makes the constraint inert for
    // legacy rows and fully enforced once the orchestrator assigns row_nums.
    //
    // Both engines run the same SQL; facts is engine-agnostic at the column
    // level. The partial-index syntax is supported by both Postgres and
    // PGLite. (Verified against migration v48's idx_facts_unconsolidated
    // partial-index precedent at line 2339.)
    sql: `
      ALTER TABLE facts ADD COLUMN IF NOT EXISTS row_num              INTEGER;
      ALTER TABLE facts ADD COLUMN IF NOT EXISTS source_markdown_slug TEXT;

      CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_fence_key
        ON facts (source_id, source_markdown_slug, row_num)
        WHERE row_num IS NOT NULL;
    `,
  },
  {
    version: 52,
    name: 'eval_contradictions_cache',
    // v0.32.6 — P2 persistent judge cache for the contradiction probe.
    //
    // Composite primary key includes prompt_version + truncation_policy
    // (Codex outside-voice fix). Without these, a prompt edit would silently
    // serve stale verdicts to consumers. The cache key is the FULL
    // configuration that produced the verdict; bumping any component
    // invalidates prior entries cleanly.
    //
    // TTL via expires_at — readers can WHERE expires_at > now() to ignore
    // stale rows; an explicit DELETE WHERE expires_at <= now() sweep runs
    // periodically (lives in cache.ts orchestration, not here).
    //
    // verdict JSONB carries the full JudgeVerdict shape (contradicts,
    // severity, axis, confidence, resolution_kind) so a cache hit is a
    // complete answer without needing a second column.
    //
    // Idempotent across PGLite and Postgres; engine-agnostic DDL.
    sql: `
      CREATE TABLE IF NOT EXISTS eval_contradictions_cache (
        chunk_a_hash       TEXT         NOT NULL,
        chunk_b_hash       TEXT         NOT NULL,
        model_id           TEXT         NOT NULL,
        prompt_version     TEXT         NOT NULL,
        truncation_policy  TEXT         NOT NULL,
        verdict            JSONB        NOT NULL,
        created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
        expires_at         TIMESTAMPTZ  NOT NULL,
        PRIMARY KEY (chunk_a_hash, chunk_b_hash, model_id, prompt_version, truncation_policy)
      );
      CREATE INDEX IF NOT EXISTS eval_contradictions_cache_expires_idx
        ON eval_contradictions_cache (expires_at);
    `,
  },
  {
    version: 53,
    name: 'eval_contradictions_runs',
    // v0.32.6 — M5 time-series tracking for the contradiction probe.
    //
    // One row per `gbrain eval suspected-contradictions` run. The headline
    // numbers (queries_evaluated, with_contradiction, total_flagged) plus
    // Wilson 95% CI bounds enable `gbrain eval suspected-contradictions
    // trend [--days N]` to plot brain consistency over time.
    //
    // report_json carries the full ProbeReport for replay/inspection.
    // source_tier_breakdown is also surfaced as a top-level JSONB column
    // so trend queries can group by tier without parsing the full report.
    //
    // No FK to other tables: this is an append-only metrics log, not a
    // relational record. Trend reads filter on ran_at.
    //
    // Idempotent across PGLite and Postgres.
    sql: `
      CREATE TABLE IF NOT EXISTS eval_contradictions_runs (
        run_id                       TEXT         PRIMARY KEY,
        ran_at                       TIMESTAMPTZ  NOT NULL DEFAULT now(),
        schema_version               INTEGER      NOT NULL DEFAULT 1,
        judge_model                  TEXT         NOT NULL,
        prompt_version               TEXT         NOT NULL,
        queries_evaluated            INTEGER      NOT NULL,
        queries_with_contradiction   INTEGER      NOT NULL,
        total_contradictions_flagged INTEGER      NOT NULL,
        wilson_ci_lower              REAL         NOT NULL,
        wilson_ci_upper              REAL         NOT NULL,
        judge_errors_total           INTEGER      NOT NULL,
        cost_usd_total               REAL         NOT NULL,
        duration_ms                  INTEGER      NOT NULL,
        source_tier_breakdown        JSONB        NOT NULL,
        report_json                  JSONB        NOT NULL
      );
      CREATE INDEX IF NOT EXISTS eval_contradictions_runs_ran_at_idx
        ON eval_contradictions_runs (ran_at DESC);
    `,
  },
  {
    version: 54,
    name: 'cjk_wave_pages_chunker_version_and_source_path',
    // v0.32.7 CJK fix wave. Two new columns on `pages` so the post-upgrade
    // reindex sweep can find markdown pages built by the old chunker AND so
    // sync's delete/rename code can resolve frontmatter-fallback slugs by
    // path (CJK files where path → slug is non-derivable).
    //
    //   chunker_version: bumped to 2 in this release. New imports populate
    //     it; existing rows inherit DEFAULT 1. `gbrain reindex --markdown`
    //     walks `WHERE chunker_version < 2 AND page_kind = 'markdown'`
    //     and re-imports each, bumping the column.
    //
    //   source_path: import-time repo-relative path. Lets sync's delete/
    //     rename resolve fallback slugs (`小米.md` w/ frontmatter slug →
    //     non-path-derivable). NULL for pre-migration rows; populated on
    //     next import / reindex.
    //
    // Both columns engine-agnostic. Partial indexes scope to the rows
    // we actually query (markdown-only chunker_version; non-NULL source_path).
    idempotent: true,
    sql: `
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS chunker_version SMALLINT NOT NULL DEFAULT 1;
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS source_path TEXT;

      CREATE INDEX IF NOT EXISTS pages_chunker_version_idx
        ON pages (chunker_version) WHERE page_kind = 'markdown';

      CREATE INDEX IF NOT EXISTS pages_source_path_idx
        ON pages (source_path) WHERE source_path IS NOT NULL;
    `,
  },
  {
    version: 59,
    name: 'code_traversal_cache_v0_34',
    // v0.34 W3b — memoization layer for code_blast / code_flow.
    // (Originally claimed v56; renumbered to v59 on merge with master which
    // landed query_cache_search_lite=v55, drift_watch=v56, search_telemetry=v57.)
    //
    // Recursive caller/callee walks on a dense (calls + imports + references)
    // graph can fan out to 200+ nodes per call. During a plan-mode agent
    // session that calls code_blast 5-15 times, we want hits to return
    // <200ms instead of re-walking the same graph.
    //
    // The cache is correctness-safe under concurrent sync via REPEATABLE
    // READ + xmin_max — the traversal-cache module wraps each walk in
    // `BEGIN ISOLATION LEVEL REPEATABLE READ` and captures the snapshot's
    // xmin_max alongside the response. On read, if the current snapshot
    // doesn't dominate the cached snapshot, the cache misses.
    //
    // D3 — cluster_generation: monotonically incrementing counter bumped
    // once per recompute_code_clusters phase. Cache rows carrying a stale
    // generation naturally miss on next read, so cluster-renaming-mid-cycle
    // doesn't return stale cluster names from cached blast/flow responses.
    sql: `
      CREATE TABLE IF NOT EXISTS code_traversal_cache (
        id SERIAL PRIMARY KEY,
        symbol_qualified TEXT NOT NULL,
        depth INT NOT NULL,
        source_id TEXT NOT NULL,
        response_json JSONB NOT NULL,
        max_chunk_updated_at TIMESTAMPTZ NOT NULL,
        xmin_max BIGINT NOT NULL,
        cluster_generation BIGINT NOT NULL DEFAULT 0,
        computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE UNIQUE INDEX IF NOT EXISTS code_traversal_cache_key_idx
        ON code_traversal_cache (symbol_qualified, depth, source_id);
      CREATE INDEX IF NOT EXISTS code_traversal_cache_source_idx
        ON code_traversal_cache (source_id);
    `,
  },
  {
    version: 58,
    name: 'edges_backfilled_at_v0_33_2',
    // v0.33.2 W0c — resumable symbol-resolution backfill watermark.
    // (Originally claimed v55; renumbered to v58 on merge with master which
    // landed query_cache_search_lite=v55, drift_watch=v56, search_telemetry=v57.)
    //
    // The within-file two-pass resolver (src/core/chunkers/symbol-resolver.ts)
    // walks every content_chunks row that has unresolved edges
    // (rows in code_edges_symbol whose to_symbol_qualified has not been
    // matched against same-file symbol_name_qualified yet) and writes the
    // resolution outcome to code_edges_symbol.edge_metadata. On a 96K-chunk
    // brain that is a 5-15 minute backfill the first time it runs.
    //
    // `edges_backfilled_at` is the resume watermark. Backfill runs in
    // 200-chunk batches; on batch success the column is set to NOW() for
    // every chunk in the batch. Resume picks up chunks where the watermark
    // is NULL or older than EDGE_EXTRACTOR_VERSION_TS (a constant bumped
    // when the extractor's shape changes). Crashes lose at most one batch.
    //
    // Composite + partial indexes for the lookup hot path (D11 from eng
    // review):
    //   - idx_code_edges_symbol_resolver (source_id, to_symbol_qualified)
    //     — every code_edges_symbol row is unresolved by construction
    //     (the table has no to_chunk_id column; that lives on code_edges_chunk).
    //     This composite index supports the resolver's per-source lookups.
    //   - idx_content_chunks_symbol_lookup (page_id, symbol_name_qualified)
    //     WHERE symbol_name_qualified IS NOT NULL — file-batched lookup
    //     used by both the resolver and the cluster recompute phase (W4-5).
    //   - idx_content_chunks_edges_backfill (edges_backfilled_at)
    //     WHERE edges_backfilled_at IS NULL — find unresumed rows quickly.
    //
    // Idempotent: IF NOT EXISTS on column + indexes. Backfill itself runs
    // separately via the resolve_symbol_edges cycle phase.
    sql: `
      ALTER TABLE content_chunks ADD COLUMN IF NOT EXISTS edges_backfilled_at TIMESTAMPTZ;

      CREATE INDEX IF NOT EXISTS idx_code_edges_symbol_resolver
        ON code_edges_symbol (source_id, to_symbol_qualified);

      CREATE INDEX IF NOT EXISTS idx_content_chunks_symbol_lookup
        ON content_chunks (page_id, symbol_name_qualified)
        WHERE symbol_name_qualified IS NOT NULL;

      CREATE INDEX IF NOT EXISTS idx_content_chunks_edges_backfill
        ON content_chunks (edges_backfilled_at)
        WHERE edges_backfilled_at IS NULL;
    `,
  },
  {
    version: 55,
    name: 'query_cache_search_lite',
    // v0.32.x (search-lite, originally claimed v52 in PR #897; renumbered
    // to v55 on merge with master to sit after eval_contradictions_cache (v52),
    // eval_contradictions_runs (v53), cjk_wave (v54)).
    //
    // Semantic query cache. Cache search results keyed by query embedding
    // similarity so a near-duplicate query reuses the previous result set
    // instead of re-running keyword + vector + RRF + dedup. Cache lookup:
    // `embedding <=> $1 < 0.08` (cosine distance, similarity >= 0.92) using HNSW.
    //
    // Schema:
    //   id            — SHA-256(query_text + source_id) for diagnostics.
    //   query_text    — the raw query for debug + cache-stats output.
    //   source_id     — scope by source so multi-source brains don't bleed.
    //   embedding     — the query embedding. Same dim as content_chunks.
    //   results       — JSONB array of SearchResult rows.
    //   meta          — JSONB; what hybridSearch actually did (intent,
    //                   vector_enabled, etc.) so cached responses can
    //                   surface the same debug info as fresh ones.
    //   ttl_seconds   — per-row TTL. Default 3600. Stale rows are skipped
    //                   at read time and pruned by `gbrain cache prune`.
    //   created_at    — TTL anchor.
    //   hit_count     — instrumentation; bumped on each lookup-hit.
    //   last_hit_at   — instrumentation.
    //
    // Schema is engine-agnostic: HALFVEC when available (matches the facts
    // table from v45 for consistency), otherwise VECTOR. Embedding dim is
    // resolved from `config.embedding_dimensions` at migration time so
    // non-OpenAI brains work — same approach as v45.
    sql: '',
    handler: async (engine: BrainEngine) => {
      // Step 1: resolve embedding dim from config table (same pattern as v45).
      let embeddingDim = 1536;
      try {
        const dimRows = await engine.executeRaw<{ value: string }>(
          `SELECT value FROM config WHERE key = 'embedding_dimensions'`,
        );
        if (dimRows.length > 0) {
          const parsed = parseInt(dimRows[0].value, 10);
          if (Number.isFinite(parsed) && parsed > 0 && parsed <= 4096) {
            embeddingDim = parsed;
          }
        }
      } catch {
        // No config row yet — fall back to default.
      }

      // Step 2: pgvector version probe for HALFVEC. Same logic as v45.
      // We deliberately mirror v45's facts table approach for consistency.
      let useHalfvec = false;
      if (engine.kind === 'postgres') {
        try {
          const vrows = await engine.executeRaw<{ extversion: string }>(
            `SELECT extversion FROM pg_extension WHERE extname = 'vector'`,
          );
          if (vrows.length > 0) {
            const v = vrows[0].extversion;
            const parts = v.split('.');
            const major = parseInt(parts[0] ?? '0', 10);
            const minor = parseInt(parts[1] ?? '0', 10);
            if (major > 0 || (major === 0 && minor >= 7)) {
              useHalfvec = true;
            }
          }
        } catch {
          // Probe failed — fall back to VECTOR.
        }
      } else {
        useHalfvec = true;
      }

      const vecType = useHalfvec ? 'HALFVEC' : 'VECTOR';
      const opclass = useHalfvec ? 'halfvec_cosine_ops' : 'vector_cosine_ops';

      const ddl = `
        CREATE TABLE IF NOT EXISTS query_cache (
          id            TEXT        PRIMARY KEY,
          query_text    TEXT        NOT NULL,
          source_id     TEXT        NOT NULL DEFAULT 'default',
          embedding     ${vecType}(${embeddingDim}),
          results       JSONB       NOT NULL DEFAULT '[]'::jsonb,
          meta          JSONB       NOT NULL DEFAULT '{}'::jsonb,
          ttl_seconds   INTEGER     NOT NULL DEFAULT 3600,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          hit_count     INTEGER     NOT NULL DEFAULT 0,
          last_hit_at   TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_query_cache_source_created
          ON query_cache(source_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_query_cache_embedding_hnsw
          ON query_cache USING hnsw (embedding ${opclass})
          WHERE embedding IS NOT NULL;
      `;

      await engine.runMigration(55, ddl);
    },
  },
  {
    version: 56,
    name: 'query_cache_knobs_hash',
    // v0.32.3 search-lite mode cache contamination hotfix [CDX-4].
    //
    // PR #897's query_cache keyed rows on (id, source_id, query_text) only.
    // The `id` is sha256(source_id::query_text). A tokenmax search
    // (expansion=on, limit=50) populates a row that a subsequent
    // conservative call (no-expansion, limit=10) reads back, serving
    // expanded-and-oversized results to a budget-tight context.
    //
    // Fix: extend the row key with a knobs_hash derived from the resolved
    // search mode bundle. Lookup filters `WHERE knobs_hash = $1 AND
    // embedding similarity < threshold`. Existing rows have NULL
    // knobs_hash and are treated as misses (silently re-populated with
    // the correct hash on first hit — no orphan data, no destructive
    // migration).
    //
    // The PRIMARY KEY stays the existing `id` column (the SHA-256 of
    // (source_id, query_text, knobs_hash) — the cache code re-derives
    // it on every write, so a tokenmax write and a conservative write
    // produce distinct `id` values and live as separate rows).
    //
    // Engine-agnostic; idempotent.
    idempotent: true,
    sql: `
      ALTER TABLE query_cache ADD COLUMN IF NOT EXISTS knobs_hash TEXT;

      CREATE INDEX IF NOT EXISTS idx_query_cache_source_knobs_created
        ON query_cache(source_id, knobs_hash, created_at DESC);
    `,
  },
  {
    version: 57,
    name: 'search_telemetry_rollup',
    // v0.32.3 search-lite: per-day rollup of search-call shape.
    //
    // Powers `gbrain search stats [--days N]` and `gbrain search tune` so an
    // operator (or an agent calling tune) can reason about hit rate, intent
    // mix, budget pressure, and result-volume averages WITHOUT pulling
    // per-call rows.
    //
    // Schema math per [CDX-17]: sums + counts only, NOT averages. Read-time
    // derives averages so concurrent ON CONFLICT writes from multiple gbrain
    // processes accumulate correctly.
    //
    // Date-bucketed cache hit/miss per [CDX-18] — query_cache.hit_count is
    // a LIFETIME counter and can't be sliced by --days. The telemetry table
    // is the truth for windowed hit rate.
    //
    // PK is (date, mode, intent) so the rollup never grows past
    // 365 days × 3 modes × 4 intents = ~4380 rows/year. Acceptable.
    //
    // Engine-agnostic; idempotent.
    idempotent: true,
    sql: `
      CREATE TABLE IF NOT EXISTS search_telemetry (
        date                TEXT         NOT NULL,
        mode                TEXT         NOT NULL,
        intent              TEXT         NOT NULL,
        count               INTEGER      NOT NULL DEFAULT 0,
        sum_results         INTEGER      NOT NULL DEFAULT 0,
        sum_tokens          INTEGER      NOT NULL DEFAULT 0,
        sum_budget_dropped  INTEGER      NOT NULL DEFAULT 0,
        cache_hit           INTEGER      NOT NULL DEFAULT 0,
        cache_miss          INTEGER      NOT NULL DEFAULT 0,
        first_seen          TIMESTAMPTZ  NOT NULL DEFAULT now(),
        last_seen           TIMESTAMPTZ  NOT NULL DEFAULT now(),
        PRIMARY KEY (date, mode, intent)
      );

      CREATE INDEX IF NOT EXISTS idx_search_telemetry_date
        ON search_telemetry (date DESC);
    `,
  },
  {
    version: 60,
    name: 'oauth_clients_source_id_fk',
    // v0.34.1 (#861 + D4 + D10 + D13 — P0 source-isolation leak seal).
    //
    // Adds oauth_clients.source_id, validates ALL existing rows can map to a
    // real source row, backfills NULL → 'default', and installs the FK with
    // ON DELETE SET NULL. PR #861's original migration claimed v47-v51; we
    // re-number to v60 because the branch already shipped through v54.
    //
    // D10 (codex outside-voice push-back): fail loud when stale source_id
    // rows exist instead of silently widening to NULL. Pre-fix this column
    // didn't exist; the only way a row has source_id IS a manual SQL poke,
    // so the stale-row branch fires only on operator-modified brains. The
    // GBRAIN_ACCEPT_SILENT_WIDEN=1 env var is the explicit opt-in for
    // operators who'd rather upgrade than psql-fix. Doctor surfaces orphan
    // rows post-clean via the v0.34.x follow-up TODO.
    //
    // D13: backfill NULL → 'default' BEFORE the FK ADD preserves the v0.33
    // effective behavior (legacy unscoped clients silently fell back to
    // 'default' via serve-http.ts:929 cast). Verify 'default' exists in
    // sources first — fresh brains have it from sources schema's default
    // seed; brains that scripted it out would otherwise wedge here.
    //
    // PGLite parity via the same DO blocks. PGLite supports DO/EXCEPTION
    // since 0.3; no engine branch needed.
    idempotent: true,
    sql: `
      -- v0.34.1 (#861 + D2 + D13 — P0 source-isolation leak seal).
      --
      -- This migration is intentionally lean: oauth_clients.source_id did
      -- NOT exist pre-v60, so the only state we inherit from upgrade is
      -- "rows with NULL source_id." Backfill those to 'default' (D13:
      -- preserves the pre-v0.34 effective fallback behavior verbatim) and
      -- install the FK with ON DELETE SET NULL.
      --
      -- D10 pre-clean is NOT NEEDED here: codex flagged the silent-widen
      -- footgun assuming source_id was an existing column with possibly-stale
      -- values. Since the column is brand new in this migration, the only
      -- post-backfill values are 'default' (which we just verified exists
      -- via the FK contract) plus any NULL the backfill left untouched
      -- because of WHERE-clause filtering — none possible. The
      -- GBRAIN_ACCEPT_SILENT_WIDEN env-flag stays in the runner for future
      -- migrations that need it; this one doesn't.

      -- 1. Add the column. NULL for every existing row.
      ALTER TABLE oauth_clients ADD COLUMN IF NOT EXISTS source_id TEXT;

      -- 2. Backfill NULL → 'default'. Pre-v0.34 legacy clients then map
      --    to the same source the serve-http fallback chain used to put
      --    them in implicitly. No-op on fresh installs (no rows yet).
      UPDATE oauth_clients SET source_id = 'default' WHERE source_id IS NULL;

      -- 3. Install FK if not already present. The PGLite + Postgres fresh-
      --    install schemas (src/core/pglite-schema.ts, src/schema.sql) now
      --    include the FK inline on the CREATE TABLE, so this DO block
      --    skips on fresh installs and only fires on upgrade brains where
      --    oauth_clients was created pre-v60 without the FK. ON DELETE SET
      --    NULL matches the original PR #861 posture; #876 later flips to
      --    RESTRICT once federated_read provides the alternative
      --    scope-recovery path.
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint
          WHERE conname = 'oauth_clients_source_id_fkey'
        ) THEN
          ALTER TABLE oauth_clients
            ADD CONSTRAINT oauth_clients_source_id_fkey
            FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL;
        END IF;
      END $$;

      -- 4. Index for token-verification lookups (verifyAccessToken's JOIN
      --    on oauth_clients.client_id → c.source_id). oauth_clients stays
      --    small so plain CREATE INDEX (no CONCURRENTLY) is fine.
      CREATE INDEX IF NOT EXISTS idx_oauth_clients_source_id
        ON oauth_clients(source_id) WHERE source_id IS NOT NULL;
    `,
  },
  {
    version: 61,
    name: 'oauth_clients_federated_read_column',
    // v0.34.1 (#876): add federated_read TEXT[] for the read-side
    // federation feature. source_id (v60) is the WRITE-authority axis;
    // federated_read is the READ-scope axis. A client can write to ONE
    // source while reading from N (a "WeCare L3 dept" client writes to
    // dept-x and reads dept-x + parent canon + shared canon).
    //
    // Default '{}' (empty array) on column add — pre-existing rows get
    // backfilled in v62 with an explicit CASE so the array reflects the
    // client's current scope rather than the column default.
    idempotent: true,
    sql: `
      ALTER TABLE oauth_clients ADD COLUMN IF NOT EXISTS federated_read TEXT[] NOT NULL DEFAULT '{}';
    `,
  },
  {
    version: 62,
    name: 'oauth_clients_federated_read_backfill',
    // v0.34.1 (#876, F5 — codex outside-voice fix). Backfill federated_read
    // with explicit CASE so source_id IS NULL doesn't produce an ambiguous
    // array containing NULL. Three cases:
    //   - source_id IS NULL → '{}' (empty read scope; legacy unscoped
    //     clients lost their implicit fallback in v60 backfill to 'default',
    //     so this branch fires only when an operator explicitly NULL'd
    //     source_id after migration).
    //   - source_id IS NOT NULL → ARRAY[source_id] (read scope matches
    //     write scope, the pre-federation default).
    // Only fires on rows where federated_read is still the column default
    // ({}). Operators who hand-set federated_read keep their config.
    idempotent: true,
    sql: `
      UPDATE oauth_clients
      SET federated_read = CASE
        WHEN source_id IS NULL THEN '{}'::text[]
        ELSE ARRAY[source_id]
      END
      WHERE federated_read = '{}'::text[];
    `,
  },
  {
    version: 63,
    name: 'oauth_clients_federated_read_validate',
    // v0.34.1 (#876): post-backfill validation. Every client with a
    // non-NULL source_id should now have its source_id reflected in
    // federated_read. Fail loud if backfill missed a row — points at a
    // logic bug in v62's WHERE clause.
    idempotent: true,
    sql: `
      DO $$
      DECLARE
        bad_count INT;
      BEGIN
        SELECT count(*) INTO bad_count FROM oauth_clients
          WHERE source_id IS NOT NULL
            AND NOT (source_id = ANY(federated_read));
        IF bad_count > 0 THEN
          RAISE EXCEPTION 'oauth_clients has % rows where source_id is not in federated_read after v62 backfill. This is a bug in v62 — re-run gbrain apply-migrations --force-retry 62.', bad_count;
        END IF;
      END $$;
    `,
  },
];
