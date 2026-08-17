/**
 * append-only-log.test.ts — AppendOnlyLog 单元测试
 *
 * 验证：
 *   1. 写：原子追加 + sort_keys + Z-suffix 校验
 *   2. 读：readAllSync + 漂移跳过
 *   3. 审计：auditSync 返回漂移行
 *   4. ISO-week 轮转
 *   5. 错误路径：校验失败抛 AuditLogError
 */

import { describe, it, expect, beforeEach, afterEach } from 'bun:test';
import { existsSync, mkdirSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import {
  AppendOnlyLog,
  AuditLogError,
  ZTimestampSchema,
  utcNow,
  type DriftRecord,
} from '../../src/core/append-only-log.ts';
import { isoWeekFilename, resolveAuditDir } from '../../src/core/audit-week-file.ts';

const TMP = '/tmp/gbrain-append-only-log-test';
const TEST_FILE = join(TMP, 'test-{YYYY-Www}.jsonl');
const TEST_PREFIX = 'aol-test';

const TestEventSchema = ZTimestampSchema.extend({
  event: z.string(),
  count: z.number().int().nonnegative().default(0),
});

type TestEvent = z.infer<typeof TestEventSchema>;

function cleanDir() {
  if (existsSync(TMP)) rmSync(TMP, { recursive: true, force: true });
  mkdirSync(TMP, { recursive: true });
}

beforeEach(() => {
  cleanDir();
});

afterEach(() => {
  cleanDir();
});

describe('AppendOnlyLog — 基本读写', () => {
  it('write/read 一条记录', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const event: TestEvent = { ts: utcNow(), event: 'hello', count: 1 };
    log.append(event);

    const read = log.readAllSync<TestEvent>();
    expect(read).toHaveLength(1);
    expect(read[0]).toEqual(event);
  });

  it('write/read 多条记录（按追加顺序）', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const ev1: TestEvent = { ts: utcNow(), event: 'first', count: 1 };
    const ev2: TestEvent = { ts: utcNow(), event: 'second', count: 2 };
    const ev3: TestEvent = { ts: utcNow(), event: 'third', count: 3 };
    log.appendMany([ev1, ev2, ev3]);

    const read = log.readAllSync<TestEvent>();
    expect(read).toHaveLength(3);
    expect(read[0]?.event).toBe('first');
    expect(read[1]?.event).toBe('second');
    expect(read[2]?.event).toBe('third');
  });

  it('latest() 返回最后一条', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const ev1: TestEvent = { ts: utcNow(), event: 'first', count: 1 };
    const ev2: TestEvent = { ts: utcNow(), event: 'last', count: 99 };
    log.append(ev1);
    log.append(ev2);

    const latest = log.latest<TestEvent>();
    expect(latest?.event).toBe('last');
    expect(latest?.count).toBe(99);
  });
});

describe('AppendOnlyLog — 文件不存在', () => {
  it('readAllSync 返回空数组', () => {
    const log = new AppendOnlyLog({
      filePath: join(TMP, 'never-created-{YYYY-Www}.jsonl'),
      prefix: 'never',
      schema: TestEventSchema,
    });
    expect(log.readAllSync()).toEqual([]);
    expect(log.latest()).toBeNull();
  });
});

describe('AppendOnlyLog — Z-suffix 校验', () => {
  it('拒绝缺 Z-suffix 的 ts', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const bad = { ts: '2026-06-11T00:00:00+00:00', event: 'no-z', count: 1 };
    expect(() => log.append(bad)).toThrow(AuditLogError);
  });

  it('auditSync 报告缺 Z 的旧记录', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    // 直接写一个缺 Z 的行（绕过 appendMany）
    const file = log.filePath;
    writeFileSync(file, JSON.stringify({ ts: '2026-06-11T00:00:00', event: 'no-z' }) + '\n', 'utf-8');

    const drift = log.auditSync();
    expect(drift.length).toBe(1);
    expect(drift[0]?.issue).toContain('Z');
  });
});

