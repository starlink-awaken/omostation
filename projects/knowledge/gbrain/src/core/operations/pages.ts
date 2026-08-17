// --- Page CRUD ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { OperationError, sourceScopeOpts, matchesSlugAllowList } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";
import { hybridSearch, hybridSearchCached } from "../search/hybrid";
import { importFromContent } from "../import-file";
import { serializePageToMarkdown, resolvePageFilePath } from "../markdown";
import { extractPageLinks, isAutoLinkEnabled, isAutoTimelineEnabled, parseTimelineEntries, makeResolver } from "../link-extraction";
import { isFactsBackstopEligible } from "../facts/eligibility";
import { stripTakesFence } from "../takes-fence";
import { stripFactsFence } from "../facts-fence";
import { bumpLastRetrievedAt } from "../last-retrieved";
import { mkdirSync, writeFileSync, existsSync, statSync } from "fs";
import { dirname } from "path";
import type { UnresolvedFrontmatterRef } from "../link-extraction";
import type { PageType } from "../types";
import { LIST_PAGES_DESCRIPTION } from "../operations-descriptions";

export const get_page: Operation = {
  name: 'get_page',
  description: 'Read a page by slug (supports optional fuzzy matching). Soft-deleted pages are hidden by default; pass include_deleted: true to surface them with deleted_at populated (see v0.26.5 recovery window).',
  params: {
    slug: { type: 'string', required: true, description: 'Page slug' },
    fuzzy: { type: 'boolean', description: 'Enable fuzzy slug resolution (default: false)' },
    include_deleted: { type: 'boolean', description: 'v0.26.5: surface soft-deleted pages with deleted_at populated (default: false). Used by restore workflows.' },
  },
  handler: async (ctx, p) => {
    const slug = p.slug as string;
    const fuzzy = (p.fuzzy as boolean) || false;
    const includeDeleted = (p.include_deleted as boolean) === true;
    // v0.31.8 (D20): thread ctx.sourceId through read-side ops. Only pass
    // sourceId when it's set on ctx — when unset (local CLI default chain
    // resolves to no source), the engine two-branch query falls through to
    // the cross-source view, preserving pre-v0.31.8 behavior. MCP callers
    // (stdio + HTTP) populate ctx.sourceId via the transport layer.
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};

    let page = await ctx.engine.getPage(slug, { includeDeleted, ...sourceOpts });
    let resolved_slug: string | undefined;

    if (!page && fuzzy) {
      const candidates = await ctx.engine.resolveSlugs(slug);
      if (candidates.length === 1) {
        page = await ctx.engine.getPage(candidates[0], { includeDeleted, ...sourceOpts });
        resolved_slug = candidates[0];
      } else if (candidates.length > 1) {
        return { error: 'ambiguous_slug', candidates };
      }
    }

    if (!page) {
      throw new OperationError('page_not_found', `Page not found: ${slug}`, includeDeleted ? 'Check the slug or use fuzzy: true' : 'Page may be soft-deleted; pass include_deleted: true to verify');
    }

    // v0.37.0 (D11): op-layer write-back for the `last_retrieved_at` stale
    // signal. Fire-and-forget — caller does NOT await. Internal callers
    // (sync, migrations, dream cycle) bypass this op handler so the signal
    // stays clean. Throttled to ~1 write / 5 min per page via the SQL clause
    // inside bumpLastRetrievedAt (D2).
    bumpLastRetrievedAt(ctx.engine, [page.id]);

    const tags = await ctx.engine.getTags(page.slug, sourceOpts);
    // Privacy boundary for the per-token allow-list (v0.28.6 for takes,
    // v0.32.2 for facts).
    //
    // takes_list / takes_search / think.gather filter rows by holder at
    // the SQL layer, but takes AND facts are also rendered as markdown
    // tables inside the page body between fence markers. A read-only
    // remote MCP caller could otherwise call `get_page <slug>` and
    // recover every fence row verbatim.
    //
    // v0.32.2 (Codex R2-#5): the strip trigger is now `ctx.remote === true`
    // rather than the takes-holders-allow-list flag (which subagent paths
    // didn't set, leaving a pre-existing privacy hole). Subagent + remote
    // MCP + scope-restricted-token callers all get the strip; local CLI
    // (`ctx.remote === false`) sees the full fence. Closes the
    // pre-existing takes hole as a bonus.
    //
    // Both fences are stripped:
    //  - stripTakesFence: drops the entire takes table for untrusted
    //    readers (per-token holder allow-list is the row-level surface
    //    for trusted callers).
    //  - stripFactsFence({keepVisibility: ['world']}): keeps world rows,
    //    drops private. World facts are public knowledge by definition;
    //    untrusted readers see them. Private facts never cross the boundary.
    const isUntrustedReader = ctx.remote === true;
    const visibleBody = isUntrustedReader
      ? {
          ...page,
          compiled_truth: stripFactsFence(
            stripTakesFence(page.compiled_truth),
            { keepVisibility: ['world'] },
          ),
        }
      : page;
    return { ...visibleBody, tags, ...(resolved_slug ? { resolved_slug } : {}) };
  },
  scope: 'read',
  cliHints: { name: 'get', positional: ['slug'] },
};

