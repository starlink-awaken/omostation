// --- Search ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { sourceScopeOpts } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";
import { hybridSearch, hybridSearchCached } from "../search/hybrid";
import { expandQuery } from "../search/expansion";
import { dedupResults } from "../search/dedup";
import { captureEvalCandidate } from "../eval-capture";
import {
  SEARCH_DESCRIPTION,
  QUERY_DESCRIPTION,
} from "../operations-descriptions";
import type { HybridSearchMeta } from "../types";
import { isEvalCaptureEnabled, isEvalScrubEnabled } from "../eval-capture";
import { bumpLastRetrievedAt } from "../last-retrieved";

export const search: Operation = {
  name: 'search',
  description: SEARCH_DESCRIPTION,
  params: {
    query: { type: 'string', required: true },
    limit: { type: 'number', description: 'Max results (default 20)' },
    offset: { type: 'number', description: 'Skip first N results (for pagination)' },
  },
  handler: async (ctx, p) => {
    const startedAt = Date.now();
    const queryText = p.query as string;
    // v0.34.1 (#861 — P0 leak seal): thread caller's source scope into
    // searchKeyword. Pre-fix this op silently returned cross-source hits
    // for any auth'd OAuth client.
    const raw = await ctx.engine.searchKeyword(queryText, {
      limit: (p.limit as number) || 20,
      offset: (p.offset as number) || 0,
      ...sourceScopeOpts(ctx),
    });
    const results = dedupResults(raw);
    const latency_ms = Date.now() - startedAt;

    // v0.37.0 (D11): op-layer last_retrieved_at write-back. Fire-and-forget;
    // results already returned by engine, this just marks them as user-surfaced
    // for LSD's stale-page signal. 5-min throttle inside bumpLastRetrievedAt.
    bumpLastRetrievedAt(ctx.engine, results.map((r) => r.page_id));

    // Op-layer capture (v0.25.0). Fire-and-forget — no await on the
    // capture call so MCP response latency is unaffected. search has
    // no expand/detail/vector semantics so meta fields are fixed.
    if (isEvalCaptureEnabled(ctx.config)) {
      void captureEvalCandidate(
        ctx.engine,
        {
          tool_name: 'search',
          query: queryText,
          results,
          meta: { vector_enabled: false, detail_resolved: null, expansion_applied: false },
          latency_ms,
          remote: ctx.remote ?? false,
          expand_enabled: null,
          detail: null,
          job_id: ctx.jobId ?? null,
          subagent_id: ctx.subagentId ?? null,
        },
        { scrub_pii: isEvalScrubEnabled(ctx.config) },
      );
    }

    return results;
  },
  scope: 'read',
  cliHints: { name: 'search', positional: ['query'] },
};

