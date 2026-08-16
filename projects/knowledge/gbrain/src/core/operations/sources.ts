// --- v0.28: whoami + sources management ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { OperationError } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";
import { buildMemoryTree, getMemoryTreeStats, pinMemoryTreeNodes } from "../memory-tree";
import {
  CODE_CALLERS_DESCRIPTION,
  CODE_CALLEES_DESCRIPTION,
  CODE_DEF_DESCRIPTION,
  CODE_REFS_DESCRIPTION,
} from "../operations-descriptions";

export const whoami: Operation = {
  name: 'whoami',
  description:
    'Introspect the calling identity. Returns one of three transport shapes: ' +
    '{transport: "oauth", client_id, client_name, scopes, expires_at}, ' +
    '{transport: "legacy", token_name, scopes, expires_at: null}, or ' +
    '{transport: "local", scopes: []}. Throws unknown_transport when the ' +
    'context is ambiguous (remote=true without auth) — fail-closed posture ' +
    'mirroring the v0.26.9 trust-boundary contract.',
  params: {},
  scope: 'read',
  handler: async (ctx) => {
    // Trust boundary: ctx.remote === false is the trusted local CLI surface.
    // Returning OAuth-shaped scopes here would resurrect the v0.26.9 footgun
    // where code conditionally trusted on `scopes.includes('admin')` instead
    // of `ctx.remote === false`. Empty scopes array forces clients to
    // special-case `transport: 'local'` explicitly.
    if (ctx.remote === false) {
      return { transport: 'local', scopes: [] };
    }
    if (!ctx.auth) {
      throw new OperationError(
        'unknown_transport',
        'whoami called over a remote transport that did not thread ctx.auth. ' +
          'This is a transport bug — every remote call site must populate ctx.auth ' +
          'or set ctx.remote === false.',
      );
    }
    // OAuth tokens have client_id starting with 'gbrain_cl_'; legacy
    // access_tokens reuse `name` as both clientId and clientName (verifyAccessToken
    // at oauth-provider.ts:417-430). Detect by inspecting the prefix.
    const isOauth = ctx.auth.clientId.startsWith('gbrain_cl_');
    if (isOauth) {
      return {
        transport: 'oauth',
        client_id: ctx.auth.clientId,
        client_name: ctx.auth.clientName ?? ctx.auth.clientId,
        scopes: ctx.auth.scopes,
        expires_at: ctx.auth.expiresAt ?? null,
      };
    }
    return {
      transport: 'legacy',
      token_name: ctx.auth.clientName ?? ctx.auth.clientId,
      scopes: ctx.auth.scopes,
      expires_at: null,
    };
  },
  cliHints: { name: 'whoami' },
};

