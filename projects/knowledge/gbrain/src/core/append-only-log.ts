/**
 * append-only-log.ts — gbrain AppendOnlyLog (TypeScript / zod v4)
 *
 * 原子 append JSONL 抽象，zod schema 校验 + OS 级别 O_APPEND 原子追加。
 * 复用 `src/core/audit-week-file.ts` 的 ISO-week 轮转逻辑。
 *
 * 契约 (§12.2.2):
 *   1. 写前用 zod schema 校验数据，漂移时拒绝写入
 *   2. fs.appendFileSync 用 O_APPEND flag（OS 级原子追加）
 *   3. JSON sort_keys=true 保证追加顺序确定性
 *   4. 不修旧记录，只追加新记录
 */

import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { z } from 'zod';
import type { ZodError } from 'zod';
import { isoWeekFilename } from './audit-week-file.ts';

export interface AppendOnlyLogOptions {
  /**
   * JSONL 文件路径。
   * 含 ISO-week 占位符 `{YYYY-Www}` 时自动轮转：
   *   e.g. `~/.gbrain/audit/budget-{YYYY-Www}.jsonl`
   */
  filePath: string;
  /** zod v4 schema，写入前校验 */
  schema: z.ZodSchema;
  /** ISO-week 前缀（配合 {YYYY-Www} 占位符使用） */
  prefix?: string;
  /**
   * 是否 sort_keys=true（JSON.stringify 时按键排序，默认 true）。
   * §12.1.4 跨仓 4 不变量：AppendOnlyLog 必须 sort_keys=True。
   */
  sortKeys?: boolean;
}

/** 校验失败的行 */
export interface DriftRecord {
  lineno: number;
  raw: string;
  issue: string;
}

/** appendMany() 的结果 */
export interface AppendResult {
  appended: number;
  drift: DriftRecord[];
}

/** ISO-week 占位符 */
const WEEK_PATTERN = /\{YYYY-Www\}/;

/**
 * 解析带 ISO-week 占位符的文件路径，返回真实路径。
 * `~/.gbrain/audit/budget-{YYYY-Www}.jsonl` → `~/.gbrain/audit/budget-2026-W24.jsonl`
 */
function resolvePath(filePath: string, prefix?: string): string {
  if (WEEK_PATTERN.test(filePath) && prefix) {
    return filePath.replace(WEEK_PATTERN, isoWeekFilename(prefix));
  }
  return filePath;
}

// ── AppendOnlyLog ──────────────────────────────────────────────────────────────

export class AppendOnlyLog {
  private readonly _opts: AppendOnlyLogOptions;

  constructor(opts: AppendOnlyLogOptions) {
    this._opts = { sortKeys: true, ...opts };
  }

  /**
   * 追加一条记录。
   * 写入前用 zod schema 校验，漂移时抛出 AuditLogError。
   *
   * @throws AuditLogError 校验失败时（不静默丢弃，符合 §17 债发现率要求）
   */
  append<T = unknown>(data: T): void {
    const result = this.appendMany([data]);
    if (result.drift.length > 0) {
      const d = result.drift[0];
      throw new AuditLogError(
        `Schema drift: ${d.issue}`,
        result.drift,
      );
    }
  }

