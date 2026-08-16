import type { Migration, BrainEngine } from './types.ts';

// MIGRATIONS_MID1 v32-v47 (auto-extracted F7114ABA Wave 2 3/7).
export const MIGRATIONS_MID1: Migration[] = [
  {
    version: 32,
    name: 'oauth_infrastructure',
    // v0.26 OAuth 2.1 tables for `gbrain serve --http`. Supports client credentials,
    // authorization code + PKCE, and refresh token rotation. Renumbered from v30
    // → v32 on merge with master's v0.23 (dream_verdicts at v30) + v0.25
    // (eval_capture_tables at v31). OAuth is independent of those chains so
    // ordering doesn't matter beyond version ledger correctness. CREATE TABLE
    // statements are idempotent so brains that previously applied this at v30
    // see version 32 as new and run IF NOT EXISTS DDL cleanly.
    sql: `
      CREATE TABLE IF NOT EXISTS oauth_clients (
        client_id               TEXT PRIMARY KEY,
        client_secret_hash      TEXT,
        client_name             TEXT NOT NULL,
        redirect_uris           TEXT[],
        grant_types             TEXT[] DEFAULT '{"client_credentials"}',
        scope                   TEXT,
        token_endpoint_auth_method TEXT,
        client_id_issued_at     BIGINT,
        client_secret_expires_at BIGINT,
        created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE TABLE IF NOT EXISTS oauth_tokens (
        token_hash   TEXT PRIMARY KEY,
        token_type   TEXT NOT NULL,
        client_id    TEXT NOT NULL REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
        scopes       TEXT[],
        expires_at   BIGINT,
        resource     TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE INDEX IF NOT EXISTS idx_oauth_tokens_expiry ON oauth_tokens(expires_at);
      CREATE INDEX IF NOT EXISTS idx_oauth_tokens_client ON oauth_tokens(client_id);
      CREATE TABLE IF NOT EXISTS oauth_codes (
        code_hash              TEXT PRIMARY KEY,
        client_id              TEXT NOT NULL REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
        scopes                 TEXT[],
        code_challenge         TEXT NOT NULL,
        code_challenge_method  TEXT NOT NULL DEFAULT 'S256',
        redirect_uri           TEXT NOT NULL,
        state                  TEXT,
        resource               TEXT,
        expires_at             BIGINT NOT NULL,
        created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE INDEX IF NOT EXISTS idx_mcp_log_time_agent ON mcp_request_log(created_at, token_name);
      DO $$
      DECLARE
        has_bypass BOOLEAN;
      BEGIN
        SELECT rolbypassrls INTO has_bypass FROM pg_roles WHERE rolname = current_user;
        IF has_bypass THEN
          ALTER TABLE oauth_clients ENABLE ROW LEVEL SECURITY;
          ALTER TABLE oauth_tokens ENABLE ROW LEVEL SECURITY;
          ALTER TABLE oauth_codes ENABLE ROW LEVEL SECURITY;
        ELSE
          RAISE WARNING 'v32: role % lacks BYPASSRLS — skipping RLS on OAuth tables. Re-run as postgres (or a BYPASSRLS role) to harden.', current_user;
        END IF;
      END $$;
    `,
  },
  {
    version: 33,
    name: 'admin_dashboard_columns_v0_26_3',
    // v0.26.3 admin dashboard expansion. Adds 5 columns referenced by
    // src/commands/serve-http.ts and src/core/oauth-provider.ts that landed
    // in PR #586 without a corresponding schema migration. Without v33,
    // existing brains hit:
    //   - SELECT c.token_ttl, ... CASE WHEN c.deleted_at -> 503 on /admin/api/agents
    //   - INSERT INTO mcp_request_log (... agent_name, params, error_message)
    //     -> caught by best-effort try/catch, request log silently empties
    //   - UPDATE oauth_clients SET deleted_at = now() (revoke-client) -> 500
    //   - UPDATE oauth_clients SET token_ttl = ... (update-client-ttl) -> 500
    // All ALTERs use ADD COLUMN IF NOT EXISTS so re-running is a no-op.
    sql: `
      ALTER TABLE oauth_clients
        ADD COLUMN IF NOT EXISTS token_ttl INTEGER,
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

      ALTER TABLE mcp_request_log
        ADD COLUMN IF NOT EXISTS agent_name TEXT,
        ADD COLUMN IF NOT EXISTS params JSONB,
        ADD COLUMN IF NOT EXISTS error_message TEXT;

      -- Backfill agent_name on existing rows so the new "agent" column in
      -- the request log isn't blank for pre-v0.26.3 entries. LEFT JOIN
      -- pattern: prefer client_name from oauth_clients (current behavior),
      -- fall back to access_tokens.name (legacy bearer tokens), fall back
      -- to the raw client_id stored as token_name.
      UPDATE mcp_request_log m
      SET agent_name = COALESCE(
        (SELECT client_name FROM oauth_clients WHERE client_id = m.token_name LIMIT 1),
        (SELECT name FROM access_tokens WHERE name = m.token_name LIMIT 1),
        m.token_name
      )
      WHERE agent_name IS NULL;

      -- Index for the new agent filter on /admin/api/request-log. The
      -- existing idx_mcp_log_time_agent (created_at, token_name) doesn't
      -- help when filtering by the resolved agent_name. Use DESC on
      -- created_at to match the typical ORDER BY clause.
      CREATE INDEX IF NOT EXISTS idx_mcp_log_agent_time
        ON mcp_request_log(agent_name, created_at DESC);
    `,
  },
  {
    version: 34,
    name: 'destructive_guard_columns',
    // v0.26.5 — soft-delete + recovery window for sources AND pages.
    // Renumbered v33→v34 on master merge: master's v33 (admin_dashboard_columns_v0_26_3)
    // landed first in PR #586. v34 follows it.
    //
    // pages.deleted_at: `delete_page` op now sets deleted_at = now() instead of
    // hard-deleting. The autopilot purge phase hard-deletes rows where
    // deleted_at < now() - 72h. Search and `get_page` filter
    // `WHERE deleted_at IS NULL` by default; `include_deleted: true` opts in.
    //
    // sources.archived/archived_at/archive_expires_at: promoted from JSONB keys
    // to real columns. v0.26.0 + the cherry-picked PR #595 wrote these inside
    // `sources.config` JSONB. Real columns are faster to filter, avoid the
    // reserved-key footgun, and let the search visibility filter compile to a
    // column lookup. The 72h TTL is preserved by reading
    // `archive_expires_at = archived_at + INTERVAL '72 hours'`.
    //
    // Backfill: any row that previously stored `{"archived":true,"archived_at":"...","archive_expires_at":"..."}`
    // in config gets migrated to the new columns, then the keys are stripped
    // from JSONB so the JSONB shape stays canonical going forward.
    //
    // Engine-aware partial index: Postgres uses CREATE INDEX CONCURRENTLY (no
    // write-blocking lock); PGLite uses plain CREATE INDEX. Mirrors v14
    // (pages_updated_at_index) handler shape.
    sql: '',
    handler: async (engine) => {
      // 1. Add columns. ALTER TABLE ADD COLUMN IF NOT EXISTS is idempotent on
      //    both engines.
      await engine.runMigration(34, `
        ALTER TABLE pages   ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
        ALTER TABLE sources ADD COLUMN IF NOT EXISTS archived           BOOLEAN     NOT NULL DEFAULT false;
        ALTER TABLE sources ADD COLUMN IF NOT EXISTS archived_at        TIMESTAMPTZ;
        ALTER TABLE sources ADD COLUMN IF NOT EXISTS archive_expires_at TIMESTAMPTZ;
      `);

      // 2. Backfill from JSONB shape used by pre-v0.26.5 cherry-picks of PR #595.
      //    Idempotent: subsequent re-runs find zero matching rows.
      await engine.runMigration(34, `
        UPDATE sources
        SET archived = true,
            archived_at = COALESCE((config->>'archived_at')::timestamptz, now()),
            archive_expires_at = COALESCE(
              (config->>'archive_expires_at')::timestamptz,
              COALESCE((config->>'archived_at')::timestamptz, now()) + INTERVAL '72 hours'
            )
        WHERE config ? 'archived'
          AND (config->>'archived')::boolean = true
          AND archived = false;
      `);
      await engine.runMigration(34, `
        UPDATE sources
        SET config = config - 'archived' - 'archived_at' - 'archive_expires_at'
        WHERE config ?| ARRAY['archived', 'archived_at', 'archive_expires_at'];
      `);

      // 3. Partial index for the autopilot purge sweep. Postgres CONCURRENTLY
      //    avoids the SHARE lock on `pages`; PGLite has no concurrent writers.
      if (engine.kind === 'postgres') {
        // Pre-drop any invalid index from a prior CONCURRENTLY failure (matches v14 pattern).
        await engine.runMigration(34, `
          DO $$ BEGIN
            IF EXISTS (
              SELECT 1 FROM pg_index i
              JOIN pg_class c ON c.oid = i.indexrelid
              WHERE c.relname = 'pages_deleted_at_purge_idx' AND NOT i.indisvalid
            ) THEN
              EXECUTE 'DROP INDEX CONCURRENTLY IF EXISTS pages_deleted_at_purge_idx';
            END IF;
          END $$;
        `);
        await engine.runMigration(34, `
          CREATE INDEX CONCURRENTLY IF NOT EXISTS pages_deleted_at_purge_idx
            ON pages (deleted_at) WHERE deleted_at IS NOT NULL;
        `);
      } else {
        await engine.runMigration(34, `
          CREATE INDEX IF NOT EXISTS pages_deleted_at_purge_idx
            ON pages (deleted_at) WHERE deleted_at IS NOT NULL;
        `);
      }
    },
    // CONCURRENTLY on Postgres requires no surrounding transaction. PGLite ignores
    // this flag, so the index DDL runs in whatever wrapper applies.
    transaction: false,
  },
  {
    version: 35,
    name: 'auto_rls_event_trigger',
    sql: '', // engine-specific via sqlFor
    // v0.26.7 — Postgres event trigger that auto-enables RLS on every new public.*
    // table, plus one-time backfill on every existing public.* table without it.
    //
    // Problem: tables created outside gbrain migrations (Baku's face_detections,
    // manual SQL, other apps sharing the Supabase project) shipped without RLS.
    // doctor caught them after the fact; the gap window between create and next
    // doctor run was the silent vector.
    //
    // Fix has two halves:
    //   1. Event trigger — fires on ddl_command_end for CREATE TABLE,
    //      CREATE TABLE AS, and SELECT INTO; runs ALTER TABLE ... ENABLE ROW
    //      LEVEL SECURITY for any new public.* table. Supabase-recommended
    //      approach (no dashboard toggle exists).
    //   2. One-time backfill — every existing public.* table whose RLS is off
    //      and whose comment does NOT match the GBRAIN:RLS_EXEMPT contract
    //      (same regex doctor.ts uses) gets RLS enabled.
    //
    // Posture choices (vs PR-as-shipped):
    //   - ENABLE only, no FORCE — matches v24/v29/schema.sql. FORCE would lock
    //     out non-BYPASSRLS apps from their own newly-created tables (the
    //     trigger function inherits the caller's role, and the new table is
    //     owned by that role). gbrain has BYPASSRLS so gbrain itself is unaffected.
    //   - public-only schema scope — Supabase manages auth/storage/realtime/etc.
    //     and runs its own RLS posture there; we must not disturb those schemas.
    //   - No EXCEPTION wrap inside the trigger — ddl_command_end fires inside
    //     the DDL transaction, so a failed ALTER aborts the offending CREATE
    //     TABLE. That's a loud signal, not a silent gap. Wrapping would CREATE
    //     the silent path this migration exists to close.
    //   - No privilege pre-check — runMigrations rethrows on SQL failure and
    //     gates config.version, so a non-superuser run already fails loud with
    //     an actionable Postgres error.
    //
    // BREAKING CHANGE: the backfill is a one-time override of intentionally
    // RLS-off public tables that don't carry the GBRAIN:RLS_EXEMPT comment.
    // Operators with such tables MUST add the exempt comment BEFORE upgrading.
    //
    // PGLite: no-op — no RLS engine, no event triggers, single-tenant by design.
    sqlFor: {
      postgres: `
        -- Trigger function: fires post-DDL inside the CREATE TABLE transaction.
        -- A failure here aborts the CREATE TABLE so no public.* table is ever
        -- created without RLS. object_identity is pre-quoted by Postgres
        -- (e.g. "public"."My Table"), so %s is correct — %I would double-quote.
        CREATE OR REPLACE FUNCTION auto_enable_rls()
        RETURNS event_trigger AS $$
        DECLARE
          obj record;
        BEGIN
          FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
            WHERE object_type = 'table'
            AND schema_name = 'public'
          LOOP
            EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', obj.object_identity);
          END LOOP;
        END;
        $$ LANGUAGE plpgsql;

        -- WHEN TAG covers all three table-creation syntaxes Postgres reports.
        -- CREATE TABLE / CREATE TABLE AS / SELECT INTO produce distinct command
        -- tags; covering only 'CREATE TABLE' would leave a syntax-shaped hole.
        DROP EVENT TRIGGER IF EXISTS auto_rls_on_create_table;
        CREATE EVENT TRIGGER auto_rls_on_create_table
          ON ddl_command_end
          WHEN TAG IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
          EXECUTE FUNCTION auto_enable_rls();

        -- One-time backfill of every existing public.* base table without RLS.
        -- Honors the same GBRAIN:RLS_EXEMPT regex doctor.ts uses
        -- (^GBRAIN:RLS_EXEMPT\\s+reason=\\S.{3,}) so the two surfaces stay aligned.
        -- %I.%I quotes the schema and table names safely, including mixed-case.
        DO $$
        DECLARE
          has_bypass BOOLEAN;
          r record;
        BEGIN
          SELECT rolbypassrls INTO has_bypass FROM pg_roles WHERE rolname = current_user;
          IF NOT has_bypass THEN
            -- Same posture as v24: raise to abort the migration so the runner
            -- leaves config.version unbumped and retries on the next call.
            RAISE EXCEPTION 'v35 auto_rls_event_trigger backfill: role % does not have BYPASSRLS — cannot enable RLS safely. Re-run as postgres (or another BYPASSRLS role).', current_user;
          END IF;

          FOR r IN
            SELECT n.nspname AS schema_name, c.relname AS table_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = 0
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relrowsecurity = false
              AND (d.description IS NULL OR d.description !~ '^GBRAIN:RLS_EXEMPT\\s+reason=\\S.{3,}')
          LOOP
            EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', r.schema_name, r.table_name);
            RAISE NOTICE 'v35: backfilled RLS on %.%', r.schema_name, r.table_name;
          END LOOP;
        END $$;
      `,
      pglite: '', // PGLite has no RLS and no event trigger support
    },
  },
  {
    version: 36,
    name: 'subagent_provider_neutral_persistence_v0_27',
    // v0.27 multi-provider subagent. Codex F-OV-1 / D11: the subagent_messages
    // and subagent_tool_executions tables stored Anthropic-shaped tool_use /
    // tool_result blocks as JSONB. When a worker resumes a job mid-loop and
    // the live model is OpenAI/DeepSeek/etc, the persisted shape becomes the
    // runtime contract — translation at read time is lossy.
    //
    // Fix: add schema_version + provider_id columns. schema_version=1 is the
    // legacy Anthropic-shape (existing rows). schema_version=2 is the
    // provider-neutral ChatBlock format documented in src/core/ai/gateway.ts
    // (text / tool-call / tool-result blocks with normalized field names).
    // Subagent.ts (commit 2) writes schema_version=2 going forward and reads
    // both shapes via a versioned mapper.
    //
    // Renumbered v34→v35→v36 across master merges: master's v34
    // (destructive_guard_columns, v0.26.5 soft-delete) and v35
    // (auto_rls_event_trigger, v0.26.8) landed first.
    //
    // No data migration. Existing in-flight jobs continue to replay against
    // their original shape; new jobs use v2. ADD COLUMN IF NOT EXISTS makes
    // the migration idempotent.
    sql: `
      ALTER TABLE subagent_messages
        ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS provider_id TEXT;

      ALTER TABLE subagent_tool_executions
        ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS provider_id TEXT;

      -- Lookup by provider for cost rollups + per-provider replay diagnostics.
      CREATE INDEX IF NOT EXISTS idx_subagent_messages_provider
        ON subagent_messages (job_id, provider_id);
    `,
  },
  {
    version: 39,
    name: 'multimodal_dual_column_v0_27_1',
    // v0.27.1 multimodal ingestion. Three changes that travel together:
    //
    // 1. content_chunks gains `modality TEXT NOT NULL DEFAULT 'text'` so image
    //    chunks declare themselves at the row level. Search filters use it to
    //    keep image OCR text out of text-page keyword search by default.
    //
    // 2. content_chunks gains `embedding_image vector(1024)` for Voyage
    //    multimodal embeddings. NULL on every text row; sparse on the column.
    //    Partial HNSW index ignores NULL rows so the index footprint stays
    //    proportional to image chunk count, not table size. Mixed-provider
    //    brains (e.g. OpenAI 1536 text + Voyage 1024 images) can keep both
    //    columns populated with distinct dim spaces.
    //
    // 3. PGLite gains the `files` table (mirroring the Postgres v0.18 shape)
    //    so the multimodal ingest pipeline can persist binary-asset metadata
    //    on the default engine. Image bytes never enter the DB; storage_path
    //    references a path inside the brain repo. The v0.18 "PGLite has no
    //    files table" omission was specific to blob storage — for path-
    //    referenced metadata PGLite hosts it fine.
    //
    // Eng-3C: a preflight handler refuses if pgvector < 0.5, BEFORE any DDL
    // fires, so the user gets a clear upgrade hint instead of a half-migrated
    // brain mid-DDL. Postgres-only — PGLite ships pgvector built in.
    // Handler-driven migration. The preflight pgvector check (Eng-3C) MUST
    // run BEFORE any DDL fires; if we used `sqlFor` the runner would DDL
    // before calling the handler. So we keep `sql` empty and let the handler
    // run preflight + DDL in the right order.
    sql: '',
    handler: async (engine: BrainEngine) => {
      // Eng-3C: refuse loudly if pgvector < 0.5 BEFORE any DDL fires.
      // Partial HNSW indexes need HNSW (pgvector 0.5.0+). PGLite ships a
      // recent pgvector inside its WASM bundle so this gate is Postgres-only.
      if (engine.kind === 'postgres') {
        const rows = await engine.executeRaw<{ extversion: string }>(
          `SELECT extversion FROM pg_extension WHERE extname = 'vector'`
        );
        if (rows.length === 0) {
          throw new Error(
            `Migration v39 requires the pgvector extension. Install it via\n` +
            `  CREATE EXTENSION vector;\n` +
            `then re-run \`gbrain apply-migrations --yes\`.`
          );
        }
        const version = rows[0].extversion;
        const [maj, minStr] = version.split('.');
        const min = parseInt(minStr ?? '0', 10);
        const major = parseInt(maj ?? '0', 10);
        if (major === 0 && min < 5) {
          throw new Error(
            `Migration v39 requires pgvector >= 0.5.0 (HNSW partial indexes).\n` +
            `Found pgvector ${version}.\n\n` +
            `Fix: ALTER EXTENSION vector UPDATE; then re-run \`gbrain apply-migrations --yes\`.\n` +
            `If your Postgres provider doesn't ship pgvector >= 0.5, request\n` +
            `an upgrade or migrate to PGLite for v0.27.1 multimodal support.`
          );
        }
      }

      // Step 1: schema delta on content_chunks + widen pages.page_kind CHECK
      // to admit 'image'. Runs through engine.runMigration so multi-statement
      // DDL works on PGLite (db.exec) and Postgres (sql.unsafe).
      await engine.runMigration(39, `
        ALTER TABLE content_chunks
          ADD COLUMN IF NOT EXISTS modality TEXT NOT NULL DEFAULT 'text',
          ADD COLUMN IF NOT EXISTS embedding_image vector(1024);

        CREATE INDEX IF NOT EXISTS idx_chunks_embedding_image
          ON content_chunks USING hnsw (embedding_image vector_cosine_ops)
          WHERE embedding_image IS NOT NULL;

        -- Widen pages.page_kind CHECK to admit 'image'. The constraint name
        -- is auto-assigned by Postgres; locate + drop + recreate with the
        -- new value list. PGLite + Postgres share the same constraint shape.
        ALTER TABLE pages DROP CONSTRAINT IF EXISTS pages_page_kind_check;
        ALTER TABLE pages ADD CONSTRAINT pages_page_kind_check
          CHECK (page_kind IN ('markdown','code','image'));
      `);

      // Step 2: PGLite-only — add the files table that v0.18 deliberately
      // omitted. Postgres has had it since v0.18; this is parity catch-up.
      if (engine.kind === 'pglite') {
        await engine.runMigration(39, `
          CREATE TABLE IF NOT EXISTS files (
            id           SERIAL PRIMARY KEY,
            source_id    TEXT   NOT NULL DEFAULT 'default'
                         REFERENCES sources(id) ON DELETE CASCADE,
            page_slug    TEXT,
            page_id      INTEGER REFERENCES pages(id) ON DELETE SET NULL,
            filename     TEXT   NOT NULL,
            storage_path TEXT   NOT NULL,
            mime_type    TEXT,
            size_bytes   BIGINT,
            content_hash TEXT   NOT NULL,
            metadata     JSONB  NOT NULL DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(storage_path)
          );

          CREATE INDEX IF NOT EXISTS idx_files_page ON files(page_slug);
          CREATE INDEX IF NOT EXISTS idx_files_page_id ON files(page_id);
          CREATE INDEX IF NOT EXISTS idx_files_source_id ON files(source_id);
          CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
        `);
      }
    },
  },
  {
    version: 40,
    name: 'pages_emotional_weight',
    // v0.29 — Salience + Anomaly Detection.
    //
    // Adds the `emotional_weight` column to pages. Populated by the new
    // `recompute_emotional_weight` cycle phase from tags + takes (deterministic;
    // no LLM). Default 0.0 so freshly imported pages don't pollute salience
    // ranking before the cycle has run; users run `gbrain dream --phase
    // recompute_emotional_weight` once after upgrading to backfill.
    //
    // No index: the salience query orders by a computed score (emotional_weight,
    // take_count, recency-decay), not by raw emotional_weight. Add an index
    // later only if a query orders by the raw column directly.
    //
    // Postgres ADD COLUMN with a constant DEFAULT is metadata-only on PG 11+
    // and PGLite (PG 17.5 via WASM) — instant on tables of any size.
    sql: `
      ALTER TABLE pages
        ADD COLUMN IF NOT EXISTS emotional_weight REAL NOT NULL DEFAULT 0.0;
    `,
  },
  {
    version: 41,
    name: 'pages_recency_columns',
    sql: '',
    // v0.29.1 — Salience-and-Recency, additive opt-in.
    //
    // Four new pages columns (all nullable, additive only, no behavior change
    // in the default search path; only consulted when a caller opts into
    // `salience='on'` / `recency='on'` or the new `since`/`until` filter):
    //
    //   effective_date         — content date (event_date / date / published /
    //                            filename-date / fallback). Read by the new
    //                            recency boost and date-filter paths only.
    //                            Auto-link doesn't touch it (immune to
    //                            updated_at churn).
    //   effective_date_source  — sentinel for the doctor's effective_date_health
    //                            check ('event_date' | 'date' | 'published' |
    //                            'filename' | 'fallback'). The 'fallback' value
    //                            is what surfaces "page that fell back to
    //                            updated_at when frontmatter was unparseable".
    //   import_filename        — basename without extension, captured at import.
    //                            computeEffectiveDate uses it for filename-date
    //                            precedence (daily/, meetings/ prefixes). Older
    //                            rows leave it NULL; backfill falls through.
    //   salience_touched_at    — bumped by recompute_emotional_weight when
    //                            emotional_weight changes. Salience window
    //                            uses GREATEST(updated_at, salience_touched_at)
    //                            so newly-salient old pages enter the recent
    //                            salience query.
    //
    // Plus an expression index used by since/until filters that read
    // COALESCE(effective_date, updated_at). Partial-index claim from earlier
    // plan iterations was wrong (codex pass-2 #15) — the planner won't use a
    // partial index for the negative side of a COALESCE; expression index does.
    //
    // CONCURRENTLY + pre-drop guard (mirror of v34) on Postgres; plain CREATE
    // INDEX on PGLite via the handler branching on engine.kind.
    handler: async (engine) => {
      // 1. ADD COLUMN x4. ALTER TABLE ADD COLUMN IF NOT EXISTS is idempotent.
      //    No defaults, all nullable, all metadata-only on PG 11+ and PGLite.
      await engine.runMigration(38, `
        ALTER TABLE pages ADD COLUMN IF NOT EXISTS effective_date        TIMESTAMPTZ;
        ALTER TABLE pages ADD COLUMN IF NOT EXISTS effective_date_source TEXT;
        ALTER TABLE pages ADD COLUMN IF NOT EXISTS import_filename       TEXT;
        ALTER TABLE pages ADD COLUMN IF NOT EXISTS salience_touched_at   TIMESTAMPTZ;
      `);

      // 2. Expression index for since/until date-range filters.
      if (engine.kind === 'postgres') {
        // Pre-drop any invalid index from a prior CONCURRENTLY failure.
        await engine.runMigration(38, `
          DO $$ BEGIN
            IF EXISTS (
              SELECT 1 FROM pg_index i
              JOIN pg_class c ON c.oid = i.indexrelid
              WHERE c.relname = 'pages_coalesce_date_idx' AND NOT i.indisvalid
            ) THEN
              EXECUTE 'DROP INDEX CONCURRENTLY IF EXISTS pages_coalesce_date_idx';
            END IF;
          END $$;
        `);
        await engine.runMigration(38, `
          CREATE INDEX CONCURRENTLY IF NOT EXISTS pages_coalesce_date_idx
            ON pages ((COALESCE(effective_date, updated_at)));
        `);
      } else {
        await engine.runMigration(38, `
          CREATE INDEX IF NOT EXISTS pages_coalesce_date_idx
            ON pages ((COALESCE(effective_date, updated_at)));
        `);
      }
    },
    // CONCURRENTLY on Postgres requires no surrounding transaction.
    transaction: false,
  },
  {
    version: 42,
    name: 'eval_candidates_recency_capture',
    // v0.29.1 — capture agent-explicit recency + salience choices for replay
    // reproducibility (D11 codex resolution).
    //
    // Without these fields, `gbrain eval replay` cannot reproduce a captured
    // run: the live behavior depends on the resolved {salience, recency}
    // values, which are absent from v0.29.0's eval_candidates schema. Replays
    // of agent-explicit choices drift the same way as_of_ts replays drifted
    // before being captured.
    //
    // All columns are nullable + additive. Pre-v0.29.1 rows stay valid. The
    // NDJSON `schema_version` STAYS at 1 — the new fields are optional, and
    // gbrain-evals consumers that don't know about them ignore them
    // (standard permissive deserialization). No cross-repo coordination
    // required (codex pass-1 #C2 dissolved).
    //
    //   as_of_ts            — brain's logical NOW at capture (replay uses
    //                         this instead of wall-clock so old captures
    //                         reproduce identically against today's brain).
    //   salience_param      — what the caller passed (or NULL if omitted).
    //   recency_param       — same for recency.
    //   salience_resolved   — final value applied ('off' / 'on' / 'strong').
    //   recency_resolved    — same for recency.
    //   salience_source     — 'caller' or 'auto_heuristic'.
    //   recency_source      — same for recency.
    //
    // ADD COLUMN with no DEFAULT is metadata-only on PG 11+ and PGLite —
    // instant on tables of any size.
    sql: `
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS as_of_ts          TIMESTAMPTZ;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS salience_param    TEXT;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS recency_param     TEXT;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS salience_resolved TEXT;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS recency_resolved  TEXT;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS salience_source   TEXT;
      ALTER TABLE eval_candidates ADD COLUMN IF NOT EXISTS recency_source    TEXT;
    `,
  },
  {
    version: 43,
    name: 'takes_resolved_quality_and_drift_decisions',
    // v0.30.0 (Slice A1, Universal Takes Epistemology wave). Bundles ALL schema
    // for the v0.30 release wave so A2/B1/C1 add no migrations (codex F6 fix:
    // schema-first ordering eliminates the cross-lane migrate.ts contention).
    // Originally landed as v40 in the v0.30.0 branch; renumbered to v43 on
    // merge with master after master claimed v40-v42 with the v0.29 +
    // v0.29.1 salience-and-recency wave. Migration runner sorts by version
    // number, so renumbering is a pure-rename — no semantic change.
    //
    // 1. takes.resolved_quality TEXT — 3-state outcome label (correct/incorrect/
    //    partial) sitting alongside existing resolved_outcome BOOLEAN. Boolean
    //    stays for back-compat reads; quality is the new source of truth for
    //    calibration math. Backfill maps legacy resolved_outcome → quality.
    //
    // 2. takes_resolution_consistency CHECK constraint — fails contradictory
    //    states like (quality='correct', outcome=false). 'partial' maps to
    //    outcome=NULL because partial isn't a binary outcome. Added AFTER the
    //    backfill so existing rows pass.
    //
    // 3. idx_takes_scorecard partial index on (holder, kind, resolved_quality)
    //    WHERE resolved_quality IS NOT NULL — scorecard hot path. ~5KB on a
    //    50K-row brain; makes scorecard O(log n) instead of full scan.
    //
    // 4. drift_decisions audit table — consumed by Slice C1 (v0.30.3) when
    //    drift LLM judge ships. Defined here so C1 carries no migration.
    //    Sized for one row per drift recommendation (insert-only, never
    //    updated except for applied_at/applied_by when --auto-update lands).
    sql: `
      -- Step 1: add resolved_quality column with kind-of-outcome CHECK.
      -- The (quality, outcome) consistency constraint comes AFTER the backfill
      -- (Step 3) so existing legacy rows don't fail the new constraint.
      ALTER TABLE takes
        ADD COLUMN IF NOT EXISTS resolved_quality TEXT
          CHECK (resolved_quality IS NULL OR resolved_quality IN ('correct','incorrect','partial'));

      -- Step 2: backfill from legacy boolean. Idempotent: only writes rows
      -- where quality is still NULL and outcome is set. Re-runs are no-ops.
      UPDATE takes
      SET resolved_quality = CASE resolved_outcome
        WHEN true  THEN 'correct'
        WHEN false THEN 'incorrect'
      END
      WHERE resolved_outcome IS NOT NULL AND resolved_quality IS NULL;

      -- Step 3: (quality, outcome) consistency constraint. Drop-then-recreate
      -- so re-runs converge. The named constraint lets us evolve it later.
      ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_resolution_consistency;
      ALTER TABLE takes ADD CONSTRAINT takes_resolution_consistency CHECK (
        (resolved_quality IS NULL     AND resolved_outcome IS NULL)
        OR (resolved_quality = 'correct'   AND resolved_outcome = true)
        OR (resolved_quality = 'incorrect' AND resolved_outcome = false)
        OR (resolved_quality = 'partial'   AND resolved_outcome IS NULL)
      );

      -- Step 4: scorecard hot path. Partial index keeps footprint proportional
      -- to resolved-take count, not table size.
      CREATE INDEX IF NOT EXISTS idx_takes_scorecard
        ON takes (holder, kind, resolved_quality)
        WHERE resolved_quality IS NOT NULL;

      -- Step 5: drift_decisions audit table (consumed by Slice C1 in v0.30.3).
      CREATE TABLE IF NOT EXISTS drift_decisions (
        id                  BIGSERIAL   PRIMARY KEY,
        take_id             BIGINT      NOT NULL REFERENCES takes(id) ON DELETE CASCADE,
        page_id             INTEGER     NOT NULL,
        row_num             INTEGER     NOT NULL,
        recommended_weight  REAL        NOT NULL CHECK (recommended_weight >= 0 AND recommended_weight <= 1),
        reasoning           TEXT,
        decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        applied_at          TIMESTAMPTZ,
        applied_by          TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_drift_decisions_take       ON drift_decisions(take_id);
      CREATE INDEX IF NOT EXISTS idx_drift_decisions_decided_at ON drift_decisions(decided_at DESC);

      -- RLS for the new table (Postgres-only — PGLite has no RLS engine).
      -- Mirrors the v37 takes/synthesis_evidence pattern: only flip RLS on
      -- when running as a BYPASSRLS role so non-BYPASSRLS apps still read.
      DO $$
      DECLARE
        has_bypass BOOLEAN;
      BEGIN
        SELECT rolbypassrls INTO has_bypass FROM pg_roles WHERE rolname = current_user;
        IF has_bypass THEN
          ALTER TABLE drift_decisions ENABLE ROW LEVEL SECURITY;
        END IF;
      END $$;
    `,
    sqlFor: {
      // PGLite: same DDL minus the RLS DO-block. Single-tenant by definition.
      pglite: `
        ALTER TABLE takes
          ADD COLUMN IF NOT EXISTS resolved_quality TEXT
            CHECK (resolved_quality IS NULL OR resolved_quality IN ('correct','incorrect','partial'));

        UPDATE takes
        SET resolved_quality = CASE resolved_outcome
          WHEN true  THEN 'correct'
          WHEN false THEN 'incorrect'
        END
        WHERE resolved_outcome IS NOT NULL AND resolved_quality IS NULL;

        ALTER TABLE takes DROP CONSTRAINT IF EXISTS takes_resolution_consistency;
        ALTER TABLE takes ADD CONSTRAINT takes_resolution_consistency CHECK (
          (resolved_quality IS NULL     AND resolved_outcome IS NULL)
          OR (resolved_quality = 'correct'   AND resolved_outcome = true)
          OR (resolved_quality = 'incorrect' AND resolved_outcome = false)
          OR (resolved_quality = 'partial'   AND resolved_outcome IS NULL)
        );

        CREATE INDEX IF NOT EXISTS idx_takes_scorecard
          ON takes (holder, kind, resolved_quality)
          WHERE resolved_quality IS NOT NULL;

        CREATE TABLE IF NOT EXISTS drift_decisions (
          id                  BIGSERIAL   PRIMARY KEY,
          take_id             BIGINT      NOT NULL REFERENCES takes(id) ON DELETE CASCADE,
          page_id             INTEGER     NOT NULL,
          row_num             INTEGER     NOT NULL,
          recommended_weight  REAL        NOT NULL CHECK (recommended_weight >= 0 AND recommended_weight <= 1),
          reasoning           TEXT,
          decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
          applied_at          TIMESTAMPTZ,
          applied_by          TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_drift_decisions_take       ON drift_decisions(take_id);
        CREATE INDEX IF NOT EXISTS idx_drift_decisions_decided_at ON drift_decisions(decided_at DESC);
      `,
    },
  },
  {
    version: 44,
    name: 'pages_emotional_weight_recomputed_at',
    idempotent: true,
    // v0.30.1 (Codex X4 / Finding P2): emotional_weight = 0 is a VALID
    // steady-state value (migration v40 default). Indexing WHERE = 0
    // would be a permanent large index over normal data, not a backlog
    // index. The actual backlog predicate is "never recomputed" — for
    // that we need a separate timestamp column. ADD COLUMN with NULL
    // default is metadata-only on PG 11+ and PGLite — instant on tables
    // of any size.
    //
    // The recompute-emotional-weight cycle phase + the new
    // `gbrain backfill emotional_weight` command both stamp this column
    // with NOW() alongside the weight write, so existing rows progress
    // out of the backlog naturally as the cycle runs.
    //
    // Partial index: idx_pages_emotional_weight_pending lives on
    // `(id) WHERE emotional_weight_recomputed_at IS NULL` and is created
    // on first run by the backfill primitive (CONCURRENTLY) rather than
    // here, because schema-time CREATE INDEX isn't CONCURRENTLY-friendly
    // when the SCHEMA_SQL replay runs in a transaction.
    sql: `
      ALTER TABLE pages ADD COLUMN IF NOT EXISTS emotional_weight_recomputed_at TIMESTAMPTZ;
    `,
  },
  {
    version: 45,
    name: 'facts_hot_memory_v0_31',
    // v0.31: hot memory layer — real-time working memory queryable across
    // sessions. Sits alongside `takes` (cold, markdown-mirrored) as the
    // ephemeral DB-only counterpart. Dream cycle's new `consolidate` phase
    // promotes facts → takes(kind='fact') overnight; the consolidated_into
    // pointer keeps facts as the audit trail.
    //
    // Schema decisions (from /plan-eng-review):
    //   - source_id TEXT (sources.id is TEXT — eE2). Per-source isolation;
    //     cross-brain federation stays agent-side.
    //   - kind CHECK constraint with 5 values; different decay halflives.
    //   - visibility column mirrors takes' world-default ACL contract (D21).
    //   - embedding column dim resolved at migration time from the
    //     `config.embedding_dimensions` row (matches content_chunks dim) so
    //     non-OpenAI brains (Voyage, etc.) work — codex F6 fix.
    //   - HALFVEC preferred (pgvector >= 0.7 needed); falls back to VECTOR
    //     with stderr warn on older pgvector — codex eE6 fix.
    //   - 5 partial indexes leading on source_id so every read uses the
    //     trust boundary as part of the index, not a callback.
    //   - consolidated_into BIGINT — takes.id is BIGSERIAL.
    sql: '',
    handler: async (engine: BrainEngine) => {
      // Step 1: resolve embedding dim from config table (already populated
      // by the schema-init __EMBEDDING_DIMS__ replacement on PGLite, or by
      // the seed config on Postgres). Default to 1536 (OpenAI text-embed-3-large).
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
        // No config row yet — fall back to default. Fresh installs hit this
        // path on first initSchema; that's fine since the schema seeds
        // the row before subsequent migrations run.
      }

      // Step 2: pgvector version preflight for HALFVEC support (>=0.7).
      // PGLite ships a recent pgvector inside its WASM bundle; we still
      // probe to be honest about the column type.
      let useHalfvec = false;
      if (engine.kind === 'postgres') {
        try {
          const vrows = await engine.executeRaw<{ extversion: string }>(
            `SELECT extversion FROM pg_extension WHERE extname = 'vector'`,
          );
          if (vrows.length === 0) {
            throw new Error(
              `Migration v40 (facts hot memory) requires the pgvector extension. ` +
              `Install it via\n  CREATE EXTENSION vector;\n` +
              `then re-run \`gbrain apply-migrations --yes\`.`,
            );
          }
          const v = vrows[0].extversion;
          const parts = v.split('.');
          const major = parseInt(parts[0] ?? '0', 10);
          const minor = parseInt(parts[1] ?? '0', 10);
          // HALFVEC introduced in pgvector 0.7.0
          if (major > 0 || (major === 0 && minor >= 7)) {
            useHalfvec = true;
          } else {
            // Fall back to full-precision vector with stderr warning.
            // eslint-disable-next-line no-console
            console.warn(
              `[v40 facts] pgvector ${v} < 0.7 — falling back to VECTOR(${embeddingDim}). ` +
              `HALFVEC space savings unavailable; functionality otherwise identical. ` +
              `Upgrade pgvector to 0.7+ to enable HALFVEC.`,
            );
          }
        } catch (err) {
          // Re-throw the missing-extension error; tolerate other probe failures.
          if (err instanceof Error && err.message.includes('requires the pgvector')) throw err;
          // Probe failed for other reason — assume older pgvector and fall back.
        }
      } else {
        // PGLite: bundled pgvector is recent enough for HALFVEC. Use it.
        useHalfvec = true;
      }

      const vecType = useHalfvec ? 'HALFVEC' : 'VECTOR';
      // HNSW operator class must match the column type:
      //   VECTOR(n)  → vector_cosine_ops
      //   HALFVEC(n) → halfvec_cosine_ops
      const opclass = useHalfvec ? 'halfvec_cosine_ops' : 'vector_cosine_ops';
      // FK to sources is added in a separate ALTER TABLE rather than inline
      // on the column. Inline `REFERENCES` worked on PGLite but silently
      // got dropped by postgres.js's `unsafe()` multi-statement path on
      // Postgres in the v0.31 e2e run (table created without FK; CASCADE
      // delete didn't fire). Splitting the FK declaration out makes the
      // intent explicit and idempotent: the named constraint either
      // exists or doesn't, and the ALTER is a no-op on re-runs.
      const factsDDL = `
        CREATE TABLE IF NOT EXISTS facts (
          id                BIGSERIAL PRIMARY KEY,
          source_id         TEXT        NOT NULL DEFAULT 'default',
          entity_slug       TEXT,
          fact              TEXT        NOT NULL,
          kind              TEXT        NOT NULL DEFAULT 'fact'
                            CHECK (kind IN ('event','preference','commitment','belief','fact')),
          visibility        TEXT        NOT NULL DEFAULT 'private'
                            CHECK (visibility IN ('private','world')),
          notability        TEXT        NOT NULL DEFAULT 'medium'
                            CHECK (notability IN ('high','medium','low')),
          context           TEXT,
          valid_from        TIMESTAMPTZ NOT NULL DEFAULT now(),
          valid_until       TIMESTAMPTZ,
          expired_at        TIMESTAMPTZ,
          superseded_by     BIGINT      REFERENCES facts(id),
          consolidated_at   TIMESTAMPTZ,
          consolidated_into BIGINT,
          source            TEXT        NOT NULL,
          source_session    TEXT,
          confidence        REAL        NOT NULL DEFAULT 1.0
                            CHECK (confidence BETWEEN 0 AND 1),
          embedding         ${vecType}(${embeddingDim}),
          embedded_at       TIMESTAMPTZ,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
          -- v0.32.2 (migration v51): fence round-trip columns. Both nullable
          -- because pre-v0.32 rows didn't have them; the v0_32_2 orchestrator
          -- backfills via fence-append. New rows from the markdown-first
          -- runFactsBackstop/runFactsPipeline paths populate them at insert
          -- time. The partial unique index below enforces (source_id,
          -- source_markdown_slug, row_num) uniqueness only once row_num is
          -- set, so legacy NULL rows don't collide with each other or block
          -- the backfill.
          row_num               INTEGER,
          source_markdown_slug  TEXT
        );

        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'facts_source_id_fkey'
              AND conrelid = 'facts'::regclass
          ) THEN
            ALTER TABLE facts
              ADD CONSTRAINT facts_source_id_fkey
              FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE;
          END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS idx_facts_entity_active
          ON facts(source_id, entity_slug, valid_from DESC)
          WHERE expired_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_facts_session
          ON facts(source_id, source_session, created_at DESC)
          WHERE expired_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_facts_since
          ON facts(source_id, created_at DESC)
          WHERE expired_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_facts_unconsolidated
          ON facts(source_id, entity_slug)
          WHERE consolidated_at IS NULL AND expired_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_facts_embedding_hnsw
          ON facts USING hnsw (embedding ${opclass})
          WHERE embedding IS NOT NULL AND expired_at IS NULL;
      `;

      await engine.runMigration(40, factsDDL);

      // Step 3: enable RLS on Postgres when role has BYPASSRLS (v24/v29 pattern).
      // PGLite has no RLS engine.
      if (engine.kind === 'postgres') {
        await engine.runMigration(40, `
          DO $$
          DECLARE
            has_bypass BOOLEAN;
          BEGIN
            SELECT rolbypassrls INTO has_bypass FROM pg_roles WHERE rolname = current_user;
            IF has_bypass THEN
              ALTER TABLE facts ENABLE ROW LEVEL SECURITY;
            END IF;
          END $$;
        `);
      }
    },
  },
  {
    version: 46,
    name: 'mcp_request_log_params_jsonb_normalize',
    idempotent: true,
    // v0.31.3 wave (D-codex-2 / D1): mcp_request_log.params is JSONB, but
    // pre-v0.31.3 serve-http.ts wrote `JSON.stringify(...)` strings into it
    // via the postgres.js template tag's loose typing. The column was
    // technically JSONB but stored as a JSON-encoded string, so reads via
    // `params->>'op'` returned the encoded string '"search"' instead of
    // 'search'. The /admin/api/requests endpoint returned both shapes raw
    // to the SPA depending on row age.
    //
    // The v0.31.3 commit re-routes those INSERTs through executeRawJsonb,
    // which writes real objects. This one-shot UPDATE lifts existing
    // string-shaped rows up to objects so the read side sees one
    // consistent shape. Idempotent: subsequent runs find no rows where
    // jsonb_typeof = 'string' and the UPDATE is a no-op.
    //
    // `params #>> '{}'` extracts the underlying string at the top level,
    // then ::jsonb re-parses it as JSON. The `WHERE` filter guards against
    // running on already-object rows AND limits the unwrap to strings that
    // start with `{` (object-shaped) so a malformed legacy string can't
    // abort the migration.
    sql: `
      UPDATE mcp_request_log
        SET params = (params #>> '{}')::jsonb
        WHERE jsonb_typeof(params) = 'string'
          AND params #>> '{}' LIKE '{%';
    `,
  },
  {
    version: 47,
    name: 'facts_notability_alter',
    // v0.31.2 (B2 ship-blocker fix). Renumbered from v46 → v47 after the
    // merge from master picked up v0.31.3's mcp_request_log_params_jsonb_normalize
    // at v46. facts.notability column shipped via v45's inline CREATE TABLE
    // on fresh installs, but every brain that ran v45 BEFORE notability
    // landed in v45's blob is now missing the column. INSERT crashes with
    // "column does not exist" on first sync after upgrade.
    //
    // This migration is the ALTER counterpart for those existing brains.
    // Idempotent under all states:
    //   - Fresh install (v45 already added column): ADD COLUMN IF NOT EXISTS
    //     no-ops; named CHECK probe finds existing constraint → skip.
    //   - Old brain (no column): ADD COLUMN adds it with NOT NULL DEFAULT;
    //     named CHECK probe finds nothing → adds CHECK.
    //   - Partial state (column exists, no CHECK): ADD COLUMN no-ops;
    //     CHECK probe adds the named constraint.
    //
    // CHECK constraint is named `facts_notability_check` (named, not autogen)
    // so the idempotency probe can find it deterministically. If v45 inline
    // already created an autogen CHECK with identical semantics, the named
    // one is additive and non-conflicting (Postgres allows multiple CHECKs
    // covering the same predicate).
    //
    // Both engines run the same SQL — PGLite is real Postgres in WASM and
    // supports DO $$ blocks. PGLite users with older persistent brains hit
    // the same bug.
    sql: `
      ALTER TABLE facts ADD COLUMN IF NOT EXISTS notability TEXT NOT NULL DEFAULT 'medium';

      DO $$ BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint
          WHERE conname = 'facts_notability_check'
            AND conrelid = 'facts'::regclass
        ) THEN
          ALTER TABLE facts ADD CONSTRAINT facts_notability_check
            CHECK (notability IN ('high','medium','low'));
        END IF;
      END $$;
    `,
  },
];