export const put_page: Operation = {
  name: 'put_page',
  description: 'Write/update a page (markdown with frontmatter). Chunks, embeds, reconciles tags, and (when auto_link/auto_timeline are enabled) extracts + reconciles graph links and timeline entries.',
  params: {
    slug: { type: 'string', required: true, description: 'Page slug' },
    content: { type: 'string', required: true, description: 'Full markdown content with YAML frontmatter' },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    const slug = p.slug as string;

    // Subagent namespace enforcement (v0.15+). Runs BEFORE the dry-run
    // short-circuit so preview calls surface the same rejection. Confines
    // LLM-driven writes to wiki/agents/<subagentId>/... — no leading slash
    // (slug grammar rejects that), anchored, slash-boundary to defeat prefix
    // collisions like `wiki/agents/12evil/*` impersonating subagent 12.
    //
    // FAIL-CLOSED: `viaSubagent=true` enforces the check even if the
    // dispatcher forgot to populate `subagentId`. Agent-originated writes
    // without an owning subagent id are rejected outright.
    if (ctx.viaSubagent === true) {
      if (typeof ctx.subagentId !== 'number' || Number.isNaN(ctx.subagentId)) {
        throw new OperationError('permission_denied', 'put_page via subagent requires ctx.subagentId');
      }
      const allowList = ctx.allowedSlugPrefixes;
      if (allowList && allowList.length > 0) {
        // Trusted-workspace path: explicit allow-list bounds writes.
        // Set only by cycle.ts (synthesize/patterns) which submits subagent
        // jobs under PROTECTED_JOB_NAMES — MCP cannot reach this branch.
        if (!matchesSlugAllowList(slug, allowList)) {
          throw new OperationError(
            'permission_denied',
            `put_page slug '${slug}' is not within the trusted-workspace allow-list (${allowList.join(', ')})`
          );
        }
      } else {
        // Legacy default: agent-namespace confinement.
        const prefix = `wiki/agents/${ctx.subagentId}/`;
        if (!slug.startsWith(prefix) || slug.length === prefix.length) {
          throw new OperationError('permission_denied', `put_page via subagent must write under '${prefix}...'`);
        }
      }
    }

    if (ctx.dryRun) return { dry_run: true, action: 'put_page', slug: p.slug };
    // Skip embedding when the AI gateway has no embedding provider configured.
    // Checks all auth env vars for the resolved provider, not just OPENAI_API_KEY,
    // so Gemini / Ollama / Voyage brains don't silently drop embeddings (Codex C2).
    const { isAvailable } = await import('../ai/gateway.ts');
    const noEmbed = !isAvailable('embedding');
    // v0.31.8 (D7 / codex OV-1): thread ctx.sourceId so put_page on a
    // multi-source brain lands in the intended source instead of the
    // default-source clobber path. importFromContent already accepts
    // opts.sourceId (PR #707/#757 engine work); previously the op handler
    // just didn't pass it.
    // v0.39 T1.5: load active pack ONCE per put_page invocation; thread to
    // parseMarkdown via importFromContent so type inference honors user-defined
    // page_types. Best-effort: pack load failure falls back to legacy inferType
    // (parity gate preserved). Federated-read closure correction is T19's scope.
    let activePack: { page_types: ReadonlyArray<{ name: string; path_prefixes: ReadonlyArray<string> }> } | undefined;
    try {
      const { loadActivePack } = await import('../schema-pack/load-active.ts');
      const { loadConfig } = await import('../config.ts');
      const resolved = await loadActivePack({
        cfg: loadConfig(),
        remote: ctx.remote === false ? false : true,
        sourceId: ctx.sourceId,
      });
      activePack = { page_types: resolved.manifest.page_types };
    } catch {
      // Pack load failed; fall through to legacy inferType behavior.
      activePack = undefined;
    }
    const result = await importFromContent(ctx.engine, slug, p.content as string, {
      noEmbed,
      ...(ctx.sourceId ? { sourceId: ctx.sourceId } : {}),
      ...(activePack ? { activePack } : {}),
    });

    // v0.39 T13 — auto-prompt on first unknown-type write.
    //
    // Contract (codex finding #8 honored — 7 cases covered):
    //   - TTY callers: stderr prompt fires once per unique unknown type;
    //     subsequent writes with the same type silently append to
    //     candidate audit.
    //   - Non-TTY callers: ALWAYS succeed; silently append to candidate
    //     audit. NEVER block. Critical regression test:
    //     test/put-page-unknown-type-prompt.test.ts pins this.
    //   - Subagent / MCP / claw-test / autopilot all go through here;
    //     non-TTY contract preserves their semantics.
    //   - Pack-load failures (activePack undefined) skip the gate entirely
    //     since "unknown" has no meaning without a pack reference.
    if (activePack && result.status === 'imported') {
      try {
        const pageType = (result as { page?: { type?: string } }).page?.type ?? null;
        const knownTypes = new Set(activePack.page_types.map((t) => t.name));
        if (pageType && !knownTypes.has(pageType)) {
          const { logSchemaEvent } = await import('../schema-events.ts');
          logSchemaEvent({
            verb: 'put_page:unknown_type',
            outcome: 'success',
            flags: [`type=${pageType.slice(0, 32)}`, `slug=${slug.slice(0, 64)}`],
          });
          if (process.stderr.isTTY && ctx.remote === false) {
            console.error(
              `[schema] put_page wrote type=\`${pageType}\` which isn't in active pack \`${activePack.page_types.length ? '<configured>' : 'gbrain-base'}\`. ` +
              `Run \`gbrain schema review-candidates\` to promote or ignore.`,
            );
          }
        }
      } catch {
        // best-effort; never block put_page
      }
    }

    // v0.38 put_page write-through (ingestion cathedral):
    // After importFromContent succeeds, if `sync.repo_path` resolves to a
    // real directory, persist the markdown file to disk alongside the DB
    // row. Failures non-fatal — DB write is durable; subsequent sync
    // reconciles drift.
    //
    // Trust gating:
    //   - Subagent sandbox (viaSubagent without allowedSlugPrefixes) → DB-only.
    //   - All other writes → write-through.
    let writeThrough: { written: boolean; path?: string; skipped?: string; error?: string } | undefined;
    const isSandboxSubagent = ctx.viaSubagent === true
      && !(Array.isArray(ctx.allowedSlugPrefixes) && ctx.allowedSlugPrefixes.length > 0);
    if (!ctx.dryRun && result.status !== 'error' && !isSandboxSubagent) {
      try {
        const repoPath = await ctx.engine.getConfig('sync.repo_path');
        if (!repoPath) {
          writeThrough = { written: false, skipped: 'no_repo_configured' };
        } else if (!existsSync(repoPath) || !statSync(repoPath).isDirectory()) {
          writeThrough = { written: false, skipped: 'repo_not_found' };
        } else {
          const sourceId = ctx.sourceId ?? 'default';
          const writtenPage = await ctx.engine.getPage(result.slug, { sourceId });
          if (writtenPage) {
            const tags = await ctx.engine.getTags(result.slug, { sourceId });
            const provenanceVia = ctx.remote === false ? 'put_page' : 'mcp:put_page';
            const md = serializePageToMarkdown(writtenPage, tags, {
              frontmatterOverrides: {
                ingested_via: provenanceVia,
                ingested_at: new Date().toISOString(),
                source_kind: provenanceVia,
              },
            });
            const filePath = resolvePageFilePath(repoPath as string, result.slug, sourceId);
            mkdirSync(dirname(filePath), { recursive: true });
            writeFileSync(filePath, md, 'utf8');
            writeThrough = { written: true, path: filePath };
          } else {
            writeThrough = { written: false, skipped: 'page_not_found_after_write' };
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        ctx.logger.warn(`[put_page] write-through failed for ${result.slug}: ${msg}`);
        writeThrough = { written: false, error: msg };
      }
    } else if (isSandboxSubagent) {
      writeThrough = { written: false, skipped: 'subagent_sandbox' };
    } else if (ctx.dryRun) {
      writeThrough = { written: false, skipped: 'dry_run' };
    }

    // Auto-link post-hook: runs AFTER importFromContent (which is its own
    // transaction). Runs even on status='skipped' so reconciliation catches drift
    // between the page text and the links table. Failures are non-blocking.
    //
    // SECURITY: skipped for remote (MCP) callers. Auto-link's bare-slug regex
    // matches `people/X` etc. anywhere in page text, including code fences,
    // quoted strings, and prompt-injected content. An untrusted page can plant
    // arbitrary outbound links by including `see meetings/board-q1` in its body.
    // Combined with the backlink boost in hybridSearch, attacker-placed targets
    // would surface higher in search. Local CLI users (ctx.remote=false) opt
    // into this behavior; MCP/remote writes do not.
    let autoLinks:
      | { created: number; removed: number; errors: number; unresolved: UnresolvedFrontmatterRef[] }
      | { error: string }
      | { skipped: 'remote' }
      | undefined;
    let autoTimeline: { created: number } | { error: string } | { skipped: 'remote' } | undefined;
    // Trusted-workspace path (v0.23 dream cycle) re-enables auto-link/timeline
    // even though ctx.remote=true, because the allow-list bounds the slug and
    // the synthesis prompt is itself the trusted dispatcher. Without this,
    // the cycle's `extract` phase would have to recompute every edge, and
    // patterns (which runs after extract) would still see the right graph
    // but auto_timeline would never fire on synth output.
    const trustedWorkspace = ctx.viaSubagent === true
      && Array.isArray(ctx.allowedSlugPrefixes)
      && ctx.allowedSlugPrefixes.length > 0;
    if (ctx.remote !== false && !trustedWorkspace) {
      autoLinks = { skipped: 'remote' };
      autoTimeline = { skipped: 'remote' };
    } else if (result.parsedPage) {
      try {
        const enabled = await isAutoLinkEnabled(ctx.engine);
        if (enabled) {
          autoLinks = await runAutoLink(ctx.engine, slug, result.parsedPage, ctx.sourceId ? { sourceId: ctx.sourceId } : undefined);
        }
      } catch (e) {
        autoLinks = { error: e instanceof Error ? e.message : String(e) };
      }
      // Timeline extraction mirrors auto-link: runs post-write, best-effort,
      // never blocks the write. ON CONFLICT DO NOTHING in
      // addTimelineEntriesBatch keeps it idempotent across re-writes, so a
      // page that's edited and re-written won't duplicate its own timeline.
      try {
        const enabled = await isAutoTimelineEnabled(ctx.engine);
        if (enabled) {
          const fullContent = result.parsedPage.compiled_truth + '\n' + result.parsedPage.timeline;
          const entries = parseTimelineEntries(fullContent);
          if (entries.length > 0) {
            const batch = entries.map(e => ({
              slug,
              date: e.date,
              summary: e.summary,
              detail: e.detail || '',
            }));
            const created = await ctx.engine.addTimelineEntriesBatch(batch);
            autoTimeline = { created };
          } else {
            autoTimeline = { created: 0 };
          }
        }
      } catch (e) {
        autoTimeline = { error: e instanceof Error ? e.message : String(e) };
      }
    }

    // v0.31 (D23): facts compliance backstop. When an agent writes a page
    // on a conversation-shape slug AND the body has substantive prose, fire
    // a fact-extraction job into the bounded queue. Skipped on dry-run,
    // dream-generated content (anti-loop), and non-eligible kinds (sync,
    // ingest, file uploads, code pages). Never blocks the put_page response.
    // v0.31.2: routed through runFactsBackstop (PR1 commit 6) so put_page
    // and sync share the same eligibility/extract/dedup/insert pipeline.
    // Queue mode preserves the prior fire-and-forget shape (caller's
    // put_page response stays fast). Default 'all' notability filter
    // (MEDIUM facts wait for the dream cycle but DO land via put_page,
    // matching the pre-fix behavior on this surface).
    let factsQueued: { queued: boolean } | { skipped: string } | undefined;
    try {
      const { runFactsBackstop } = await import('../facts/backstop.ts');
      const r = await runFactsBackstop(
        {
          slug,
          type: result.parsedPage!.type,
          compiled_truth: result.parsedPage!.compiled_truth,
          frontmatter: result.parsedPage!.frontmatter,
        },
        {
          engine: ctx.engine,
          sourceId: ctx.sourceId ?? 'default',
          sessionId: (ctx as { source_session?: string }).source_session ?? null,
          source: 'mcp:put_page',
          mode: 'queue',
        },
      );
      if (r.mode === 'queue' && r.enqueued) {
        factsQueued = { queued: true };
      } else if (r.mode === 'queue' && r.skipped) {
        // Preserve the pre-v0.31.2 response shape for MCP clients:
        // 'kind:guide' / 'too_short' / 'subagent_namespace' / 'dream_generated'
        // (bare reasons), not the helper's namespaced 'eligibility_failed:...'
        // discriminator. Map back here.
        const bare = r.skipped.startsWith('eligibility_failed:')
          ? r.skipped.slice('eligibility_failed:'.length)
          : r.skipped;
        factsQueued = { skipped: bare };
      }
    } catch {
      factsQueued = { skipped: 'backstop_error' };
    }

    // Post-write validator lint (PR 2.5): feature-flag-gated, non-blocking.
    // When `writer.lint_on_put_page` is enabled, runs the BrainWriter's
    // validators on the freshly-written page and logs findings to
    // ingest_log + ~/.gbrain/validator-lint.jsonl. Does NOT reject the
    // write — that's the deferred strict-mode flip after the 7-day soak.
    let writerLint: { error_count: number; warning_count: number } | { skipped: string } | undefined;
    try {
      const { runPostWriteLint } = await import('../output/post-write.ts');
      const lint = await runPostWriteLint(ctx.engine, result.slug);
      if (lint.ran) {
        writerLint = {
          error_count: lint.findings.filter(f => f.severity === 'error').length,
          warning_count: lint.findings.filter(f => f.severity === 'warning').length,
        };
      } else if (lint.skippedReason) {
        writerLint = { skipped: lint.skippedReason };
      }
    } catch {
      // Non-fatal; never blocks put_page.
    }

    return {
      slug: result.slug,
      status: result.status === 'imported' ? 'created_or_updated' : result.status,
      chunks: result.chunks,
      ...(autoLinks ? { auto_links: autoLinks } : {}),
      ...(autoTimeline ? { auto_timeline: autoTimeline } : {}),
      ...(writerLint ? { writer_lint: writerLint } : {}),
      ...(factsQueued ? { facts_backstop: factsQueued } : {}),
      ...(writeThrough ? { write_through: writeThrough } : {}),
    };
  },
  cliHints: { name: 'put', positional: ['slug'], stdin: 'content' },
};

// v0.31.2: isFactsBackstopEligible moved to src/core/facts/eligibility.ts
// so sync.ts, file_upload, code_import, and runFactsBackstop all share one
// predicate. Imported above.

/**
 * Extract entity refs from a freshly-written page, sync the links table to match.
 * Creates new links via addLink, removes stale ones (links present in DB but no
 * longer referenced in content) via removeLink. Returns counts.
 *
 * Runs OUTSIDE importFromContent's transaction so it doesn't block the page write
 * or get rolled back if a single link operation fails. Per-link failures are
 * counted; the overall function never throws (catch in put_page handler covers
 * extraction errors).
 */
async function runAutoLink(
  engine: BrainEngine,
  slug: string,
  parsed: { type: PageType; compiled_truth: string; timeline: string; frontmatter: Record<string, unknown> },
  opts?: { sourceId?: string },
): Promise<{ created: number; removed: number; errors: number; unresolved: UnresolvedFrontmatterRef[] }> {
  const fullContent = parsed.compiled_truth + '\n' + parsed.timeline;
  // v0.31.8 (codex OV-2): thread sourceId through every read + write inside
  // reconcileLinks. Without this the FS walker reads cross-source links/slugs
  // but writes scoped to one source — phantom stale-deletions and duplicate
  // inserts. opts.sourceId is set when caller knows the source (put_page from
  // a multi-source-aware handler); when omitted, every read returns the
  // pre-v0.31.8 cross-source view (back-compat for any existing caller).
  const sourceOpts = opts?.sourceId ? { sourceId: opts.sourceId } : {};
  const linkSourceOpts = opts?.sourceId
    ? { fromSourceId: opts.sourceId, toSourceId: opts.sourceId, originSourceId: opts.sourceId }
    : {};
  const removeSourceOpts = opts?.sourceId
    ? { fromSourceId: opts.sourceId, toSourceId: opts.sourceId }
    : {};

  // Live-mode resolver: per-put throwaway cache, pg_trgm + optional search.
  const resolver = makeResolver(engine, { mode: 'live' });
  const { candidates, unresolved } = await extractPageLinks(
    slug, fullContent, parsed.frontmatter, parsed.type, resolver,
  );

  // Resolve which targets exist (skip refs to non-existent pages to avoid FK
  // violation churn in addLink). One getAllSlugs call upfront, O(1) lookup.
  // v0.31.8 (D12): scoped to the source when opts.sourceId is set so wikilink
  // resolution doesn't span unrelated sources.
  const allSlugs = await engine.getAllSlugs(sourceOpts);
  const valid = candidates.filter(c =>
    allSlugs.has(c.targetSlug) && (!c.fromSlug || allSlugs.has(c.fromSlug))
  );

  // Split candidates by direction. Outgoing (fromSlug === slug or unset) are
  // this page's own edges, reconciled against getLinks(slug). Incoming
  // (fromSlug !== slug — frontmatter with `direction: incoming`) are edges
  // where this page is the TO side; reconciled against getBacklinks(slug)
  // but SCOPED to the frontmatter edges this page authored via
  // (link_source='frontmatter' AND origin_slug = slug). We never touch
  // frontmatter edges authored by OTHER pages.
  const out = valid.filter(c => !c.fromSlug || c.fromSlug === slug);
  const inc = valid.filter(c => c.fromSlug && c.fromSlug !== slug);

  // Run getLinks + addLink/removeLink loops inside a single transaction so that
  // concurrent put_page calls on the same slug can't race the reconciliation:
  // without this, two simultaneous writes both read stale `existingKeys` and
  // re-create links the other side just removed (lost-update).
  //
  // Row-level locks alone aren't enough: both writers can read the same
  // `existingKeys` set BEFORE either mutates a row, so the union-of-writes
  // race survives. A transaction-scoped advisory lock keyed on the slug
  // hash serializes the entire reconciliation across processes. Falls
  // through on engines that don't support pg_advisory_xact_lock (PGLite is
  // single-process so there's no cross-process concern there anyway).
  const result = await engine.transaction(async (tx) => {
    try {
      await tx.executeRaw(`SELECT pg_advisory_xact_lock(hashtext($1)::bigint)`, [`auto_link:${slug}`]);
    } catch {
      // engine doesn't support advisory locks — fall through
    }
    const existingOut = await tx.getLinks(slug, sourceOpts);
    // Incoming: we only look at frontmatter edges WE authored (origin_slug=slug).
    // Non-frontmatter and other-page frontmatter edges survive untouched.
    const existingInRaw = await tx.getBacklinks(slug, sourceOpts);
    const existingIn = existingInRaw.filter(
      l => l.link_source === 'frontmatter' && l.origin_slug === slug,
    );

    // Reconcilable outgoing edges: markdown + our own frontmatter edges.
    // Manual edges (link_source='manual') are NEVER touched by reconciliation.
    const reconcilableOut = existingOut.filter(
      l => l.link_source === 'markdown' || l.link_source == null ||
           (l.link_source === 'frontmatter' && l.origin_slug === slug),
    );

    const outKeys = new Set(out.map(c =>
      `${c.targetSlug}\u0000${c.linkType}\u0000${c.linkSource ?? 'markdown'}`
    ));
    const incKeys = new Set(inc.map(c =>
      `${c.fromSlug}\u0000${c.linkType}`
    ));

    let created = 0, removed = 0, errors = 0;

    // Add outgoing edges.
    for (const c of out) {
      try {
        await tx.addLink(
          slug, c.targetSlug, c.context, c.linkType,
          c.linkSource, c.originSlug, c.originField,
          linkSourceOpts,
        );
        const existKey = `${c.targetSlug}\u0000${c.linkType}\u0000${c.linkSource ?? 'markdown'}`;
        const exists = reconcilableOut.some(l =>
          `${l.to_slug}\u0000${l.link_type}\u0000${l.link_source ?? 'markdown'}` === existKey
        );
        if (!exists) created++;
      } catch {
        errors++;
      }
    }

    // Add incoming edges (other page → slug).
    for (const c of inc) {
      try {
        await tx.addLink(
          c.fromSlug!, c.targetSlug, c.context, c.linkType,
          'frontmatter', c.originSlug, c.originField,
          linkSourceOpts,
        );
        const existKey = `${c.fromSlug}\u0000${c.linkType}`;
        const exists = existingIn.some(l =>
          `${l.from_slug}\u0000${l.link_type}` === existKey
        );
        if (!exists) created++;
      } catch {
        errors++;
      }
    }

    // Remove stale outgoing (markdown or our-frontmatter, not in desired set).
    for (const l of reconcilableOut) {
      const key = `${l.to_slug}\u0000${l.link_type}\u0000${l.link_source ?? 'markdown'}`;
      if (!outKeys.has(key)) {
        try {
          await tx.removeLink(slug, l.to_slug, l.link_type, l.link_source ?? undefined, removeSourceOpts);
          removed++;
        } catch {
          errors++;
        }
      }
    }

    // Remove stale incoming (our frontmatter → slug, not in desired set).
    for (const l of existingIn) {
      const key = `${l.from_slug}\u0000${l.link_type}`;
      if (!incKeys.has(key)) {
        try {
          await tx.removeLink(l.from_slug, slug, l.link_type, 'frontmatter', removeSourceOpts);
          removed++;
        } catch {
          errors++;
        }
      }
    }

    return { created, removed, errors };
  });

  return { ...result, unresolved };
}

export const delete_page: Operation = {
  name: 'delete_page',
  description: 'Soft-delete a page. The row is hidden from search and from get_page/list_pages, but is recoverable via restore_page within 72h. The autopilot purge phase hard-deletes after the recovery window. Pass include_deleted: true to get_page to verify the soft-delete landed.',
  params: {
    slug: { type: 'string', required: true },
    _confirmed: { type: 'boolean', description: 'L2: Explicit confirmation required for destructive operations. Must be true to proceed.' },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    const slug = p.slug as string;
    // L2 deny path: destructive operation requires explicit confirmation
    if (!p._confirmed) {
      throw new OperationError('permission_denied', 'L2 operation delete_page requires _confirmed=true');
    }
    if (ctx.dryRun) return { dry_run: true, action: 'soft_delete_page', slug };
    // v0.31.8 (D7): thread ctx.sourceId so multi-source brains soft-delete the
    // intended row instead of always targeting (default, slug).
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};
    // v0.26.5: rewired from hard-delete to soft-delete. The hard-delete primitive
    // (engine.deletePage) is now reserved for purgeDeletedPages and explicit
    // tests. softDeletePage returns null when the slug is unknown OR already
    // soft-deleted (idempotent-as-null) — preserve that as a clean no-op shape.
    const result = await ctx.engine.softDeletePage(slug, sourceOpts);
    if (result === null) {
      // Distinguish "not found" from "already soft-deleted" so the agent gets a
      // clear signal. Probe once with include_deleted to disambiguate.
      const existing = await ctx.engine.getPage(slug, { includeDeleted: true, ...sourceOpts });
      if (!existing) {
        throw new OperationError('page_not_found', `Page not found: ${slug}`, 'Check the slug.');
      }
      return { status: 'already_soft_deleted', slug, deleted_at: existing.deleted_at };
    }
    return { status: 'soft_deleted', slug, recoverable_until: 'now + 72h via restore_page' };
  },
  cliHints: { name: 'delete', positional: ['slug'] },
};

export const restore_page: Operation = {
  name: 'restore_page',
  description: 'v0.26.5 — restore a soft-deleted page (clear deleted_at). Returns success only if the page was actually soft-deleted. After this op, the page reappears in search and in get_page/list_pages without the include_deleted flag.',
  params: {
    slug: { type: 'string', required: true },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    const slug = p.slug as string;
    if (ctx.dryRun) return { dry_run: true, action: 'restore_page', slug };
    // v0.31.8 (D7): thread ctx.sourceId.
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};
    const ok = await ctx.engine.restorePage(slug, sourceOpts);
    if (!ok) {
      // Distinguish "not found" from "already active" (idempotent-as-false).
      const existing = await ctx.engine.getPage(slug, { includeDeleted: true, ...sourceOpts });
      if (!existing) {
        throw new OperationError('page_not_found', `Page not found: ${slug}`, 'Check the slug.');
      }
      return { status: 'already_active', slug };
    }
    return { status: 'restored', slug };
  },
  cliHints: { name: 'restore', positional: ['slug'] },
};

