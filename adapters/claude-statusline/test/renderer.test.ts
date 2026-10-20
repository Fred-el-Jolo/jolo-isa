// Run: node --test test/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderStatusLine } from '../renderer.ts';
import type { IsaView } from '../types.ts';

const view = (over: Partial<IsaView> = {}): IsaView => ({
  bound: '/tmp/x/ISA.md',
  spec: null,
  stage: 'BUILD',
  task: 'Rebuild progress-outline as the ISA status line',
  effort: 'E3',
  phase: 'build',
  progress: '2/5',
  iscs: [
    { id: 'ISC-1', text: 'first', done: true },
    { id: 'ISC-2.1', text: 'second', done: true },
    { id: 'ISC-3.4.2', text: 'third open', done: false },
    { id: 'ISC-4', text: 'fourth open', done: false },
    { id: 'ISC-5', text: 'fifth open', done: false },
  ],
  ...over,
});

const plain = (v: IsaView | null, columns = 100, mode: 'wide' | 'compact' | 'auto' = 'wide') =>
  renderStatusLine(v, columns, mode, false);

const allDone = (over: Partial<IsaView> = {}) =>
  view({ progress: '5/5', iscs: view().iscs.map((i) => ({ ...i, done: true })), ...over });

test('wide one row: tier first, bar, progress, stage, current ISC, task', () => {
  const out = plain(view());
  assert.ok(!out.includes('\n'));
  assert.equal(out, 'E3 - ##--- 2/5 · BUILD · ISC-3.4.2 · Rebuild progress-outline as the ISA status line');
});

test('wide one row: the task is cut to the width, then dropped', () => {
  const out = plain(view(), 50);
  assert.equal(out.length, 50);
  assert.ok(out.startsWith('E3 - ##--- 2/5 · BUILD · ISC-3.4.2 · Rebuil') && out.endsWith('…'));
  assert.equal(plain(view(), 38), 'E3 - ##--- 2/5 · BUILD · ISC-3.4.2');
});

test('compact tier: one line with tier, progress, stage, current ISC, within width', () => {
  assert.equal(plain(view(), 30, 'compact'), 'E3 - 2/5 BUILD ISC-3.4.2');
  const narrow = plain(view(), 15, 'compact');
  assert.equal(narrow.length, 15);
  assert.ok(narrow.endsWith('…'));
});

test('stage labels drop the ISA prefix and replace the phase', () => {
  const label = (stage: string) => plain(view({ stage }), 30, 'compact').split(' ')[3];
  assert.equal(label('ISA DRAFT'), 'DRAFT');
  assert.equal(label('ISA REFINE'), 'REFINE');
  assert.equal(label('BUILD'), 'BUILD');
  assert.equal(plain(allDone({ stage: 'CLOSED', phase: 'complete' }), 60, 'compact'), 'E3 - 5/5 CLOSED');
  assert.ok(!plain(view({ phase: 'draft', stage: 'ISA DRAFT' })).includes('draft'));
});

test('only the current ISC: its id, no text, no other open id, no +N', () => {
  const out = plain(view(), 200);
  assert.ok(out.includes('ISC-3.4.2'));
  for (const no of ['third open', 'ISC-4', 'ISC-5', '+']) assert.ok(!out.includes(no), no);
});

test('all ticked but not closed says so; closed shows no ISC', () => {
  assert.equal(plain(allDone(), 60, 'compact'), 'E3 - 5/5 BUILD all verified');
  assert.equal(plain(allDone({ stage: 'CLOSED' }), 100), 'E3 - ##### 5/5 · CLOSED · Rebuild progress-outline as the ISA status line');
});

test('spec only: tier, stage and the spec file name', () => {
  const spec = view({ bound: null, spec: '/p/docs/2026-10-13-foo-01-spec.md', stage: 'SPEC DRAFT', iscs: [] });
  assert.equal(plain(spec), 'E3 - SPEC DRAFT · 2026-10-13-foo-01-spec.md');
  assert.equal(plain({ ...spec, stage: 'SPEC ACKED' }, 40, 'compact'), 'E3 - SPEC ACKED · 2026-10-13-foo-01-spe…');
});

test('auto picks compact under 70 columns', () => {
  assert.ok(!plain(view(), 60, 'auto').includes('##'));
  assert.ok(plain(view(), 90, 'auto').includes('##'));
});

test('nothing bound renders nothing', () => {
  assert.equal(plain(null), '');
  assert.equal(plain(view({ bound: null, spec: null, stage: 'TRIAGE', iscs: [] })), '');
  assert.equal(plain(view({ bound: null, spec: '/p/docs/old-01-spec.md', stage: 'TRIAGE', iscs: [] })), '');
});

test('color off emits no escape codes; color on does', () => {
  assert.ok(!plain(view()).includes('\x1b'));
  assert.ok(!plain(view(), 40, 'compact').includes('\x1b'));
  assert.ok(renderStatusLine(view(), 100, 'wide', true).includes('\x1b'));
});

test('bar is capped at 20 dots for large ISAs', () => {
  const iscs = Array.from({ length: 40 }, (_, n) => ({ id: `ISC-${n + 1}`, text: 't', done: n < 10 }));
  assert.ok(plain(view({ iscs, progress: '10/40' })).startsWith('E3 - #####--------------- 10/40'));
});

test('a DISABLED session shows only that, bound or not', () => {
  assert.equal(plain(view({ mode: 'disabled' })), 'ISA DISABLED');
  assert.equal(plain(view({ bound: null, spec: null, stage: 'TRIAGE', iscs: [], mode: 'disabled' }), 40, 'compact'), 'ISA DISABLED');
  assert.ok(plain(view({ mode: 'on' })).startsWith('E3 - '));
});
