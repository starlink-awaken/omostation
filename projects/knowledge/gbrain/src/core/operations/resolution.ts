// --- Resolution & Chunks ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const resolve_slugs: Operation = {
  name: 'resolve_slugs',
  description: 'Fuzzy-resolve a partial slug to matching page slugs',
  params: {
    partial: { type: 'string', required: true },
  },
  handler: async (ctx, p) => {
    return ctx.engine.resolveSlugs(p.partial as string);
  },
  scope: 'read',
};

export const get_chunks: Operation = {
  name: 'get_chunks',
  description: 'Get content chunks for a page',
  params: {
    slug: { type: 'string', required: true },
  },
  handler: async (ctx, p) => {
    // v0.31.8 (D20): thread ctx.sourceId.
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};
    return ctx.engine.getChunks(p.slug as string, sourceOpts);
  },
  scope: 'read',
};

