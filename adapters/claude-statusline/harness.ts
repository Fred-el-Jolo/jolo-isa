#!/usr/bin/env node
// Claude Code statusLine command:
//
//   node harness.ts render    stdin: { session_id, cwd, ... }, width via $COLUMNS
//
// Shows the ISA bound to this session by the ISA hooks, as reported by
// `isa status --json`. Pure read: it never writes anything, prints nothing
// when no ISA is bound, and always exits 0.

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { loadView, resolveIsaBin } from './isa.ts';
import { renderStatusLine } from './renderer.ts';
import type { StatusLineConfig } from './types.ts';

const CONFIG_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), 'config.json');

function loadConfig(): StatusLineConfig {
  const defaults: StatusLineConfig = { mode: 'auto', color: true };
  try {
    return { ...defaults, ...JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8')) };
  } catch {
    return defaults;
  }
}

function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    if (process.stdin.isTTY) {
      resolve('');
      return;
    }
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', () => resolve(data));
  });
}

async function runRender(): Promise<void> {
  let payload: { session_id?: string } = {};
  try {
    payload = JSON.parse(await readStdin());
  } catch {
    process.exit(0);
  }
  if (!payload.session_id) process.exit(0);

  const config = loadConfig();
  const columns = Number.parseInt(process.env.COLUMNS || '', 10) || 80;
  try {
    const view = loadView(payload.session_id, resolveIsaBin(config.isaBin));
    const color = config.color && !process.env.NO_COLOR;
    const output = renderStatusLine(view, columns, config.mode, color);
    if (output) process.stdout.write(output);
  } catch (err) {
    process.stderr.write(`isa statusline error: ${err}\n`);
  }
  process.exit(0);
}

if (process.argv[2] === 'render') runRender();
else process.exit(0);
