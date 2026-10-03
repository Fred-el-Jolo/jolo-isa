#!/usr/bin/env node
// Composes a pre-existing statusLine command (e.g. ccstatusline) with the
// ISA statusLine, so installing this doesn't hide the other tool. The ISA
// rows start on their own line below the other tool's output.
//
// Usage: node statusline-wrapper.cjs <nodeBin> <harnessPath> [innerCommand]
// Receives the same stdin (JSON payload) and env ($COLUMNS etc.) that
// Claude Code gives any statusLine command, and forwards both to each half.

const { spawnSync } = require('child_process');

const [, , nodeBin, harnessPath, innerCommand] = process.argv;

let input = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => (input += chunk));
process.stdin.on('end', () => {
  const parts = [];

  if (innerCommand) {
    const inner = spawnSync(innerCommand, { input, shell: true, encoding: 'utf-8', env: process.env });
    if (inner.status === 0 && inner.stdout && inner.stdout.trim()) {
      parts.push(inner.stdout.trim());
    }
  }

  const isa = spawnSync(nodeBin, [harnessPath, 'render'], { input, encoding: 'utf-8', env: process.env });
  if (isa.status === 0 && isa.stdout && isa.stdout.trim()) {
    parts.push(isa.stdout.trim());
  }

  process.stdout.write(parts.join('\n'));
  process.exit(0);
});
