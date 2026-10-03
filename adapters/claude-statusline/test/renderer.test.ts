// Run: node --test test/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderStatusLine } from '../renderer.ts';
import type { IsaView } from '../types.ts';

const view = (over: Partial<IsaView> = {}): IsaView => ({
  bound: '/tmp/x/ISA.md',
  task: 'Rebuild progress-outline as the ISA status line',
  effort: 'E3',
  phase: 'build',
  progress: '2/5',
  iteration: null,
  iscs: [
    { id: 'ISC-1', text: 'first', done: true },
    { id: 'ISC-2', text: 'second', done: true },
    { id: 'ISC-3', text: 'third open', done: false },
    { id: 'ISC-4', text: 'fourth open', done: false },
    { id: 'ISC-5', text: 'fifth open', done: false },
  ],
  ...over,
});

const plain = (v: IsaView | null, columns = 100, mode: 'wide' | 'compact' | 'auto' = 'wide') =>
  renderStatusLine(v, columns, mode, false);

test('wide row 1: progress bar, tier, phase, task', () => {
  const [head] = plain(view()).split('\n');
  assert.equal(head, '##--- 2/5  E3 · build · Rebuild progress-outline as the ISA status line');
});

test('wide: two open ISCs, the last with +N', () => {
  const rows = plain(view()).split('\n');
  assert.deepEqual(rows.slice(1), ['[ ] ISC-3 third open', '[ ] ISC-4 fourth open  +1']);
});

test('wide: a single open ISC gets no +N', () => {
  const v = view({ progress: '4/5', iscs: view().iscs.map((i) => ({ ...i, done: i.id !== 'ISC-5' })) });
  assert.deepEqual(plain(v).split('\n').slice(1), ['[ ] ISC-5 fifth open']);
});

test('compact: one line with progress, phase, first open ISC, within width', () => {
  const out = plain(view(), 30, 'compact');
  assert.equal(out, '2/5 build ISC-3 third open');
  const narrow = plain(view({ iscs: [{ id: 'ISC-1', text: 'x'.repeat(200), done: false }] }), 40, 'compact');
  assert.ok(!narrow.includes('\n'));
  assert.equal(narrow.length, 40);
  assert.ok(narrow.endsWith('…'));
});

test('auto picks compact under 70 columns', () => {
  assert.ok(!plain(view(), 60, 'auto').includes('\n'));
  assert.ok(plain(view(), 90, 'auto').includes('\n'));
});

test('phase complete shows a done row instead of open ISCs', () => {
  const done = view({ phase: 'complete', progress: '5/5', iscs: view().iscs.map((i) => ({ ...i, done: true })) });
  assert.deepEqual(plain(done).split('\n').slice(1), ['[x] complete']);
  assert.equal(plain(done, 60, 'compact'), '5/5 [x] complete');
});

test('all ticked but not closed says so', () => {
  const v = view({ phase: 'verify', progress: '5/5', iscs: view().iscs.map((i) => ({ ...i, done: true })) });
  assert.equal(plain(v, 60, 'compact'), '5/5 verify all ISCs verified');
});

test('iteration > 1 is marked on the phase', () => {
  assert.ok(plain(view({ iteration: 2 })).startsWith('##--- 2/5  E3 · build ↻2 ·'));
});

test('no bound ISA renders nothing', () => {
  assert.equal(plain(null), '');
});

test('color off emits no escape codes; color on does', () => {
  assert.ok(!plain(view()).includes('\x1b'));
  assert.ok(!plain(view(), 40, 'compact').includes('\x1b'));
  assert.ok(renderStatusLine(view(), 100, 'wide', true).includes('\x1b'));
});

test('bar is capped at 20 dots for large ISAs', () => {
  const iscs = Array.from({ length: 40 }, (_, n) => ({ id: `ISC-${n + 1}`, text: 't', done: n < 10 }));
  const [head] = plain(view({ iscs, progress: '10/40' })).split('\n');
  assert.ok(head.startsWith('#####--------------- 10/40'));
});