export const sources_add: Operation = {
  name: 'sources_add',
  description:
    'Register a new source. Supports either --path (existing v0.17 behavior) ' +
    'or --url (v0.28 federated remote-clone path: parses the URL through the ' +
    'SSRF gate, clones into $GBRAIN_HOME/clones/<id>/ via temp-dir + rename ' +
    'atomicity, and stores remote_url in sources.config). Pre-flight collision ' +
    'check on id; rollback on either-side failure.',
  params: {
    id: {
      type: 'string',
      required: true,
      description: 'Source id ([a-z0-9-]{1,32}). Immutable citation key.',
    },
    name: { type: 'string', description: 'Display name (defaults to id).' },
    path: { type: 'string', description: 'Local path. Mutually optional with url.' },
    url: {
      type: 'string',
      description:
        'HTTPS git URL. Cloned into $GBRAIN_HOME/clones/<id>/. SSRF-guarded.',
    },
    federated: {
      type: 'boolean',
      description: 'true → cross-source default search. false → isolated.',
    },
    clone_dir: {
      type: 'string',
      description:
        'Override clone destination (only valid with url). Default: $GBRAIN_HOME/clones/<id>/.',
    },
  },
  mutating: true,
  scope: 'sources_admin',
  handler: async (ctx, p) => {
    const { addSource } = await import('../sources-ops.ts');

    // v0.28.1 codex finding (CRITICAL + HIGH): a `sources_admin` token over
    // HTTP MCP must not be able to plant content at arbitrary host paths.
    //
    // - `path` lets a remote caller register `/etc/` (or any host dir) as a
    //   "source"; later `gbrain sync --all` walks every sources.local_path,
    //   which exfiltrates host content into the brain.
    // - `clone_dir` lets a remote caller name the destination directly;
    //   addSource's renameSync places the cloned tree there with no
    //   confinement, AND validateRepoState's degraded-state recovery later
    //   does rm -rf on src.local_path, so the same primitive doubles as
    //   arbitrary-delete.
    //
    // Both fields are CLI-only (the operator runs `gbrain sources add --path
    // /home/me/notes`). For HTTP MCP, ignore overrides — clone_dir defaults
    // to $GBRAIN_HOME/clones/<id>/ and path is rejected. Local CLI callers
    // (ctx.remote === false, per F7b fail-closed contract) keep the override.
    const isLocal = ctx.remote === false;
    const remotePath = isLocal ? (p.path as string | undefined) ?? null : null;
    const remoteCloneDir = isLocal ? (p.clone_dir as string | undefined) : undefined;
    if (!isLocal && (p.path !== undefined || p.clone_dir !== undefined)) {
      ctx.logger.warn(
        '[sources_add] ignoring path/clone_dir overrides on HTTP MCP transport ' +
          '(remote callers can only register a remote --url; the clone path is ' +
          'fixed under $GBRAIN_HOME/clones/).',
      );
    }

    const row = await addSource(ctx.engine, {
      id: p.id as string,
      name: p.name as string | undefined,
      localPath: remotePath,
      remoteUrl: p.url as string | undefined,
      federated:
        p.federated === undefined ? null : (p.federated as boolean),
      cloneDir: remoteCloneDir,
    });
    return row;
  },
  cliHints: { name: 'sources_add', hidden: true },
};

export const sources_list: Operation = {
  name: 'sources_list',
  description:
    'List registered sources with page counts and remote_url. v0.28 surfaces ' +
    'the new remote_url field so a remote MCP caller can confirm a source is ' +
    'managed by clone+pull rather than user-supplied path.',
  params: {
    include_archived: { type: 'boolean', description: 'Include soft-deleted sources.' },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const { listSources } = await import('../sources-ops.ts');
    return {
      sources: await listSources(ctx.engine, {
        includeArchived: (p.include_archived as boolean) === true,
      }),
    };
  },
  cliHints: { name: 'sources_list', hidden: true },
};

export const sources_remove: Operation = {
  name: 'sources_remove',
  description:
    'Hard-remove a source (cascades pages/chunks/embeddings). Refuses to ' +
    'delete the auto-managed clone dir unless its resolved path is confined ' +
    'under $GBRAIN_HOME/clones/ (realpath+lstat — symlink-safe). For most ' +
    'workflows prefer sources_archive for the soft-delete path.',
  params: {
    id: { type: 'string', required: true },
    confirm_destructive: {
      type: 'boolean',
      description:
        'Required when the source has data (pages, chunks). Without it the op refuses.',
    },
    dry_run: { type: 'boolean', description: 'Preview impact without side effects.' },
    keep_storage: {
      type: 'boolean',
      description: 'Skip clone-dir cleanup even when the source is auto-managed.',
    },
  },
  mutating: true,
  scope: 'sources_admin',
  handler: async (ctx, p) => {
    const { removeSource } = await import('../sources-ops.ts');
    return removeSource(ctx.engine, {
      id: p.id as string,
      confirmDestructive: (p.confirm_destructive as boolean) === true,
      dryRun: (p.dry_run as boolean) === true || ctx.dryRun,
      keepStorage: (p.keep_storage as boolean) === true,
    });
  },
  cliHints: { name: 'sources_remove', hidden: true },
};

export const sources_status: Operation = {
  name: 'sources_status',
  description:
    'Per-source diagnostic. Returns clone_state ("healthy" | "missing" | ' +
    '"not-a-dir" | "no-git" | "url-drift" | "corrupted" | "not-applicable") ' +
    'so a remote MCP caller can diagnose whether the on-disk clone is ' +
    'syncable without SSH access to the brain host.',
  params: {
    id: { type: 'string', required: true },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const { getSourceStatus } = await import('../sources-ops.ts');
    return getSourceStatus(ctx.engine, p.id as string);
  },
  cliHints: { name: 'sources_status', hidden: true },
};

