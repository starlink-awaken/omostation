/** memU Engine — All-in-One Integration Test with Debug */
const { MemUEngine } = await import('../src/core/memu-engine.ts');

const TEST_DB = '/tmp/memu-all-test.db';
try { require('fs').unlinkSync(TEST_DB); } catch {}
const engine = new MemUEngine();
await engine.connect({ dbPath: TEST_DB, engine: 'memu' });
await engine.initSchema();

let p = 0, f = 0;
const check = (cond: boolean, msg: string) => {
  console.log(`  ${cond ? '✅' : '❌'} ${msg}`);
  if (cond) p++; else f++;
};

// Pages CRUD
const pg = await engine.putPage('hello', { title: 'Hello', body: 'World' });
check(pg.slug === 'hello', 'create page');
check((await engine.getPage('hello')).title === 'Hello', 'get page');
check((await engine.listPages()).length >= 1, 'list pages');
check((await engine.putPage('hello', { title: 'Updated', body: 'New' })).title === 'Updated', 'update');

// Tags
await engine.addTag('hello', 'important');
await engine.addTag('hello', 'ai');
const t = (await engine.getTags('hello')).map((x: any) => x.name);
check(t.includes('important'), 'add tag');
check(t.includes('ai'), 'multiple tags');
await engine.removeTag('hello', 'important');
check(!(await engine.getTags('hello')).map((x: any) => x.name).includes('important'), 'remove tag');

// Links
const s = await engine.putPage('src', { title: 'Source', body: 'x' });
check(s.slug === 'src', 'create src page');
const tg = await engine.putPage('tgt', { title: 'Target', body: 'y' });
check(tg.slug === 'tgt', 'create tgt page');
await engine.addLink('src', 'tgt', { linkType: 'refs' });
const links = await engine.getLinks('src');
check(links.some((l: any) => l.target_slug === 'tgt'), 'add link');
const bl = await engine.getBacklinks('tgt');
check(bl.some((l: any) => l.source_slug === 'src'), 'backlinks');
await engine.removeLink('src', 'tgt');
const linksAfter = await engine.getLinks('src');
check(!linksAfter.some((l: any) => l.target_slug === 'tgt'), 'remove link');

// Chunks
await engine.upsertChunks('hello', [{ content: 'chunk1', embedding: null }]);
check((await engine.getChunks('hello')).length === 1, 'upsert chunks');

// Raw data
await engine.putRawData('hello', { a: 1 }, { pageSlug: 'test' });
const rd = await engine.getRawData('hello');
check(JSON.parse(rd?.value || '{}')?.a === 1, 'raw data');

// Search
check((await engine.searchKeyword('Updated')).length >= 1, 'search keyword');

// Soft delete + restore
const sd = await engine.softDeletePage('hello');
check(sd?.slug === 'hello', 'soft delete');
check(await engine.restorePage('hello') === true, 'restore');

// Resolve slugs
await engine.putPage('hello-world', { title: 'HW', body: 'test' });
check((await engine.resolveSlugs('hello')).length >= 2, 'resolve slugs');

// Purge
await engine.softDeletePage('hello-world');
check((await engine.purgeDeletedPages(0)).count >= 0, 'purge deleted');

// Config
await engine.setConfig('theme', 'dark');
check(await engine.getConfig('theme') === 'dark', 'get config');
check((await engine.listConfigKeys()).includes('theme'), 'list config');
await engine.unsetConfig('theme');
check(await engine.getConfig('theme') === null, 'unset config');

// Stats & Health
check((await engine.getStats()).pageCount > 0, 'stats');
check((await engine.getHealth()).status === 'ok', 'health');

// Ingest
await engine.logIngest({ source: 'test', pages: 1, status: 'success' });
check((await engine.getIngestLog()).length >= 1, 'ingest log');

// Transaction
check(await engine.transaction(async (txn: any) => (await txn.getPage('hello'))?.slug) === 'hello', 'txn');

// Raw SQL
check(Number((await engine.executeRaw('SELECT COUNT(*) as cnt FROM pages'))[0].cnt) > 0, 'execute raw');

await engine.disconnect();
try { require('fs').unlinkSync(TEST_DB); } catch {}
console.log(`\n📊 ${p}/${p+f} passed (${(p/(p+f)*100).toFixed(1)}%)`);
console.log(`${f === 0 ? '✅' : '❌'} ${f === 0 ? 'ALL PASS — memU Engine READY' : 'SOME FAILED'}`);
process.exit(f === 0 ? 0 : 1);
