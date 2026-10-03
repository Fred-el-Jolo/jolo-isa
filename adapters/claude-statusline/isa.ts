import { spawnSync } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import type { IsaView } from './types.ts';

const TIMEOUT_MS = 1500;

export function resolveIsaBin(configured?: string): string {
  if (process.env.ISA_BIN) return process.env.ISA_BIN;
  if (configured) return configured;
  const local = path.join(os.homedir(), '.local', 'bin', 'isa');
  return fs.existsSync(local) ? local : 'isa';
}

// The session's bound ISA, or null when nothing is bound or anything fails.
// The runtime owns the binding and the ISA parsing; this only asks it.
export function loadView(sessionId: string, isaBin: string, harness = 'claude'): IsaView | null {
  const r = spawnSync(isaBin, ['status', '--json', '--harness', harness, '--session', sessionId], {
    encoding: 'utf-8',
    timeout: TIMEOUT_MS,
  });
  if (r.error || r.status !== 0 || !r.stdout) return null;
  try {
    const v = JSON.parse(r.stdout);
    if (!v || typeof v.bound !== 'string') return null;
    return { ...v, iscs: Array.isArray(v.iscs) ? v.iscs : [] };
  } catch {
    return null;
  }
}