  /**
   * 批量追加记录。返回追加数和漂移行列表。
   */
  appendMany<T = unknown>(records: T[]): AppendResult {
    if (records.length === 0) return { appended: 0, drift: [] };

    const s = this._opts.schema;
    const sortKeys = this._opts.sortKeys ?? true;
    const path = resolvePath(this._opts.filePath, this._opts.prefix);

    // 1. 逐条校验，收集有效 JSON 字符串
    const drift: DriftRecord[] = [];
    const lines: string[] = [];
    for (let i = 0; i < records.length; i++) {
      const record = records[i];
      const parsed = s.safeParse(record);
      if (!parsed.success) {
        drift.push({
          lineno: i + 1,
          raw: JSON.stringify(record),
          issue: zodIssuesToString(parsed.error),
        });
        continue;
      }
      // Z-suffix 检查（如果 record 有 ts 字段）
      if (typeof record === 'object' && record !== null && 'ts' in record) {
        const ts = String((record as Record<string, unknown>)['ts']);
        if (!ts.endsWith('Z')) {
          drift.push({
            lineno: i + 1,
            raw: JSON.stringify(record),
            issue: `ts="${ts}" 缺 Z 后缀（UTC ISO8601）`,
          });
          continue;
        }
      }
      // 序列化（按 key 排序，§12.1.4 跨仓 4 不变量）
      // Replacer 必须是函数而非 key 数组：数组 replacer 会递归作用于嵌套对象，
      // 只保留顶层 key 集合里的名字，导致 candidates 等嵌套对象字段被静默丢弃
      // （写入 [{},{}]，读端 schema 校验失败 → audit 事件丢失）。
      const sortedKeysReplacer = (_key: string, value: unknown): unknown => {
        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
          return Object.fromEntries(
            Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)),
          );
        }
        return value;
      };
      const line = JSON.stringify(parsed.data, sortedKeysReplacer, 0);
      lines.push(line);
      // 注意：上面 sortKeys 分支未使用（replacer 已按 sort_keys 处理），
      // 但保留变量以应对未来 sortKeys=false 的扩展。
      void sortKeys;
    }

    if (lines.length === 0) return { appended: 0, drift };

    // 2. mkdir
    mkdirSync(dirname(path), { recursive: true });

    // 3. 原子追加（O_APPEND，OS 级原子，多进程安全）
    appendFileSync(path, lines.join('\n') + '\n', 'utf-8');

    return { appended: lines.length, drift };
  }

  /**
   * 同步读取所有记录。
   *
   * @param filter 可选：过滤函数（返回 true 保留该行）
   */
  readAllSync<T = unknown>(filter?: (record: T, lineno: number) => boolean): T[] {
    const path = resolvePath(this._opts.filePath, this._opts.prefix);
    const s = this._opts.schema;

    let content: string;
    try {
      content = readFileSync(path, 'utf-8');
    } catch {
      return [];
    }

    const out: T[] = [];
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      try {
        const raw = JSON.parse(line) as unknown;
        const parsed = s.safeParse(raw);
        if (!parsed.success) continue;
        if (!filter || filter(parsed.data as T, i + 1)) {
          out.push(parsed.data as T);
        }
      } catch {
        // corrupt row — skip
      }
    }
    return out;
  }

  /** 返回最新一条记录 */
  latest<T = unknown>(): T | null {
    const records = this.readAllSync<T>();
    return records.length > 0 ? records[records.length - 1] : null;
  }

  /**
   * 用 zod schema 审计，返回漂移行列表。
   * 读路径漂移静默跳过（不投毒已有数据），写路径拒绝。
   */
  auditSync(): DriftRecord[] {
    const path = resolvePath(this._opts.filePath, this._opts.prefix);
    const s = this._opts.schema;

    let content: string;
    try {
      content = readFileSync(path, 'utf-8');
    } catch {
      return [];
    }

    const drift: DriftRecord[] = [];
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      let raw: unknown;
      try {
        raw = JSON.parse(line);
      } catch (e) {
        drift.push({
          lineno: i + 1,
          raw: line,
          issue: `JSON 解析失败: ${String(e)}`,
        });
        continue;
      }
      const parsed = s.safeParse(raw);
      if (!parsed.success) {
        drift.push({
          lineno: i + 1,
          raw: line,
          issue: zodIssuesToString(parsed.error),
        });
        continue;
      }
      // Z-suffix 检查
      if (typeof raw === 'object' && raw !== null && 'ts' in raw) {
        const ts = String((raw as Record<string, unknown>)['ts']);
        if (!ts.endsWith('Z')) {
          drift.push({
            lineno: i + 1,
            raw: line,
            issue: `ts="${ts}" 缺 Z 后缀（UTC ISO8601）`,
          });
        }
      }
    }
    return drift;
  }

  /** 当前文件路径（已解析 ISO-week 占位符） */
  get filePath(): string {
    return resolvePath(this._opts.filePath, this._opts.prefix);
  }
}

// ── 错误类型 ────────────────────────────────────────────────────────────────

export class AuditLogError extends Error {
  readonly drift: DriftRecord[];
  constructor(message: string, drift: DriftRecord[]) {
    super(message);
    this.name = 'AuditLogError';
    this.drift = drift;
  }
}

// ── ZTimestampModel 等价物（zod v4）───────────────────────────────────────

/**
 * zod v4 mixin：校验 ts 字段以 Z 结尾（UTC ISO8601）。
 *
 * ```ts
 * const MyEventSchema = ZTimestampSchema.extend({
 *   event: z.string(),
 * });
 * ```
 */
export const ZTimestampSchema = z.object({
  ts: z
    .string()
    .refine(
      (s: string) =>
        s.endsWith('Z') &&
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(s),
      { message: 'ts must be UTC ISO8601 ending in Z (e.g. 2026-06-11T00:00:00Z or 2026-06-11T00:00:00.123Z)' },
    ),
});

export type ZTimestamp = z.infer<typeof ZTimestampSchema>;

/**
 * 构造 UTC Z-suffix 时间戳。
 * 等价于 Python 的 `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`
 * 注意：`new Date().toISOString()` 在 Python 3.14 返回 `+00:00` 而非 `Z`，
 * 故手动格式化。
 */
export function utcNow(): string {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const h = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  const s = String(d.getUTCSeconds()).padStart(2, '0');
  return `${y}-${m}-${day}T${h}:${min}:${s}Z`;
}

// ── 工具函数 ───────────────────────────────────────────────────────────────

/** 解析 zod v4 error issues 为单行字符串 */
function zodIssuesToString(error: ZodError): string {
  return error.issues.map(i => `${i.path.join('.')}: ${i.message}`).join('; ');
}

// ── 显式 re-export（让测试更易 import）─────────────────────────────────────
export { writeFileSync, readFileSync };