// ============================================================
// v0.31 — Hot memory ops: extract_facts / recall / forget_fact
// ============================================================

export const extract_facts: Operation = {
  name: 'extract_facts',
  description:
    'v0.31: extract personal-knowledge facts (events, preferences, commitments, beliefs) from a conversation turn into the per-source hot memory. Sanitizes turn_text via INJECTION_PATTERNS, calls Haiku to extract structured claims, runs the cosine fast-path + classifier dedup pipeline, INSERTs into facts. Returns counts by status. Skips extraction when the turn is dream-generated content (anti-loop).',
  params: {
    turn_text: { type: 'string', required: true, description: 'The user message or page body to extract facts from. Sanitized via INJECTION_PATTERNS before the LLM call.' },
    session_id: { type: 'string', description: 'Opaque session id (e.g. topic-id from MCP _meta.session_id, or CLI --session). Stored on each fact for the recall --session filter. Not an auth surface.' },
    entity_hints: { type: 'array', items: { type: 'string' }, description: 'Existing canonical entity slugs the agent has already resolved. Helps the extractor pick the right slug.' },
    is_dream_generated: { type: 'boolean', description: 'When true, extraction is skipped (anti-loop). Caller flips this on for pages with dream_generated:true frontmatter.' },
    visibility: { type: 'string', description: 'Default visibility for extracted facts. private (default) | world.' },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'extract_facts' };
    const { isFactsExtractionEnabled } = await import('../facts/extract.ts');
    const { runFactsPipeline } = await import('../facts/backstop.ts');

    // D15: kill switch. Operator can disable facts extraction across the
    // brain without binary downgrade by setting `facts.extraction_enabled`
    // to false. Returns zero-counts envelope so callers see a clean
    // success rather than a 'permission_denied' false alarm.
    if (!(await isFactsExtractionEnabled(ctx.engine))) {
      return { inserted: 0, duplicate: 0, superseded: 0, fact_ids: [], skipped: 'extraction_disabled' };
    }

    // v0.31.2: routed through the shared pipeline (PR1 commit 9). Anti-loop
    // dream-generated check stays at the op layer because extract_facts is
    // an explicit user op without a parsedPage — the eligibility predicate
    // doesn't apply, but the dream-generated guard still does.
    if (p.is_dream_generated === true) {
      return { inserted: 0, duplicate: 0, superseded: 0, fact_ids: [], skipped: 'dream_generated' };
    }

    const sourceId = ctx.sourceId ?? 'default';
    const visibility: 'private' | 'world' = p.visibility === 'world' ? 'world' : 'private';

    const r = await runFactsPipeline(p.turn_text as string, {
      engine: ctx.engine,
      sourceId,
      sessionId: typeof p.session_id === 'string' ? p.session_id : null,
      entityHints: Array.isArray(p.entity_hints) ? (p.entity_hints as string[]) : undefined,
      source: 'mcp:extract_facts',
      visibility,
      mode: 'inline',  // declarative; runFactsPipeline always inline
    });

    return {
      inserted: r.inserted,
      duplicate: r.duplicate,
      superseded: r.superseded,
      fact_ids: r.fact_ids,
    };
  },
};