describe('AppendOnlyLog — Schema 校验', () => {
  it('拒绝错误类型', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const bad = { ts: utcNow(), event: 123, count: 1 }; // event 应为 string
    expect(() => log.append(bad)).toThrow(AuditLogError);
  });

  it('auditSync 报告 schema 漂移', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const file = log.filePath;
    writeFileSync(file, JSON.stringify({ ts: utcNow(), event: 123 }) + '\n', 'utf-8');

    const drift = log.auditSync();
    expect(drift.length).toBe(1);
    expect(drift[0]?.lineno).toBe(1);
  });
});

describe('AppendOnlyLog — sort_keys', () => {
  it('JSON 按 key 排序', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    log.append({ ts: utcNow(), event: 'sort-test', count: 1 });

    const content = readFileSync(log.filePath, 'utf-8');
    // 排序后：count, event, ts
    expect(content).toContain('"count":1');
    expect(content).toContain('"event":"sort-test"');
  });
});

describe('AppendOnlyLog — 漂移写', () => {
  it('appendMany 混合有效/无效记录', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const valid: TestEvent = { ts: utcNow(), event: 'ok', count: 1 };
    const invalid = { ts: utcNow(), event: 999, count: 1 } as unknown as TestEvent;
    const result = log.appendMany([valid, invalid]);

    expect(result.appended).toBe(1);
    expect(result.drift).toHaveLength(1);
    // 有效记录应写入
    expect(log.readAllSync()).toHaveLength(1);
  });
});

describe('AppendOnlyLog — ISO-week 轮转', () => {
  it('filePath getter 返回解析后的周文件名', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const expected = isoWeekFilename(TEST_PREFIX);
    expect(log.filePath).toContain(expected);
  });
});

describe('AppendOnlyLog — drift write 抛出', () => {
  it('append 抛 AuditLogError 包含 drift 详情', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const bad = { ts: utcNow(), event: 999, count: 1 } as unknown as TestEvent;
    try {
      log.append(bad);
      expect(true).toBe(false); // 不应到达
    } catch (err) {
      expect(err).toBeInstanceOf(AuditLogError);
      const aErr = err as AuditLogError;
      expect(aErr.drift).toHaveLength(1);
      expect(aErr.drift[0]?.issue).toBeTruthy();
    }
  });
});

describe('AppendOnlyLog — corrupt row 读取跳过', () => {
  it('坏 JSON 行不污染读取', () => {
    const log = new AppendOnlyLog({
      filePath: TEST_FILE,
      prefix: TEST_PREFIX,
      schema: TestEventSchema,
    });
    const file = log.filePath;
    writeFileSync(
      file,
      JSON.stringify({ ts: utcNow(), event: 'good', count: 1 }) + '\n' +
      'NOT VALID JSON\n' +
      JSON.stringify({ ts: utcNow(), event: 'also-good', count: 2 }) + '\n',
      'utf-8',
    );
    const read = log.readAllSync<TestEvent>();
    expect(read).toHaveLength(2);
    expect(read[0]?.event).toBe('good');
    expect(read[1]?.event).toBe('also-good');
  });
});

describe('utcNow — 格式', () => {
  it('返回 YYYY-MM-DDTHH:MM:SSZ 格式', () => {
    const ts = utcNow();
    expect(ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  });
});

describe('ZTimestampSchema', () => {
  it('接受合法 UTC Z-suffix 时间戳', () => {
    const r = ZTimestampSchema.safeParse({ ts: '2026-06-11T00:00:00Z' });
    expect(r.success).toBe(true);
  });

  it('接受带毫秒的 UTC 时间戳', () => {
    const r = ZTimestampSchema.safeParse({ ts: '2026-06-11T00:00:00.123Z' });
    expect(r.success).toBe(true);
  });

  it('接受 ISO toISOString() 输出', () => {
    // JS toISOString() 输出 .123Z 格式
    const r = ZTimestampSchema.safeParse({ ts: new Date().toISOString() });
    expect(r.success).toBe(true);
  });

  it('拒绝缺 Z 的时间戳', () => {
    const r = ZTimestampSchema.safeParse({ ts: '2026-06-11T00:00:00+00:00' });
    expect(r.success).toBe(false);
  });

  it('拒绝本地时区格式', () => {
    const r = ZTimestampSchema.safeParse({ ts: '2026-06-11 00:00:00' });
    expect(r.success).toBe(false);
  });
});