export const purge_deleted_pages: Operation = {
  name: 'purge_deleted_pages',
  description: 'v0.26.5 — admin-only. Hard-deletes pages whose deleted_at is older than older_than_hours (default 72). Cascades through content_chunks, page_links, chunk_relations. Local CLI only (not exposed over HTTP MCP). Manual escape hatch alongside the autopilot purge phase.',
  params: {
    older_than_hours: { type: 'number', description: 'Age cutoff in hours. Default 72.' },
  },
  mutating: true,
  scope: 'admin',
  localOnly: true,
  handler: async (ctx, p) => {
    const olderThanHours = (p.older_than_hours as number | undefined) ?? 72;
    if (ctx.dryRun) return { dry_run: true, action: 'purge_deleted_pages', older_than_hours: olderThanHours };
    const result = await ctx.engine.purgeDeletedPages(olderThanHours);
    return { status: 'purged', count: result.count, slugs: result.slugs };
  },
  cliHints: { name: 'purge-deleted' },
};

const LIST_PAGES_SORT_VALUES = ['updated_desc', 'updated_asc', 'created_desc', 'slug'] as const;
type ListPagesSort = typeof LIST_PAGES_SORT_VALUES[number];

export const list_pages: Operation = {
  name: 'list_pages',
  description: LIST_PAGES_DESCRIPTION,
  params: {
    type: { type: 'string', description: 'Filter by page type' },
    tag: { type: 'string', description: 'Filter by tag' },
    limit: { type: 'number', description: 'Max results (default 50)' },
    // v0.29 — surface filter that already exists on PageFilters.
    updated_after: {
      type: 'string',
      description: 'ISO date (YYYY-MM-DD) or full timestamp. Returns pages with updated_at > value.',
    },
    sort: {
      type: 'string',
      enum: [...LIST_PAGES_SORT_VALUES],
      description: 'Sort order. Default updated_desc (matches pre-v0.29). Options: updated_desc, updated_asc, created_desc, slug.',
    },
    include_deleted: { type: 'boolean', description: 'v0.26.5: include soft-deleted pages (default: false). Used by restore workflows and operator diagnostics.' },
  },
  handler: async (ctx, p) => {
    // Whitelist the sort enum at the handler before passing to the engine.
    // Engines also whitelist via PAGE_SORT_SQL but defending here keeps
    // unsupported strings from reaching the SQL layer.
    const rawSort = p.sort as string | undefined;
    const sort = rawSort && (LIST_PAGES_SORT_VALUES as readonly string[]).includes(rawSort)
      ? (rawSort as ListPagesSort)
      : undefined;
    // v0.34.1 (#861 — P0 leak seal): thread the auth'd client's source scope
    // into the listPages filter so an OAuth client scoped to src-A cannot
    // enumerate src-B pages. Pre-fix, ctx.sourceId / ctx.auth?.allowedSources
    // were ignored at this op handler and the engine returned every source's
    // pages indiscriminately.
    const scope = sourceScopeOpts(ctx);
    const pages = await ctx.engine.listPages({
      type: p.type as any,
      tag: p.tag as string,
      limit: clampSearchLimit(p.limit as number | undefined, 50, 100),
      includeDeleted: (p.include_deleted as boolean) === true,
      updated_after: typeof p.updated_after === 'string' ? p.updated_after : undefined,
      sort,
      ...scope,
    });
    return pages.map(pg => ({
      slug: pg.slug,
      type: pg.type,
      title: pg.title,
      updated_at: pg.updated_at,
      ...(pg.deleted_at ? { deleted_at: pg.deleted_at } : {}),
    }));
  },
  scope: 'read',
  cliHints: { name: 'list' },
};

