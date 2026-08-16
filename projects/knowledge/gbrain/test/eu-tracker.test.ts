/**
 * Tests for gbrain EU cost tracker module.
 *
 * Uses bun:test (built-in) and global fetch mocking.
 */

import { describe, test, expect, mock, beforeEach, afterEach } from 'bun:test';

// ── Module under test ─────────────────────────────────────────
const { trackMemoryWriteEUCost } = await import('../src/core/eu-tracker.ts');

// ── Helpers ────────────────────────────────────────────────────

function mockFetch(response: Partial<Response>): void {
  globalThis.fetch = mock(() => Promise.resolve(response as Response)) as unknown as typeof fetch;
}

function mockFetchError(message: string): void {
  globalThis.fetch = mock(() => Promise.reject(new Error(message))) as unknown as typeof fetch;
}

function restoreFetch(): void {
  delete (globalThis as any).fetch;
}

// ── Tests ─────────────────────────────────────────────────────

describe('trackMemoryWriteEUCost', () => {
  afterEach(() => {
    restoreFetch();
  });

  test('sends POST to D-Economy with correct payload', async () => {
    let calledUrl = '';
    let calledBody = '';
    let calledHeaders: Record<string, string> = {};

    globalThis.fetch = mock(async (url: RequestInfo | URL, opts?: RequestInit) => {
      calledUrl = url.toString();
      calledBody = opts?.body as string;
      calledHeaders = (opts?.headers || {}) as Record<string, string>;
      return new Response('ok', { status: 200 });
    }) as unknown as typeof fetch;

    await trackMemoryWriteEUCost('gbrain', 'gbrain_memory_write', 1);

    expect(calledUrl).toBe('http://localhost:7430/api/v1/economy/consume');
    expect(JSON.parse(calledBody)).toEqual({
      caller: 'gbrain',
      cost: 1,
      operation: 'gbrain_memory_write',
    });
    expect(calledHeaders['Content-Type']).toBe('application/json');
  });

  test('does NOT throw when D-Economy returns non-200', async () => {
    mockFetch({
      ok: false,
      status: 402,
      statusText: 'Payment Required',
    } as Response);

    await expect(trackMemoryWriteEUCost()).resolves.toBeUndefined();
  });

  test('does NOT throw on network error', async () => {
    mockFetchError('ECONNREFUSED');
    await expect(trackMemoryWriteEUCost()).resolves.toBeUndefined();
  });

  test('does NOT throw on timeout', async () => {
    globalThis.fetch = mock(async () => {
      throw new DOMException('The operation was aborted', 'AbortError');
    }) as unknown as typeof fetch;
    await expect(trackMemoryWriteEUCost()).resolves.toBeUndefined();
  });

  test('uses default caller and operation when not specified', async () => {
    let calledBody = '';
    globalThis.fetch = mock(async (_url, opts) => {
      calledBody = opts?.body as string;
      return new Response('ok', { status: 200 });
    }) as unknown as typeof fetch;

    await trackMemoryWriteEUCost();

    const payload = JSON.parse(calledBody);
    expect(payload.caller).toBe('gbrain');
    expect(payload.operation).toBe('gbrain_memory_write');
    expect(payload.cost).toBe(1);
  });

  test('accepts custom endpoint with trailing slash stripped', async () => {
    let calledUrl = '';
    globalThis.fetch = mock(async (url) => {
      calledUrl = url.toString();
      return new Response('ok', { status: 200 });
    }) as unknown as typeof fetch;

    await trackMemoryWriteEUCost('gbrain', 'gbrain_memory_write', 1, 'http://localhost:9999/');

    expect(calledUrl).toBe('http://localhost:9999/api/v1/economy/consume');
  });
});
