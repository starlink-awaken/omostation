/**
 * EU (Energy Unit) cost tracking for gbrain memory writes.
 *
 * Fire-and-forget HTTP calls to SharedBrain D-Economy API.
 * Failures are logged but never block the caller.
 *
 * D-Economy endpoint: http://localhost:7430
 * (same endpoint used by kairon/eu-pricing/EULedger)
 */

const DEFAULT_ECONOMY_ENDPOINT = process.env.SHAREDBRAIN_ENDPOINT || process.env.ECONOMY_ENDPOINT || 'http://localhost:7430';

/**
 * Fire-and-forget EU cost tracking for a memory write operation.
 *
 * @param caller - caller identifier (default "gbrain")
 * @param operation - operation name (e.g. "gbrain_memory_write")
 * @param cost - EU cost (default 1)
 * @param endpoint - SharedBrain D-Economy endpoint override
 */
export async function trackMemoryWriteEUCost(
  caller: string = 'gbrain',
  operation: string = 'gbrain_memory_write',
  cost: number = 1,
  endpoint: string = DEFAULT_ECONOMY_ENDPOINT,
): Promise<void> {
  try {
    const url = `${endpoint.replace(/\/$/, '')}/api/v1/economy/consume`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caller, cost, operation }),
      signal: AbortSignal.timeout(5_000),
    });

    if (!resp.ok) {
      console.warn(
        `[eu-tracker] eu_cost_tracking_failed caller=${caller} operation=${operation} cost=${cost} status=${resp.status}`,
      );
    }
  } catch (err) {
    // Fire-and-forget: failures never propagate to the caller
    console.debug(
      `[eu-tracker] eu_cost_tracking_skipped caller=${caller} operation=${operation} cost=${cost} error=${(err as Error).message}`,
    );
  }
}