export const recall: Operation = {
  name: 'recall',
  description:
    'v0.31: query per-source hot memory (facts table). Filters by entity / since / session. Remote callers see only visibility=world facts. Returns most-recent first. v0.32 adds optional include_pending to return pending_consolidation_count alongside facts in one round trip.',
  params: {
    entity: { type: 'string', description: 'Entity slug (canonical). Returns facts about this entity newest first.' },
    since: { type: 'string', description: 'ISO datetime or duration shorthand (e.g. "8 hours ago"). Returns facts created since.' },
    session_id: { type: 'string', description: 'Source session id (e.g. topic-A). Returns facts captured in that session.' },
    include_expired: { type: 'boolean', description: 'When true, include expired_at IS NOT NULL rows. Default false.' },
    supersessions: { type: 'boolean', description: 'When true, return only the supersession audit log (expired_at + superseded_by both set).' },
    limit: { type: 'number', description: 'Max rows to return. Default 50, cap 100.' },
    grep: { type: 'string', description: 'Substring filter on fact text (case-insensitive). Applied client-side after recall.' },
    include_pending: { type: 'boolean', description: 'v0.32: when true, response includes pending_consolidation_count (facts not yet promoted to takes by the dream-cycle consolidate phase). One round trip; backward-compatible (field omitted when false).' },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const sourceId = ctx.sourceId ?? 'default';
    const limit = typeof p.limit === 'number' ? p.limit : 50;
    const includeExpired = p.include_expired === true;
    const grep = typeof p.grep === 'string' ? p.grep.toLowerCase() : null;

    // Visibility filter: remote callers see world-only unless their token
    // grants elevated visibility (future-proofing; v0.31 ships world-only
    // for remote, all for local CLI).
    const visibility =
      ctx.remote === false
        ? undefined
        : ['world'] as ('private' | 'world')[];

    let rows: Awaited<ReturnType<typeof ctx.engine.listFactsByEntity>> = [];

    if (p.supersessions === true) {
      const since = parseSinceParam(p.since);
      rows = await ctx.engine.listSupersessions(sourceId, { since: since ?? undefined, limit });
    } else if (typeof p.entity === 'string' && p.entity.length > 0) {
      const { resolveEntitySlug } = await import('../entities/resolve.ts');
      const slug = (await resolveEntitySlug(ctx.engine, sourceId, p.entity)) ?? p.entity;
      rows = await ctx.engine.listFactsByEntity(sourceId, slug, {
        activeOnly: !includeExpired,
        limit,
        visibility,
      });
    } else if (typeof p.session_id === 'string' && p.session_id.length > 0) {
      rows = await ctx.engine.listFactsBySession(sourceId, p.session_id, {
        activeOnly: !includeExpired,
        limit,
        visibility,
      });
    } else if (p.since !== undefined) {
      const since = parseSinceParam(p.since);
      if (since) {
        rows = await ctx.engine.listFactsSince(sourceId, since, {
          activeOnly: !includeExpired,
          limit,
          visibility,
        });
      }
    } else {
      // No filter: return recent across the source.
      rows = await ctx.engine.listFactsSince(sourceId, new Date(0), {
        activeOnly: !includeExpired,
        limit,
        visibility,
      });
    }

    if (grep) rows = rows.filter(r => r.fact.toLowerCase().includes(grep));

    // v0.32: optional pending-consolidation count piggy-backed on the recall
    // response. Single round trip on thin-client; omitted when not requested
    // so existing callers see no shape change.
    let pending_consolidation_count: number | undefined;
    if (p.include_pending === true) {
      try {
        pending_consolidation_count = await ctx.engine.countUnconsolidatedFacts(sourceId);
      } catch (e) {
        // Best-effort: if the count query fails we still return facts. Field
        // stays undefined so callers can tell the difference between "0
        // pending" and "we couldn't ask."
        process.stderr.write(
          `[recall] countUnconsolidatedFacts failed: ${(e as Error).message}\n`,
        );
      }
    }

    return {
      facts: rows.map(r => ({
        id: r.id,
        fact: r.fact,
        kind: r.kind,
        entity_slug: r.entity_slug,
        visibility: r.visibility,
        // v0.31.2: notability surfaced to recall consumers (CLI, MCP, admin).
        // Pre-v46 brains return 'medium' via the row mapper's fallback so the
        // contract stays total.
        notability: r.notability,
        valid_from: r.valid_from.toISOString(),
        valid_until: r.valid_until?.toISOString() ?? null,
        expired_at: r.expired_at?.toISOString() ?? null,
        superseded_by: r.superseded_by,
        consolidated_at: r.consolidated_at?.toISOString() ?? null,
        consolidated_into: r.consolidated_into,
        source: r.source,
        source_session: r.source_session,
        confidence: r.confidence,
        created_at: r.created_at.toISOString(),
      })),
      total: rows.length,
      ...(pending_consolidation_count !== undefined ? { pending_consolidation_count } : {}),
    };
  },
};

