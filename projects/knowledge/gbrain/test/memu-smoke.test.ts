/**
 * memU engine smoke test (F7114ABA B++ 阶段 6).
 * Verifies the repaired MemUEngine can actually run, not just typecheck green.
 * createEngine({engine:'memu'}) → connect → initSchema → putPage → getPage → disconnect.
 */
import { test, expect } from 'bun:test';
import { createEngine } from '../src/core/engine-factory.ts';
import type { BrainEngine } from '../src/core/engine.ts';

test('memu engine: create + connect + initSchema + put/get page round-trip', async () => {
  const engine: BrainEngine = await createEngine({ engine: 'memu', database_path: ':memory:' } as any);
  expect(engine.kind).toBe('memu');

  await engine.connect({ database_path: ':memory:' } as any);
  await engine.initSchema();

  // putPage + getPage round-trip
  await engine.putPage('test/hello', {
    type: 'wiki',
    title: 'Hello',
    compiled_truth: 'world content',
  } as any, { sourceId: 'default' });

  const page = await engine.getPage('test/hello', { sourceId: 'default' });
  expect(page).not.toBeNull();
  expect(page?.slug).toBe('test/hello');
  expect(page?.title).toBe('Hello');

  // link round-trip
  await engine.addLink('test/hello', 'test/world', undefined, 'mentions');
  const links = await engine.getLinks('test/hello', { sourceId: 'default' });
  expect(links.length).toBeGreaterThanOrEqual(1);

  // config round-trip
  await engine.setConfig('smoke.key', 'value');
  const cfg = await engine.getConfig('smoke.key');
  expect(cfg).toBe('value');

  await engine.disconnect();
});

test('memu engine: getStats returns brain stats shape', async () => {
  const engine: BrainEngine = await createEngine({ engine: 'memu', database_path: ':memory:' } as any);
  await engine.connect({ database_path: ':memory:' } as any);
  await engine.initSchema();

  await engine.putPage('a', { type: 'wiki', title: 'A', compiled_truth: 'x' } as any);
  const stats = await engine.getStats();
  expect(stats.page_count).toBeGreaterThanOrEqual(1);

  await engine.disconnect();
});
