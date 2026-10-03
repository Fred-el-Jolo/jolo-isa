import type { Isc, IsaView, StatusLineMode } from './types.ts';

// Glyph shape is the primary signal (check / circle read even with no color
// at all); color only reinforces it.
const GLYPH = { done: '✔', open: '○' };
const GLYPH_ASCII = { done: '[x]', open: '[ ]' };

const HEX_DONE = '#22c55e'; // vivid green
const HEX_PHASE = '#f59e0b'; // vivid amber
const HEX_OPEN = '#38bdf8'; // vivid sky blue

// Row *text* brightness is separate from glyph color: the first open ISC is
// brightest, the one after it dimmer.
const TEXT_DIM = '#4b5563';
const TEXT_MID = '#7d8590';
const TEXT_BRIGHT = '#f4f6f8';
const TEXT_RULE = '#2a323d'; // empty progress-bar dots

const AUTO_WIDE_THRESHOLD = 70;
const WIDE_BAR_CAP = 20;
const OPEN_ROWS = 2;

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function paint(text: string, hex: string, color: boolean, bold = false): string {
  if (!color || !text) return text;
  const [r, g, b] = hexToRgb(hex);
  return `${bold ? '\x1b[1m' : ''}\x1b[38;2;${r};${g};${b}m${text}\x1b[0m`;
}

// Truncates plain text to a visible-width budget *before* any ANSI color is
// applied, so escape codes never get counted against the terminal width.
function ellipsize(text: string, maxWidth: number): string {
  if (maxWidth <= 0) return '';
  if (text.length <= maxWidth) return text;
  if (maxWidth === 1) return '…';
  return text.slice(0, maxWidth - 1) + '…';
}

function counts(view: IsaView): { done: number; total: number; label: string } {
  const done = view.iscs.filter((i) => i.done).length;
  const total = view.iscs.length;
  // `progress` is what the ISA itself claims (lint keeps it equal to the
  // checkboxes); fall back to the count if it's missing or malformed.
  const label = /^\d+\/\d+$/.test(String(view.progress ?? '')) ? String(view.progress) : `${done}/${total}`;
  return { done, total, label };
}

function phaseLabel(view: IsaView): string {
  const phase = view.phase || '?';
  return view.iteration && view.iteration > 1 ? `${phase} ↻${view.iteration}` : phase;
}

function isComplete(view: IsaView): boolean {
  return view.phase === 'complete';
}

function doneMessage(view: IsaView): string {
  return isComplete(view) ? 'complete' : 'all ISCs verified';
}

function progressBar(done: number, total: number, color: boolean): string {
  let filled = done;
  let empty = total - done;
  if (total > WIDE_BAR_CAP) {
    filled = Math.round((done / total) * WIDE_BAR_CAP);
    empty = WIDE_BAR_CAP - filled;
  }
  const on = (color ? '●' : '#').repeat(Math.max(0, filled));
  const off = (color ? '○' : '-').repeat(Math.max(0, empty));
  return paint(on, HEX_DONE, color) + paint(off, TEXT_RULE, color);
}

function renderCompact(view: IsaView, columns: number, color: boolean): string {
  const { label } = counts(view);
  if (isComplete(view)) {
    return `${label} ${paint((color ? GLYPH : GLYPH_ASCII).done, HEX_DONE, color)} ${paint('complete', TEXT_BRIGHT, color)}`;
  }
  const phase = phaseLabel(view);
  const prefix = `${label} ${paint(phase, HEX_PHASE, color)} `;
  const prefixWidth = label.length + 1 + phase.length + 1;
  const next = view.iscs.find((i) => !i.done);
  const text = next ? `${next.id} ${next.text}` : doneMessage(view);
  return prefix + paint(ellipsize(text, Math.max(4, columns - prefixWidth)), TEXT_BRIGHT, color);
}

// One open (or done) ISC row. `more` appends a "+N" for open ISCs not shown.
function iscRow(isc: Isc | null, message: string, textHex: string, columns: number, color: boolean, more: number): string {
  const isOpen = !!isc && !isc.done;
  const glyph = (color ? GLYPH : GLYPH_ASCII)[isOpen ? 'open' : 'done'];
  const suffix = more > 0 ? `  +${more}` : '';
  const budget = Math.max(4, columns - glyph.length - 1 - suffix.length);
  const text = ellipsize(isc ? `${isc.id} ${isc.text}` : message, budget);
  return `${paint(glyph, isOpen ? HEX_OPEN : HEX_DONE, color)} ${paint(text, textHex, color, textHex === TEXT_BRIGHT)}${suffix}`;
}

function renderWide(view: IsaView, columns: number, color: boolean): string {
  const { done, total, label } = counts(view);
  const bar = progressBar(done, total, color);
  const barWidth = Math.min(total, WIDE_BAR_CAP);
  const phase = phaseLabel(view);
  const effort = view.effort || '?';
  const head = `${bar} ${label}  ${paint(effort, TEXT_MID, color)} · ${paint(phase, HEX_PHASE, color)}`;
  const headWidth = barWidth + 1 + label.length + 2 + effort.length + 3 + phase.length;
  const taskBudget = columns - headWidth - 3;
  const task = view.task && taskBudget >= 4 ? ` · ${paint(ellipsize(view.task, taskBudget), TEXT_BRIGHT, color, true)}` : '';
  const rows = [head + task];

  const open = view.iscs.filter((i) => !i.done);
  if (isComplete(view) || open.length === 0) {
    rows.push(iscRow(null, doneMessage(view), TEXT_BRIGHT, columns, color, 0));
    return rows.join('\n');
  }
  const shown = open.slice(0, OPEN_ROWS);
  shown.forEach((isc, n) => {
    const last = n === shown.length - 1;
    rows.push(iscRow(isc, '', n === 0 ? TEXT_BRIGHT : TEXT_DIM, columns, color, last ? open.length - shown.length : 0));
  });
  return rows.join('\n');
}

// Nothing bound renders nothing: the status line shows progress only.
export function renderStatusLine(view: IsaView | null, columns: number, mode: StatusLineMode, color: boolean): string {
  if (!view) return '';
  const resolved = mode === 'auto' ? (columns < AUTO_WIDE_THRESHOLD ? 'compact' : 'wide') : mode;
  return resolved === 'compact' ? renderCompact(view, columns, color) : renderWide(view, columns, color);
}