export const query: Operation = {
  name: 'query',
  description: QUERY_DESCRIPTION,
  params: {
    // v0.27.1: `query` is no longer strictly required — `--image <path>`
    // is the alternative entry point for image-similarity search. The CLI
    // validator at src/cli.ts honors `cliHints.altRequired` and admits the
    // image-only invocation. MCP / programmatic callers must still pass
    // `query` OR `image` (handler refuses if both are absent).
    query: { type: 'string', required: false },
    /** v0.27.1: image-similarity search. Path resolved on the CLI side
     *  before the op fires (the op receives raw bytes neither side; the
     *  CLI loads the file, base64-encodes, and passes through `image`). */
    image: { type: 'string', description: 'Base64-encoded image bytes for image-similarity search (CLI: --image <path>).' },
    image_mime: { type: 'string', description: 'MIME type for the image bytes (auto-derived from path on CLI; required when calling op directly).' },
    limit: { type: 'number', description: 'Max results (default 20)' },
    offset: { type: 'number', description: 'Skip first N results (for pagination)' },
    expand: { type: 'boolean', description: 'Enable multi-query expansion (default: true)' },
    detail: { type: 'string', description: 'Result detail level: low (compiled truth only), medium (default, all with dedup), high (all chunks)' },
    // v0.20.0 Cathedral II Layer 10 C1/C2: language + symbol-kind filters.
    lang: { type: 'string', description: 'Filter to chunks where content_chunks.language matches (e.g., typescript, python, ruby)' },
    symbol_kind: { type: 'string', description: 'Filter to chunks where content_chunks.symbol_type matches (e.g., function, class, method, type, interface)' },
    // v0.20.0 Cathedral II Layer 7 (A2) / Layer 10 C3: two-pass structural expansion.
    near_symbol: { type: 'string', description: 'Anchor retrieval at this qualified symbol name (e.g., BrainEngine.searchKeyword). Enables A2 two-pass.' },
    walk_depth: { type: 'number', description: 'Structural walk depth 1-2. Default 0 (off). Expands anchors through code_edges with 1/(1+hop) decay.' },
    // v0.29.1 — orthogonal recency + salience axes. YOU (the agent) decide.
    salience: {
      type: 'string',
      enum: ['off', 'on', 'strong'],
      description:
        "v0.29.1 salience boost — emotional_weight + take_count, NO time component.\n" +
        "  'off' — default for entity / canonical / definitional queries\n" +
        "  'on'  — surface emotionally-weighted + take-rich pages\n" +
        "  'strong' — aggressive mattering tilt\n" +
        "Omit and gbrain auto-detects from query text. Independent of `recency`.",
    },
    recency: {
      type: 'string',
      enum: ['off', 'on', 'strong'],
      description:
        "v0.29.1 recency boost — per-prefix age decay, NO mattering signal.\n" +
        "  'off' — default for canonical truth\n" +
        "  'on'  — daily/, media/x/, chat/ decay aggressively; concepts/, originals/, writing/ stay evergreen\n" +
        "  'strong' — multiplies the recency factor by 1.5 (use for 'today' / 'right now')\n" +
        "Omit and gbrain auto-detects. Independent of `salience` (orthogonal axes).",
    },
    since: {
      type: 'string',
      description:
        "v0.29.1 — filter to pages whose effective_date is >= this. ISO-8601 (YYYY-MM-DD or full timestamp) OR relative ('7d', '2w', '1y'). Replaces deprecated `afterDate`.",
    },
    until: {
      type: 'string',
      description:
        "v0.29.1 — filter to effective_date <= this. Same format as `since`. Replaces deprecated `beforeDate`. YYYY-MM-DD lands at end-of-day.",
    },
    source_id: {
      type: 'string',
      description:
        "v0.34: scope search to a single source. Defaults to OperationContext.sourceId (set from CLI --source / GBRAIN_SOURCE / .gbrain-source dotfile). Pass '__all__' to force cross-source search in multi-source brains.",
    },
    cross_modal: {
      type: 'string',
      enum: ['text', 'image', 'both', 'auto'],
      description:
        "v0.36 cross-modal search routing.\n" +
        "  'text' (default for non-image-intent queries) — text-only path, no behavior change vs v0.35.\n" +
        "  'image' — route the query through Voyage multimodal-3 + the embedding_image column. Best for 'show me photos of...' phrasings.\n" +
        "  'both' — run text AND image searches in parallel; merge via weighted RRF.\n" +
        "  'auto' — same effect as omitting the field; intent classifier decides based on query phrasing.",
    },
    embedding_column: {
      type: 'string',
      description:
        "v0.36: route vector search through a non-default embedding column. Defaults to 'embedding' (OpenAI 1536d) unless `search_embedding_column` config sets a different default. Per-call override for A/B benchmarking across providers (e.g. 'embedding_voyage', 'embedding_zeroentropy'). Column MUST be declared in the `embedding_columns` config registry — unknown names throw with a paste-ready hint listing valid columns.",
    },
  },
  handler: async (ctx, p) => {
    const startedAt = Date.now();
    const expand = p.expand !== false;
    const detail = (p.detail as 'low' | 'medium' | 'high') || undefined;
    const queryText = p.query as string | undefined;
    const imageData = p.image as string | undefined;
    const imageMime = (p.image_mime as string) || 'image/jpeg';
    const embeddingColumnParam =
      typeof p.embedding_column === 'string' && p.embedding_column.length > 0
        ? (p.embedding_column as string)
        : undefined;
    // Explicit per-call source_id must win over ctx.sourceId. The special
    // __all__ value opts out of source filtering for local cross-source search.
    const sourceIdParam = typeof p.source_id === 'string' ? p.source_id : undefined;
    const querySourceScope =
      sourceIdParam !== undefined
        ? sourceIdParam === '__all__'
          ? {}
          : { sourceId: sourceIdParam }
        : sourceScopeOpts(ctx);

    // v0.27.1: image-similarity branch. Bypasses hybridSearch (which is
    // text-only); embeds the image via embedMultimodal and runs a direct
    // vector search against the embedding_image column.
    if (imageData) {
      const { embedMultimodal } = await import('../ai/gateway.ts');
      const [vec] = await embedMultimodal([
        { kind: 'image_base64', data: imageData, mime: imageMime },
      ]);
      // v0.34.1 (#861 F2 — 6th leak surface): the image path bypasses
      // hybridSearch and calls searchVector directly, so it needs its
      // own thread of the source scope. Pre-fix, this branch leaked
      // image pages across sources independent of the text path's fix.
      const results = await ctx.engine.searchVector(vec, {
        limit: (p.limit as number) || 20,
        offset: (p.offset as number) || 0,
        embeddingColumn: 'embedding_image',
        ...querySourceScope,
      });
      return results;
    }

    if (!queryText) {
      throw new Error('query requires either `query` (text) or `image` (base64 bytes).');
    }

    // v0.25.0 — capture meta side-channel. hybridSearch's return contract
    // stays SearchResult[] (Cathedral II callers depend on that); meta
    // arrives via callback so eval capture can record what actually ran.
    //
    // v0.34 (Codex finding #2): thread ctx.sourceId so multi-source brains
    // get source-scoped retrieval. Explicit `source_id` param wins over
    // ctx.sourceId for callers that want to override (per-call multi-source
    // search). When the param is the literal '__all__', force-allow
    // cross-source mode (matches SearchOpts.sourceId contract).
    let capturedMeta: HybridSearchMeta | null = null;
    // v0.32.x search-lite: route the query op through hybridSearchCached so
    // semantic cache + token budget + intent weighting fire automatically.
    // Plain hybridSearch remains the bare API for callers that opt out.
    const results = await hybridSearchCached(ctx.engine, queryText, {
      limit: (p.limit as number) || 20,
      offset: (p.offset as number) || 0,
      expansion: expand,
      expandFn: expand ? expandQuery : undefined,
      detail,
      language: (p.lang as string) || undefined,
      symbolKind: (p.symbol_kind as string) || undefined,
      nearSymbol: (p.near_symbol as string) || undefined,
      walkDepth: typeof p.walk_depth === 'number' ? (p.walk_depth as number) : undefined,
      ...querySourceScope,
      // v0.29.1 — agent-explicit recency + salience. Omitted = heuristic defaults.
      salience: p.salience as 'off' | 'on' | 'strong' | undefined,
      recency: p.recency as 'off' | 'on' | 'strong' | undefined,
      since: typeof p.since === 'string' ? p.since : undefined,
      until: typeof p.until === 'string' ? p.until : undefined,
      // v0.32.x search-lite: token budget + cache opt-outs.
      tokenBudget: typeof p.token_budget === 'number' ? (p.token_budget as number) : undefined,
      useCache: typeof p.use_cache === 'boolean' ? (p.use_cache as boolean) : undefined,
      intentWeighting: typeof p.intent_weighting === 'boolean' ? (p.intent_weighting as boolean) : undefined,
      // v0.36 cross-modal routing param.
      crossModal: p.cross_modal as 'text' | 'image' | 'both' | 'auto' | undefined,
      onMeta: (m) => { capturedMeta = m; },
      // v0.36 (D15): per-call embedding column override. Resolver rejects
      // unknown names at hybrid entry with EmbeddingColumnNotRegisteredError;
      // the error surfaces back to the agent as the op error envelope.
      // Source scope is already threaded via ...querySourceScope above
      // (master's #1182 cleanup of the duplicate sourceScopeOpts spread).
      embeddingColumn: embeddingColumnParam,
    });
    const latency_ms = Date.now() - startedAt;

    // v0.37.0 (D11): op-layer last_retrieved_at write-back. Same shape as the
    // search handler — fire-and-forget, internal callers bypass this path.
    bumpLastRetrievedAt(ctx.engine, results.map((r) => r.page_id));

    // Op-layer capture (v0.25.0). Fire-and-forget. meta tells gbrain-evals
    // what hybridSearch *actually* did so replay can distinguish "with API
    // key" from "keyword-only fallback" and "expansion fired" from
    // "expansion requested + silently fell back."
    if (isEvalCaptureEnabled(ctx.config)) {
      const meta: HybridSearchMeta = capturedMeta ?? {
        vector_enabled: false, detail_resolved: detail ?? null, expansion_applied: false,
      };
      void captureEvalCandidate(
        ctx.engine,
        {
          tool_name: 'query',
          query: queryText,
          results,
          meta,
          latency_ms,
          remote: ctx.remote ?? false,
          expand_enabled: expand,
          detail: detail ?? null,
          job_id: ctx.jobId ?? null,
          subagent_id: ctx.subagentId ?? null,
        },
        { scrub_pii: isEvalScrubEnabled(ctx.config) },
      );
    }

    return results;
  },
  scope: 'read',
  cliHints: { name: 'query', positional: ['query'] },
};

