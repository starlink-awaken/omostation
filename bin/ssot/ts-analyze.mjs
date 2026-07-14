#!/usr/bin/env node
/**
 * ts-analyze.mjs — TypeScript file structure analyzer (P110-D, ADR-0111)
 *
 * Uses TypeScript Compiler API (built-in, no extra dep) to extract:
 * - top-level functions (with line counts)
 * - top-level classes
 * - top-level interfaces
 * - top-level type aliases
 *
 * Output: JSON to stdout, suitable for Python subprocess.
 *
 * Usage:
 *   node ts-analyze.mjs <file.ts>          # single file
 *   node ts-analyze.mjs <dir>             # recursive batch
 *   node ts-analyze.mjs --json <file.ts>   # explicit JSON
 *
 * Returns: { path, total_lines, top_functions, top_classes, top_interfaces, error? }
 */

import { readFileSync, statSync, readdirSync } from 'node:fs';
import { join, extname, relative } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
// Use typescript from gbrain's node_modules (P110-D ts-morph 替代)
// Try multiple locations (gbrain/ecos/aetherforge/...)
function loadTypescript() {
  for (const p of [
    'projects/gbrain/node_modules/typescript',
    '/opt/homebrew/lib/node_modules/typescript',
  ]) {
    try { return require(p); } catch (e) { /* try next */ }
  }
  throw new Error('typescript not found in expected locations');
}
const ts = loadTypescript();

function analyzeFile(filePath) {
  const source = readFileSync(filePath, 'utf-8');
  const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true);
  const lines = source.split('\n').length;

  const functions = [];
  const classes = [];
  const interfaces = [];
  const typeAliases = [];

  for (const stmt of sourceFile.statements) {
    if (ts.isFunctionDeclaration(stmt) && stmt.name) {
      const start = sourceFile.getLineAndCharacterOfPosition(stmt.getStart(sourceFile)).line + 1;
      const end = stmt.getEnd() > 0
        ? sourceFile.getLineAndCharacterOfPosition(stmt.getEnd()).line + 1
        : start;
      functions.push({ name: stmt.name.text, lines: end - start + 1, lineno: start });
    } else if (ts.isClassDeclaration(stmt) && stmt.name) {
      const start = sourceFile.getLineAndCharacterOfPosition(stmt.getStart(sourceFile)).line + 1;
      const end = stmt.getEnd() > 0
        ? sourceFile.getLineAndCharacterOfPosition(stmt.getEnd()).line + 1
        : start;
      classes.push({ name: stmt.name.text, lines: end - start + 1, lineno: start });
    } else if (ts.isInterfaceDeclaration(stmt)) {
      const start = sourceFile.getLineAndCharacterOfPosition(stmt.getStart(sourceFile)).line + 1;
      const end = stmt.getEnd() > 0
        ? sourceFile.getLineAndCharacterOfPosition(stmt.getEnd()).line + 1
        : start;
      interfaces.push({ name: stmt.name.text, lines: end - start + 1, lineno: start });
    } else if (ts.isTypeAliasDeclaration(stmt) && stmt.name) {
      const start = sourceFile.getLineAndCharacterOfPosition(stmt.getStart(sourceFile)).line + 1;
      const end = stmt.getEnd() > 0
        ? sourceFile.getLineAndCharacterOfPosition(stmt.getEnd()).line + 1
        : start;
      typeAliases.push({ name: stmt.name.text, lines: end - start + 1, lineno: start });
    }
  }

  // Sort by size desc
  functions.sort((a, b) => b.lines - a.lines);
  classes.sort((a, b) => b.lines - a.lines);
  interfaces.sort((a, b) => b.lines - a.lines);
  typeAliases.sort((a, b) => b.lines - a.lines);

  return {
    path: filePath,
    total_lines: lines,
    top_functions: functions.slice(0, 20),
    top_classes: classes.slice(0, 20),
    top_interfaces: interfaces.slice(0, 20),
    top_type_aliases: typeAliases.slice(0, 20),
  };
}

function collectTsFiles(dir) {
  const results = [];
  const walk = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name === '.venv' || entry.name === '__pycache__') continue;
      const full = join(d, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile() && (extname(entry.name) === '.ts' || extname(entry.name) === '.tsx')) {
        results.push(full);
      }
    }
  };
  walk(dir);
  return results.sort();
}

function main() {
  const args = process.argv.slice(2);
  const jsonFlag = args.includes('--json');
  const target = args.find(a => !a.startsWith('--')) || '.';

  let results;
  try {
    const stat = statSync(target);
    if (stat.isDirectory()) {
      const files = collectTsFiles(target);
      results = files.map(f => analyzeFile(f));
    } else {
      results = [analyzeFile(target)];
    }
  } catch (e) {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  }

  console.log(JSON.stringify(results, null, 2));
}

main();
