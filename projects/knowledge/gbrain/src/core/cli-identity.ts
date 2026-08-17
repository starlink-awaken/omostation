// F7114ABA wave 1: cli.ts identity banner 提取 (SRP)
import { callRemoteTool, unpackToolResult } from './mcp-client.ts';
import { maybePromptForUpgrade } from './thin-client-upgrade-prompt.ts';
import type { GBrainConfig } from './config.ts';
import type { CliOptions } from './cli-options.ts';

export interface BrainIdentity {
  version: string;
  engine: 'postgres' | 'pglite';
  page_count: number;
  chunk_count: number;
  last_sync_iso: string | null;
}

interface CachedIdentity {
  identity: BrainIdentity;
  cached_at_ms: number;
}

const IDENTITY_TTL_MS = 60_000;
const identityCache = new Map<string, CachedIdentity>();

/** Test-only escape hatch — clears the in-memory cache between test runs. */
export function _clearIdentityCacheForTest(): void {
  identityCache.clear();
}

export function bannerSuppressed(cliOpts: CliOptions): boolean {
  if (cliOpts.quiet) return true;
  if (process.env.GBRAIN_NO_BANNER === '1') return true;
  // Non-TTY default is suppressed (clean pipes); explicit env-flag overrides.
  if (!process.stderr.isTTY && process.env.GBRAIN_BANNER !== '1') return true;
  return false;
}

function formatPageCount(n: number): string {
  if (n >= 1000) {
    const k = (n / 1000).toFixed(n >= 100_000 ? 0 : 1);
    return `${k}k`;
  }
  return String(n);
}

function formatBanner(mcpUrl: string, id: BrainIdentity): string {
  const host = mcpUrl.replace(/^https?:\/\//, '').split('/')[0];
  const counts = `brain: ${formatPageCount(id.page_count)} pages, ${formatPageCount(id.chunk_count)} chunks`;
  return `[thin-client → ${host} · ${counts} · v${id.version}]`;
}

async function fetchIdentity(
  cfg: GBrainConfig,
  signal: AbortSignal,
): Promise<BrainIdentity> {
  // 2s timeout for the banner fetch — must not delay the underlying command.
  const raw = await callRemoteTool(cfg, 'get_brain_identity', {}, {
    timeoutMs: 2000,
    signal,
  });
  const id = unpackToolResult<BrainIdentity>(raw);
  return id;
}

export async function printIdentityBannerBestEffort(
  cfg: GBrainConfig,
  cliOpts: CliOptions,
  signal: AbortSignal,
): Promise<void> {
  if (bannerSuppressed(cliOpts)) return;
  const mcpUrl = cfg.remote_mcp?.mcp_url;
  if (!mcpUrl) return;

  // Cache lookup keyed by mcp_url so switching hosts via `gbrain init`
  // invalidates cleanly even within a long-lived process.
  const cached = identityCache.get(mcpUrl);
  if (cached && Date.now() - cached.cached_at_ms < IDENTITY_TTL_MS) {
    process.stderr.write(formatBanner(mcpUrl, cached.identity) + '\n');
    // v0.31.11: detect remote-version drift, prompt user to upgrade.
    // bannerIsSuppressed=false here — the early return above guaranteed it.
    await maybePromptForUpgrade(cfg, cached.identity, cliOpts, false);
    return;
  }

  // Cache miss — fetch. Failure is non-fatal: banner is observability,
  // never load-bearing for the underlying command.
  try {
    const id = await fetchIdentity(cfg, signal);
    identityCache.set(mcpUrl, { identity: id, cached_at_ms: Date.now() });
    process.stderr.write(formatBanner(mcpUrl, id) + '\n');
    // v0.31.11: detect remote-version drift, prompt user to upgrade.
    await maybePromptForUpgrade(cfg, id, cliOpts, false);
  } catch {
    // Swallow. Banner suppressed; main command continues. The CDX-4
    // hardened callRemoteTool will surface the same error class on the
    // actual command call if the host is genuinely unreachable.
  }
}
