// --- Raw Data ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const put_raw_data: Operation = {
  name: 'put_raw_data',
  description: 'Store raw API response data for a page',
  params: {
    slug: { type: 'string', required: true },
    source: { type: 'string', required: true, description: 'Data source (e.g., crustdata, happenstance)' },
    data: { type: 'object', required: true, description: 'Raw data object' },
  },
  mutating: true,
  scope: 'write',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'put_raw_data', slug: p.slug, source: p.source };
    // v0.31.8 (D7 + D21): thread ctx.sourceId.
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};
    await ctx.engine.putRawData(p.slug as string, p.source as string, p.data as object, sourceOpts);
    return { status: 'ok' };
  },
};

export const get_raw_data: Operation = {
  name: 'get_raw_data',
  description: 'Retrieve raw data for a page',
  params: {
    slug: { type: 'string', required: true },
    source: { type: 'string', description: 'Filter by source' },
  },
  handler: async (ctx, p) => {
    // v0.31.8 (D20 + D21): thread ctx.sourceId.
    const sourceOpts = ctx.sourceId ? { sourceId: ctx.sourceId } : {};
    return ctx.engine.getRawData(p.slug as string, p.source as string | undefined, sourceOpts);
  },
  scope: 'read',
};