export const forget_fact: Operation = {
  name: 'forget_fact',
  description: 'v0.32.2: forget a fact. Rewrites the page\'s `## Facts` fence to strike through the row and set valid_until=today (the DB\'s expired_at derives via valid_until + now() on the next reconcile so the forget survives `gbrain rebuild`). Falls back to legacy DB-only expire for pre-v51 / thin-client rows. Idempotent on already-expired or unknown ids.',
  params: {
    id: { type: 'number', required: true, description: 'Fact id to forget.' },
    reason: { type: 'string', required: false, description: 'Optional reason; written to the fence row\'s context cell as "forgotten: <reason>". Default: "forgotten".' },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'forget_fact', id: p.id };
    const id = p.id as number;
    const reason = typeof p.reason === 'string' ? p.reason : undefined;
    const { forgetFactInFence } = await import('../facts/forget.ts');
    const result = await forgetFactInFence(ctx.engine, id, { reason });
    if (!result.ok && result.path === 'not_found') {
      throw new OperationError('fact_not_found', `Fact id ${id} not found.`);
    }
    if (!result.ok && result.path === 'already_expired') {
      throw new OperationError('fact_already_expired', `Fact id ${id} already expired.`);
    }
    return { id, expired: true, path: result.path, reason: result.reason };
  },
};

export const memory_tree: Operation = {
  name: 'memory_tree',
  description: 'Build, pin, and inspect a rooted memory tree spanning entities, pages, and hot facts.',
  params: {
    action: { type: 'string', required: true, description: 'search | pin | stats', enum: ['search', 'pin', 'stats'] },
    query: { type: 'string', description: 'Search query used to build the tree.' },
    limit: { type: 'number', description: 'Max number of pages/facts to include in search mode.' },
    node_ids: {
      type: 'array',
      description: 'Node ids to persist as pinned memory anchors.',
      items: { type: 'string' },
    },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const args = ((p ?? (ctx as OperationContext & { args?: Record<string, unknown> }).args) ?? {}) as Record<string, unknown>;
    const action = String(args.action ?? 'search');
    if (action === 'pin') {
      const nodeIds = Array.isArray(args.node_ids) ? args.node_ids.filter((value): value is string => typeof value === 'string') : [];
      const pinned = await pinMemoryTreeNodes(ctx.engine, nodeIds);
      return { action, pinned };
    }
    if (action === 'stats') {
      return { action, ...(await getMemoryTreeStats(ctx.engine)) };
    }
    const query = String(args.query ?? '');
    const limit = typeof args.limit === 'number' ? args.limit : 10;
    return {
      action: 'search',
      query,
      tree: await buildMemoryTree(ctx.engine, query, limit),
    };
  },
};

/**
 * Parse a `since` parameter into a Date. Accepts ISO 8601, plain duration
 * shorthand ("8 hours ago", "3 days ago", "30m", "1h", "2d", "7d"), or
 * Unix epoch millis. Returns null on unparseable input.
 */
function parseSinceParam(raw: unknown): Date | null {
  if (raw == null) return null;
  if (typeof raw === 'number' && Number.isFinite(raw)) return new Date(raw);
  if (typeof raw !== 'string') return null;
  const s = raw.trim();
  if (!s) return null;

  // Try ISO first.
  const iso = Date.parse(s);
  if (Number.isFinite(iso)) return new Date(iso);

  // "N (minutes|hours|days) ago" or compact forms.
  const ago = s.match(/^(\d+)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|days?)(?:\s+ago)?$/i);
  if (ago) {
    const n = parseInt(ago[1], 10);
    const unit = ago[2].toLowerCase();
    const ms =
      unit.startsWith('s') ? n * 1000 :
      unit.startsWith('m') ? n * 60 * 1000 :
      unit.startsWith('h') ? n * 60 * 60 * 1000 :
      n * 24 * 60 * 60 * 1000;
    return new Date(Date.now() - ms);
  }
  return null;
}

// ──────────────────────────────────────────────────────────────────────────────
// v0.34 Cathedral III — code-intelligence ops (MCP-exposed).
//
// Pre-v0.34 code-callers / code-callees / code-def / code-refs lived only in
// the CLI_ONLY set at cli.ts:30 — agents calling gbrain via MCP couldn't reach
// them and fell through to text search. These wrappers expose the existing
// engine + library functions to the MCP surface with resolver-grade
// descriptions (operations-descriptions.ts) so agents route to them
// automatically during plan-mode.
//
// All four are scope:'read'. Source-scoped via ctx.sourceId when set.
// Both `source_id` and `all_sources` are params so per-call overrides work.
// ──────────────────────────────────────────────────────────────────────────────

export const code_callers: Operation = {
  name: 'code_callers',
  description: CODE_CALLERS_DESCRIPTION,
  params: {
    symbol: { type: 'string', required: true, description: 'Symbol to find callers of (bare or qualified name).' },
    limit: { type: 'number', description: 'Max edges returned. Default 100.' },
    source_id: { type: 'string', description: "Scope to a single source. Defaults to ctx.sourceId; pass '__all__' to force cross-source." },
    all_sources: { type: 'boolean', description: 'Force cross-source search (equivalent to source_id=__all__).' },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const symbol = p.symbol as string;
    const limit = (p.limit as number) ?? 100;
    const allSourcesParam = p.all_sources === true;
    const sourceIdParam = typeof p.source_id === 'string' ? p.source_id : undefined;
    const allSources = allSourcesParam || sourceIdParam === '__all__';
    const sourceId = allSources
      ? undefined
      : sourceIdParam !== undefined
        ? sourceIdParam
        : ctx.sourceId;
    const edges = await ctx.engine.getCallersOf(symbol, {
      limit,
      allSources,
      sourceId,
    });
    return { symbol, count: edges.length, callers: edges };
  },
  cliHints: { name: 'code_callers', hidden: true },
};

export const code_callees: Operation = {
  name: 'code_callees',
  description: CODE_CALLEES_DESCRIPTION,
  params: {
    symbol: { type: 'string', required: true, description: 'Symbol to find callees of (bare or qualified name).' },
    limit: { type: 'number', description: 'Max edges returned. Default 100.' },
    source_id: { type: 'string', description: "Scope to a single source. Defaults to ctx.sourceId; pass '__all__' to force cross-source." },
    all_sources: { type: 'boolean', description: 'Force cross-source search.' },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const symbol = p.symbol as string;
    const limit = (p.limit as number) ?? 100;
    const allSourcesParam = p.all_sources === true;
    const sourceIdParam = typeof p.source_id === 'string' ? p.source_id : undefined;
    const allSources = allSourcesParam || sourceIdParam === '__all__';
    const sourceId = allSources
      ? undefined
      : sourceIdParam !== undefined
        ? sourceIdParam
        : ctx.sourceId;
    const edges = await ctx.engine.getCalleesOf(symbol, {
      limit,
      allSources,
      sourceId,
    });
    return { symbol, count: edges.length, callees: edges };
  },
  cliHints: { name: 'code_callees', hidden: true },
};

export const code_def: Operation = {
  name: 'code_def',
  description: CODE_DEF_DESCRIPTION,
  params: {
    symbol: { type: 'string', required: true, description: 'Symbol name (bare token; e.g., parseMarkdown, BrainEngine).' },
    limit: { type: 'number', description: 'Max definition sites returned. Default 20.' },
    lang: { type: 'string', description: "Filter by content_chunks.language (e.g. 'typescript', 'python')." },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const { findCodeDef } = await import('../../commands/code-def.ts');
    const defs = await findCodeDef(ctx.engine, p.symbol as string, {
      limit: (p.limit as number) ?? 20,
      language: (p.lang as string) || undefined,
    });
    return { symbol: p.symbol as string, count: defs.length, defs };
  },
  cliHints: { name: 'code_def', hidden: true },
};

export const code_refs: Operation = {
  name: 'code_refs',
  description: CODE_REFS_DESCRIPTION,
  params: {
    symbol: { type: 'string', required: true, description: 'Symbol to find references to.' },
    limit: { type: 'number', description: 'Max references returned. Default 50.' },
    lang: { type: 'string', description: "Filter by content_chunks.language." },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const { findCodeRefs } = await import('../../commands/code-refs.ts');
    const refs = await findCodeRefs(ctx.engine, p.symbol as string, {
      limit: (p.limit as number) ?? 50,
      language: (p.lang as string) || undefined,
    });
    return { symbol: p.symbol as string, count: refs.length, refs };
  },
  cliHints: { name: 'code_refs', hidden: true },
};

